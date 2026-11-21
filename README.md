# Day 12 — AI SDLC: Quán Ăn Chợ Nổi

> **Làm theo nhóm 4–6 người** · Dùng AI để xây game 2D qua **4 phase** trong **3 giờ**: Út Sen lặn bắt cá, hái rau trên mặt nước rồi tối mở quán phục vụ khách.
> **Yêu cầu từng phase mở đúng mốc giờ tại lab board:** **[Chợ Nổi Lab](https://claude.ai/artifact/E35v787wSx2wDgPTNhMVDg)** (cần đăng nhập claude.ai; có trợ giảng AI cho từng phase).

## Nhóm Uno — Hướng dẫn nhanh Phase 1 – Phase 3 (`v1.2`)

- **Thành viên:** Cao Phạm Thành Đạt (`tcaopham216-gif`) — thực hiện solo toàn bộ 4 lát (`team_size: 1` trong [`game.contract.json`](game.contract.json), xem [`TEAM.md`](TEAM.md)). Nhóm `< 5` người nên làm đầy đủ phần **Lõi** (không đăng ký mục Mở rộng).
- **Chạy từ clone sạch (≤ 3 lệnh, macOS / Linux; Python 3.10+ chuẩn):**
  ```bash
  git clone https://github.com/tcaopham216-gif/K5-L3B-LAB-Day12-AI-SDLC-Uno.git && cd K5-L3B-LAB-Day12-AI-SDLC-Uno
  python3 -m chonoi.live --mode day   # chơi trọn vòng ngày D1–D5 (hoặc --mode gather / --mode quan để test lẻ)
  ```
- **Chạy toàn bộ bộ test (1 lệnh):**
  ```bash
  PYTHONPATH=tests:. python3 -m unittest discover -s tests -v
  ```
  *(Trên Windows dùng `python`; để chạy test hộp đen gọi `python3` trong `game.contract.json`, đặt `python3.exe` trỏ tới Python 3 trong `PATH` và `$env:PYTHONPATH = "tests;."`.)*
- **Điều khiển:** `WASD` / phím mũi tên để bơi hoặc đi lại · `E` để hái rau / cập bến / đóng Shop (`gather`/`shop`) hoặc nấu / bưng / phục vụ (`quan`) · `Space` để bắt cá dưới nước (`gather`) · `Esc` / `P` tạm dừng (kể cả trong Shop) · `1` / `2` mua nâng cấp Oxy / Áo phao trong Shop · `R` để chơi lại.
- **Nội dung Phase 3 (`Test Contract v1.2` — Mùa Nước Nổi, xem [`CHANGELOG.md`](CHANGELOG.md)):**
  - **Kho cá thể & độ tươi:** chuyển sang `{"items": [{"id": "I1", "kind": "...", "fresh": 100}]}` (từ chối schema đếm cũ bằng mã `2`), cấp ID `I1, I2,...` liên tục; hàng mới bắt đầu tại `100`, hao `0.5/s` trong giỏ và `0.25/s` trong kho quán (`pause`, món chín & `Shop` không hao).
  - **Hàng ươn & giữ chỗ theo ID:** cá thể đi từ `>= 30` xuống `< 30` phát `spoiled` một lần và không dùng nấu (vẫn chiếm chỗ giỏ); đơn bị ươn tự nhả và giữ lại một lần theo `(order_tick, id bàn)`, thiếu chuyển `unfulfillable`.
  - **Chốt giá theo độ tươi:** khi bắt đầu nấu, `base_price = floor(giá niêm yết × trung bình fresh / 100)`; boa `20%` tính trên giá chốt (`earned + 100 * floor(reputation)`). HUD hiển thị thanh độ tươi từng ô giỏ, cảnh báo hàng ươn đỏ và kho tươi khả dụng.
- **Tóm tắt Phase 2 (`v1.1`):** `6` nguyên liệu, `6` món, `N1..N6`, `B1..B2`, `T1..T4`, `8` đàn cá bơi/đổi hướng/phản xạ mép/sinh thêm, Cá Sấu `M1`/`M2` (`patrol`/`chase`/`recoil`/mất hàng LIFO), vòng `--mode day` D1–D5 & nâng cấp **Bình oxy** (`200k`→45s, `400k`→60s) / **Áo phao** (`250k`→4 Máu, `500k`→5 Máu).
- **Hợp đồng & Kiểm chứng (`v1.2`):** xem [`docs/contracts/README.md`](docs/contracts/README.md), [`docs/adr/0001-freshness-item-instances.md`](docs/adr/0001-freshness-item-instances.md) và [`docs/verification/phase-3.md`](docs/verification/phase-3.md).

## Bắt buộc (chỉ có thế)

Cách làm việc kỹ thuật là **tự do** (push thẳng, nhánh + PR, pair, có hay không CI…). Cái bắt buộc:

1. **Một repo chung:** trưởng nhóm **fork** repo này, đặt tên `K5-L3B-LAB-Day12-AI-SDLC-<ten-nhom>`, thêm mọi thành viên làm collaborator (*Settings → Collaborators*, quyền Write) và để repo **public** (giảng viên xem được, không cần mời).
2. **Cả nhóm cùng commit** bằng tài khoản GitHub của mình, mỗi người **≥ 3 commit có nội dung** (làm cặp thì ghi `Co-authored-by:`).
3. **Điền [`TEAM.md`](TEAM.md):** danh sách thành viên + thỏa thuận làm việc nhóm; sửa `team_size` trong [`game.contract.json`](game.contract.json). Commit của người không có trong `TEAM.md` không được tính.
4. **Gắn tag** `phase-1` … `phase-4` đúng hạn; chạy được tại từng tag.
5. **Ghi chép tối thiểu:** `docs/verification/phase-n.md`, `docs/clarify.md`, `docs/ai-usage-log.md`, `docs/retro.md`, `docs/members/<handle>.md`.

## Bắt đầu nhanh

```bash
git clone <fork-của-nhóm> && cd <fork-của-nhóm>
PYTHONPATH=tests:. python3 -m unittest discover -s tests -v        # smoke test
python3 -m chonoi.live --mode gather                                # chơi thử trên trình duyệt (tùy chọn)
```

Game cần chế độ **headless** theo Test Contract (`python3 -m chonoi.headless --mode gather|quan …`) để được chạy và chấm tự động. **Công nghệ không ràng buộc**: khung Python trong `chonoi/` chỉ là gợi ý, chi tiết ở [`docs/STARTER.md`](docs/STARTER.md).

## Tự do sáng tạo

Ngoài phần đề yêu cầu, nhóm được **thêm** nhân vật, loài cá/cây, sinh vật, món, bản đồ, cơ chế, câu chuyện, đồ họa, âm nhạc… với ba điều kiện: **không phá phần cố định** (tắt ở headless), ghi mục **"Sáng tạo của nhóm"** trong README của nhóm, và **làm lõi đúng trước**.

## Lịch 3 giờ

| Mốc | Phase | Hạn tag |
|---|---|---|
| 0:00 | Phase 1 (PRD-0) | `phase-1` trước 1:00 |
| 1:00 | Phase 2 | `phase-2` trước 1:55 |
| 1:55 | Phase 3 | `phase-3` trước 2:30 |
| 2:30 | Phase 4 | `phase-4` + Release `v1.0.0` trước 3:00 |

Hết giờ mỗi phase thì gắn tag rồi đi tiếp; chỗ chưa xong ghi trung thực trong bằng chứng.

## Đánh giá (100 điểm)

| Hạng mục | Điểm |
|---|---|
| Test tự động ẩn (headless, gồm kiểm tra lại phase trước) | 25 |
| Làm việc nhóm (một repo chung, chia việc, tích hợp, đổi yêu cầu) | 25 |
| Kiểm chứng & bằng chứng | 15 |
| Harness AI (AGENTS.md, skill, nhật ký dùng AI) | 10 |
| Đánh giá & retro | 10 |
| Chất lượng sản phẩm (đúng yêu cầu, mở rộng/sáng tạo) | 10 |
| Demo | 5 |

## Quy định

- Dùng AI thoải mái; **không sao chép repo của nhóm khác**; bằng chứng phải thật.
- Nhân vật, bối cảnh là bản gốc của lab; asset ngoài chỉ dùng CC0/CC-BY/MIT hoặc tự tạo, ghi nguồn trong `CREDITS.md`. Không commit API key, token, `.env`.
