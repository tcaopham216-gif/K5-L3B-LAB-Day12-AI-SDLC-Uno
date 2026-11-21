# tcaopham216-gif — phản tư cá nhân (≤ 200 từ)

- **Tôi đã làm:** Thực hiện solo 4 lát qua Phase 1 (`66cfbec`, `81afc2c`, `547f07b`, `767b372`, tag `phase-1`) và Phase 2 (`3de57ef` Contract v1.1, `af0871a` cá bơi/sinh & Cá Sấu, `ec7a27b` `DaySim`/`Shop`/`pause`/UI `index.html`, và commit test + bằng chứng Phase 2).
- **Tôi đã review:** Tự rà toàn bộ luật Contract v1.0 & v1.1 đối chiếu hộp đen qua `tests/test_smoke_p1.py`, `tests/test_phase1_rules.py` và `tests/test_phase2_rules.py` (`57/57` tests PASS).
- **AI sai ở đâu và tôi phát hiện thế nào:**
  1. Starter HUD render `st.dish` thành `[object Object]` ở P1; phát hiện khi đối chiếu snapshot `quan`.
  2. Trong `DaySim`, `money`/`reputation` ban đầu chỉ sync cuối ca quán -> sửa thành `@property` đọc thẳng từ `QuanSim` đang chạy.
  3. Test biên chạm mép cá `[4.025, 6.0]` lật mặt lỗi float `tx = 1.0000000000000355 > 1.0` và Shop DOM gắn `snap.tick` -> kẹp `tx`/`td` về `[0.0, 1.0]` và chỉ cập nhật text timer `#shop-sec`.
- **Điều học được:** Luôn viết test chạm đúng biên số thực và tách rõ vòng đời state chuyển pha ngay từ kế hoạch.
