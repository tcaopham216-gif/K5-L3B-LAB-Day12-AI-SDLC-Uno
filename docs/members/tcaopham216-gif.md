# tcaopham216-gif — phản tư cá nhân (≤ 200 từ)

- **Tôi đã làm:** Thực hiện solo trọn 4 lát qua Phase 1 (`phase-1` tại `767b372`), Phase 2 (`phase-2` tại `74674ea`) và Phase 3 (`8acfb7d` ADR-0001 & adapter v1.2, `ff2c010` độ tươi/`spoiled`/giá chốt ở `GatherSim`·`QuanSim`·`DaySim`, `f843340` HUD độ tươi, và commit test + bằng chứng + `CHANGELOG.md`).
- **Tôi đã review:** Tự rà toàn bộ breaking change `[THAY THẾ]` của Contract v1.2, đối chiếu 64/64 bài test tự động PASS (`55.725s`) và kiểm chứng thủ công bảng event/snapshot tại ngưỡng `fresh = 30`.
- **AI sai ở đâu và tôi phát hiện thế nào:**
  1. Ở P1–P2 đã phát hiện & khóa các lỗi UI (`st.dish`), `DaySim` sync tiền giữa ca và sai số float mép cá `1.0000000000000355`.
  2. Ở P3 thiết kế ngay `Fraction` + khôi phục `1/240` nên sim vượt qua mọi ca biên file round-trip; chỉ phát hiện một typo test (`write_json` trả string) và một kỳ vọng thứ tự re-reserve ở `test_phase3_rules.py`.
- **Điều học được:** Chốt `ADR` + thứ tự tích hợp (`adapter → sim → UI → migration test`) giúp đổi breaking schema lớn mà không làm gãy `main`.
