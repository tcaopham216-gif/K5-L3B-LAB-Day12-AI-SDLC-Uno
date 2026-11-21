# Retro nhóm

## Phase 2 (nhanh)
- Điều tốt: Cấu trúc tách `Session`, `GatherSim`, `QuanSim`, `DaySim` giúp nối trọn vòng ngày D1–D5 (kèm `pause` trong Shop và lọc món theo `day_plan`) nhanh và sạch; thời gian chạy 1 Ngày đủ 22.200 tick chỉ ~4.4s (dư chuẩn 20s). Toàn bộ bằng chứng chạy thật và 57/57 test xanh trước giờ khóa tag.
- Điều tệ: Làm 1 mình (solo) vừa chỉnh UI vừa viết luật phản xạ mép cá khiến lần test đầu dính lỗi biên float `x + dx - x_lo` lệch ~`1e-15` làm bỏ lỡ cú bật hướng ngay tick chạm mép, và quên kiểm `Shop` DOM bị poll 60Hz vẽ đè trước khi rà kỹ.
- 1 hành động cho Phase 3: Mọi phép toán hình học chạm biên/góc trong sim phải viết test chạm đúng giá trị biên làm tròn (edge touch) ngay cùng lúc viết code (`tcaopham216-gif`).

## Phase 4 (cuối)
- Rà lại hành động Phase 2: đã làm chưa? vì sao?
- Điều tốt / điều tệ:
- Số liệu: số commit theo người, cách đọc code của nhau, token theo người:
- Một lần AI sai và cách nhóm phát hiện:
- Nếu làm lại, đổi gì:
