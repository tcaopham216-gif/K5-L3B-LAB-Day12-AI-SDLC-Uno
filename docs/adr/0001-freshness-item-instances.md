# ADR-0001: Chuyển kho đếm sang kho cá thể có độ tươi (Contract v1.2)

- Trạng thái: chấp nhận
- Ngày, người quyết: 2026-11-21, PO / Tech Lead (`tcaopham216-gif`)

## Bối cảnh

TICKET-03 ("Mùa Nước Nổi", Test Contract v1.2) thay thế hoàn toàn mô hình kho đếm theo loại (`{"items": {kind: count}}`) ở v1.0–v1.1 bằng mô hình kho cá thể (`{"items": [{"id": "I1", "kind": ..., "fresh": ...}]}`) để theo dõi độ tươi từng món hàng xuyên suốt từ lúc thu hoạch (`gather`) đến khi bảo quản, giữ chỗ theo ID và định giá theo độ tươi ở buổi tối (`quan`) và xuyên nhiều Ngày (`day`).

## Các lựa chọn đã cân nhắc

1. **Lưu độ tươi bằng `float` trực tiếp mỗi tick (`-= 0.5/60`, `-= 0.25/60`):** dễ bị trôi sai số nhị phân IEEE-754 tại ngưỡng `spoiled_below = 30` (ví dụ trừ nhiều bước cho `29.9999999999999` hoặc `30.0000000000001`), dẫn tới sai lệch thời điểm phát event `spoiled` hoặc lệch khi bàn giao qua file JSON.
2. **Dùng phân số chính xác `fractions.Fraction` nội bộ và chuẩn hóa bước lưới `1/240` khi đọc JSON:** trong một giây 60 tick, mức hao `0.5/s = 1/120 = 2/240` mỗi tick ở `gather` và `0.25/s = 1/240` mỗi tick ở `quan`. Mọi bước hao từ mức nguyên đều là bội chính xác của `1/240`; khi xuất file JSON giữ đầy đủ float và khi đọc lại bằng `parse_fresh`, nếu giá trị gần bội `n/240` trong sai số `<= 1e-12` sẽ khôi phục đúng `Fraction(n, 240)` (ngược lại dùng `Fraction(str(val))`).

## Quyết định

- Chọn **lựa chọn 2 (`fractions.Fraction` + khôi phục lưới `1/240`)** cho mọi phép tính độ tươi, so sánh ngưỡng `fresh < 30` trước làm tròn, và tính giá chốt món `floor(giá niêm yết × trung bình fresh / 100)`.
- **Áp dụng ngay v1.2 (breaking change):** `read_inventory` và `scenario.py` chỉ chấp nhận schema cá thể (từ chối schema kho đếm cũ với mã thoát `2`), đảm bảo bộ chấm hộp đen kiểm chứng đúng yêu cầu Contract v1.2.
- **Thứ tự tích hợp trên `main` giữ xanh từng bước:**
  1. Cập nhật `game.contract.json` (`1.2`), `chonoi/contract.py`, adapter `chonoi/inventory.py` và validator `chonoi/scenario.py` (cùng ADR & kế hoạch).
  2. Cập nhật `chonoi/jsonl.py`, `GatherSim`, `QuanSim`, `DaySim` theo đúng thứ tự xử lý v1.2.
  3. Cập nhật `chonoi/live.py` và HUD trong `chonoi/web/index.html` để hiển thị độ tươi từng ô/kho và nhãn hàng ươn.
  4. Cập nhật các fixture P1–P2 bị thay bởi `[THAY THẾ]`, bổ sung bộ test `tests/test_phase3_rules.py`, sinh bằng chứng `docs/proof/phase-3/*`, viết `CHANGELOG.md` và hoàn thiện tài liệu kiểm chứng.

## Hệ quả — Bảng phân tích tác động

| Module | File cần đổi | Test bị ảnh hưởng | Người phụ trách |
|---|---|---|---|
| Manifest & Validator | `game.contract.json`, `chonoi/contract.py`, `chonoi/inventory.py`, `chonoi/scenario.py` | `test_smoke_p1.py` (`Integration`), `test_python_starter_units.py`, `test_phase3_rules.py` (mới) | `tcaopham216-gif` |
| Lặn (`gather`) | `chonoi/sim/gather.py` | `test_smoke_p1.py`, `test_phase1_rules.py` (`GatherRulesTests`), `test_phase2_rules.py` (`MonsterCaSauTests`), `test_phase3_rules.py` | `tcaopham216-gif` |
| Quán (`quan`) | `chonoi/sim/quan.py` | `test_phase1_rules.py` (`QuanRulesTests`, `ScenarioConflictExit2Tests`), `test_phase2_rules.py` (`lau_mam` giá & kho), `test_phase3_rules.py` | `tcaopham216-gif` |
| Vòng ngày (`day`) | `chonoi/sim/day.py`, `chonoi/jsonl.py` | `test_phase2_rules.py` (`DayModeAndShopTests`, `Phase2Exit2AndLiveTests`), `test_phase3_rules.py` | `tcaopham216-gif` |
| Live & HUD | `chonoi/live.py`, `chonoi/web/index.html` | `test_live.py`, `test_phase2_rules.py` (`test_live_server_*`), `test_phase3_rules.py` | `tcaopham216-gif` |
| Tài liệu & QA | `CHANGELOG.md`, `README.md`, `AGENTS.md`, `docs/contracts/*`, `docs/verification/phase-3.md`, `docs/proof/phase-3/*` | Kiểm thử hồi quy toàn bộ `tests/` | `tcaopham216-gif` |
