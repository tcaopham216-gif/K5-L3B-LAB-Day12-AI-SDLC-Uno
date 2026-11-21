# tcaopham216-gif — phản tư cá nhân (≤ 200 từ)

- **Tôi đã làm:** Thực hiện solo trọn 4 phase: P1 (`phase-1` `767b372` lõi `gather`/`quan`), P2 (`phase-2` `74674ea` số chuẩn, cá bơi/Cá Sấu, `--mode day`/Shop), P3 (`phase-3` `1ec56a4` độ tươi `Fraction`, `spoiled`, giá chốt) và P4 v1.0.0 (`d8194cd` `bench_cmd`/`soak_cmd`/lặp D1–D5, `32c94b3` 3 cảnh báo + Tương phản cao + packager + `LICENSE`/`CREDITS`, `1eae7b5` bộ test P4 & bằng chứng thật).
- **Review & phối hợp:** Tự kiểm đối chiếu hợp đồng v1.0→v1.3 trước mỗi commit: `70/70` test PASS (`109.747s`), GUI benchmark `30s` `1280×720` đạt `73.81` avg FPS / `33.93` 1% low / `1575.97` ms load, soak `10 Ngày` lặp giống nhau `100%`, xác nhận clone sạch và gói `.zip`.
- **AI sai ở đâu & phát hiện thế nào:**
  1. P2: float chạm mép cá `1.0000000000000355` -> bắt bằng test biên & kẹp `[0, 1]`.
  2. P3: test `C1/C2` giả định nhả song song -> sửa đúng tuần tự `(order_tick, bàn)`.
  3. P4: `avg_fps` lệch `0.3036` khi `measured_s` làm tròn -> bắt ở `test_bench_cli_exit_2_and_schema_math`.
- **Bài học:** Kết hợp ADR + test biên + benchmark thật từ sớm giữ `main` luôn chạy được qua mọi phase.
