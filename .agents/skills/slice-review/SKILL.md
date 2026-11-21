---
name: slice-review
description: Tự rà soát thay đổi theo từng lát công việc (Lát 1-4) đối chiếu Test Contract v1.0 và quy tắc AGENTS.md trước khi commit.
---

# Skill: slice-review

Dùng skill này trước mỗi commit trên `main` để kiểm tra lỗi biên, hard-code và rò rỉ tài liệu.

## Checklist rà soát

1. **Không hard-code số liệu:** mọi bán kính, thời gian (`_s * 60`), giá món, tỷ lệ boa, mức phạt uy tín đều đọc từ `tuning` (`game.contract.json`).
2. **Thứ tự trong một tick (Contract F):**
   - `gather`: giảm timer & `node_regrown` → `_move` & `dive`/`surface` → oxy/ngạt/`faint` → `interact` (bến trước hái) → `catch` → hết giờ `time`.
   - `quan`: tăng `phase_tick` & giảm timer (chỉ tăng `ready_ticks` cho bếp đã `ready` từ đầu bước) → bếp chín `dish_ready` → `_move` & tối đa một `interact` không fallback → thanh toán/`customer_left`/`quan_end` → sinh khách mới theo `phase_tick`.
3. **Tính tất định & sắp ID:**
   - Mọi ngẫu nhiên dùng `Streams.get(...)` (`chonoi/rng.py`), không dùng `random` toàn cục hay `time`.
   - Thực thể xuất theo `ids.sort_by_id`; hòa khoảng cách giải theo `id_key`.
4. **Tính nhất quán dữ liệu đầu vào:** mọi mâu thuẫn schema/ràng buộc trong `scenario` hoặc `--inventory` phải trả mã thoát `2` trước khi tạo file đầu ra.
5. **Kiểm tra git diff:** chỉ commit các file thuộc lát đang làm; không commit key, `.env` hay file tạm.
