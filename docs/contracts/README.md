# Hợp đồng tích hợp — Phase 4 (Test Contract v1.3)

Tài liệu hợp đồng chung của nhóm **Uno** (`team_size: 1`, `"extensions": []`) từ v1.0 → v1.3. Mọi luật gameplay, tuning, schema kho cá thể `{id, kind, fresh}` và JSONL giữ nguyên theo **Contract v1.2**; **v1.3** bổ sung `bench_cmd` và `soak_cmd` ở gốc `game.contract.json`.

## 1. Các điểm vào Contract v1.3 (`game.contract.json`)

- `contract_version`: `"1.3"`
- `run_cmd`: `python3 -m chonoi.live --mode day`
- `headless_cmd`: `python3 -m chonoi.headless` (`--mode gather|quan|day`, với `--days 1..5`)
- `bench_cmd`: `python3 -m chonoi.bench`
- `soak_cmd`: `python3 -m chonoi.soak`

## 2. Hợp đồng Benchmark có render (`bench_cmd`)

- Cú pháp: `python3 -m chonoi.bench --seed <int> --duration <giây> --out <bench.json>`
- Cảnh đo: buổi sáng lõi v1.2 (có độ tươi cá thể, cá bơi/sinh, Cá Sấu Năm Chèo, bọt nước mặc định), Út Sen đứng yên ở bến, cửa sổ `1280×720`, làm nóng mặc định `3 s` rồi đo `<duration>` giây.
- Đầu ra JSON nguyên tử có **đúng 5 khóa**:
  ```json
  {"avg_fps":72,"p1_low_fps":38,"frames":2160,"measured_s":30,"load_ms":2400}
  ```
  trong đó `k = max(1, ceil(0.01 * frames))` và `p1_low_fps = k / sum(k frame_dt chậm nhất)`.

## 3. Hợp đồng Soak headless (`soak_cmd`)

- Cú pháp: `python3 -m chonoi.soak --seed <int> --days <N> --out <soak.json>`
- Chạy `N` Ngày liên tiếp trong một tiến trình duy nhất bằng bot tất định (không dùng đồng hồ thực để quyết định hành động). Ngày `6..10` lặp kế hoạch `D1–D5` (`((day - 1) % 5) + 1`), giữ liên tục tiền, tổng thu (`earned`), uy tín, cấp nâng cấp và ID cá thể `I1, I2, ...`.
- Đầu ra JSON:
  - `days`, `days_completed`, `crashes`, `results`, `duration_s`
  - Mỗi phần tử `results[]`: `{"day", "earned", "reputation", "score"}` chốt tại lúc Shop đóng (`score = earned + 100 * floor(reputation)`).

## 4. Schema kho cá thể & độ tươi (giữ từ Contract v1.2)

- File kho: `{"items":[{"id":"I1","kind":"ca_loc","fresh":100},{"id":"I2","kind":"bong_sung","fresh":97.5}]}` (mã thoát `2` với kho đếm cũ, `kind` lạ, `id` trùng hoặc `fresh` ngoài `[0, 100]`).
- Hao tươi theo `Fraction` (`1/120`/tick ở `gather`, `1/240`/tick ở `quan`, lưới `1/240` khi đọc lại file); `spoiled` phát 1 lần khi đi từ `>= 30` xuống `< 30`; đơn bị ươn nhả hết và giữ lại một lần theo `(order_tick, id bàn)`; giá chốt lúc nấu `floor(price * avg_fresh / 100)`.
- File kho mẫu: [`docs/contracts/inventory.sample.json`](inventory.sample.json).
