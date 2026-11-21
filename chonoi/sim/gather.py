"""Buổi sáng — Lặn & Hái (`gather`) theo Test Contract v1.1.

Mặt cắt dòng sông nhìn NGANG: `[x, d]` (`x` sang phải, `d` độ sâu hướng xuống, `d = 0` là mặt nước).

Thứ tự xử lý một bước (Test Contract v1.1 mục 4.5):
  1. Tăng `phase_tick`; giảm `time_left_ticks`, `invuln_ticks`, `catch_cd_ticks` và hồi nút (`node_regrown`).
  2. Bơi, chặn mép, phát `dive`/`surface`, oxy & ngạt (`oxygen_empty`, `choke`); Máu = 0 -> `faint(choke)` + `gather_end(fainted)`.
  3. Cập nhật thủy quái theo id (`recoil` hoặc `patrol`/`chase`), xét tối đa 1 hit (`monster_hit`, rơi LIFO, `faint(monster)` + `gather_end(fainted)`).
  4. Cạnh lên `interact`: bến trước (`docked`), nếu ngoài bến ở mặt nước thì hái nút (`gather`/`hold_full`).
  5. Cạnh lên `catch`: nếu hết hồi và dưới nước thì bắt đàn cá theo vị trí trước khi bơi (`fish_caught`/`hold_full`).
  6. Hết giờ (`time_left_ticks <= 0`) -> `gather_end(time)`.
  7. Nếu còn giờ & `random_fish`: đàn cá bơi/đổi hướng/phản xạ mép rồi sinh cá theo lịch `360·k` (`fish_spawned`).
"""

import math

from ..ids import id_key, sort_by_id
from ..inventory import hold_to_items
from .ramp import ramp_velocity

TICK = 60.0
AXES = ("x", "d")


def _resolve_gather_caps(tuning, active_upgrades):
    t = tuning["gather"]
    oxy_s = t["oxygen_max_s"]
    hp_max = t["hp_max"]
    if active_upgrades:
        shop_up = tuning.get("shop", {}).get("upgrades", {})
        ox_lvl = active_upgrades.get("oxygen", 0)
        if ox_lvl > 0:
            oxy_s = next(item["oxygen_max_s"] for item in shop_up["oxygen"] if item["level"] == ox_lvl)
        hp_lvl = active_upgrades.get("hp", 0)
        if hp_lvl > 0:
            hp_max = next(item["hp_max"] for item in shop_up["hp"] if item["level"] == hp_lvl)
    return int(round(oxy_s * TICK)), int(hp_max)


class GatherSim:
    mode = "gather"
    phase = "gather"

    def __init__(self, tuning, scenario, streams, ids, day=1, active_upgrades=None,
                 money=0, earned=0, reputation=None):
        t = tuning["gather"]
        self.t = t
        self.rng = streams
        self.ids = ids
        self.day = int(day)
        p = scenario.get("player", {})
        self.pos = [float(c) for c in p.get("pos", t["start_pos"])]
        self.vel = [float(c) for c in p.get("vel", [0.0, 0.0])]
        self._tgt = None
        self._ramp_left = 0
        self.heading = float(p.get("heading_deg", t["start_heading_deg"]))
        self.oxygen_max, self.hp_max = _resolve_gather_caps(tuning, active_upgrades)
        self.oxygen_ticks = p.get("oxygen_ticks", self.oxygen_max)
        self.hp = p.get("hp", self.hp_max)
        self.zero_oxy_ticks = p.get("zero_oxy_ticks", 0)
        self.invuln_ticks = p.get("invuln_ticks", 0)
        self.catch_cd_ticks = p.get("catch_cd_ticks", 0)
        self.hold = list(scenario.get("hold", []))
        self.phase_tick = 0
        self.time_left_ticks = scenario.get("time_left_ticks", int(round(t["duration_s"] * TICK)))
        self.random_fish = bool(scenario.get("random_fish", True))

        src_nodes = scenario["nodes"] if "nodes" in scenario else t["nodes"]
        self.nodes = [{"id": n["id"], "kind": n["kind"], "pos": [float(c) for c in n["pos"]],
                       "regrow_ticks": n.get("regrow_ticks", 0)} for n in src_nodes]
        for n in self.nodes:
            ids.reserve(n["id"])

        if "monsters" in scenario:
            src_monsters = scenario["monsters"]
        else:
            src_monsters = [sp for sp in t["monsters"]["spawns"] if sp["from_day"] <= self.day]
        self.monsters = []
        for m in src_monsters:
            self.monsters.append({
                "id": m["id"],
                "kind": m["kind"],
                "pos": [float(c) for c in m["pos"]],
                "waypoints": [[float(c) for c in wp] for wp in m["waypoints"]],
                "target_idx": int(m.get("target_idx", 1)),
                "state": m.get("state", "patrol"),
                "state_ticks_left": int(m.get("state_ticks_left", 0)),
                "recoil_dir": [float(c) for c in m["recoil_dir"]] if m.get("recoil_dir") is not None else None,
            })
            ids.reserve(m["id"])

        self.fish = []
        if "fish" in scenario:
            for f in scenario["fish"]:
                self.fish.append({
                    "id": f["id"],
                    "kind": f["kind"],
                    "pos": [float(c) for c in f["pos"]],
                    "heading_deg": float(f.get("heading_deg", 0.0)),
                    "age_ticks": int(f.get("age_ticks", 0)),
                })
                ids.reserve(f["id"])
        elif self.random_fish:
            count = int(t["fish_initial"])
            for _ in range(count):
                nf = self._spawn_one_fish()
                if nf is None:
                    break
                self.fish.append(nf)

        self.money = int(money)
        self.earned = int(earned)
        self.reputation = float(tuning["quan"]["reputation_initial"] if reputation is None else reputation)
        self.done = False
        self.reason = None

    # --- giao diện cho runner -------------------------------------------------
    def inventory_items(self) -> dict:
        return hold_to_items(self.hold)

    def snapshot(self) -> dict:
        return {
            "player": {"pos": list(self.pos), "vel": list(self.vel), "heading_deg": self.heading,
                       "oxygen_ticks": self.oxygen_ticks, "oxygen_max_ticks": self.oxygen_max,
                       "hp": self.hp, "hp_max": self.hp_max, "zero_oxy_ticks": self.zero_oxy_ticks,
                       "invuln_ticks": self.invuln_ticks, "catch_cd_ticks": self.catch_cd_ticks,
                       "at_surface": self._at_surface()},
            "hold": list(self.hold), "hold_count": len(self.hold),
            "hold_capacity": self.t["hold_capacity"],
            "nodes": [{"id": n["id"], "pos": list(n["pos"]), "kind": n["kind"],
                       "ready": n["regrow_ticks"] == 0, "regrow_ticks": n["regrow_ticks"]}
                      for n in sort_by_id(self.nodes)],
            "fish": [{"id": f["id"], "pos": list(f["pos"]), "kind": f["kind"],
                      "heading_deg": f["heading_deg"], "age_ticks": f["age_ticks"]}
                     for f in sort_by_id(self.fish)],
            "monsters": [{"id": m["id"], "kind": m["kind"], "pos": list(m["pos"]),
                          "waypoints": [list(wp) for wp in m["waypoints"]],
                          "target_idx": m["target_idx"], "state": m["state"],
                          "state_ticks_left": m["state_ticks_left"],
                          "recoil_dir": list(m["recoil_dir"]) if m["recoil_dir"] is not None else None}
                         for m in sort_by_id(self.monsters)],
        }

    # --- một bước ---------------------------------------------------------------
    def step(self, inp):
        if self.done:
            return []
        events = []

        # 1. đồng hồ, cooldown, giảm bất tử và hồi nút
        self.phase_tick += 1
        self.time_left_ticks = max(0, self.time_left_ticks - 1)
        self.invuln_ticks = max(0, self.invuln_ticks - 1)
        self.catch_cd_ticks = max(0, self.catch_cd_ticks - 1)
        for n in sort_by_id(self.nodes):
            if n["regrow_ticks"] > 0:
                n["regrow_ticks"] -= 1
                if n["regrow_ticks"] == 0:
                    events.append(("node_regrown", {"node_id": n["id"]}))

        # 2. bơi + chặn mép + chuyển vùng mặt nước/dưới nước + oxy/ngạt
        was_surface = self._at_surface()
        self._move(inp)
        now_surface = self._at_surface()
        if was_surface and not now_surface:
            events.append(("dive", {"pos": list(self.pos)}))
        elif not was_surface and now_surface:
            events.append(("surface", {"pos": list(self.pos)}))

        if now_surface:
            self.oxygen_ticks = min(self.oxygen_max, self.oxygen_ticks + int(self.t["oxygen_refill_per_tick"]))
            self.zero_oxy_ticks = 0
        else:
            prev_oxy = self.oxygen_ticks
            self.oxygen_ticks = max(0, self.oxygen_ticks - 1)
            if prev_oxy > 0 and self.oxygen_ticks == 0:
                events.append(("oxygen_empty", {"oxygen_ticks": 0}))
            if self.oxygen_ticks == 0:
                self.zero_oxy_ticks += 1
                if self.zero_oxy_ticks >= int(self.t["choke_interval_ticks"]):
                    self.zero_oxy_ticks = 0
                    self.hp -= 1
                    events.append(("choke", {"hp": self.hp}))
                    if self.hp <= 0:
                        self.hp = 0
                        lost = list(reversed(self.hold))
                        self.hold.clear()
                        events.append(("faint", {"cause": "choke", "lost": lost, "hp": 0}))
                        self._finish("fainted", events)
                        return events

        # 3. cập nhật thủy quái theo id rồi xét tối đa một hit
        if self._step_monsters(events):
            return events

        # 4. interact: bến trước, rồi hái nút ở mặt nước
        if inp.pressed("interact"):
            if self._in_dock():
                self._finish("docked", events)
                return events
            if now_surface:
                r = self.t["interact_radius"]
                candidates = [
                    n for n in self.nodes
                    if n["regrow_ticks"] == 0 and math.dist(self.pos, n["pos"]) <= r
                ]
                if candidates:
                    target = min(candidates, key=lambda n: (math.dist(self.pos, n["pos"]), id_key(n["id"])))
                    amount = int(self.t["node_yield"])
                    free = int(self.t["hold_capacity"]) - len(self.hold)
                    if free >= amount:
                        self.hold.extend([target["kind"]] * amount)
                        target["regrow_ticks"] = int(round(self.t["regrow_s"] * TICK))
                        events.append(("gather", {"node_id": target["id"], "kind": target["kind"], "amount": amount}))
                    else:
                        events.append(("hold_full", {"action": "gather", "node_id": target["id"],
                                                     "required": amount, "free": free}))

        # 5. bắt cá theo vị trí trước khi cá bơi
        if inp.pressed("catch"):
            if self.catch_cd_ticks == 0 and not now_surface:
                r = self.t["catch_radius"]
                candidates = [f for f in self.fish if math.dist(self.pos, f["pos"]) <= r]
                if candidates:
                    target = min(candidates, key=lambda f: (math.dist(self.pos, f["pos"]), id_key(f["id"])))
                    yld = int(self.t["fish_yield"][target["kind"]])
                    free = int(self.t["hold_capacity"]) - len(self.hold)
                    if free >= yld:
                        self.hold.extend([target["kind"]] * yld)
                        self.fish = [f for f in self.fish if f["id"] != target["id"]]
                        self.catch_cd_ticks = int(round(self.t["catch_cooldown_s"] * TICK))
                        events.append(("fish_caught", {"fish_id": target["id"], "kind": target["kind"], "yield": yld}))
                    else:
                        events.append(("hold_full", {"action": "catch", "fish_id": target["id"],
                                                     "required": yld, "free": free}))

        # 6. hết giờ
        if self.time_left_ticks <= 0:
            self._finish("time", events)
            return events

        # 7. còn giờ: cá bơi và sinh thêm theo lịch
        if self.random_fish:
            self._swim_fish()
            spawn_ticks = int(self.t["fish_spawn_ticks"])
            if self.phase_tick % spawn_ticks == 0 and len(self.fish) < int(self.t["fish_max"]):
                nf = self._spawn_one_fish()
                if nf is not None:
                    self.fish.append(nf)
                    events.append(("fish_spawned", {"id": nf["id"], "kind": nf["kind"], "pos": list(nf["pos"])}))

        return events

    # --- thủy quái & cá --------------------------------------------------------
    def _step_monsters(self, events) -> bool:
        mcfg = self.t["monsters"]
        species_map = mcfg["species"]
        x_lo, x_hi = self.t["bounds"]["x"]
        ended_recoil = set()

        for m in sort_by_id(self.monsters):
            sp = species_map[m["kind"]]
            d_lo, d_hi = sp["depths"]
            if m["state"] == "recoil":
                step_d = sp["recoil_dist"] / sp["recoil_ticks"]
                rx, rd = m["recoil_dir"]
                m["pos"][0] = min(x_hi, max(x_lo, m["pos"][0] + rx * step_d))
                m["pos"][1] = min(d_hi, max(d_lo, m["pos"][1] + rd * step_d))
                m["state_ticks_left"] -= 1
                if m["state_ticks_left"] <= 0:
                    m["state"] = "patrol"
                    m["state_ticks_left"] = 0
                    m["recoil_dir"] = None
                    ended_recoil.add(m["id"])
                continue

            dist_p = math.dist(m["pos"], self.pos)
            if m["state"] == "patrol":
                if self.pos[1] >= d_lo and dist_p <= sp["detect_radius"]:
                    m["state"] = "chase"
            elif m["state"] == "chase":
                if self.pos[1] < d_lo or dist_p > sp["exit_radius"]:
                    m["state"] = "patrol"

            if m["state"] == "chase":
                step_d = sp["chase_speed"] / TICK
                if dist_p > 1e-12:
                    move_d = min(step_d, dist_p)
                    m["pos"][0] += (self.pos[0] - m["pos"][0]) / dist_p * move_d
                    m["pos"][1] += (self.pos[1] - m["pos"][1]) / dist_p * move_d
            else:
                wp = m["waypoints"][m["target_idx"]]
                step_d = sp["patrol_speed"] / TICK
                dist_w = math.dist(m["pos"], wp)
                if dist_w <= step_d:
                    m["pos"][0], m["pos"][1] = float(wp[0]), float(wp[1])
                    m["target_idx"] = 1 - m["target_idx"]
                else:
                    m["pos"][0] += (wp[0] - m["pos"][0]) / dist_w * step_d
                    m["pos"][1] += (wp[1] - m["pos"][1]) / dist_w * step_d
            m["pos"][0] = min(x_hi, max(x_lo, m["pos"][0]))
            m["pos"][1] = min(d_hi, max(d_lo, m["pos"][1]))

        if self.invuln_ticks == 0 and self.monsters:
            hit_candidates = []
            for m in self.monsters:
                if m["id"] in ended_recoil or m["state"] == "recoil":
                    continue
                sp = species_map[m["kind"]]
                if self.pos[1] >= sp["depths"][0] and math.dist(m["pos"], self.pos) <= sp["hit_radius"]:
                    hit_candidates.append(m)
            if hit_candidates:
                hitter = min(hit_candidates, key=lambda m: (math.dist(m["pos"], self.pos), id_key(m["id"])))
                sp = species_map[hitter["kind"]]
                self.hp = max(0, self.hp - 1)
                drop_n = math.floor(len(self.hold) * mcfg["loss_ratio"])
                lost = [self.hold.pop() for _ in range(drop_n)]
                self.invuln_ticks = int(mcfg["invuln_ticks"])
                dx = hitter["pos"][0] - self.pos[0]
                dd = hitter["pos"][1] - self.pos[1]
                dist_hp = math.hypot(dx, dd)
                rdir = [1.0, 0.0] if dist_hp <= 1e-12 else [dx / dist_hp, dd / dist_hp]
                hitter["state"] = "recoil"
                hitter["state_ticks_left"] = int(sp["recoil_ticks"])
                hitter["recoil_dir"] = rdir
                events.append(("monster_hit", {
                    "monster_id": hitter["id"],
                    "hp": self.hp,
                    "lost": lost,
                    "pos": list(self.pos),
                }))
                if self.hp <= 0:
                    rem_lost = list(reversed(self.hold))
                    self.hold.clear()
                    events.append(("faint", {"cause": "monster", "lost": rem_lost, "hp": 0}))
                    self._finish("fainted", events)
                    return True
        return False

    def _spawn_one_fish(self):
        t = self.t
        clearance = float(t["fish_spawn_clearance"])
        weights = t["fish_weights"]
        spawn_xs = sorted(float(x) for x in t["fish_spawn_x"])
        valid_by_sp = {}
        for sp in sorted(weights):
            ds = sorted(float(d) for d in t["fish_spawn_depths"][sp])
            pts = []
            for x in spawn_xs:
                for d in ds:
                    if all(math.dist((x, d), f["pos"]) > clearance for f in self.fish):
                        pts.append((x, d))
            if pts:
                valid_by_sp[sp] = pts
        if not valid_by_sp:
            return None
        rng = self.rng.get("fish_spawn")
        avail_species = list(valid_by_sp.keys())
        sp_weights = [float(weights[sp]) for sp in avail_species]
        sp = rng.choices(avail_species, weights=sp_weights, k=1)[0]
        x, d = rng.choice(valid_by_sp[sp])
        heading = rng.random() * 360.0
        return {
            "id": self.ids.new("F"),
            "kind": sp,
            "pos": [x, d],
            "heading_deg": heading,
            "age_ticks": 0,
        }

    def _swim_fish(self):
        t = self.t
        step_dist = float(t["fish_speed"]) / TICK
        turn_ticks = int(t["fish_turn_ticks"])
        x_lo, x_hi = float(t["fish_x"][0]), float(t["fish_x"][1])
        turn_rng = self.rng.get("fish_turn")

        for f in sort_by_id(self.fish):
            f["age_ticks"] += 1
            if f["age_ticks"] % turn_ticks == 0:
                f["heading_deg"] = turn_rng.random() * 360.0
            d_lo, d_hi = t["fish_depths"][f["kind"]]
            d_lo, d_hi = float(d_lo), float(d_hi)
            rad = math.radians(f["heading_deg"])
            vx = math.cos(rad)
            vd = math.sin(rad)
            x, d = float(f["pos"][0]), float(f["pos"][1])
            # Nếu fixture đặt cá ngoài dải bơi của loài, giữ nguyên khi không vượt biên ngoài hay kẹp mềm khi chạm
            if x < x_lo:
                x = x_lo
                if vx < 0:
                    vx = -vx
            elif x > x_hi:
                x = x_hi
                if vx > 0:
                    vx = -vx
            if d < d_lo:
                d = d_lo
                if vd < 0:
                    vd = -vd
            elif d > d_hi:
                d = d_hi
                if vd > 0:
                    vd = -vd

            rem = 1.0
            bounced = False
            for _ in range(4):
                if rem <= 1e-12:
                    break
                dx = vx * step_dist * rem
                dd = vd * step_dist * rem
                tx = math.inf
                if dx > 0 and x + dx > x_hi:
                    tx = (x_hi - x) / dx
                elif dx < 0 and x + dx < x_lo:
                    tx = (x_lo - x) / dx
                td = math.inf
                if dd > 0 and d + dd > d_hi:
                    td = (d_hi - d) / dd
                elif dd < 0 and d + dd < d_lo:
                    td = (d_lo - d) / dd
                tmin = min(tx, td)
                if tmin > 1.0:
                    x += dx
                    d += dd
                    break
                bounced = True
                x += dx * tmin
                d += dd * tmin
                if abs(tx - tmin) <= 1e-12:
                    x = x_hi if dx > 0 else x_lo
                    vx = -vx
                if abs(td - tmin) <= 1e-12:
                    d = d_hi if dd > 0 else d_lo
                    vd = -vd
                rem *= (1.0 - tmin)

            f["pos"][0] = min(x_hi, max(x_lo, x))
            f["pos"][1] = min(d_hi, max(d_lo, d))
            if bounced:
                f["heading_deg"] = math.degrees(math.atan2(vd, vx)) % 360.0

    # --- tiện ích ---------------------------------------------------------------
    def _at_surface(self) -> bool:
        return self.pos[1] <= self.t["surface_depth"]

    def _in_dock(self) -> bool:
        return math.dist(self.pos, self.t["dock_pos"]) <= self.t["dock_radius"]

    def _finish(self, reason, events):
        self.done = True
        self.reason = reason
        events.append(("gather_end", {"reason": reason, "inventory": {"items": self.inventory_items()}}))

    def _move(self, inp):
        speed = self.t["swim_speed"]
        mx, md = inp.move
        self.vel = ramp_velocity(self, (mx * speed, md * speed), int(self.t["ramp_max_ticks"]))
        if (mx, md) != (0.0, 0.0):
            self.heading = math.degrees(math.atan2(md, mx)) % 360
        b = self.t["bounds"]
        for i, axis in enumerate(AXES):
            self.pos[i] += self.vel[i] / TICK
            lo, hi = b[axis]
            if self.pos[i] <= lo:
                self.pos[i] = lo
                self.vel[i] = max(0.0, self.vel[i])
            elif self.pos[i] >= hi:
                self.pos[i] = hi
                self.vel[i] = min(0.0, self.vel[i])
