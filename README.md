# Day 12 — AI SDLC: Quán Ăn Chợ Nổi

> **Làm theo nhóm 4–6 người** · Dùng AI để xây game 2D qua **4 phase** trong **3 giờ**: Út Sen lặn bắt cá, hái rau trên mặt nước rồi tối mở quán phục vụ khách.
> **Yêu cầu từng phase mở đúng mốc giờ tại lab board:** **[Chợ Nổi Lab](https://claude.ai/artifact/E35v787wSx2wDgPTNhMVDg)** (cần đăng nhập claude.ai; có trợ giảng AI cho từng phase).

## Nhóm Uno — Hướng dẫn nhanh Phase 1 & Phase 2 (`v1.1`)

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
- **Nội dung Phase 2 (`Test Contract v1.1`):**
  - **6 nguyên liệu & 6 món (`menu`):** thêm `ca_keo`, `keo_neo`, 2 nút `N5..N6`, 2 bếp `B1..B2`, 4 bàn `T1..T4`, thêm 3 món `canh_chua_ca_loc` (`90k`), `ca_keo_nuong` (`70k`), `lau_mam` (`200k`).
  - **Buổi sáng sống động:** 8 đàn cá ban đầu bơi `1.5 m/s`, đổi hướng tại bước bơi `120·k`, phản xạ mép/góc, sinh thêm tại `360·k` (trần `12`); thêm **Cá Sấu Năm Chèo** (`M1` từ Ngày 1, `M2` từ Ngày 3) tuần tra / truy đuổi / giật lùi `recoil` 60 bước, chạm mất 1 Máu + rơi `floor(n/2)` hàng theo LIFO + bất tử `90` tick.
  - **Vòng ngày D1–D5 & Shop (`--mode day --days 1..5`):** `DayIntro → gather → EveningIntro → quan → DayResult → Shop`, khách chỉ gọi món nằm trong `day_plan` đủ nguyên liệu, mua nâng cấp **Bình oxy** (`200k`→45s, `400k`→60s) và **Áo phao** (`250k`→4 Máu, `500k`→5 Máu) có hiệu lực từ Ngày kế tiếp.
- **Cách tính điểm:** $\text{score} = \text{earned} + 100 \times \lfloor \text{reputation} \rfloor$ (mua nâng cấp chỉ trừ `money`, giữ nguyên `earned` và `score`; boa `20%` làm tròn xuống khi kiên nhẫn còn $\ge 50\%$ và cộng `0.2` uy tín; khách bỏ đi trừ `0.5` uy tín, kẹp `[0, 5]`).
- **Hợp đồng file kho (`v1.1`, [`docs/contracts/README.md`](docs/contracts/README.md)):** `{"items": {<id>: <int >= 0>}}`, chấp nhận đủ 6 nguyên liệu, tự bàn giao ở `--mode day` và vẫn hỗ trợ 2 tiến trình `--inventory-out` / `--inventory` ([bằng chứng Phase 2](docs/verification/phase-2.md)).

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
