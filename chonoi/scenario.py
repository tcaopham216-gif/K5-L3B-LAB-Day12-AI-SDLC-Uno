"""Nạp và kiểm scenario (Contract D v1.1). Trả về dict theo mode.

Kiểm tra cú pháp, id trùng, bộ đếm âm/mâu thuẫn, khoang vượt sức chứa, trường lạ,
cá bơi/quái vật, khối day và kế hoạch ngày trước khi ghi đầu ra (mã thoát 2).
"""

import json
import math

from .errors import BadInput
from .inventory import KINDS_P2, validate_items

GATHER_KEYS = {"player", "hold", "nodes", "fish", "random_fish", "monsters", "time_left_ticks"}
GATHER_PLAYER_KEYS = {"pos", "vel", "heading_deg", "hp", "oxygen_ticks", "zero_oxy_ticks",
                      "invuln_ticks", "catch_cd_ticks"}
GATHER_NODE_KEYS = {"id", "kind", "pos", "regrow_ticks"}
GATHER_FISH_KEYS = {"id", "kind", "pos", "heading_deg", "age_ticks"}
GATHER_MONSTER_KEYS = {"id", "kind", "pos", "waypoints", "target_idx", "state",
                       "state_ticks_left", "recoil_dir"}
NODE_KINDS = ("bong_dien_dien", "bong_sung", "keo_neo")
FISH_KINDS = ("ca_linh", "ca_loc", "ca_keo")
MONSTER_STATES = ("patrol", "chase", "recoil")

QUAN_PLAYER_KEYS = {"pos", "vel"}
QUAN_KEYS = {"player", "stock", "hand", "stoves", "tables", "customers", "random_customers",
             "reputation", "time_left_ticks"}
QUAN_STOVE_KEYS = {"id", "pos", "state", "dish", "cook_ticks_left", "ready_ticks"}
QUAN_TABLE_KEYS = {"id", "pos"}
QUAN_CUSTOMER_KEYS = {"id", "table_id", "dish_id", "order_tick", "state",
                      "patience_ticks_left", "eat_ticks_left", "order_status",
                      "reserved", "base_price", "tip"}
DISH_PAYLOAD_KEYS = {"order_id", "dish_id", "base_price"}
STOVE_STATES = ("idle", "cooking", "ready")
CUSTOMER_STATES = ("waiting", "eating")
ORDER_STATUSES = ("reserved", "assigned", "unfulfillable", "served")

DAY_KEYS = {"money", "earned", "reputation", "upgrades", "day_plan"}
DAY_PLAN_KEYS = {"day", "dishes", "ingredients"}


def _check_ids(name, arr):
    if not isinstance(arr, list):
        raise BadInput(f"{name} phải là mảng")
    seen = set()
    for e in arr:
        if not isinstance(e, dict) or not isinstance(e.get("id"), str) or not e["id"]:
            raise BadInput(f"{name}: mỗi phần tử cần id (chuỗi khác rỗng)")
        if e["id"] in seen:
            raise BadInput(f"{name}: id trùng {e['id']}")
        seen.add(e["id"])


def _effective_gather_caps(day_block, tuning):
    g = tuning["gather"]
    oxy_s = g["oxygen_max_s"]
    hp_max = g["hp_max"]
    up = day_block.get("upgrades", {}) if day_block else {}
    shop_up = tuning.get("shop", {}).get("upgrades", {})
    ox_lvl = up.get("oxygen", 0)
    if ox_lvl > 0:
        oxy_s = next(t["oxygen_max_s"] for t in shop_up["oxygen"] if t["level"] == ox_lvl)
    hp_lvl = up.get("hp", 0)
    if hp_lvl > 0:
        hp_max = next(t["hp_max"] for t in shop_up["hp"] if t["level"] == hp_lvl)
    return int(round(oxy_s * 60)), int(hp_max)


def load_scenario(path, mode: str, tuning: dict) -> dict:
    if path is None:
        return {"day": {}, "gather": {}, "quan": {}} if mode == "day" else {}
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError) as e:
        raise BadInput(f"không đọc được scenario {path}: {e}")

    if mode == "day":
        if not isinstance(data, dict) or not set(data) <= {"day", "gather", "quan"}:
            raise BadInput("scenario chế độ day chỉ nhận các khối 'day', 'gather', 'quan'")
        day_b = data.get("day", {})
        gather_b = data.get("gather", {})
        quan_b = data.get("quan", {})
        if not isinstance(day_b, dict) or not isinstance(gather_b, dict) or not isinstance(quan_b, dict):
            raise BadInput("các khối day, gather, quan phải là object")
        _validate_day(day_b, tuning)
        _check_common_block(gather_b, "gather", GATHER_KEYS, tuning)
        oxy_max, hp_max = _effective_gather_caps(day_b, tuning)
        _validate_gather(gather_b, tuning, oxy_max=oxy_max, hp_max=hp_max)
        if "stock" in quan_b or "reputation" in quan_b:
            raise BadInput("cấm quan.stock và quan.reputation khi chạy --mode day")
        _check_common_block(quan_b, "quan", QUAN_KEYS, tuning)
        _validate_quan(quan_b, tuning)
        return {"day": day_b, "gather": gather_b, "quan": quan_b}

    if not isinstance(data, dict) or not set(data) <= {"gather", "quan"}:
        raise BadInput("scenario chỉ được có khối 'gather' hoặc 'quan'")
    if set(data) - {mode}:
        raise BadInput(f"khối sai mode: chạy --mode {mode} chỉ nhận khối '{mode}'")
    block = data.get(mode, {})
    if not isinstance(block, dict):
        raise BadInput(f"khối {mode} phải là object")
    allowed = GATHER_KEYS if mode == "gather" else QUAN_KEYS
    _check_common_block(block, mode, allowed, tuning)
    if mode == "gather":
        _validate_gather(block, tuning)
    else:
        _validate_quan(block, tuning)
    return block


def _check_common_block(block, phase_name, allowed, tuning):
    extra = set(block) - allowed
    if extra:
        raise BadInput(f"trường lạ/chưa hỗ trợ trong {phase_name}: {sorted(extra)}")
    dur = int(round(tuning[phase_name]["duration_s"] * 60))
    if "time_left_ticks" in block:
        t = block["time_left_ticks"]
        if isinstance(t, bool) or not isinstance(t, int) or not (1 <= t <= dur):
            raise BadInput(f"time_left_ticks phải là số nguyên trong [1, {dur}]")


def _num(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)


def _pos_int(name, v):
    if isinstance(v, bool) or not isinstance(v, int) or v <= 0:
        raise BadInput(f"{name} phải là số nguyên dương")


def _nonneg_int(name, v):
    if isinstance(v, bool) or not isinstance(v, int) or v < 0:
        raise BadInput(f"{name} phải là số nguyên không âm")


def _pos(name, pos, bounds, axes=("x", "d")):
    if not (isinstance(pos, list) and len(pos) == 2 and all(_num(c) for c in pos)):
        raise BadInput(f"{name} phải là [{axes[0]}, {axes[1]}]")
    for c, axis in zip(pos, axes):
        lo, hi = bounds[axis]
        if not (lo <= c <= hi):
            raise BadInput(f"{name} nằm ngoài vùng ({axis} ∈ [{lo}, {hi}])")


def _validate_dish_payload(label, dish, menu):
    if not isinstance(dish, dict) or set(dish.keys()) != DISH_PAYLOAD_KEYS:
        raise BadInput(f"{label} phải là object có đúng khóa {sorted(DISH_PAYLOAD_KEYS)}")
    if not isinstance(dish.get("order_id"), str) or not dish["order_id"]:
        raise BadInput(f"{label}.order_id phải là chuỗi khác rỗng")
    if not isinstance(dish.get("dish_id"), str) or dish["dish_id"] not in menu:
        raise BadInput(f"{label}.dish_id ngoài menu: {dish.get('dish_id')!r}")
    _pos_int(f"{label}.base_price", dish.get("base_price"))


def _validate_day(d, tuning):
    extra = set(d) - DAY_KEYS
    if extra:
        raise BadInput(f"trường lạ trong khối day: {sorted(extra)}")
    has_money = "money" in d
    has_earned = "earned" in d
    money = d.get("money", 0)
    earned = d.get("earned", 0)
    _nonneg_int("day.money", money)
    _nonneg_int("day.earned", earned)
    if has_money and money > 0 and not has_earned:
        raise BadInput("day: khi có tiền đầu kỳ (money > 0) phải khai cả money và earned")
    if money > earned:
        raise BadInput(f"day: money ({money}) không được vượt earned ({earned})")
    if "reputation" in d:
        rep = d["reputation"]
        q = tuning["quan"]
        if not _num(rep) or not (q["reputation_min"] <= rep <= q["reputation_max"]):
            raise BadInput("day.reputation nằm ngoài khoảng hợp lệ")
    if "upgrades" in d:
        up = d["upgrades"]
        shop_up = tuning["shop"]["upgrades"]
        if not isinstance(up, dict):
            raise BadInput("day.upgrades phải là object")
        for uid, lvl in up.items():
            if uid not in ("oxygen", "hp"):
                raise BadInput(f"day.upgrades: nâng cấp không hợp lệ/chưa bật: {uid}")
            max_lvl = len(shop_up[uid])
            if isinstance(lvl, bool) or not isinstance(lvl, int) or not (0 <= lvl <= max_lvl):
                raise BadInput(f"day.upgrades.{uid} phải là số nguyên trong [0, {max_lvl}]")
    if "day_plan" in d:
        dp = d["day_plan"]
        if not isinstance(dp, list):
            raise BadInput("day.day_plan phải là mảng")
        menu = tuning["menu"]
        seen = set()
        for idx, item in enumerate(dp):
            if not isinstance(item, dict):
                raise BadInput(f"day.day_plan[{idx}] phải là object")
            extra_i = set(item) - DAY_PLAN_KEYS
            if extra_i:
                raise BadInput(f"day.day_plan[{idx}]: trường lạ {sorted(extra_i)}")
            day_no = item.get("day")
            if isinstance(day_no, bool) or not isinstance(day_no, int) or not (1 <= day_no <= 5):
                raise BadInput(f"day.day_plan[{idx}].day phải thuộc [1, 5]")
            if day_no in seen:
                raise BadInput(f"day.day_plan trùng ngày {day_no}")
            seen.add(day_no)
            dishes = item.get("dishes")
            if not isinstance(dishes, dict) or not dishes:
                raise BadInput(f"day.day_plan ngày {day_no}: dishes phải là map khác rỗng")
            calc = {}
            for did, cnt in dishes.items():
                if did not in menu or isinstance(cnt, bool) or not isinstance(cnt, int) or cnt <= 0:
                    raise BadInput(f"day.day_plan ngày {day_no}: món {did!r}={cnt!r} không hợp lệ")
                for ing, qty in menu[did]["recipe"].items():
                    calc[ing] = calc.get(ing, 0) + qty * cnt
            if "ingredients" in item:
                ings = item["ingredients"]
                if not isinstance(ings, dict):
                    raise BadInput(f"day.day_plan ngày {day_no}: ingredients phải là object")
                for k, v in ings.items():
                    if k not in KINDS_P2 or isinstance(v, bool) or not isinstance(v, int) or v <= 0:
                        raise BadInput(f"day.day_plan ngày {day_no}: ingredients.{k}={v!r} không hợp lệ")
                if ings != calc:
                    raise BadInput(f"day.day_plan ngày {day_no}: ingredients {ings} khác công thức {calc}")


def _validate_gather(b, tuning, oxy_max=None, hp_max=None):
    g = tuning["gather"]
    bounds = g["bounds"]
    omax = oxy_max if oxy_max is not None else int(round(g["oxygen_max_s"] * 60))
    hp_cap = hp_max if hp_max is not None else g["hp_max"]
    for arr in ("nodes", "fish", "monsters"):
        if arr in b:
            _check_ids(arr, b[arr])
    if "random_fish" in b and not isinstance(b["random_fish"], bool):
        raise BadInput("random_fish phải là boolean")
    if "hold" in b:
        h = b["hold"]
        if not isinstance(h, list) or any(k not in KINDS_P2 for k in h):
            raise BadInput("hold phải là mảng id nguyên liệu hợp lệ")
        if len(h) > g["hold_capacity"]:
            raise BadInput("hold vượt sức chứa")
    p = b.get("player", {})
    if not isinstance(p, dict):
        raise BadInput("player phải là object")
    extra = set(p) - GATHER_PLAYER_KEYS
    if extra:
        raise BadInput(f"trường lạ/chưa hỗ trợ trong gather.player: {sorted(extra)}")
    if "pos" in p:
        _pos("player.pos", p["pos"], bounds)
    if "vel" in p and not (isinstance(p["vel"], list) and len(p["vel"]) == 2 and all(_num(c) for c in p["vel"])):
        raise BadInput("player.vel phải là [x, d]")
    if "heading_deg" in p and not _num(p["heading_deg"]):
        raise BadInput("player.heading_deg phải là số")
    for key in ("invuln_ticks", "catch_cd_ticks", "zero_oxy_ticks", "oxygen_ticks", "hp"):
        if key in p:
            _nonneg_int(f"player.{key}", p[key])
    if "oxygen_ticks" in p and p["oxygen_ticks"] > omax:
        raise BadInput("player.oxygen_ticks vượt oxy tối đa")
    if "hp" in p and not (1 <= p["hp"] <= hp_cap):
        raise BadInput("player.hp phải trong [1, hp_max]")
    if "zero_oxy_ticks" in p:
        pos = p.get("pos", g["start_pos"])
        oxy = p.get("oxygen_ticks", omax)
        choke_lim = int(g.get("choke_interval_ticks", 60)) - 1
        if p["zero_oxy_ticks"] > choke_lim:
            raise BadInput(f"player.zero_oxy_ticks phải trong [0, {choke_lim}]")
        if p["zero_oxy_ticks"] > 0 and not (oxy == 0 and pos[1] > g["surface_depth"]):
            raise BadInput("player.zero_oxy_ticks > 0 chỉ khi oxy = 0 và đang dưới nước")
    for n in b.get("nodes", []):
        extra_n = set(n) - GATHER_NODE_KEYS
        if extra_n:
            raise BadInput(f"nodes.{n['id']}: trường lạ {sorted(extra_n)}")
        if n.get("kind") not in NODE_KINDS:
            raise BadInput(f"nodes.{n['id']}: kind phải là một trong {NODE_KINDS}")
        _pos(f"nodes.{n['id']}.pos", n.get("pos"), bounds)
        if n["pos"][1] != 0:
            raise BadInput(f"nodes.{n['id']}: nút hái nằm ở mặt nước (d = 0)")
        if "regrow_ticks" in n:
            _nonneg_int(f"nodes.{n['id']}.regrow_ticks", n["regrow_ticks"])
    for f in b.get("fish", []):
        extra_f = set(f) - GATHER_FISH_KEYS
        if extra_f:
            raise BadInput(f"fish.{f['id']}: trường lạ {sorted(extra_f)}")
        if f.get("kind") not in FISH_KINDS:
            raise BadInput(f"fish.{f['id']}: kind phải là một trong {FISH_KINDS}")
        _pos(f"fish.{f['id']}.pos", f.get("pos"), bounds)
        if f["pos"][1] <= g["surface_depth"]:
            raise BadInput(f"fish.{f['id']}: đàn cá phải ở dưới nước")
        if "heading_deg" in f and not _num(f["heading_deg"]):
            raise BadInput(f"fish.{f['id']}.heading_deg phải là số")
        if "age_ticks" in f:
            _nonneg_int(f"fish.{f['id']}.age_ticks", f["age_ticks"])

    species = g["monsters"]["species"]
    for m in b.get("monsters", []):
        mid = m["id"]
        extra_m = set(m) - GATHER_MONSTER_KEYS
        if extra_m:
            raise BadInput(f"monsters.{mid}: trường lạ {sorted(extra_m)}")
        kind = m.get("kind")
        if kind not in species:
            raise BadInput(f"monsters.{mid}: kind không hợp lệ {kind!r}")
        sp_bounds = {"x": bounds["x"], "d": species[kind]["depths"]}
        _pos(f"monsters.{mid}.pos", m.get("pos"), sp_bounds)
        wps = m.get("waypoints")
        if not isinstance(wps, list) or len(wps) != 2:
            raise BadInput(f"monsters.{mid}.waypoints phải là 2 điểm")
        for i, wp in enumerate(wps):
            _pos(f"monsters.{mid}.waypoints[{i}]", wp, sp_bounds)
        tidx = m.get("target_idx", 1)
        if isinstance(tidx, bool) or tidx not in (0, 1):
            raise BadInput(f"monsters.{mid}.target_idx phải là 0 hoặc 1")
        st = m.get("state", "patrol")
        if st not in MONSTER_STATES:
            raise BadInput(f"monsters.{mid}.state không hợp lệ: {st!r}")
        stl = m.get("state_ticks_left", 0)
        _nonneg_int(f"monsters.{mid}.state_ticks_left", stl)
        rdir = m.get("recoil_dir", None)
        if st == "recoil":
            if stl <= 0:
                raise BadInput(f"monsters.{mid}: recoil cần state_ticks_left > 0")
            if not (isinstance(rdir, list) and len(rdir) == 2 and all(_num(c) for c in rdir)):
                raise BadInput(f"monsters.{mid}: recoil_dir phải là vector [x, d]")
            if abs(math.hypot(rdir[0], rdir[1]) - 1.0) > 1e-3:
                raise BadInput(f"monsters.{mid}: recoil_dir phải là vector đơn vị")
        else:
            if stl != 0:
                raise BadInput(f"monsters.{mid}: trạng thái {st} phải có state_ticks_left == 0")
            if rdir is not None:
                raise BadInput(f"monsters.{mid}: trạng thái {st} phải có recoil_dir == null")


def _validate_quan(b, tuning):
    q = tuning["quan"]
    menu = tuning["menu"]
    qb = q["bounds"]
    for arr in ("stoves", "tables", "customers"):
        if arr in b:
            _check_ids(arr, b[arr])
    if "random_customers" in b and not isinstance(b["random_customers"], bool):
        raise BadInput("random_customers phải là boolean")
    if "reputation" in b:
        rep = b["reputation"]
        if not _num(rep) or not (q["reputation_min"] <= rep <= q["reputation_max"]):
            raise BadInput("reputation nằm ngoài khoảng hợp lệ")
    if "stock" in b:
        validate_items(b["stock"])
    p = b.get("player", {})
    if not isinstance(p, dict) or set(p) - QUAN_PLAYER_KEYS:
        raise BadInput("quan.player chỉ có pos và vel")
    if "pos" in p:
        _pos("player.pos", p["pos"], qb, axes=("x", "z"))
    if "vel" in p and not (isinstance(p["vel"], list) and len(p["vel"]) == 2 and all(_num(c) for c in p["vel"])):
        raise BadInput("player.vel phải là [x, z]")

    known_tables = {tb["id"] for tb in q["tables"]}
    for tb in b.get("tables", []):
        extra_tb = set(tb) - QUAN_TABLE_KEYS
        if extra_tb:
            raise BadInput(f"tables.{tb['id']}: trường lạ {sorted(extra_tb)}")
        if tb["id"] not in known_tables:
            raise BadInput(f"id bàn không tồn tại: {tb['id']}")
        if "pos" in tb:
            _pos(f"tables.{tb['id']}.pos", tb["pos"], qb, axes=("x", "z"))

    known_stoves = {s["id"] for s in q["stoves"]}
    for s in b.get("stoves", []):
        extra_s = set(s) - QUAN_STOVE_KEYS
        if extra_s:
            raise BadInput(f"stoves.{s['id']}: trường lạ {sorted(extra_s)}")
        if s["id"] not in known_stoves:
            raise BadInput(f"id bếp không tồn tại: {s['id']}")
        if "pos" in s:
            _pos(f"stoves.{s['id']}.pos", s["pos"], qb, axes=("x", "z"))
        st = s.get("state", "idle")
        if st not in STOVE_STATES:
            raise BadInput(f"stoves.{s['id']}: state không hợp lệ {st!r}")
        ctl = s.get("cook_ticks_left", 0)
        rt = s.get("ready_ticks", 0)
        _nonneg_int(f"stoves.{s['id']}.cook_ticks_left", ctl)
        _nonneg_int(f"stoves.{s['id']}.ready_ticks", rt)
        dish = s.get("dish")
        if st == "idle":
            if dish is not None or ctl != 0 or rt != 0:
                raise BadInput(f"stoves.{s['id']}: bếp idle không được có món hay timer dương")
        elif st == "cooking":
            _validate_dish_payload(f"stoves.{s['id']}.dish", dish, menu)
            if ctl <= 0 or rt != 0:
                raise BadInput(f"stoves.{s['id']}: bếp cooking cần cook_ticks_left > 0 và ready_ticks == 0")
        elif st == "ready":
            _validate_dish_payload(f"stoves.{s['id']}.dish", dish, menu)
            if ctl != 0:
                raise BadInput(f"stoves.{s['id']}: bếp ready cần cook_ticks_left == 0")

    if "hand" in b and b["hand"] is not None:
        _validate_dish_payload("quan.hand", b["hand"], menu)

    patience_max = int(round(q["patience_s"] * 60))
    eat_max = int(round(q["eat_s"] * 60))
    table_ids = []
    for c in b.get("customers", []):
        cid = c["id"]
        extra_c = set(c) - QUAN_CUSTOMER_KEYS
        if extra_c:
            raise BadInput(f"customers.{cid}: trường lạ {sorted(extra_c)}")
        tid = c.get("table_id")
        if not isinstance(tid, str) or tid not in known_tables:
            raise BadInput(f"customers.{cid}: table_id phải là bàn có thật")
        table_ids.append(tid)
        did = c.get("dish_id")
        if not isinstance(did, str) or did not in menu:
            raise BadInput(f"customers.{cid}: dish_id không thuộc menu: {did!r}")
        ot = c.get("order_tick", 0)
        _nonneg_int(f"customers.{cid}.order_tick", ot)
        cst = c.get("state", "waiting")
        if cst not in CUSTOMER_STATES:
            raise BadInput(f"customers.{cid}: state phải thuộc {CUSTOMER_STATES}")
        pat = c.get("patience_ticks_left", patience_max if cst == "waiting" else 0)
        _nonneg_int(f"customers.{cid}.patience_ticks_left", pat)
        if pat > patience_max:
            raise BadInput(f"customers.{cid}.patience_ticks_left vượt tối đa ({patience_max})")
        eat = c.get("eat_ticks_left", 0)
        _nonneg_int(f"customers.{cid}.eat_ticks_left", eat)
        if cst == "eating":
            if not (1 <= eat <= eat_max):
                raise BadInput(f"customers.{cid}: khách eating phải có eat_ticks_left trong [1, {eat_max}]")
        else:
            if eat != 0:
                raise BadInput(f"customers.{cid}: khách waiting phải có eat_ticks_left == 0")

        if "order_status" in c:
            ost = c["order_status"]
            if ost not in ORDER_STATUSES:
                raise BadInput(f"customers.{cid}: order_status phải thuộc {ORDER_STATUSES}")
        else:
            ost = "served" if cst == "eating" else "reserved"

        if cst == "eating":
            if ost != "served":
                raise BadInput(f"customers.{cid}: khách eating phải có order_status == 'served'")
            if "base_price" not in c or "tip" not in c:
                raise BadInput(f"customers.{cid}: khách eating phải khai base_price và tip")
            _pos_int(f"customers.{cid}.base_price", c["base_price"])
            _nonneg_int(f"customers.{cid}.tip", c["tip"])
        else:
            if ost == "served":
                raise BadInput(f"customers.{cid}: khách waiting không được có order_status == 'served'")
            if c.get("base_price") is not None or c.get("tip") is not None:
                raise BadInput(f"customers.{cid}: khách waiting không được khai base_price/tip")

        if "reserved" in c:
            res = validate_items(c["reserved"])
            if ost == "reserved":
                expected = {k: int(v) for k, v in menu[did]["recipe"].items() if v > 0}
                if res != expected:
                    raise BadInput(f"customers.{cid}: giữ chỗ {res} khác công thức {expected}")
            elif res:
                raise BadInput(f"customers.{cid}: đơn {ost} phải có reserved rỗng")

    if len(table_ids) != len(set(table_ids)):
        raise BadInput("hai khách cùng bàn")
