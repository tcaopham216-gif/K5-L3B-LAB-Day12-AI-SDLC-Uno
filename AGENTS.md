# AGENTS.md — hướng dẫn chung cho mọi agent AI của nhóm

> Cập nhật file này qua các phase (lịch sử git phải cho thấy điều đó). Ngắn gọn, có lệnh chạy thật.

## Lệnh
- Test đầy đủ (Linux / macOS): `PYTHONPATH=tests:. python3 -m unittest discover -s tests -v`
- Test đầy đủ (Windows PowerShell, cần `python3.exe` trong `PATH` vì `game.contract.json` dùng `python3`):
  `$env:PYTHONPATH = "tests;."; python -m unittest discover -s tests -v`
- Headless (`v1.2`):
  - `python3 -m chonoi.headless --mode gather|quan --seed 1 --ticks 600 --out out.jsonl`
  - `python3 -m chonoi.headless --mode day --days 1 --seed 1 --ticks 22200 --out day.jsonl`
- Chơi thử trên trình duyệt: `python3 -m chonoi.live --mode day` (hoặc `--mode gather|quan`; `WASD`/mũi tên, `E`, `Space`, `Esc`/`P` pause, `R` chơi lại)

## Cấu trúc & quy ước (`Contract v1.2`)
- Khung do giảng viên cấp: `chonoi/{headless,inputs,scenario,contract,rng,ids,jsonl,inventory,runner,live}.py` và `chonoi/web/index.html`.
- Luật chơi Phase 1–3: `chonoi/sim/gather.py` (cá bơi/sinh, Cá Sấu, hao tươi `0.5/s`), `chonoi/sim/quan.py` (2 bếp/4 bàn, 6 món, hao tươi `0.25/s`, `spoiled`, re-reserve theo ID, `base_price = floor(price * avg_fresh / 100)`), `chonoi/sim/day.py` (D1–D5, Shop `oxygen`/`hp`, chuỗi ID `I*`).
- **Độ tươi dùng `fractions.Fraction` nội bộ** (`chonoi/inventory.py` khôi phục lưới `1/240` khi đọc JSON) và dùng `decimal.Decimal` với `ROUND_FLOOR` cho tính boa; không dùng float thô so ngưỡng `< 30`.
- Kho & `reserved` bắt buộc theo schema cá thể `v1.2` (`[{"id", "kind", "fresh"}]` / `["I1", ...]`); file kho đếm cũ trả mã thoát `2`.
- Mọi ngẫu nhiên dùng `Streams`; sắp thực thể bằng `ids.sort_by_id` và giải hòa bằng `ids.id_key`; cấp id bằng `IdAllocator`.

## Nên tránh
- Không sửa số chuẩn `tuning` hay `headless_cmd` trong `game.contract.json`. Nếu Contract mới thay thế luật cũ, ghi vào [`CHANGELOG.md`](CHANGELOG.md) và [`docs/verification/phase-3.md`](docs/verification/phase-3.md).
- Nhóm `Uno` có 1 thành viên (`team_size: 1`): chỉ hoàn thiện phần Lõi, đặt `"extensions": []` và không bật cơ chế mở rộng ngoài phạm vi.
- Không commit file nháp/tạm; dùng thư mục `docs/proof/phase-n/` cho bằng chứng chạy thật.

## Skills / hooks của nhóm
- [`verify-contract`](.agents/skills/verify-contract/SKILL.md): chạy sau khi sửa sim / scenario / contract để kiểm tra toàn bộ `unittest`, tích hợp kho 2 tiến trình, `--mode day`, tính tất định và cập nhật `docs/proof/`.
- [`slice-review`](.agents/skills/slice-review/SKILL.md): rà soát trước commit theo checklist không hard-code, thứ tự tick v1.2, `Fraction`/`Decimal`, `Streams`/`id_key` và lỗi mã `2`.
