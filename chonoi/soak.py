"""Soak headless nhiều Ngày liên tiếp (`chonoi.soak`, Test Contract v1.3).

Chạy:
    python3 -m chonoi.soak --seed 7 --days 10 --out soak.json

Lặp kế hoạch D1-D5 cho Ngày 6..N, điều khiển bằng bot tất định 100%, không phụ thuộc đồng hồ thực.
Xuất JSON nguyên tử: days, days_completed, crashes, results, duration_s.
"""

import argparse
import json
import math
import os
import sys
import tempfile
import time

from .contract import load_contract
from .errors import BadInput
from .ids import id_key, sort_by_id
from .inputs import InputState
from .runner import Session


class _Parser(argparse.ArgumentParser):
    def error(self, message):
        self.print_usage(sys.stderr)
        sys.stderr.write(f"lỗi: {message}\n")
        sys.exit(2)


def _int(name):
    def conv(s):
        try:
            return int(s)
        except ValueError:
            raise argparse.ArgumentTypeError(f"{name} phải là số nguyên")
    return conv


def _atomic_write_json(path: str, payload: dict):
    parent = os.path.dirname(os.path.abspath(path))
    if parent:
        os.makedirs(parent, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=".soak-", suffix=".tmp", dir=parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as f:
            json.dump(payload, f, ensure_ascii=False, separators=(",", ":"))
            f.write("\n")
        os.replace(tmp, path)
    except BaseException:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise


def _vec_to(src, dst):
    dx = dst[0] - src[0]
    dy = dst[1] - src[1]
    n = math.hypot(dx, dy)
    if n <= 1e-6:
        return (0.0, 0.0)
    return (dx / n, dy / n)


class _SoakBot:
    """Bot tất định chơi đủ vòng gather -> quan -> shop qua N Ngày."""

    def __init__(self, tuning):
        self.tuning = tuning
        self._held_interact = False
        self._held_catch = False
        self._held_shop_done = False

    def _pulse(self, btn_attr: str, want: bool, edges: set, held: dict, name: str):
        prev = getattr(self, btn_attr)
        now = bool(want) and not prev
        setattr(self, btn_attr, now)
        held[name] = now
        if now:
            edges.add(name)

    def decide(self, sess: Session) -> InputState:
        sim = sess.sim
        phase = sim.phase
        edges = set()
        held = {"interact": False, "catch": False, "pause": False, "shop_done": False, "attack": False, "photo": False}
        buy = None

        if phase == "gather":
            move = self._decide_gather(sim, edges, held)
            self._held_shop_done = False
            return InputState(move, held, edges, buy=None)

        if phase == "quan":
            move = self._decide_quan(sim, edges, held)
            self._held_catch = False
            self._held_shop_done = False
            return InputState(move, held, edges, buy=None)

        # phase == "shop"
        self._held_interact = False
        self._held_catch = False
        st = sim.shop_phase_tick
        if st == 0 and self._can_buy(sim, "oxygen"):
            buy = "oxygen"
        elif st == 1 and self._can_buy(sim, "hp"):
            buy = "hp"
        want_done = st >= 2
        self._pulse("_held_shop_done", want_done, edges, held, "shop_done")
        return InputState((0.0, 0.0), held, edges, buy=buy)

    def _can_buy(self, sim, upgrade_id: str) -> bool:
        cur = sim.upgrades.get(upgrade_id, 0)
        tiers = self.tuning["shop"]["upgrades"].get(upgrade_id, [])
        if cur >= len(tiers):
            return False
        return sim.money >= int(tiers[cur]["price"])

    def _decide_gather(self, sim, edges: set, held: dict):
        g = sim.gather
        plan_ing = sim.plans[sim._plan_key(sim.day)]["ingredients"]
        fresh_counts = {}
        for it in g.hold:
            if it["fresh"] >= g.spoiled_below:
                fresh_counts[it["kind"]] = fresh_counts.get(it["kind"], 0) + 1

        cap = int(g.t["hold_capacity"])
        free_slots = cap - len(g.hold)
        need_nodes = {}
        need_fish = {}
        fish_yield = g.t["fish_yield"]
        for kind, target_qty in sorted(plan_ing.items()):
            lack = int(target_qty) - fresh_counts.get(kind, 0)
            if lack > 0:
                if kind in fish_yield:
                    if int(fish_yield[kind]) <= free_slots:
                        need_fish[kind] = lack
                else:
                    if free_slots >= 1:
                        need_nodes[kind] = lack

        dock_pos = g.t["dock_pos"]
        dock_r = float(g.t["dock_radius"])
        interact_r = float(g.t["interact_radius"])
        catch_r = float(g.t["catch_radius"])

        # Kiểm tra điều kiện nên về bến giao hàng
        all_plan_met = all(fresh_counts.get(k, 0) >= qty for k, qty in plan_ing.items())
        should_dock = (
            all_plan_met
            or free_slots == 0
            or (not need_nodes and not need_fish and len(g.hold) > 0)
            or g.time_left_ticks <= 2700
            or (g.phase_tick >= 6600 and len(g.hold) > 0)
        )

        # Tránh Cá Sấu khi ở gần
        nearest_m = None
        nearest_md = math.inf
        for m in sort_by_id(g.monsters):
            dist = math.dist(g.pos, m["pos"])
            if dist < nearest_md:
                nearest_md = dist
                nearest_m = m

        if g.oxygen_ticks < 0.38 * g.oxygen_max:
            # Ưu tiên ngoi lên mặt nước hồi oxy
            self._pulse("_held_interact", False, edges, held, "interact")
            self._pulse("_held_catch", False, edges, held, "catch")
            return _vec_to(g.pos, [g.pos[0], 0.0])

        if nearest_m is not None and nearest_md < 6.5 and g.invuln_ticks == 0 and g.pos[1] > 1.0:
            self._pulse("_held_interact", False, edges, held, "interact")
            self._pulse("_held_catch", False, edges, held, "catch")
            dx = g.pos[0] - nearest_m["pos"][0]
            dd = min(-1.0, g.pos[1] - nearest_m["pos"][1])
            n = math.hypot(dx, dd)
            return (dx / n, dd / n) if n > 1e-6 else (0.0, -1.0)

        if should_dock:
            self._pulse("_held_catch", False, edges, held, "catch")
            dist_dock = math.dist(g.pos, dock_pos)
            self._pulse("_held_interact", dist_dock <= dock_r - 0.15, edges, held, "interact")
            return _vec_to(g.pos, dock_pos)

        # Chọn mục tiêu gần nhất giữa nút rau cần thiết và đàn cá cần thiết
        best_target = None
        best_score = math.inf

        for n in sort_by_id(g.nodes):
            if n["kind"] in need_nodes and n["regrow_ticks"] == 0:
                d = math.dist(g.pos, n["pos"])
                if d < best_score:
                    best_score = d
                    best_target = ("node", n)

        for f in sort_by_id(g.fish):
            if f["kind"] in need_fish:
                # Né đàn cá nằm sát Cá Sấu khi máu thấp
                m_dist = min((math.dist(f["pos"], m["pos"]) for m in g.monsters), default=99.0)
                if m_dist < 4.5 and g.hp <= 1:
                    continue
                d = math.dist(g.pos, f["pos"])
                if d < best_score:
                    best_score = d
                    best_target = ("fish", f)

        if best_target is None:
            # Nếu vẫn còn thiếu nhưng nút đang mọc lại / chưa thấy cá, hoặc sang ngày kế, đi về bến nếu đã có đồ
            self._pulse("_held_catch", False, edges, held, "catch")
            if g.phase_tick >= 3600 and len(g.hold) > 0:
                dist_dock = math.dist(g.pos, dock_pos)
                self._pulse("_held_interact", dist_dock <= dock_r - 0.15, edges, held, "interact")
                return _vec_to(g.pos, dock_pos)
            # Đợi quanh vùng giữa ở mặt nước
            self._pulse("_held_interact", False, edges, held, "interact")
            return _vec_to(g.pos, [45.0, 0.0])

        kind_t, obj = best_target
        dist = math.dist(g.pos, obj["pos"])
        if kind_t == "node":
            self._pulse("_held_catch", False, edges, held, "catch")
            at_surf = g.pos[1] <= g.t["surface_depth"]
            want_int = at_surf and dist <= interact_r - 0.15 and not g._in_dock()
            self._pulse("_held_interact", want_int, edges, held, "interact")
            return _vec_to(g.pos, obj["pos"])

        # fish
        self._pulse("_held_interact", False, edges, held, "interact")
        underwater = g.pos[1] > g.t["surface_depth"]
        want_catch = underwater and g.catch_cd_ticks == 0 and dist <= catch_r - 0.15
        self._pulse("_held_catch", want_catch, edges, held, "catch")
        return _vec_to(g.pos, obj["pos"])

    def _decide_quan(self, sim, edges: set, held: dict):
        q = sim.quan
        ir = float(q.t["interact_radius"])
        tables_by_id = {tb["id"]: tb for tb in q.tables}
        waiting_ids = {c["id"]: c for c in q.customers if c["state"] == "waiting"}

        # 1. Đang cầm món -> mang ra bàn khách
        if q.hand is not None:
            cust = waiting_ids.get(q.hand["order_id"])
            if cust is not None:
                tb = tables_by_id[cust["table_id"]]
                dist = math.dist(q.pos, tb["pos"])
                self._pulse("_held_interact", dist <= ir - 0.15, edges, held, "interact")
                return _vec_to(q.pos, tb["pos"])

        # 2. Nhấc món chín từ bếp
        ready_stoves = [
            s for s in sort_by_id(q.stoves)
            if s["state"] == "ready" and s["dish"] and s["dish"]["order_id"] in waiting_ids
        ]
        if ready_stoves:
            target = min(ready_stoves, key=lambda s: (math.dist(q.pos, s["pos"]), id_key(s["id"])))
            dist = math.dist(q.pos, target["pos"])
            self._pulse("_held_interact", dist <= ir - 0.15, edges, held, "interact")
            return _vec_to(q.pos, target["pos"])

        # 3. Nấu đơn reserved tiếp theo ở bếp rảnh
        has_reserved = any(
            c["state"] == "waiting" and c["order_status"] == "reserved"
            for c in q.customers
        )
        idle_stoves = [s for s in sort_by_id(q.stoves) if s["state"] == "idle"]
        if has_reserved and idle_stoves:
            target = min(idle_stoves, key=lambda s: (math.dist(q.pos, s["pos"]), id_key(s["id"])))
            dist = math.dist(q.pos, target["pos"])
            self._pulse("_held_interact", dist <= ir - 0.15, edges, held, "interact")
            return _vec_to(q.pos, target["pos"])

        # 4. Đứng chờ gần cụm bếp
        self._pulse("_held_interact", False, edges, held, "interact")
        return _vec_to(q.pos, [5.0, 6.0])


def run_soak(seed: int, days: int, out_path: str) -> dict:
    contract = load_contract()
    tuning = contract["tuning"]
    mult = int(tuning["score"]["reputation_multiplier"])
    bot = _SoakBot(tuning)
    sess = Session("day", tuning, {}, seed, days=days)
    max_ticks = int(days) * 25000
    results = []
    crashes = 0
    t0 = time.perf_counter()

    try:
        while not sess.done and sess.tick < max_ticks:
            inp = bot.decide(sess)
            evs = sess.step(inp)
            for ev in evs:
                if ev["name"] == "shop_end":
                    sim = sess.sim
                    score = int(sim.earned) + mult * math.floor(sim.reputation)
                    results.append({
                        "day": int(ev["day"]),
                        "earned": int(sim.earned),
                        "reputation": round(float(sim.reputation), 3),
                        "score": int(score),
                    })
    except Exception as e:
        crashes += 1
        sys.stderr.write(f"lỗi soak: {e}\n")

    elapsed = time.perf_counter() - t0
    report = {
        "days": int(days),
        "days_completed": int(sess.sim.days_completed),
        "crashes": int(crashes),
        "results": results,
        "duration_s": round(elapsed, 3),
    }
    _atomic_write_json(out_path, report)
    return report


def main(argv=None) -> int:
    p = _Parser(prog="chonoi.soak")
    p.add_argument("--seed", required=True, type=_int("seed"))
    p.add_argument("--days", required=True, type=_int("days"))
    p.add_argument("--out", required=True)
    a = p.parse_args(argv)
    try:
        if a.days <= 0:
            raise BadInput("--days phải >= 1")
        if not str(a.out).strip():
            raise BadInput("--out không được rỗng")
        run_soak(a.seed, a.days, a.out)
    except BadInput as e:
        sys.stderr.write(f"đầu vào sai: {e}\n")
        return 2
    except OSError as e:
        sys.stderr.write(f"lỗi ghi: {e}\n")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
