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
- Rà lại hành động Phase 2: đã làm chưa? vì sao?
- Điều tốt / điều tệ:
- Số liệu: số commit theo người, cách đọc code của nhau, token theo người:
- Một lần AI sai và cách nhóm phát hiện:
- Nếu làm lại, đổi gì:
