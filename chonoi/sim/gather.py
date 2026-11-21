"""Buổi sáng — Lặn & Hái (`gather`).

Mặt cắt dòng sông nhìn NGANG: vị trí `[x, d]` (x sang phải, `d` độ sâu hướng xuống, d = 0 là mặt nước).
`move = [x, d]`: thành phần thứ hai DƯƠNG = bơi xuống. Hướng mặt là góc từ +x, dương = xuống.

Luật xử lý một bước (Test Contract v1.0 mục F):
  1. Giảm timer ca, hồi bắt và hồi nút; nút từ 1 về 0 phát `node_regrown`.
  2. Bơi, chặn mép, phát `dive`/`surface`, cập nhật oxy & ngạt theo d cuối bước; Máu = 0 -> `faint` + `gather_end(fainted)`.
  3. Cạnh lên `interact`: xét bến trước (`docked`), nếu ngoài bến và ở mặt nước thì hái nút `ready` gần nhất (`gather`/`hold_full`).
  4. Cạnh lên `catch`: nếu hết hồi và dưới nước thì bắt đàn cá gần nhất (`fish_caught`/`hold_full`).
  5. Hết giờ (`time_left_ticks <= 0`) -> `gather_end(time)`.
"""

import math

from ..ids import id_key, sort_by_id
from ..inventory import hold_to_items
from .ramp import ramp_velocity

TICK = 60.0
AXES = ("x", "d")


class GatherSim:
    mode = "gather"
    phase = "gather"

    def __init__(self, tuning, scenario, streams, ids):
        t = tuning["gather"]
        self.t = t
        self.rng = streams
        self.ids = ids
        p = scenario.get("player", {})
        self.pos = [float(c) for c in p.get("pos", t["start_pos"])]
        self.vel = [float(c) for c in p.get("vel", [0.0, 0.0])]
        self._tgt = None
        self._ramp_left = 0
        self.heading = float(p.get("heading_deg", t["start_heading_deg"]))
        self.oxygen_max = int(round(t["oxygen_max_s"] * TICK))
        self.oxygen_ticks = p.get("oxygen_ticks", self.oxygen_max)
        self.hp = p.get("hp", t["hp_max"])
        self.zero_oxy_ticks = p.get("zero_oxy_ticks", 0)
        self.invuln_ticks = p.get("invuln_ticks", 0)
        self.catch_cd_ticks = p.get("catch_cd_ticks", 0)
        self.hold = list(scenario.get("hold", []))  # thứ tự nhặt, cuối mảng là mới nhất
        self.time_left_ticks = scenario.get("time_left_ticks", int(round(t["duration_s"] * TICK)))
        # nút và đàn cá: scenario THAY THẾ danh sách mặc định; random_fish=false tắt cá mặc định
        src_nodes = scenario["nodes"] if "nodes" in scenario else t["nodes"]
        self.nodes = [{"id": n["id"], "kind": n["kind"], "pos": [float(c) for c in n["pos"]],
                       "regrow_ticks": n.get("regrow_ticks", 0)} for n in src_nodes]
        if "fish" in scenario:
            src_fish = scenario["fish"]
        elif scenario.get("random_fish", True):
            src_fish = t["fish_initial"]
        else:
            src_fish = []
        # Đàn cá đứng yên ở phase này. Cá bơi / sinh thêm là việc của phase sau.
        self.fish = [{"id": f["id"], "kind": f["kind"], "pos": [float(c) for c in f["pos"]],
                      "heading_deg": f.get("heading_deg", 0)} for f in src_fish]
        for coll in (self.nodes, self.fish):
            for e in coll:
                ids.reserve(e["id"])
        self.money = 0
        self.earned = 0
        self.reputation = tuning["quan"]["reputation_initial"]
        self.done = False
        self.reason = None

    # --- giao diện cho runner -------------------------------------------------
    def inventory_items(self) -> dict:
        return hold_to_items(self.hold)

    def snapshot(self) -> dict:
        return {
            "player": {"pos": list(self.pos), "vel": list(self.vel), "heading_deg": self.heading,
                       "oxygen_ticks": self.oxygen_ticks, "oxygen_max_ticks": self.oxygen_max,
                       "hp": self.hp, "hp_max": self.t["hp_max"], "zero_oxy_ticks": self.zero_oxy_ticks,
                       "invuln_ticks": self.invuln_ticks, "catch_cd_ticks": self.catch_cd_ticks,
                       "at_surface": self._at_surface()},
            "hold": list(self.hold), "hold_count": len(self.hold),
            "hold_capacity": self.t["hold_capacity"],
            "nodes": [{"id": n["id"], "pos": list(n["pos"]), "kind": n["kind"],
                       "ready": n["regrow_ticks"] == 0, "regrow_ticks": n["regrow_ticks"]}
                      for n in sort_by_id(self.nodes)],
            "fish": [{"id": f["id"], "pos": list(f["pos"]), "kind": f["kind"], "heading_deg": f["heading_deg"]}
                     for f in sort_by_id(self.fish)],
        }

    # --- một bước ---------------------------------------------------------------
    def step(self, inp):
        if self.done:
            return []
        events = []
        # 1. đồng hồ và hàng có sẵn: giảm bộ đếm, nút mọc lại
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

        # 3. interact: bến trước, rồi hái nút ở mặt nước
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

        # 4. bắt cá: hết hồi chiêu và đang dưới nước
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

        # 5. hết giờ
        if self.time_left_ticks <= 0:
            self._finish("time", events)
        return events

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
