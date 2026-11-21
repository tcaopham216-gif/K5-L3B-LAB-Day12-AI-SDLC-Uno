# Standup giữa phase (mỗi người một dòng, 2–3 phút)

| Phase | Người | Đã xong | Sắp làm | Vướng gì |
|---|---|---|---|---|
| Phase 1 (0:15) | `tcaopham216-gif` | Kickoff repo, chốt `TEAM.md`, `game.contract.json`, hợp đồng tích hợp (`docs/contracts/README.md`) | Code `GatherSim` Lát 1–2 (`chonoi/sim/gather.py`) | Windows dùng `python`, xử lý bằng shim `python3.exe` ngoài repo |
| Phase 1 (0:35) | `tcaopham216-gif` | Xong `GatherSim` Lát 1–2, `QuanSim` Lát 3–4, kiểm lỗi `scenario.py` mã 2, sửa HUD `index.html`, 32/32 smoke test xanh | Viết `tests/test_phase1_rules.py`, sinh bằng chứng thật `docs/proof/phase-1/`, cập nhật `docs/*` và `README.md` | Cần phủ đủ các case biên boa 1800/1799 và đóng ca |
| Phase 1 (0:55) | `tcaopham216-gif` | Xong test mở rộng Phase 1, 2 skill Harness AI, chạy smoke 2 tiến trình và ma trận truy vết AC-P1-01..12 | Rà soát lần cuối trước khi gắn tag `phase-1` | Không |
| Phase 2 (1:15) | `tcaopham216-gif` | Khóa `phase-1` tại `767b372`; cập nhật `game.contract.json` v1.1, `inventory.py`, `contract.py`, `inputs.py`, `scenario.py`, `GatherSim` cá bơi/sinh & Cá Sấu | Viết `QuanSim` lọc `day_plan`, `DaySim`, `Shop`, `pause`/`resumed` trong `runner.py` & HUD `index.html` | Kiểm tra dung sai float phản xạ đúng mép bể cá |
| Phase 2 (1:40) | `tcaopham216-gif` | Xong `DaySim`, `Shop`, `pause`/`resumed`, `live.py`/`index.html` ≥ 18px, chạy benchmark 22.200 tick mất 3.9–4.4s; sửa xong bug float kẹp `tx`/`td` | Sinh bộ proof thật `docs/proof/phase-2/`, chạy đủ 57 tests, cập nhật `verification/phase-2.md` & `retro.md` | Cần ghi rõ lý do cập nhật 4 assertion Phase 1 theo v1.1 |
| Phase 2 (1:50) | `tcaopham216-gif` | 57/57 tests PASS, sinh đủ 6 file bằng chứng thật ở `docs/proof/phase-2/`, hoàn thiện retro & tài liệu | Commit cuối & gắn tag `phase-2` | Không |
| Phase 3 (2:02) | `tcaopham216-gif` | Phân tích tác động (`ADR-0001`), khóa kế hoạch `phase-3.md`, nâng `game.contract.json` v1.2, `inventory.py` `Fraction` (`1/240`) & validator `scenario.py` | Chuyển `GatherSim`, `QuanSim`, `DaySim` sang kho cá thể, `spoiled` và chốt giá theo độ tươi | Từ chối kho đếm cũ trả mã `2` sạch |
| Phase 3 (2:20) | `tcaopham216-gif` | Xong lõi độ tươi ở `gather`/`quan`/`day` + `index.html` thanh tươi/cảnh báo ươn, sửa 3 assertion test | Sinh bằng chứng thật `docs/proof/phase-3/`, hoàn tất `CHANGELOG.md`, `verification/phase-3.md` & tag `phase-3` | Không |
