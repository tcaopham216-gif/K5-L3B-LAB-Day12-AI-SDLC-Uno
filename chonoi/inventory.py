"""File kho cá thể v1.2 (Contract v1.2): {"items": [{"id": str, "kind": str, "fresh": float}]}.

Đọc: chỉ chấp nhận mảng cá thể v1.2; từ chối kho đếm cũ / sai schema / id trùng / fresh ngoài [0, 100] (mã 2).
Ghi: giữ mọi cá thể (kể cả hàng ươn < 30), sắp theo id_key, ghi nguyên tử qua file tạm cùng thư mục.
Nội bộ dùng Fraction (khôi phục lưới 1/240 trong sai số <= 1e-12) để giữ chính xác ngưỡng 30 khi qua file.
"""

from fractions import Fraction
import json
import math
import os
import tempfile

from .errors import BadInput
from .ids import sort_by_id

KINDS_P1 = ("ca_loc", "ca_linh", "bong_dien_dien", "bong_sung")
KINDS_P2 = ("ca_loc", "ca_linh", "ca_keo", "bong_dien_dien", "bong_sung", "keo_neo")
ITEM_KEYS = {"id", "kind", "fresh"}


def parse_fresh(val) -> Fraction:
    if isinstance(val, Fraction):
        if not (0 <= val <= 100):
            raise BadInput(f"fresh phải trong [0, 100], đang là {val}")
        return val
    if isinstance(val, bool) or not isinstance(val, (int, float)):
        raise BadInput(f"fresh phải là số hữu hạn trong [0, 100], đang là {val!r}")
    if isinstance(val, int):
        if not (0 <= val <= 100):
            raise BadInput(f"fresh phải trong [0, 100], đang là {val!r}")
        return Fraction(val)
    if not math.isfinite(val) or not (0.0 <= val <= 100.0):
        raise BadInput(f"fresh phải trong [0, 100], đang là {val!r}")
    n240 = round(val * 240)
    if abs(val - n240 / 240.0) <= 1e-12:
        return Fraction(n240, 240)
    return Fraction(str(val))


def fresh_to_json(f: Fraction):
    if f.denominator == 1:
        return int(f)
    return float(f)


def serialize_item(it: dict) -> dict:
    f = it["fresh"] if isinstance(it["fresh"], Fraction) else parse_fresh(it["fresh"])
    return {"id": it["id"], "kind": it["kind"], "fresh": fresh_to_json(f)}


def validate_item_list(items, kinds=KINDS_P2) -> list:
    if not isinstance(items, list):
        raise BadInput("items phải là mảng cá thể v1.2 (không nhận kho đếm cũ)")
    out = []
    seen = set()
    for idx, it in enumerate(items):
        if not isinstance(it, dict) or set(it.keys()) != ITEM_KEYS:
            raise BadInput(f"items[{idx}] phải là object có đúng khóa {sorted(ITEM_KEYS)}")
        iid = it["id"]
        if not isinstance(iid, str) or not iid:
            raise BadInput(f"items[{idx}].id phải là chuỗi khác rỗng")
        if iid in seen:
            raise BadInput(f"items: trùng id cá thể {iid!r}")
        seen.add(iid)
        kind = it["kind"]
        if kind not in kinds:
            raise BadInput(f"items[{iid}]: nguyên liệu lạ {kind!r}")
        fresh = parse_fresh(it["fresh"])
        out.append({"id": iid, "kind": kind, "fresh": fresh})
    return out


def read_inventory(path: str, kinds=KINDS_P2) -> list:
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError) as e:
        raise BadInput(f"không đọc được file kho {path}: {e}")
    if not isinstance(data, dict) or set(data.keys()) != {"items"}:
        raise BadInput("file kho chỉ được có khóa gốc 'items'")
    return validate_item_list(data["items"], kinds)


def hold_to_items(hold: list) -> list:
    """Khoang (mảng cá thể theo thứ tự nhặt) -> mảng cá thể xuất JSON sắp theo id."""
    return [serialize_item(it) for it in sort_by_id(hold)]


def write_inventory(path: str, items: list):
    out = [serialize_item(it) for it in sort_by_id(validate_item_list(items))]
    d = os.path.dirname(os.path.abspath(path))
    fd, tmp = tempfile.mkstemp(prefix=".inv-", suffix=".tmp", dir=d)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as f:
            json.dump({"items": out}, f, ensure_ascii=False, separators=(",", ":"))
            f.write("\n")
        os.replace(tmp, path)
    except BaseException:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise
