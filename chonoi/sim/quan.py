"""Buổi tối — Mở Quán (`quan`).

Luật xử lý một bước (Test Contract v1.0 mục F):
  1. Tăng phase_tick; giảm time_left_ticks, timer nấu, timer ăn, kiên nhẫn;
     chỉ tăng ready_ticks cho món đã `ready` ở đầu bước.
  2. Xét bếp theo id: cooking có cook_ticks_left == 0 -> `ready` (ready_ticks=0) + `dish_ready`.
  3. Đi lại + tối đa một `interact` (chọn theo khoảng cách, bếp trước bàn, id; không fallback):
     - Bếp `idle`: nhận đơn `reserved` cũ nhất theo (order_tick, table_id) -> `cook_started`.
     - Bếp `ready`: tay trống -> nhấc món (`dish_picked`), bếp về `idle`.
     - Bàn: có khách `waiting` khớp `hand.order_id` -> `served` (chốt `tip` bằng Decimal chính xác).
  4. Xử lý khách theo id bàn: ăn xong `eat_ticks_left == 0` -> `paid` (`finished_eating`);
     nếu còn giờ thì khách `waiting` hết kiên nhẫn -> `customer_left(patience)` + đổi uy tín;
     nếu hết ca -> khách ăn trả ngay (`closing`), khách chờ rời (`closing`, không trừ uy tín) -> `quan_end`.
  5. Nếu còn giờ & `random_customers`, xét lịch đến (first_customer_tick, customer_interval_s):
     bàn trống id nhỏ nhất, chọn món nấu được bằng `Streams("quan_customer")` (`customer_arrived` / `no_dish`).
"""

from decimal import Decimal, ROUND_FLOOR
import math

from ..errors import BadInput
from ..ids import id_key, sort_by_id
from ..inventory import validate_items
from .ramp import ramp_velocity

TICK = 60.0


class QuanSim:
    mode = "quan"
    phase = "quan"

    def __init__(self, tuning, scenario, streams, ids, inventory=None):
        t = tuning["quan"]
        self.t = t
        self.menu = tuning["menu"]
        self.rng = streams
        self.ids = ids
        p = scenario.get("player", {})
        self.pos = [float(c) for c in p.get("pos", t["start_pos"])]
        self.vel = [float(c) for c in p.get("vel", [0.0, 0.0])]
        self._tgt = None
        self._ramp_left = 0
        self.phase_tick = 0
        self.random_customers = bool(scenario.get("random_customers", True))
        # kho: --inventory HOẶC scenario.stock (cả hai -> cli đã báo mã 2)
        raw_stock = inventory if inventory is not None else scenario.get("stock", {})
        self.stock = {k: int(v) for k, v in raw_stock.items() if v > 0}
        self.hand = dict(scenario["hand"]) if scenario.get("hand") is not None else None
        self.time_left_ticks = scenario.get("time_left_ticks", int(round(t["duration_s"] * 60)))
        self.reputation = float(scenario.get("reputation", t["reputation_initial"]))

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
            reserved = validate_items(c["reserved"]) if "reserved" in c else {}
            self.customers.append({
                "id": c["id"],
                "table_id": c["table_id"],
                "dish_id": c["dish_id"],
                "order_tick": c.get("order_tick", 0),
                "state": cst,
                "patience_ticks_left": c.get("patience_ticks_left", patience_max if cst == "waiting" else 0),
                "eat_ticks_left": c.get("eat_ticks_left", 0),
                "order_status": ost,
                "reserved": reserved,
                "base_price": c.get("base_price"),
                "tip": c.get("tip"),
            })
            ids.reserve(c["id"])

        self._validate_initial_state()
        self.money = 0
        self.earned = 0
        self.shift_earned = 0
        self.done = False
        self.reason = None

    def _validate_initial_state(self):
        """Kiểm mâu thuẫn chéo giữa bếp, tay, khách và kho trước khi chạy/ghi output."""
        by_id = {c["id"]: c for c in self.customers}
        assigned_dishes = {}

        def register_dish(source, dish):
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

        # Cấp giữ chỗ cho đơn reserved thiếu `reserved` theo (order_tick, id bàn), rồi kiểm tổng giữ <= stock
        total_reserved = {}
        reserved_customers = [
            c for c in self.customers if c["order_status"] == "reserved"
        ]
        reserved_customers.sort(key=lambda c: (c["order_tick"], id_key(c["table_id"])))
        for c in reserved_customers:
            if not c["reserved"]:
                c["reserved"] = {
                    k: int(v) for k, v in sorted(self.menu[c["dish_id"]]["recipe"].items()) if v > 0
                }
            for k, qty in c["reserved"].items():
                total_reserved[k] = total_reserved.get(k, 0) + qty
        for k, needed in total_reserved.items():
            have = self.stock.get(k, 0)
            if needed > have:
                raise BadInput(f"giữ chỗ nguyên liệu {k} ({needed}) vượt tồn kho ({have})")

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
            "stock": {k: self.stock[k] for k in sorted(self.stock) if self.stock[k] > 0},
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
                    "reserved": dict(c["reserved"]),
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

        # 1. tăng đồng hồ, giảm timer ca, nấu, ăn, kiên nhẫn; ready_ticks chỉ tăng cho bếp đã ready đầu bước
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

        # 2. bếp nấu xong chuyển sang ready
        for s in sort_by_id(self.stoves):
            if s["state"] == "cooking" and s["cook_ticks_left"] == 0:
                s["state"] = "ready"
                s["ready_ticks"] = 0
                events.append(("dish_ready", {
                    "stove_id": s["id"],
                    "order_id": s["dish"]["order_id"],
                    "dish_id": s["dish"]["dish_id"],
                }))

        # 3. di chuyển và tối đa một interact theo (khoảng cách, bếp trước bàn, id)
        self._move(inp)
        if inp.pressed("interact"):
            self._handle_interact(events)

        # 4. xử lý khách ăn xong, hết kiên nhẫn, hoặc đóng ca
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

        # 5. nếu còn giờ, xét lịch khách mới
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
                recipe = cust["reserved"]
                items = []
                for ing in sorted(recipe):
                    qty = recipe[ing]
                    self.stock[ing] = self.stock.get(ing, 0) - qty
                    if self.stock[ing] <= 0:
                        self.stock.pop(ing, None)
                    items.extend([ing] * qty)
                cust["reserved"] = {}
                cust["order_status"] = "assigned"
                dish_id = cust["dish_id"]
                base_price = int(self.menu[dish_id]["price"])
                obj["state"] = "cooking"
                obj["dish"] = {"order_id": cust["id"], "dish_id": dish_id, "base_price": base_price}
                obj["cook_ticks_left"] = int(round(self.menu[dish_id]["cook_s"] * TICK))
                obj["ready_ticks"] = 0
                events.append(("cook_started", {
                    "stove_id": obj["id"],
                    "order_id": cust["id"],
                    "dish_id": dish_id,
                    "items": items,
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
        cust["reserved"] = {}
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
        c["reserved"] = {}
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
        avail = dict(self.stock)
        for c in self.customers:
            for k, qty in c["reserved"].items():
                avail[k] = avail.get(k, 0) - qty
        cookable = [
            d for d in sorted(self.menu)
            if all(avail.get(k, 0) >= qty for k, qty in self.menu[d]["recipe"].items())
        ]
        if not cookable:
            events.append(("no_dish", {}))
            return
        dish_id = self.rng.get("quan_customer").choice(cookable)
        cid = self.ids.new("C")
        reserved = {k: int(v) for k, v in sorted(self.menu[dish_id]["recipe"].items()) if v > 0}
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
