# TEAM

**Tên nhóm:** Uno  **Số người:** 1 (khớp `team_size` trong `game.contract.json` — thực hiện solo toàn bộ 4 lát)

| Thành viên | GitHub handle | Module chính | Vai quy trình | Người dự phòng cho |
|---|---|---|---|---|
| Cao Phạm Thành Đạt | tcaopham216-gif | `sim/gather`, `sim/quan`, `client/ui`, `qa` | PO / Integrator / QA lead / Scrum | — (solo) |

**Vai quy trình:** PO (đầu mối hỏi giảng viên, giữ `docs/clarify.md`) · Integrator (giữ `docs/contracts/`, gắn tag) · QA lead · Scrum/Release. Kiêm toàn bộ do nhóm chỉ có 1 thành viên.

## Thỏa thuận làm việc nhóm (kickoff, ≤ 10 dòng)

- Kênh liên lạc & ghi chép: làm solo, lưu mọi giả định/quyết định thiết kế trong [`docs/clarify.md`](docs/clarify.md).
- Khi gặp chỗ mơ hồ / bất đồng với đặc tả: kiểm tra Test Contract v1.0 trước, không đoán bừa; ghi rõ quyết định và người chốt (PO) vào `docs/clarify.md`.
- Khi vướng quá 10 phút: chuyển sang kiểm tra nhỏ hơn hoặc viết test tái hiện lỗi trước khi sửa luật.
- Mốc kiểm tra giữa phase: rà lại tiến độ 4 lát ở phút 20 và phút 45 trong [`docs/standup.md`](docs/standup.md).
- Cách đọc & review code: tự review từng lát đối chiếu với [`AGENTS.md`](AGENTS.md) và Test Contract v1.0 trước khi commit.
- Cách làm việc với Git: phát triển tuần tự từng lát với commit riêng có nội dung trên `main`; chạy đầy đủ `unittest` trước mỗi commit và gắn tag `phase-1` tại commit bàn giao.
