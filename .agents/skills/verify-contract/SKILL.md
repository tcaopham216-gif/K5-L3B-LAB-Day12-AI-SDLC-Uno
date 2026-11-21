---
name: verify-contract
description: Kiểm tra tuân thủ Test Contract v1.0 cho hai chế độ gather và quan (smoke test hộp đen, xuất kho nguyên tử, định dạng JSONL và tính tất định).
---

# Skill: verify-contract

Dùng skill này sau khi sửa luật mô phỏng (`chonoi/sim/*.py`), bộ kiểm tra đầu vào (`chonoi/scenario.py`, `chonoi/contract.py`) hoặc trước khi gắn tag bàn giao.

## Quy trình kiểm tra

1. **Chạy toàn bộ bộ test từ gốc repo:**
   - Linux / macOS:
     `PYTHONPATH=tests:. python3 -m unittest discover -s tests -v`
   - Windows (PowerShell, cần `python3.exe` trỏ tới Python 3 trong `PATH`):
     `$env:PYTHONPATH = "tests;."; python -m unittest discover -s tests -v`
2. **Kiểm tra tích hợp hai tiến trình (Contract G):**
   - Chạy `python3 -m chonoi.headless --mode gather --seed 42 --scenario ... --inputs ... --ticks 1 --out gather.jsonl --inventory-out catch.json`.
   - Chạy tiếp `python3 -m chonoi.headless --mode quan --seed 42 --inventory catch.json --ticks 600 --out quan.jsonl`.
   - Đối chiếu `inventory` trong event `gather_end` khớp từng khóa với `catch.json` và snapshot tick 0 của `quan.jsonl`.
3. **Kiểm tra tính tất định (Contract E):**
   - Chạy hai lần cùng `--seed`, `--scenario`, `--inputs`, `--ticks` ra hai file `.jsonl` khác nhau và xác nhận giống nhau từng byte.
4. **Cập nhật bằng chứng:**
   - Lưu đầu ra thật vào `docs/proof/phase-1/` và cập nhật bảng truy vết trong `docs/verification/phase-1.md`.
