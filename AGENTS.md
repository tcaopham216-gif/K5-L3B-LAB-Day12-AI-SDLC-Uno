# AGENTS.md — hướng dẫn chung cho mọi agent AI của nhóm

> Cập nhật file này qua các phase (lịch sử git phải cho thấy điều đó). Ngắn gọn, có lệnh chạy thật.

## Lệnh
- Test đầy đủ (Linux / macOS): `PYTHONPATH=tests:. python3 -m unittest discover -s tests -v`
- Test đầy đủ (Windows PowerShell, cần `python3.exe` trong `PATH` vì `game.contract.json` dùng `python3`):
  `$env:PYTHONPATH = "tests;."; python -m unittest discover -s tests -v`
- Headless (`v1.1`):
  - `python3 -m chonoi.headless --mode gather|quan --seed 1 --ticks 600 --out out.jsonl`
  - `python3 -m chonoi.headless --mode day --days 1 --seed 1 --ticks 22200 --out day.jsonl`
- Chơi thử trên trình duyệt: `python3 -m chonoi.live --mode day` (hoặc `--mode gather|quan`; `WASD`/mũi tên, `E`, `Space`, `Esc`/`P` pause, `R` chơi lại)

## Cấu trúc & quy ước
- Khung do giảng viên cấp (`v1.1`): `chonoi/{headless,inputs,scenario,contract,rng,ids,jsonl,inventory,runner,live}.py` và `chonoi/web/index.html`.
- Luật chơi Phase 1–2: `chonoi/sim/gather.py` (cá bơi/sinh & Cá Sấu), `chonoi/sim/quan.py` (2 bếp/4 bàn, 6 món, lọc `day_plan`), `chonoi/sim/day.py` (vòng ngày D1–D5 & Shop `oxygen`/`hp`).
- **Số liệu chỉ đọc từ `game.contract.json`** (`tuning`, `contract_version: "1.1"`), không hard-code trong luật. Dùng `decimal.Decimal` với `ROUND_FLOOR` cho tính boa.
- Mọi ngẫu nhiên dùng `Streams` (`fish_spawn`, `fish_turn`, `quan_customer`); không dùng `random` toàn cục hay đồng hồ hệ thống.
- Sắp thực thể bằng `ids.sort_by_id`, giải hòa khoảng cách bằng `ids.id_key`; cấp id bằng `IdAllocator`.
- Kiểm tra mọi mâu thuẫn CLI, scenario, kho, kế hoạch ngày -> ném `BadInput` (thoát mã `2`) và xóa file out nếu có lỗi khi mở quán.

## Nên tránh
- Không sửa số chuẩn `tuning` hay `headless_cmd` trong `game.contract.json`. Nếu Contract mới đổi quy tắc test cũ, phải ghi rõ lý do trong `docs/verification/phase-n.md`.
- Nhóm `Uno` có 1 thành viên (`team_size: 1`): chỉ hoàn thiện phần Lõi, đặt `"extensions": []` và không bật cơ chế mở rộng ngoài phạm vi.
- Không commit file nháp/tạm; dùng thư mục `docs/proof/phase-n/` cho bằng chứng chạy thật.

## Skills / hooks của nhóm
- [`verify-contract`](.agents/skills/verify-contract/SKILL.md): chạy sau khi sửa sim / scenario / contract để kiểm tra toàn bộ `unittest`, tích hợp kho 2 tiến trình, `--mode day`, tính tất định và cập nhật `docs/proof/`.
- [`slice-review`](.agents/skills/slice-review/SKILL.md): rà soát trước commit theo checklist không hard-code, thứ tự tick v1.1 (mục 4.5), `Streams`/`id_key` và lỗi mã `2`.
