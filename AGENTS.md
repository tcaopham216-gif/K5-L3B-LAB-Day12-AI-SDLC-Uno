# AGENTS.md — hướng dẫn chung cho mọi agent AI của nhóm

> Cập nhật file này qua các phase (lịch sử git phải cho thấy điều đó). Ngắn gọn, có lệnh chạy thật.

## Lệnh
- Test đầy đủ (Linux / macOS): `PYTHONPATH=tests:. python3 -m unittest discover -s tests -v`
- Test đầy đủ (Windows PowerShell, cần `python3.exe` trong `PATH` vì `game.contract.json` dùng `python3`):
  `$env:PYTHONPATH = "tests;."; python -m unittest discover -s tests -v`
- Headless: `python3 -m chonoi.headless --mode gather|quan --seed 1 --ticks 600 --out out.jsonl`
- Chơi thử trên trình duyệt: `python3 -m chonoi.live --mode gather|quan` (mở địa chỉ in ra; WASD / mũi tên, E, Space, R)

## Cấu trúc & quy ước
- Khung do giảng viên cấp: `chonoi/{headless,inputs,scenario,contract,rng,ids,jsonl,inventory,runner,live}.py` và `chonoi/web/`. Hạn chế sửa khung; mọi thay đổi ở `scenario.py` và `chonoi/web/index.html` đã ghi vào [`docs/clarify.md`](docs/clarify.md).
- Luật chơi Phase 1: `chonoi/sim/gather.py` (Lát 1–2) và `chonoi/sim/quan.py` (Lát 3–4).
- **Số liệu chỉ đọc từ `game.contract.json` / dữ liệu** (`tuning`), không hard-code trong luật. Dùng `decimal.Decimal` với `ROUND_FLOOR` cho tính boa (`tip_min_patience_ratio`, `tip_rate`) để tránh sai số dấu phẩy động.
- Mọi số ngẫu nhiên đi qua `Streams` (`chonoi/rng.py`, ví dụ `Streams.get("quan_customer")`); không dùng `random` toàn cục, không dùng đồng hồ hệ thống.
- Sắp danh sách thực thể bằng `ids.sort_by_id` và giải hòa khoảng cách bằng `ids.id_key`; cấp id bằng `IdAllocator`.
- Mọi kiểm tra mâu thuẫn scenario/kho phải ném `BadInput` (thoát mã `2`) trong `scenario.py` hoặc `__init__` của sim trước khi ghi JSONL.

## Nên tránh
- Không sửa `game.contract.json` (khóa `tuning`, `headless_cmd`, `build_cmd`), `docs/contracts/` hoặc các bài test gốc (`tests/test_smoke_p1.py`, `tests/test_python_starter_units.py`, `tests/test_live.py`, `tests/test_team_check.py`).
- Không làm hỏng nhánh chính: trước khi commit/push, luôn chạy đủ `unittest`.
- Không bịa yêu cầu: chỗ mơ hồ ghi rõ vào `docs/clarify.md`.
- Không sửa test cho xanh khi luật sai; phải sửa luật đúng theo Test Contract v1.0.

## Quy tắc làm việc với agent
- Mỗi agent một lát rõ ràng. Luôn đọc `PRD-0`, Test Contract v1.0 và [`docs/contracts/README.md`](docs/contracts/README.md) trước khi sửa sim.
- Sau khi sửa code phải chạy toàn bộ `unittest`, lưu bằng chứng chạy thật vào `docs/proof/phase-1/` và rà soát diff trước khi commit.
- Sáng tạo thêm nếu có phải tắt ở headless hoặc không làm thay đổi tick, sự kiện, tiền, uy tín và snapshot chuẩn.

## Skills / hooks của nhóm
- [`verify-contract`](.agents/skills/verify-contract/SKILL.md): chạy sau khi sửa sim / scenario / contract để kiểm tra toàn bộ `unittest`, tích hợp 2 tiến trình kho (`gather` → `quan`), tính tất định theo byte và cập nhật `docs/proof/phase-1/`.
- [`slice-review`](.agents/skills/slice-review/SKILL.md): rà soát trước commit theo checklist không hard-code, đúng thứ tự tick trong mục F, `Streams`/`id_key`, và lỗi mã `2`.
