"""Buổi tối — Mở Quán (`quan`) theo Test Contract v1.2 (kho cá thể, độ tươi, giữ chỗ theo ID & giá theo tươi).

Luật xử lý một bước (Test Contract v1.2 mục 1):
  1. Tăng `phase_tick`; giảm `time_left_ticks`, timer nấu, timer ăn, kiên nhẫn;
     chỉ tăng `ready_ticks` cho món đã `ready` ở đầu bước.
  2. Hao tươi toàn bộ kho thô (`quan_decay_per_s / 60`), phát hết `spoiled` theo `id` nếu đi từ >= 30 xuống < 30;
     sau đó xử lý các đơn `waiting` + `reserved` bị ươn theo `(order_tick, id bàn)`: nhả toàn bộ và giữ lại một lần,
     không đủ thì chuyển `unfulfillable`.
  3. Xét bếp theo id: `cooking` có `cook_ticks_left == 0` -> `ready` (`ready_ticks = 0`) + `dish_ready`.
  4. Đi lại + tối đa một `interact` (chọn theo khoảng cách, bếp trước bàn, id; không fallback):
     - Bếp `idle`: nhận đơn `reserved` cũ nhất theo `(order_tick, id bàn)`, tiêu đúng cá thể đang giữ,
       chốt `base_price = floor(price * avg_fresh / 100)` -> `cook_started`.
     - Bếp `ready`: tay trống -> nhấc món (`dish_picked`), bếp về `idle`.
     - Bàn: có khách `waiting` khớp `hand.order_id` -> `served` (tính `tip = floor(base_price * tip_rate)` bằng Decimal).
  5. Xử lý khách theo id bàn: ăn xong -> `paid`; còn giờ hết kiên nhẫn -> `customer_left(patience)`;
     hết ca -> khách ăn trả ngay (`closing`), khách chờ rời (`closing`, không trừ uy tín) -> `quan_end`.
  6. Nếu còn giờ & `random_customers`, xét lịch đến (`first_customer_tick`, `customer_interval_s`):
     chọn món giữ được đủ cá thể tươi theo `Streams("quan_customer")` (`customer_arrived` / `no_dish`).
"""

from decimal import Decimal, ROUND_FLOOR
from fractions import Fraction
import math

from ..errors import BadInput
from ..ids import id_key, sort_by_id
from ..inventory import parse_fresh, serialize_item, validate_item_list
from .ramp import ramp_velocity

TICK = 60.0


class QuanSim:
    mode = "quan"
    phase = "quan"

    def __init__(self, tuning, scenario, streams, ids, inventory=None,
                 allowed_dishes=None, money=0, earned=0, reputation=None):
        t = tuning["quan"]
        fcfg = tuning["freshness"]
        self.t = t
        self.menu = tuning["menu"]
        self.allowed_dishes = set(allowed_dishes) if allowed_dishes is not None else set(self.menu.keys())
        self.quan_decay = Fraction(str(fcfg["quan_decay_per_s"])) / int(round(TICK))
        self.spoiled_below = parse_fresh(fcfg["spoiled_below"])
        self.rng = streams
        self.ids = ids
        p = scenario.get("player", {})
        self.pos = [float(c) for c in p.get("pos", t["start_pos"])]
        self.vel = [float(c) for c in p.get("vel", [0.0, 0.0])]
        self._tgt = None
        self._ramp_left = 0
        self.phase_tick = 0
        self.random_customers = bool(scenario.get("random_customers", True))

        raw_stock = inventory if inventory is not None else scenario.get("stock", [])
        parsed_stock = validate_item_list(raw_stock)
        self.stock = {}
        for it in parsed_stock:
            self.stock[it["id"]] = it
            ids.reserve(it["id"])

        self.hand = dict(scenario["hand"]) if scenario.get("hand") is not None else None
        self.time_left_ticks = scenario.get("time_left_ticks", int(round(t["duration_s"] * 60)))
        self.reputation = float(reputation if reputation is not None else scenario.get("reputation", t["reputation_initial"]))

        self.stoves = []
        for s in self._merge(t["stoves"], scenario.get("stoves", [])):
            dish = dict(s["dish"]) if s.get("dish") is not None else None
            self.stoves.append({
                "id": s["id"],
                "pos": [float(c) for c in s["pos"]],
                "state": s.get("state", "idle"),
                "dish": dish,
                "cook_ticks_left": s.get("cook_ticks_left", 0),
                "ready_ticks": s.get("ready_ticks", 0),
            })
        self.tables = [
            {"id": tb["id"], "pos": [float(c) for c in tb["pos"]]}
            for tb in self._merge(t["tables"], scenario.get("tables", []))
        ]

        patience_max = int(round(t["patience_s"] * TICK))
        self.customers = []
        for c in scenario.get("customers", []):
            cst = c.get("state", "waiting")
            ost = c["order_status"] if "order_status" in c else ("served" if cst == "eating" else "reserved")
            self.customers.append({
                "id": c["id"],
                "table_id": c["table_id"],
                "dish_id": c["dish_id"],
                "order_tick": c.get("order_tick", 0),
                "state": cst,
                "patience_ticks_left": c.get("patience_ticks_left", patience_max if cst == "waiting" else 0),
                "eat_ticks_left": c.get("eat_ticks_left", 0),
                "order_status": ost,
                "reserved": list(c.get("reserved", [])),
                "base_price": c.get("base_price"),
                "tip": c.get("tip"),
                "_explicit_reserved": "reserved" in c,
            })
            ids.reserve(c["id"])

        self._validate_initial_state()
        for c in self.customers:
            c.pop("_explicit_reserved", None)

        self.money = int(money)
        self.earned = int(earned)
        self.shift_earned = 0
        self.done = False
        self.reason = None

    def _validate_initial_state(self):
        """Kiểm mâu thuẫn chéo giữa bếp, tay, khách, kế hoạch và kho cá thể v1.2."""
        by_id = {c["id"]: c for c in self.customers}
        assigned_dishes = {}

        for c in self.customers:
            if c["dish_id"] not in self.allowed_dishes:
                raise BadInput(f"customers.{c['id']}: món {c['dish_id']} không thuộc kế hoạch ngày")

        def register_dish(source, dish):
            if dish["dish_id"] not in self.allowed_dishes:
                raise BadInput(f"{source}: món {dish['dish_id']} không thuộc kế hoạch ngày")
            oid = dish["order_id"]
            if oid not in by_id:
                raise BadInput(f"{source}: món tham chiếu đơn không tồn tại ({oid})")
            if oid in assigned_dishes:
                raise BadInput(f"{source}: trùng đơn {oid} với {assigned_dishes[oid]}")
            cust = by_id[oid]
            if dish["dish_id"] != cust["dish_id"]:
                raise BadInput(f"{source}: dish_id {dish['dish_id']} khác đơn {oid} ({cust['dish_id']})")
            if cust["order_status"] != "assigned":
                raise BadInput(f"{source}: đơn {oid} có món nhưng order_status là {cust['order_status']!r}")
            assigned_dishes[oid] = source

        for s in self.stoves:
            if s["state"] in ("cooking", "ready"):
                register_dish(f"stoves.{s['id']}", s["dish"])
        if self.hand is not None:
            register_dish("quan.hand", self.hand)

        for c in self.customers:
            if c["order_status"] == "assigned" and c["id"] not in assigned_dishes:
                raise BadInput(f"customers.{c['id']}: đơn assigned phải có đúng một món ở bếp hoặc tay")

        claimed = set()
        for c in self.customers:
            if c["order_status"] == "reserved" and c["_explicit_reserved"]:
                expected = {k: int(v) for k, v in self.menu[c["dish_id"]]["recipe"].items() if v > 0}
                counts = {}
                for iid in c["reserved"]:
                    if iid not in self.stock:
                        raise BadInput(f"customers.{c['id']}: cá thể giữ chỗ {iid} không có trong kho")
                    if iid in claimed:
                        raise BadInput(f"customers.{c['id']}: cá thể {iid} bị giữ trùng đơn khác")
                    it = self.stock[iid]
                    if it["fresh"] < self.spoiled_below:
                        raise BadInput(f"customers.{c['id']}: cá thể {iid} đã ươn")
                    counts[it["kind"]] = counts.get(it["kind"], 0) + 1
                    claimed.add(iid)
                if counts != expected:
                    raise BadInput(f"customers.{c['id']}: giữ chỗ {counts} khác công thức {expected}")

        auto_res = [c for c in self.customers if c["order_status"] == "reserved" and not c["_explicit_reserved"]]
        auto_res.sort(key=lambda c: (c["order_tick"], id_key(c["table_id"])))
        for c in auto_res:
            picked = self._try_reserve_for_dish(c["dish_id"], extra_claimed=claimed)
            if picked is None:
                raise BadInput(f"customers.{c['id']}: không đủ nguyên liệu tươi giữ chỗ cho {c['dish_id']}")
            c["reserved"] = picked
            claimed.update(picked)

    def _try_reserve_for_dish(self, dish_id: str, extra_claimed=None):
        claimed = {iid for c in self.customers for iid in c["reserved"]}
        if extra_claimed:
            claimed |= extra_claimed
        recipe = self.menu[dish_id]["recipe"]
        avail = {}
        for it in self.stock.values():
            if it["id"] in claimed or it["fresh"] < self.spoiled_below:
                continue
            avail.setdefault(it["kind"], []).append(it)
        picked = []
        for kind in sorted(recipe):
            qty = int(recipe[kind])
            if qty <= 0:
                continue
            pool = avail.get(kind, [])
            if len(pool) < qty:
                return None
            pool.sort(key=lambda it: (-it["fresh"], id_key(it["id"])))
            picked.extend(it["id"] for it in pool[:qty])
        return sorted(picked, key=id_key)

    @staticmethod
    def _merge(defaults, updates):
        by_id = {d["id"]: dict(d) for d in defaults}
        for u in updates:
            if u["id"] not in by_id:
                raise BadInput(f"id bếp/bàn không tồn tại: {u['id']}")
            by_id[u["id"]].update(u)
        return sort_by_id(list(by_id.values()))

    def snapshot(self) -> dict:
        occupied = {c["table_id"]: c["id"] for c in self.customers}
        return {
            "player": {"pos": list(self.pos), "vel": list(self.vel)},
            "stock": [serialize_item(it) for it in sort_by_id(list(self.stock.values()))],
            "hand": dict(self.hand) if self.hand is not None else None,
            "stoves": [
                {
                    "id": s["id"],
                    "pos": list(s["pos"]),
                    "state": s["state"],
                    "dish": dict(s["dish"]) if s["dish"] is not None else None,
                    "cook_ticks_left": s["cook_ticks_left"],
                    "ready_ticks": s["ready_ticks"],
                }
                for s in sort_by_id(self.stoves)
            ],
            "tables": [
                {"id": tb["id"], "pos": list(tb["pos"]), "customer_id": occupied.get(tb["id"])}
                for tb in sort_by_id(self.tables)
            ],
            "customers": [
                {
                    "id": c["id"],
                    "table_id": c["table_id"],
                    "dish_id": c["dish_id"],
                    "order_tick": c["order_tick"],
                    "state": c["state"],
                    "patience_ticks_left": c["patience_ticks_left"],
                    "eat_ticks_left": c["eat_ticks_left"],
                    "order_status": c["order_status"],
                    "reserved": list(c["reserved"]),
                    "base_price": c["base_price"],
                    "tip": c["tip"],
                }
                for c in sort_by_id(self.customers)
            ],
        }

    def step(self, inp):
        if self.done:
            return []
        events = []

        # 1. tăng đồng hồ và cập nhật timer
        self.phase_tick += 1
        self.time_left_ticks = max(0, self.time_left_ticks - 1)
        for s in self.stoves:
            if s["state"] == "ready":
                s["ready_ticks"] += 1
            elif s["state"] == "cooking":
                s["cook_ticks_left"] = max(0, s["cook_ticks_left"] - 1)
        for c in self.customers:
            if c["state"] == "waiting":
                c["patience_ticks_left"] = max(0, c["patience_ticks_left"] - 1)
            elif c["state"] == "eating":
                c["eat_ticks_left"] = max(0, c["eat_ticks_left"] - 1)

        # 2. hao tươi toàn bộ kho thô -> phát hết spoiled theo id -> xử lý giữ chỗ bị ươn
        newly_spoiled = set()
        for it in sort_by_id(list(self.stock.values())):
            prev = it["fresh"]
            nxt = max(Fraction(0), prev - self.quan_decay)
            it["fresh"] = nxt
            if prev >= self.spoiled_below and nxt < self.spoiled_below:
                newly_spoiled.add(it["id"])
                events.append(("spoiled", {"item_id": it["id"], "kind": it["kind"], "location": "stock"}))

        if newly_spoiled:
            affected = [
                c for c in self.customers
                if c["state"] == "waiting" and c["order_status"] == "reserved"
                and any(iid in newly_spoiled for iid in c["reserved"])
            ]
            affected.sort(key=lambda c: (c["order_tick"], id_key(c["table_id"])))
            for c in affected:
                c["reserved"] = []
                picked = self._try_reserve_for_dish(c["dish_id"])
                if picked is not None:
                    c["reserved"] = picked
                else:
                    c["order_status"] = "unfulfillable"

        # 3. bếp nấu xong chuyển sang ready
        for s in sort_by_id(self.stoves):
            if s["state"] == "cooking" and s["cook_ticks_left"] == 0:
                s["state"] = "ready"
                s["ready_ticks"] = 0
                events.append(("dish_ready", {
                    "stove_id": s["id"],
                    "order_id": s["dish"]["order_id"],
                    "dish_id": s["dish"]["dish_id"],
                }))

        # 4. di chuyển và tối đa một interact theo (khoảng cách, bếp trước bàn, id)
        self._move(inp)
        if inp.pressed("interact"):
            self._handle_interact(events)

        # 5. xử lý khách ăn xong, hết kiên nhẫn, hoặc đóng ca
        remaining = []
        for c in sorted(self.customers, key=lambda x: id_key(x["table_id"])):
            if c["state"] == "eating" and c["eat_ticks_left"] == 0:
                self._settle_paid(c, "finished_eating", events)
            else:
                remaining.append(c)
        self.customers = remaining

        if self.time_left_ticks > 0:
            still_here = []
            for c in sorted(self.customers, key=lambda x: id_key(x["table_id"])):
                if c["state"] == "waiting" and c["patience_ticks_left"] == 0:
                    self.reputation = self._clamp_rep(
                        self.reputation + float(self.t["left_reputation_delta"])
                    )
                    self._discard_order(c)
                    events.append(("customer_left", {
                        "order_id": c["id"],
                        "table_id": c["table_id"],
                        "reason": "patience",
                        "reputation": self.reputation,
                    }))
                else:
                    still_here.append(c)
            self.customers = still_here
        else:
            for c in sorted(self.customers, key=lambda x: id_key(x["table_id"])):
                if c["state"] == "eating":
                    self._settle_paid(c, "closing", events)
                else:
                    self._discard_order(c)
                    events.append(("customer_left", {
                        "order_id": c["id"],
                        "table_id": c["table_id"],
                        "reason": "closing",
                        "reputation": self.reputation,
                    }))
            self.customers = []
            self.done = True
            self.reason = "time"
            events.append(("quan_end", {
                "reason": "time",
                "money": self.money,
                "earned": self.earned,
                "shift_earned": self.shift_earned,
                "reputation": self.reputation,
            }))
            return events

        # 6. nếu còn giờ, xét lịch khách mới
        if self.random_customers:
            first = int(self.t["first_customer_tick"])
            interval = int(round(self.t["customer_interval_s"] * TICK))
            if self.phase_tick >= first and (self.phase_tick - first) % interval == 0:
                self._spawn_customer(events)

        return events

    def _handle_interact(self, events):
        r = self.t["interact_radius"]
        candidates = []
        for s in self.stoves:
            d = math.dist(self.pos, s["pos"])
            if d <= r:
                candidates.append((d, 0, s, "stove"))
        for tb in self.tables:
            d = math.dist(self.pos, tb["pos"])
            if d <= r:
                candidates.append((d, 1, tb, "table"))
        if not candidates:
            return
        _, _, obj, kind = min(candidates, key=lambda item: (item[0], item[1], id_key(item[2]["id"])))

        if kind == "stove":
            if obj["state"] == "idle":
                waiting = [
                    c for c in self.customers
                    if c["state"] == "waiting" and c["order_status"] == "reserved"
                ]
                if not waiting:
                    return
                cust = min(waiting, key=lambda c: (c["order_tick"], id_key(c["table_id"])))
                used_items = [self.stock.pop(iid) for iid in cust["reserved"]]
                used_items.sort(key=lambda it: (it["kind"], id_key(it["id"])))
                cust["reserved"] = []
                cust["order_status"] = "assigned"
                dish_id = cust["dish_id"]
                avg_fresh = sum((it["fresh"] for it in used_items), Fraction(0)) / len(used_items)
                base_price = math.floor(Fraction(int(self.menu[dish_id]["price"])) * avg_fresh / 100)
                obj["state"] = "cooking"
                obj["dish"] = {"order_id": cust["id"], "dish_id": dish_id, "base_price": base_price}
                obj["cook_ticks_left"] = int(round(self.menu[dish_id]["cook_s"] * TICK))
                obj["ready_ticks"] = 0
                events.append(("cook_started", {
                    "stove_id": obj["id"],
                    "order_id": cust["id"],
                    "dish_id": dish_id,
                    "items": [serialize_item(it) for it in used_items],
                    "base_price": base_price,
                }))
            elif obj["state"] == "ready":
                if self.hand is not None:
                    return
                dish = obj["dish"]
                self.hand = dish
                obj["state"] = "idle"
                obj["dish"] = None
                obj["cook_ticks_left"] = 0
                obj["ready_ticks"] = 0
                events.append(("dish_picked", {
                    "stove_id": obj["id"],
                    "order_id": dish["order_id"],
                    "dish_id": dish["dish_id"],
                }))
            return

        # kind == "table"
        cust = next((c for c in self.customers if c["table_id"] == obj["id"]), None)
        if cust is None or cust["state"] != "waiting":
            return
        if self.hand is None or self.hand["order_id"] != cust["id"]:
            return
        dish = self.hand
        self.hand = None
        patience_max = int(round(self.t["patience_s"] * TICK))
        rem = cust["patience_ticks_left"]
        gets_tip = Decimal(rem) >= Decimal(patience_max) * Decimal(str(self.t["tip_min_patience_ratio"]))
        base_price = int(dish["base_price"])
        tip = (
            int((Decimal(base_price) * Decimal(str(self.t["tip_rate"]))).to_integral_value(rounding=ROUND_FLOOR))
            if gets_tip
            else 0
        )
        cust["state"] = "eating"
        cust["order_status"] = "served"
        cust["eat_ticks_left"] = int(round(self.t["eat_s"] * TICK))
        cust["base_price"] = base_price
        cust["tip"] = tip
        cust["reserved"] = []
        events.append(("served", {
            "order_id": cust["id"],
            "table_id": obj["id"],
            "dish_id": dish["dish_id"],
            "patience_ticks_left": rem,
            "base_price": base_price,
            "tip": tip,
        }))

    def _settle_paid(self, c, reason, events):
        base_price = int(c["base_price"])
        tip = int(c["tip"])
        amount = base_price + tip
        self.money += amount
        self.earned += amount
        self.shift_earned += amount
        if tip > 0:
            self.reputation = self._clamp_rep(self.reputation + float(self.t["tip_reputation"]))
        events.append(("paid", {
            "order_id": c["id"],
            "table_id": c["table_id"],
            "base_price": base_price,
            "tip": tip,
            "amount": amount,
            "reason": reason,
        }))

    def _discard_order(self, c):
        c["reserved"] = []
        oid = c["id"]
        if self.hand is not None and self.hand["order_id"] == oid:
            self.hand = None
        for s in self.stoves:
            if s["dish"] is not None and s["dish"]["order_id"] == oid:
                s["state"] = "idle"
                s["dish"] = None
                s["cook_ticks_left"] = 0
                s["ready_ticks"] = 0

    def _spawn_customer(self, events):
        occupied = {c["table_id"] for c in self.customers}
        free_tables = [tb for tb in sort_by_id(self.tables) if tb["id"] not in occupied]
        if not free_tables:
            return
        tb = free_tables[0]
        cookable = [
            d for d in sorted(self.allowed_dishes)
            if self._try_reserve_for_dish(d) is not None
        ]
        if not cookable:
            events.append(("no_dish", {}))
            return
        dish_id = self.rng.get("quan_customer").choice(cookable)
        reserved = self._try_reserve_for_dish(dish_id)
        cid = self.ids.new("C")
        self.customers.append({
            "id": cid,
            "table_id": tb["id"],
            "dish_id": dish_id,
            "order_tick": self.phase_tick,
            "state": "waiting",
            "patience_ticks_left": int(round(self.t["patience_s"] * TICK)),
            "eat_ticks_left": 0,
            "order_status": "reserved",
            "reserved": reserved,
            "base_price": None,
            "tip": None,
        })
        events.append(("customer_arrived", {
            "order_id": cid,
            "table_id": tb["id"],
            "dish_id": dish_id,
        }))

    def _clamp_rep(self, value: float) -> float:
        return min(float(self.t["reputation_max"]), max(float(self.t["reputation_min"]), float(value)))

    def _move(self, inp):
        speed = self.t["walk_speed"]
        mx, mz = inp.move
        self.vel = ramp_velocity(self, (mx * speed, mz * speed), int(self.t.get("ramp_max_ticks", 6)))
        b = self.t["bounds"]
        for i, axis in enumerate(("x", "z")):
            self.pos[i] += self.vel[i] / TICK
            lo, hi = b[axis]
            if self.pos[i] <= lo:
                self.pos[i], self.vel[i] = lo, max(0.0, self.vel[i])
            elif self.pos[i] >= hi:
                self.pos[i], self.vel[i] = hi, min(0.0, self.vel[i])
