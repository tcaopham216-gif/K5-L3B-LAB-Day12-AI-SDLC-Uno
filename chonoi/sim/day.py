"""Vòng ngày (`day`): DayIntro/gather -> quan -> shop -> ngày kế (`days` = 1..5) theo Contract v1.1."""

import copy

from ..errors import BadInput
from .gather import GatherSim
from .quan import QuanSim


class DaySim:
    mode = "day"

    def __init__(self, tuning, scenario, streams, ids, days=1):
        self.tuning = tuning
        self.rng = streams
        self.ids = ids
        self.target_days = int(days)

        day_b = scenario.get("day", {})
        self.gather_tpl = copy.deepcopy(scenario.get("gather", {}))
        self.quan_tpl = copy.deepcopy(scenario.get("quan", {}))

        self._money = int(day_b.get("money", 0))
        self._earned = int(day_b.get("earned", 0))
        self._reputation = float(day_b.get("reputation", tuning["quan"]["reputation_initial"]))
        raw_up = day_b.get("upgrades", {})
        self.upgrades = {k: int(v) for k, v in raw_up.items() if int(v) > 0}
        self.active_upgrades = dict(self.upgrades)

        self.plans = {}
        menu = tuning["menu"]
        for entry in tuning["day_plan"]:
            self.plans[int(entry["day"])] = {
                "dishes": dict(entry["dishes"]),
                "ingredients": dict(entry["ingredients"]),
            }
        for entry in day_b.get("day_plan", []):
            dno = int(entry["day"])
            dishes = dict(entry["dishes"])
            if "ingredients" in entry:
                ings = dict(entry["ingredients"])
            else:
                ings = {}
                for did, cnt in dishes.items():
                    for k, qty in menu[did]["recipe"].items():
                        ings[k] = ings.get(k, 0) + qty * cnt
            self.plans[dno] = {"dishes": dishes, "ingredients": ings}

        self._validate_quan_template_upfront()

        self.day = 1
        self.days_completed = 0
        self.done = False
        self.reason = None
        self.phase = "gather"
        self.quan = None
        self.shop_stock = {}
        self.shop_phase_tick = 0
        self.shop_time_left = 0
        self.gather = self._make_gather(self.day)

    def _validate_quan_template_upfront(self):
        """Kiểm mâu thuẫn tĩnh trong khối `quan` của scenario (không phụ thuộc kho động)."""
        q = self.quan_tpl
        if not q:
            return
        d1_dishes = set(self.plans[1]["dishes"].keys())
        by_id = {c["id"]: c for c in q.get("customers", [])}
        assigned = {}

        for c in q.get("customers", []):
            if c["dish_id"] not in d1_dishes:
                raise BadInput(f"customers.{c['id']}: món {c['dish_id']} không thuộc kế hoạch Ngày 1")

        def reg(source, dish):
            if dish["dish_id"] not in d1_dishes:
                raise BadInput(f"{source}: món {dish['dish_id']} không thuộc kế hoạch Ngày 1")
            oid = dish["order_id"]
            if oid not in by_id:
                raise BadInput(f"{source}: món tham chiếu đơn không tồn tại ({oid})")
            if oid in assigned:
                raise BadInput(f"{source}: trùng đơn {oid} với {assigned[oid]}")
            cust = by_id[oid]
            if dish["dish_id"] != cust["dish_id"]:
                raise BadInput(f"{source}: dish_id {dish['dish_id']} khác đơn {oid}")
            cst = cust.get("state", "waiting")
            ost = cust.get("order_status", "served" if cst == "eating" else "reserved")
            if ost != "assigned":
                raise BadInput(f"{source}: đơn {oid} có món nhưng order_status là {ost!r}")
            assigned[oid] = source

        for s in q.get("stoves", []):
            if s.get("state") in ("cooking", "ready"):
                reg(f"stoves.{s['id']}", s["dish"])
        if q.get("hand") is not None:
            reg("quan.hand", q["hand"])
        for c in q.get("customers", []):
            cst = c.get("state", "waiting")
            ost = c.get("order_status", "served" if cst == "eating" else "reserved")
            if ost == "assigned" and c["id"] not in assigned:
                raise BadInput(f"customers.{c['id']}: đơn assigned phải có đúng một món ở bếp hoặc tay")

    def _make_gather(self, day):
        return GatherSim(
            self.tuning,
            copy.deepcopy(self.gather_tpl),
            self.rng,
            self.ids,
            day=day,
            active_upgrades=self.active_upgrades,
            money=self.money,
            earned=self.earned,
            reputation=self.reputation,
        )

    def _plan_payload(self, day):
        pl = self.plans[day]
        return {"dishes": dict(pl["dishes"]), "ingredients": dict(pl["ingredients"])}

    @property
    def money(self) -> int:
        return self.quan.money if self.quan is not None else self._money

    @property
    def earned(self) -> int:
        return self.quan.earned if self.quan is not None else self._earned

    @property
    def reputation(self) -> float:
        return self.quan.reputation if self.quan is not None else self._reputation

    @property
    def phase_tick(self) -> int:
        if self.phase == "gather":
            return self.gather.phase_tick
        if self.phase == "quan":
            return self.quan.phase_tick
        return self.shop_phase_tick

    @property
    def time_left_ticks(self) -> int:
        if self.phase == "gather":
            return self.gather.time_left_ticks
        if self.phase == "quan":
            return self.quan.time_left_ticks
        return self.shop_time_left

    def startup_events(self) -> list:
        return [
            ("day_start", {}, "gather", self.day),
            ("day_plan", self._plan_payload(self.day), "gather", self.day),
            ("phase_start", {}, "gather", self.day),
        ]

    def snapshot(self) -> dict:
        base = {
            "day": self.day,
            "day_plan": self._plan_payload(self.day),
            "upgrades": dict(self.upgrades),
            "active_upgrades": dict(self.active_upgrades),
        }
        if self.phase == "gather":
            base.update(self.gather.snapshot())
        elif self.phase == "quan":
            base.update(self.quan.snapshot())
        else:
            base["stock"] = {k: self.shop_stock[k] for k in sorted(self.shop_stock) if self.shop_stock[k] > 0}
        return base

    def step(self, inp) -> list:
        if self.done:
            return []

        if self.phase == "gather":
            cur_day = self.day
            evs = self.gather.step(inp)
            out = [(name, data, "gather", cur_day) for name, data in evs]
            if self.gather.done:
                inv = self.gather.inventory_items()
                allowed = set(self.plans[cur_day]["dishes"].keys())
                self.quan = QuanSim(
                    self.tuning,
                    copy.deepcopy(self.quan_tpl),
                    self.rng,
                    self.ids,
                    inventory=inv,
                    allowed_dishes=allowed,
                    money=self.money,
                    earned=self.earned,
                    reputation=self.reputation,
                )
                self.gather = None
                self.phase = "quan"
                out.append(("phase_start", {}, "quan", cur_day))
            return out

        if self.phase == "quan":
            cur_day = self.day
            evs = self.quan.step(inp)
            out = [(name, data, "quan", cur_day) for name, data in evs]
            if self.quan.done:
                self._money = self.quan.money
                self._earned = self.quan.earned
                self._reputation = self.quan.reputation
                self.shop_stock = {k: int(v) for k, v in sorted(self.quan.stock.items()) if v > 0}
                self.quan = None
                self.phase = "shop"
                self.shop_phase_tick = 0
                self.shop_time_left = int(self.tuning["shop"]["max_ticks"])
                out.append(("phase_start", {}, "shop", cur_day))
            return out

        # phase == "shop"
        cur_day = self.day
        out = []
        self.shop_phase_tick += 1
        self.shop_time_left = max(0, self.shop_time_left - 1)

        if inp.buy is not None:
            action = inp.buy
            if action in ("oxygen", "hp"):
                cur_lvl = self.upgrades.get(action, 0)
                tiers = self.tuning["shop"]["upgrades"][action]
                if cur_lvl >= len(tiers):
                    out.append(("buy_failed", {"action": action, "reason": "max_level"}, "shop", cur_day))
                else:
                    tier = tiers[cur_lvl]
                    price = int(tier["price"])
                    if self._money < price:
                        out.append(("buy_failed", {"action": action, "reason": "funds"}, "shop", cur_day))
                    else:
                        self._money -= price
                        new_lvl = int(tier["level"])
                        self.upgrades[action] = new_lvl
                        out.append(("bought", {
                            "upgrade": action,
                            "level": new_lvl,
                            "price": price,
                            "money": self._money,
                        }, "shop", cur_day))
            else:
                out.append(("buy_failed", {"action": action, "reason": "unknown"}, "shop", cur_day))

        end_reason = None
        if inp.pressed("shop_done"):
            end_reason = "done"
        elif self.shop_time_left <= 0:
            end_reason = "time"

        if end_reason is not None:
            out.append(("shop_end", {"reason": end_reason}, "shop", cur_day))
            self.days_completed += 1
            self.shop_stock = {}
            if self.days_completed >= self.target_days:
                self.done = True
                self.reason = "days_complete"
            else:
                self.day += 1
                self.active_upgrades = dict(self.upgrades)
                self.phase = "gather"
                self.gather = self._make_gather(self.day)
                out.append(("day_start", {}, "gather", self.day))
                out.append(("day_plan", self._plan_payload(self.day), "gather", self.day))
                out.append(("phase_start", {}, "gather", self.day))

        return out
