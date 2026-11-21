"""Đọc game.contract.json và kiểm dải hợp lệ của tuning (Contract v1.1)."""

import json
import math
import os

from .errors import BadInput
from .inventory import KINDS_P2

DEFAULT_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "game.contract.json")

NODE_KINDS = ("bong_dien_dien", "bong_sung", "keo_neo")
FISH_SPECIES = ("ca_linh", "ca_loc", "ca_keo")


def _num(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)


def _between(name, v, lo, hi):
    if not _num(v) or not (lo <= v <= hi):
        raise BadInput(f"tuning.{name} phải trong [{lo}, {hi}], đang là {v!r}")


def _gt(name, v, lo):
    if not _num(v) or not (v > lo):
        raise BadInput(f"tuning.{name} phải > {lo}, đang là {v!r}")


def load_contract(path=DEFAULT_PATH) -> dict:
    try:
        with open(path, encoding="utf-8") as f:
            c = json.load(f)
    except (OSError, ValueError) as e:
        raise BadInput(f"không đọc được {path}: {e}")
    if "extensions" in c and (not isinstance(c["extensions"], list) or not all(isinstance(x, str) for x in c["extensions"])):
        raise BadInput("extensions phải là mảng chuỗi")
    validate_tuning(c.get("tuning"))
    return c


def _int_between(name, v, lo, hi):
    if isinstance(v, bool) or not isinstance(v, int) or not (lo <= v <= hi):
        raise BadInput(f"tuning.{name} phải là số nguyên trong [{lo}, {hi}], đang là {v!r}")


def _pos_in(name, pos, bounds, keys):
    if not isinstance(pos, list) or len(pos) != 2 or not all(_num(c) for c in pos):
        raise BadInput(f"tuning.{name} phải là [số, số]")
    for c, k in zip(pos, keys):
        lo, hi = bounds[k]
        if not (lo <= c <= hi):
            raise BadInput(f"tuning.{name} nằm ngoài vùng {k} ∈ [{lo}, {hi}]")


def _bounds(name, b, keys):
    if not isinstance(b, dict) or set(b) != set(keys):
        raise BadInput(f"tuning.{name}.bounds phải có đúng khóa {list(keys)}")
    for k in keys:
        v = b[k]
        if not (isinstance(v, list) and len(v) == 2 and all(_num(c) for c in v) and v[0] == 0 and v[1] > 0):
            raise BadInput(f"tuning.{name}.bounds.{k} phải là [0, số dương]")


def _range_pair(name, pair, lo_bound, hi_bound, strict_gt_lo=False):
    if not (isinstance(pair, list) and len(pair) == 2 and all(_num(c) for c in pair)):
        raise BadInput(f"tuning.{name} phải là [min, max]")
    a, b = pair
    if (a <= lo_bound if strict_gt_lo else a < lo_bound) or a >= b or b > hi_bound:
        raise BadInput(f"tuning.{name} không hợp lệ: {pair!r} với miền [{lo_bound}, {hi_bound}]")


def _validate_monsters(m, g, b):
    if not isinstance(m, dict):
        raise BadInput("tuning.gather.monsters phải là object")
    _int_between("gather.monsters.invuln_ticks", m.get("invuln_ticks"), 0, 10_000)
    _between("gather.monsters.loss_ratio", m.get("loss_ratio"), 0, 1)
    species = m.get("species")
    if not isinstance(species, dict) or "ca_sau" not in species:
        raise BadInput("tuning.gather.monsters.species phải có ca_sau")
    for sp_id, sp in species.items():
        if not isinstance(sp, dict):
            raise BadInput(f"tuning.gather.monsters.species.{sp_id} phải là object")
        _gt(f"gather.monsters.species.{sp_id}.patrol_speed", sp.get("patrol_speed"), 0)
        _gt(f"gather.monsters.species.{sp_id}.chase_speed", sp.get("chase_speed"), 0)
        _gt(f"gather.monsters.species.{sp_id}.detect_radius", sp.get("detect_radius"), 0)
        _between(f"gather.monsters.species.{sp_id}.exit_radius", sp.get("exit_radius"), sp["detect_radius"], 1_000)
        _range_pair(f"gather.monsters.species.{sp_id}.depths", sp.get("depths"), g["surface_depth"], b["d"][1], strict_gt_lo=True)
        _gt(f"gather.monsters.species.{sp_id}.hit_radius", sp.get("hit_radius"), 0)
        _int_between(f"gather.monsters.species.{sp_id}.recoil_ticks", sp.get("recoil_ticks"), 1, 10_000)
        _between(f"gather.monsters.species.{sp_id}.recoil_dist", sp.get("recoil_dist"), 0, 100)
    spawns = m.get("spawns")
    if not isinstance(spawns, list):
        raise BadInput("tuning.gather.monsters.spawns phải là mảng")
    seen = set()
    for s in spawns:
        if not isinstance(s, dict) or not isinstance(s.get("id"), str) or not s["id"] or s["id"] in seen:
            raise BadInput("tuning.gather.monsters.spawns: mỗi phần tử cần id duy nhất")
        seen.add(s["id"])
        kind = s.get("kind")
        if kind not in species:
            raise BadInput(f"tuning.gather.monsters.spawns.{s['id']}: kind lạ {kind!r}")
        sp_bounds = {"x": b["x"], "d": species[kind]["depths"]}
        _pos_in(f"gather.monsters.spawns.{s['id']}.pos", s.get("pos"), sp_bounds, ("x", "d"))
        wps = s.get("waypoints")
        if not isinstance(wps, list) or len(wps) != 2:
            raise BadInput(f"tuning.gather.monsters.spawns.{s['id']}.waypoints phải có 2 điểm")
        for i, wp in enumerate(wps):
            _pos_in(f"gather.monsters.spawns.{s['id']}.waypoints[{i}]", wp, sp_bounds, ("x", "d"))
        _int_between(f"gather.monsters.spawns.{s['id']}.from_day", s.get("from_day"), 1, 5)


def _validate_gather(g):
    _between("gather.duration_s", g.get("duration_s"), 60, 600)
    _bounds("gather", g.get("bounds"), ("x", "d"))
    b = g["bounds"]
    _between("gather.dock_radius", g.get("dock_radius"), 0.5, 5)
    _between("gather.interact_radius", g.get("interact_radius"), 0.5, 5)
    _between("gather.catch_radius", g.get("catch_radius"), 0.5, 5)
    _between("gather.swim_speed", g.get("swim_speed"), 1, 10)
    _between("gather.catch_cooldown_s", g.get("catch_cooldown_s"), 0, 10)
    _between("gather.oxygen_max_s", g.get("oxygen_max_s"), 10, 120)
    _int_between("gather.ramp_max_ticks", g.get("ramp_max_ticks"), 0, 6)
    _int_between("gather.hold_capacity", g.get("hold_capacity"), 4, 30)
    _int_between("gather.hp_max", g.get("hp_max"), 1, 99)
    _int_between("gather.oxygen_refill_per_tick", g.get("oxygen_refill_per_tick"), 1, 10_000)
    _int_between("gather.choke_interval_ticks", g.get("choke_interval_ticks"), 1, 10_000)
    _int_between("gather.node_yield", g.get("node_yield"), 1, 12)
    _between("gather.regrow_s", g.get("regrow_s"), 0.1, 600)
    _between("gather.surface_depth", g.get("surface_depth"), 0, 5)
    _pos_in("gather.dock_pos", g.get("dock_pos"), b, ("x", "d"))
    _pos_in("gather.start_pos", g.get("start_pos"), b, ("x", "d"))
    if not _num(g.get("start_heading_deg")):
        raise BadInput("tuning.gather.start_heading_deg phải là số")

    fy = g.get("fish_yield")
    if not isinstance(fy, dict) or not set(FISH_SPECIES) <= set(fy):
        raise BadInput(f"tuning.gather.fish_yield phải có đủ {FISH_SPECIES}")
    for k, v in fy.items():
        _int_between(f"gather.fish_yield.{k}", v, 1, g["hold_capacity"])

    _gt("gather.fish_speed", g.get("fish_speed"), 0)
    _int_between("gather.fish_turn_ticks", g.get("fish_turn_ticks"), 1, 100_000)
    _int_between("gather.fish_max", g.get("fish_max"), 1, 200)
    _int_between("gather.fish_initial", g.get("fish_initial"), 0, g["fish_max"])
    _int_between("gather.fish_spawn_ticks", g.get("fish_spawn_ticks"), 1, 100_000)
    _between("gather.fish_spawn_clearance", g.get("fish_spawn_clearance"), 0, 100)
    _range_pair("gather.fish_x", g.get("fish_x"), b["x"][0], b["x"][1])
    fx_lo, fx_hi = g["fish_x"]

    fdepths = g.get("fish_depths")
    fsx = g.get("fish_spawn_x")
    fsd = g.get("fish_spawn_depths")
    fw = g.get("fish_weights")
    if not isinstance(fsx, list) or not fsx or not all(_num(x) and fx_lo <= x <= fx_hi for x in fsx):
        raise BadInput("tuning.gather.fish_spawn_x phải là mảng tọa độ x nằm trong fish_x")
    for name, mp in (("fish_depths", fdepths), ("fish_spawn_depths", fsd), ("fish_weights", fw)):
        if not isinstance(mp, dict) or set(mp) != set(FISH_SPECIES):
            raise BadInput(f"tuning.gather.{name} phải có đúng 3 loài {FISH_SPECIES}")
    for sp in FISH_SPECIES:
        _range_pair(f"gather.fish_depths.{sp}", fdepths[sp], g["surface_depth"], b["d"][1], strict_gt_lo=True)
        lo_d, hi_d = fdepths[sp]
        if not isinstance(fsd[sp], list) or not fsd[sp] or not all(_num(d) and lo_d <= d <= hi_d for d in fsd[sp]):
            raise BadInput(f"tuning.gather.fish_spawn_depths.{sp} phải là mảng độ sâu nằm trong fish_depths.{sp}")
        _gt(f"gather.fish_weights.{sp}", fw[sp], 0)

    nodes = g.get("nodes")
    if not isinstance(nodes, list) or not nodes:
        raise BadInput("tuning.gather.nodes phải là mảng không rỗng")
    seen, kinds = set(), set()
    for n in nodes:
        if not isinstance(n, dict) or not isinstance(n.get("id"), str) or n["id"] in seen:
            raise BadInput("tuning.gather.nodes: mỗi nút cần id duy nhất")
        seen.add(n["id"])
        if n.get("kind") not in NODE_KINDS:
            raise BadInput(f"tuning.gather.nodes.{n['id']}: kind phải thuộc {NODE_KINDS}")
        kinds.add(n["kind"])
        _pos_in(f"gather.nodes.{n['id']}.pos", n.get("pos"), b, ("x", "d"))
        if n["pos"][1] != 0:
            raise BadInput(f"tuning.gather.nodes.{n['id']}: nút hái nằm ở mặt nước (d = 0)")
    if kinds != set(NODE_KINDS):
        raise BadInput(f"tuning.gather.nodes phải có đủ các loại {NODE_KINDS}")

    _validate_monsters(g.get("monsters"), g, b)


def _validate_quan_and_menu(q, menu):
    _between("quan.duration_s", q.get("duration_s"), 60, 600)
    _bounds("quan", q.get("bounds"), ("x", "z"))
    qb = q["bounds"]
    _pos_in("quan.start_pos", q.get("start_pos"), qb, ("x", "z"))
    _between("quan.patience_s", q.get("patience_s"), 20, 180)
    _between("quan.walk_speed", q.get("walk_speed"), 1, 10)
    _between("quan.interact_radius", q.get("interact_radius"), 0.5, 5)
    _int_between("quan.ramp_max_ticks", q.get("ramp_max_ticks", 6), 0, 6)
    _between("quan.eat_s", q.get("eat_s"), 0.1, 600)
    _between("quan.customer_interval_s", q.get("customer_interval_s"), 0.1, 600)
    _int_between("quan.first_customer_tick", q.get("first_customer_tick"), 1, int(q["duration_s"] * 60) - 1)
    if not (_num(q.get("tip_rate")) and q["tip_rate"] > 0 and _num(q.get("left_reputation_delta")) and q["left_reputation_delta"] < 0):
        raise BadInput("tip_rate phải > 0 và left_reputation_delta phải < 0")
    ratio = q.get("tip_min_patience_ratio")
    if not (_num(ratio) and 0 < ratio <= 1):
        raise BadInput("quan.tip_min_patience_ratio phải thuộc (0, 1]")
    if not (_num(q.get("tip_reputation")) and q["tip_reputation"] > 0):
        raise BadInput("quan.tip_reputation phải > 0")
    if q.get("burn_s") is not None:
        raise BadInput("burn_s phải là null ở bản lõi")
    for coll_name in ("stoves", "tables"):
        arr = q.get(coll_name)
        if not isinstance(arr, list) or not arr:
            raise BadInput(f"tuning.quan.{coll_name} phải là mảng không rỗng")
        seen = set()
        for item in arr:
            if not isinstance(item, dict) or not isinstance(item.get("id"), str) or not item["id"] or item["id"] in seen:
                raise BadInput(f"tuning.quan.{coll_name}: mỗi phần tử cần id duy nhất")
            seen.add(item["id"])
            _pos_in(f"quan.{coll_name}.{item['id']}.pos", item.get("pos"), qb, ("x", "z"))

    if not menu:
        raise BadInput("tuning.menu không được rỗng")
    for dish_id, d in menu.items():
        if not isinstance(d, dict):
            raise BadInput(f"menu.{dish_id} phải là object")
        price, cook, rec = d.get("price"), d.get("cook_s"), d.get("recipe")
        if isinstance(price, bool) or not isinstance(price, int) or price <= 0 or not _num(cook) or cook <= 0:
            raise BadInput(f"menu.{dish_id}: price (nguyên) và cook_s phải > 0")
        if not isinstance(rec, dict) or not rec:
            raise BadInput(f"menu.{dish_id}.recipe phải là map không rỗng")
        for ing, qty in rec.items():
            if ing not in KINDS_P2 or isinstance(qty, bool) or not isinstance(qty, int) or qty <= 0:
                raise BadInput(f"menu.{dish_id}.recipe.{ing} không hợp lệ: {qty!r}")


def _validate_day_plan_and_shop(dp, shop, g, menu):
    if not isinstance(dp, list) or len(dp) != 5:
        raise BadInput("tuning.day_plan phải có đúng 5 Ngày")
    seen_days = set()
    for entry in dp:
        if not isinstance(entry, dict):
            raise BadInput("tuning.day_plan phần tử phải là object")
        day_no = entry.get("day")
        _int_between("day_plan.day", day_no, 1, 5)
        if day_no in seen_days:
            raise BadInput(f"tuning.day_plan trùng ngày {day_no}")
        seen_days.add(day_no)
        dishes = entry.get("dishes")
        ings = entry.get("ingredients")
        if not isinstance(dishes, dict) or not dishes or not isinstance(ings, dict):
            raise BadInput(f"tuning.day_plan ngày {day_no}: thiếu dishes hoặc ingredients")
        calc = {}
        for did, cnt in dishes.items():
            if did not in menu or isinstance(cnt, bool) or not isinstance(cnt, int) or cnt <= 0:
                raise BadInput(f"tuning.day_plan ngày {day_no}: món {did!r}={cnt!r} không hợp lệ")
            for k, qty in menu[did]["recipe"].items():
                calc[k] = calc.get(k, 0) + qty * cnt
        for k, qty in ings.items():
            if k not in KINDS_P2 or isinstance(qty, bool) or not isinstance(qty, int) or qty <= 0:
                raise BadInput(f"tuning.day_plan ngày {day_no}: ingredients.{k}={qty!r} không hợp lệ")
        norm_ings = {k: v for k, v in ings.items() if v > 0}
        if calc != norm_ings:
            raise BadInput(f"tuning.day_plan ngày {day_no}: ingredients {norm_ings} khác tổng công thức {calc}")

    if not isinstance(shop, dict):
        raise BadInput("tuning.shop phải là object")
    _int_between("shop.max_ticks", shop.get("max_ticks"), 1, 100_000)
    up = shop.get("upgrades")
    if not isinstance(up, dict) or not {"oxygen", "hp"} <= set(up):
        raise BadInput("tuning.shop.upgrades phải có oxygen và hp")
    for uid, key, base in (("oxygen", "oxygen_max_s", g["oxygen_max_s"]), ("hp", "hp_max", g["hp_max"])):
        tiers = up.get(uid)
        if not isinstance(tiers, list) or not tiers:
            raise BadInput(f"tuning.shop.upgrades.{uid} phải là mảng không rỗng")
        prev = base
        for idx, tier in enumerate(tiers, 1):
            if not isinstance(tier, dict) or tier.get("level") != idx:
                raise BadInput(f"tuning.shop.upgrades.{uid}[{idx-1}] phải có level == {idx}")
            price = tier.get("price")
            if isinstance(price, bool) or not isinstance(price, int) or price <= 0:
                raise BadInput(f"tuning.shop.upgrades.{uid} cấp {idx}: price phải là số nguyên > 0")
            val = tier.get(key)
            if uid == "hp":
                if isinstance(val, bool) or not isinstance(val, int) or val <= prev:
                    raise BadInput(f"tuning.shop.upgrades.hp cấp {idx}: {key} phải tăng dần")
            else:
                if not _num(val) or val <= prev:
                    raise BadInput(f"tuning.shop.upgrades.oxygen cấp {idx}: {key} phải tăng dần")
            prev = val


def validate_tuning(t):
    if not isinstance(t, dict):
        raise BadInput("thiếu khối tuning")
    g, q, menu = t.get("gather"), t.get("quan"), t.get("menu")
    dp, shop = t.get("day_plan"), t.get("shop")
    if not isinstance(g, dict) or not isinstance(q, dict) or not isinstance(menu, dict):
        raise BadInput("tuning phải có gather, quan, menu")
    _validate_gather(g)
    _validate_quan_and_menu(q, menu)
    _validate_day_plan_and_shop(dp, shop, g, menu)
