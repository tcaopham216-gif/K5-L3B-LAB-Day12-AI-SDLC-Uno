# Retro nhóm

## Phase 2 (nhanh)
- Điều tốt: Cấu trúc tách `Session`, `GatherSim`, `QuanSim`, `DaySim` giúp nối trọn vòng ngày D1–D5 (kèm `pause` trong Shop và lọc món theo `day_plan`) nhanh và sạch; thời gian chạy 1 Ngày đủ 22.200 tick chỉ ~4.4s (dư chuẩn 20s). Toàn bộ bằng chứng chạy thật và 57/57 test xanh trước giờ khóa tag.
- Điều tệ: Làm 1 mình (solo) vừa chỉnh UI vừa viết luật phản xạ mép cá khiến lần test đầu dính lỗi biên float `x + dx - x_lo` lệch ~`1e-15` làm bỏ lỡ cú bật hướng ngay tick chạm mép, và quên kiểm `Shop` DOM bị poll 60Hz vẽ đè trước khi rà kỹ.
- 1 hành động cho Phase 3: Mọi phép toán hình học chạm biên/góc trong sim phải viết test chạm đúng giá trị biên làm tròn (edge touch) ngay cùng lúc viết code (`tcaopham216-gif`).

## Phase 3 (nhanh — đổi schema kho sang v1.2)
- Điều tốt: Áp dụng hành động Phase 2 (viết `ADR-0001` phân tích tác động & dùng `fractions.Fraction` + lưới `1/240` cho phép toán biên `fresh: 30`) ngay từ đầu nên toàn bộ 64/64 test qua mượt không lỗi sai số dấu phẩy động khi round-trip qua JSON.
- Điều tệ: Một câu test ở `test_phase3_rules.py` ban đầu giả định `C1` và `C2` cùng nhả hàng song song trước khi giữ lại, trong khi đặc tả yêu cầu xử lý tuần tự theo `(order_tick, id bàn)`.
- 1 hành động cho Phase 4: Luôn trace tay tuần tự từng đơn hàng cho các test đa đơn cùng sự kiện trong cùng một tick trước khi viết assertion (`tcaopham216-gif`).

## Phase 4 (cuối)
- **Rà lại hành động Phase 2 & Phase 3:**
  - *Hành động P2 (test biên chạm đúng mép/góc bằng giá trị làm tròn):* **Đã làm đủ.** Áp dụng trực tiếp ở P3 (`Fraction` + lưới `1/240` qua ngưỡng `fresh: 30` ở [`test_phase3_rules.py`](../tests/test_phase3_rules.py)) và tiếp tục kiểm ở P4 cho `avg_fps` so với `measured_s`.
  - *Hành động P3 (trace tay tuần tự đa đơn):* **Đã duy trì.** Trong `chonoi.soak`, `_SoakBot` bám đúng thứ tự `id_key` và `(order_tick, table_id)`, không gặp bất đồng nào trên cả 10 Ngày (`days_completed = 10, crashes = 0`).
  - *Còn vướng gì:* Làm solo (`team_size: 1`) nên thiếu người chơi thử chéo trực tiếp trước demo; đã bù bằng tự động hóa kiểm clone sạch, gói đóng gói và `LiveServer` API test cho cả 3 cảnh báo + High-Contrast.
- **Điều tốt / điều tệ:**
  - *Tốt:* Chia rõ 4 lát theo Contract v1.3 (`d8194cd` → `32c94b3` → `1eae7b5` → commit cuối); đạt thật **`73.8149` avg FPS / `33.9265` 1% low / `1575.97` ms load** ở cửa sổ Tkinter `1280×720` (`30 s`) và **`70 / 70` tests PASS (`109.747s`)**.
  - *Tệ:* Lúc chạy thử benchmark tốc độ cực cao (`--renderer software` 0.25s), `round(measured_s, 4)` làm lệch `frames / measured_s` khoảng `0.3036` FPS so với `avg_fps` tính trước khi làm tròn `measured_s`.
- **Số liệu thật:** `git shortlog -sn HEAD` ghi nhận **`16` commit của `tcaopham216-gif`** (`4` P1 + `4` P2 + `4` P3 + `4` P4) trên nền `9` commit starter của `Hai Duong` (`origin/main` `f0a1906`); tự rà 100% diff qua 4 phase; tổng chi phí AI ước tính **~375k tokens** qua P1–P4 (chi tiết ở [`docs/ai-usage-log.md`](ai-usage-log.md)).
- **Một lần AI sai và cách nhóm phát hiện:** Trong P4, `chonoi/bench.py` ban đầu tính `avg_fps = frames / measured_s` trước khi làm tròn `measured_s` xuống 4 chữ số thập phân; khi `test_phase4_rules.py::test_bench_cli_exit_2_and_schema_math` chạy với backend software (~1500 FPS, `0.25s`), assertion phát hiện sai lệch `0.30365 > 0.1`. Cách xác minh: đổi sang tính `avg_fps = frames / measured_s` trên chính giá trị `measured_s` đã làm tròn, chạy lại toàn bộ 70 tests (`OK`). *(Ngoài ra ở P2–P3 cũng đã bắt được lỗi float `1.0000000000000355` ở mép bể cá và lỗi giả định thứ tự `C1/C2` song song.)*
- **Nếu làm lại, đổi gì:** Tổ chức tách branch feature + PR ngay từ P1 kể cả khi solo để có thêm mốc rà chéo độc lập trước khi merge vào `main`, và thêm script smoke check đồ họa tự động với headless browser sớm hơn.
