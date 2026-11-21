# Nhật ký dùng AI (theo phase và theo người)

| Phase | Người | Công cụ / model | Việc | Token / chi phí ước tính | Ghi chú (AI sai ở đâu?) |
|---|---|---|---|---|---|
| Phase 1 | `tcaopham216-gif` | Antigravity AI Assistant | Clone repo, rà soát PRD-0 & Test Contract v1.0, lập kế hoạch kickoff | ~25k tokens (ước tính) | Cần kiểm tra kỹ đường dẫn Windows `python3` khi chạy `unittest` qua `subprocess.run`. |
| Phase 1 | `tcaopham216-gif` | Antigravity AI Assistant | Cài đặt `GatherSim` (Lát 1–2), `QuanSim` (Lát 3–4), kiểm mâu thuẫn `scenario.py`, sửa HUD `index.html` | ~45k tokens (ước tính) | Phát hiện `chonoi/web/index.html` render `st.dish` thành `[object Object]` vì starter mẫu dùng chuỗi còn Contract D dùng object `{order_id, dish_id, base_price}`; đã sửa hiển thị đúng và bổ sung `Kho khả dụng`. |
| Phase 1 | `tcaopham216-gif` | Antigravity AI Assistant | Viết `tests/test_phase1_rules.py`, 2 skill trong `.agents/skills/`, chạy proof và tổng hợp `docs/*` | ~30k tokens (ước tính) | PowerShell `2>&1 \| Tee-Object` làm gói lỗi stderr vào `NativeCommandError`; tách chạy `python` thuần để ghi log sạch vào `docs/proof/phase-1/`. |
