# Kế hoạch Phase 4 (TICKET-04 — Phát hành v1.0.0, Test Contract v1.3)

- **Phân công vai (`team_size: 1`, solo `tcaopham216-gif`):** Kiêm toàn bộ 4 vai theo đề (Đóng gói · Bench/QA · Release/Integrator · Điều phối retro), giữ `"extensions": []` và chỉ làm phần Lõi + Soak headless + Release v1.0.0.
- **Lịch thực hiện & các lát bàn giao:**
  1. **Nền tảng v1.3, Soak & Render Benchmark (`AC-P4-01`, `AC-P4-02`, `AC-P4-03`):**
     - Nâng `game.contract.json` lên `contract_version: "1.3"`, khai báo `bench_cmd` (`python3 -m chonoi.bench`) và `soak_cmd` (`python3 -m chonoi.soak`).
     - Hỗ trợ lặp kế hoạch `D1–D5` cho Ngày `6..N` trong `DaySim`, giữ nguyên ID cá thể/tiền/uy tín/cấp nâng cấp xuyên suốt.
     - Viết `chonoi/bench.py` (cửa sổ `1280×720` Tkinter + fallback software cho CI headless, làm nóng `3 s`, đo `duration`, xuất đúng 5 trường `avg_fps`, `p1_low_fps`, `frames`, `measured_s`, `load_ms`) và `chonoi/soak.py` (bot tất định 100%, xuất `days`, `days_completed`, `crashes`, `results`, `duration_s`).
  2. **Cảnh báo dễ nhận biết, Tương phản cao & Đóng gói (`AC-P4-04`, `AC-P4-05`, `AC-P4-06`):**
     - Nâng cấp `chonoi/web/index.html` bổ sung chữ + biểu tượng + viền phân biệt cho 3 cảnh báo (thủy quái gần, oxy sắp hết/hết oxy, khách sắp giận) và chế độ tương phản cao (phím `H`, nút HUD/Menu/Pause, `?hc=1`, lưu `localStorage`).
     - Viết `tools/package_release.py` tạo gói `quan-an-cho-noi-v1.0.0.zip` và `.tar.gz` trong `dist/`; rà `LICENSE` (MIT) và `CREDITS.md`.
  3. **Kiểm chứng & Hồi quy (`AC-P4-07`, `AC-P4-08`):**
     - Cập nhật kiểm chứng phiên bản contract trong test P2–P3, bổ sung `tests/test_phase4_rules.py` kiểm `v1.3`, `bench`, `soak`, lặp D1–D5, 3 cảnh báo/tương phản cao và packager.
  4. **Bằng chứng thật, Clone sạch, Retro & Phát hành (`AC-P4-09`, `AC-P4-10`):**
     - Chạy benchmark thật `30 s` (`seed=42`), soak thật `10 Ngày` (`seed=7`) + kiểm tra lặp tất định, thử chạy từ clone sạch và từ gói đóng gói trong `dist/`.
     - Hoàn tất `docs/verification/phase-4.md`, `CHANGELOG.md` theo từng phase, `docs/release/v1.0.0.md`, `README.md`, `docs/retro.md` (rà lại hành động P2), `docs/members/tcaopham216-gif.md` (≤ 200 từ), gắn tag cục bộ `phase-4` & `v1.0.0`.
