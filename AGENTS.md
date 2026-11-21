# AGENTS.md — hướng dẫn chung cho mọi agent AI của nhóm

> Cập nhật file này qua các phase (lịch sử git phải cho thấy điều đó). Ngắn gọn, có lệnh chạy thật.

## Lệnh
- Test đầy đủ (Linux / macOS): `PYTHONPATH=tests:. python3 -m unittest discover -s tests -v`
- Test đầy đủ (Windows PowerShell, cần `python3.exe` trong `PATH` vì `game.contract.json` dùng `python3`):
  `$env:PYTHONPATH = "tests;."; python -m unittest discover -s tests -v`
- Headless (`v1.2`/`v1.3`):
  - `python3 -m chonoi.headless --mode gather|quan --seed 1 --ticks 600 --out out.jsonl`
  - `python3 -m chonoi.headless --mode day --days 1 --seed 1 --ticks 22200 --out day.jsonl`
- Benchmark render `1280×720` (`v1.3`):
  - `python3 -m chonoi.bench --seed 42 --duration 30 --out bench.json` (dùng `--renderer software` nếu ép chạy không GUI)
- Soak headless `10 Ngày` (`v1.3`):
  - `python3 -m chonoi.soak --seed 7 --days 10 --out soak.json`
- Chơi thử trên trình duyệt & Đóng gói:
  - `python3 -m chonoi.live --mode day` (`WASD`/mũi tên, `E`, `Space`, `Esc`/`P` pause, `H` tương phản cao, `R` chơi lại)
  - `python3 tools/package_release.py --out-dir dist --version 1.0.0`

## Cấu trúc & quy ước (`Contract v1.3`)
- Khung & công cụ: `chonoi/{headless,bench,soak,inputs,scenario,contract,rng,ids,jsonl,inventory,runner,live}.py`, `chonoi/web/index.html`, `tools/package_release.py`.
- Luật chơi Lõi: `chonoi/sim/gather.py` (cá bơi/sinh, Cá Sấu, hao tươi `0.5/s`), `chonoi/sim/quan.py` (2 bếp/4 bàn, 6 món, hao tươi `0.25/s`, `spoiled`, re-reserve theo ID, `base_price = floor(price * avg_fresh / 100)`), `chonoi/sim/day.py` (lặp `D1–D5` qua `_plan_key` cho Ngày `6..N`, Shop `oxygen`/`hp`, chuỗi ID `I*`).
- **Độ tươi dùng `fractions.Fraction` nội bộ** (`chonoi/inventory.py` khôi phục lưới `1/240`) và `decimal.Decimal` (`ROUND_FLOOR`) cho boa; không dùng float thô so ngưỡng `< 30`.
- Kho & `reserved` bắt buộc theo schema cá thể `v1.2+`; file kho đếm cũ trả mã thoát `2`.
- Mọi ngẫu nhiên dùng `Streams`; sắp bằng `ids.sort_by_id` / `ids.id_key`; cấp id bằng `IdAllocator`. Bot `chonoi.soak` phải tất định `100%`, không đọc `time.perf_counter()` để quyết định hành động.

## Nên tránh
- Không sửa số chuẩn `tuning` hay các lệnh `headless_cmd` / `bench_cmd` / `soak_cmd` (`python3 -m ...`) trong `game.contract.json`.
- Nhóm `Uno` có 1 thành viên (`team_size: 1`): giữ `"extensions": []` và không bật cơ chế mở rộng ngoài phạm vi.
- Không commit `dist/` hay file nháp/tạm; lưu bằng chứng chạy thật ở `docs/proof/phase-n/`.

## Skills / hooks của nhóm
- [`verify-contract`](.agents/skills/verify-contract/SKILL.md): chạy sau khi sửa sim / scenario / contract để kiểm tra toàn bộ `unittest`, tích hợp kho 2 tiến trình, `--mode day`, tính tất định và cập nhật `docs/proof/`.
- [`slice-review`](.agents/skills/slice-review/SKILL.md): rà soát trước commit theo checklist không hard-code, thứ tự tick v1.2/v1.3, `Fraction`/`Decimal`, `Streams`/`id_key`, 5 khóa `bench.json` và lỗi mã `2`.
