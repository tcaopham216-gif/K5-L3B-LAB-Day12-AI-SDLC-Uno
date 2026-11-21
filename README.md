# Day 12 — AI SDLC: Quán Ăn Chợ Nổi (`v1.0.0`)

> **Làm theo nhóm 4–6 người** · Dùng AI để xây game 2D qua **4 phase** trong **3 giờ**: Út Sen lặn bắt cá, hái rau trên mặt nước rồi tối mở quán phục vụ khách.
> **Yêu cầu từng phase mở đúng mốc giờ tại lab board:** **[Chợ Nổi Lab](https://claude.ai/artifact/E35v787wSx2wDgPTNhMVDg)** (cần đăng nhập claude.ai; có trợ giảng AI cho từng phase).

## Nhóm Uno — Hướng dẫn sử dụng & phát hành `v1.0.0` (`Test Contract v1.3`)

- **Thành viên:** Cao Phạm Thành Đạt (`tcaopham216-gif`) — thực hiện solo toàn bộ 4 phase (`team_size: 1`, `"extensions": []` trong [`game.contract.json`](game.contract.json), xem [`TEAM.md`](TEAM.md)). Do nhóm `< 5` người nên hoàn thiện đầy đủ phần **Lõi**, chế độ soak 10 Ngày và đóng gói phát hành.
- **Yêu cầu môi trường:**
  - **Python `3.10+`** (chỉ dùng thư viện chuẩn — không cần `pip install`).
  - Trình duyệt hiện đại (Chrome / Edge / Firefox / Safari) để hiển thị giao diện web `chonoi.live`.
  - **Tkinter** (đi kèm Python desktop) để chạy cửa sổ GUI `1280×720` cho `chonoi.bench` (tự rơi về software framebuffer `1280×720` nếu chạy trên server/CI không có display).

### 1. Chạy từ clone sạch (≤ 3 lệnh, macOS / Linux)
```bash
git clone https://github.com/tcaopham216-gif/K5-L3B-LAB-Day12-AI-SDLC-Uno.git
cd K5-L3B-LAB-Day12-AI-SDLC-Uno
python3 -m chonoi.live --mode day
```
Mở địa chỉ `http://127.0.0.1:8000/` trên trình duyệt để chơi trọn vòng D1–D5 (hoặc dùng `--mode gather` / `--mode quan` để chơi từng buổi).

### 2. Chạy từ bản đóng gói GitHub Release (`v1.0.0`)
```bash
# Tạo lại bản đóng gói cục bộ (xuất vào dist/, đã gitignore):
python3 tools/package_release.py --out-dir dist --version 1.0.0

# Giải nén & chạy trên macOS / Linux:
tar -xzf dist/quan-an-cho-noi-v1.0.0.tar.gz && cd quan-an-cho-noi-v1.0.0 && ./run.sh
```
*(Trên Windows: giải nén `quan-an-cho-noi-v1.0.0.zip` và chạy `run.bat` hoặc `python -m chonoi.live --mode day`.)*

### 3. Điều khiển & Tiếp cận (Accessibility)
- `WASD` / phím mũi tên: bơi (`gather`) hoặc đi lại (`quan`).
- `E`: hái rau / cập bến (`gather`), nấu / bưng / phục vụ (`quan`), hoặc đóng Shop (`shop`).
- `Space`: bắt đàn cá dưới nước (`gather`).
- `Esc` / `P`: tạm dừng / tiếp tục (đóng băng đồng hồ & hao tươi, kể cả trong `Shop`).
- `1` / `2`: mua nâng cấp **Bình oxy** / **Áo phao** trong `Shop`.
- `H` *(hoặc nút góc phải trên / Menu / Tạm dừng / `?hc=1`)*: bật/tắt **Chế độ tương phản cao (High-Contrast)**.
- `R`: chơi lại.
- **3 cảnh báo dễ nhận biết (chữ + biểu tượng + viền nét đứt):** `⚠ THỦY QUÁI GẦN!`, `🫧 OXY SẮP HẾT!` / `☠ HẾT OXY!`, và `🔥 KHÁCH SẮP GIẬN!`.

### 4. Lệnh Test, Headless, Benchmark & Soak (`Contract v1.3`)
```bash
# Toàn bộ 70 bài kiểm thử P1–P4:
PYTHONPATH=tests:. python3 -m unittest discover -s tests -v

# Headless (gather / quan / day 1..5):
python3 -m chonoi.headless --mode gather --seed 1 --ticks 600 --out out.jsonl
python3 -m chonoi.headless --mode day --days 1 --seed 1 --ticks 22200 --out day.jsonl

# Benchmark có render 1280x720 (làm nóng 3s + đo 30s -> 5 trường JSON):
python3 -m chonoi.bench --seed 42 --duration 30 --out bench.json

# Soak headless 10 Ngày (lặp D1–D5 ở Ngày 6–10 bằng bot tất định):
python3 -m chonoi.soak --seed 7 --days 10 --out soak.json
```
*(Trên Windows PowerShell: dùng `python`; khi chạy các test hộp đen đọc `headless_cmd`/`bench_cmd`/`soak_cmd` dùng `python3`, đặt `python3.exe` trỏ tới Python 3 trong `PATH` và `$env:PYTHONPATH = "tests;."`.)*

### 5. Tài liệu dự án, kiểm chứng & phát hành
- **Thay đổi qua từng phase:** [`CHANGELOG.md`](CHANGELOG.md) · **Ghi chú phát hành `v1.0.0`:** [`docs/release/v1.0.0.md`](docs/release/v1.0.0.md)
- **Kiến trúc & Hợp đồng:** [`docs/contracts/README.md`](docs/contracts/README.md) · [`docs/adr/0001-freshness-item-instances.md`](docs/adr/0001-freshness-item-instances.md)
- **Kiểm chứng & Bằng chứng:** [`docs/verification/phase-4.md`](docs/verification/phase-4.md) · [`docs/proof/phase-4/`](docs/proof/phase-4/)
- **Retro, Phản tư & Pháp lý:** [`docs/retro.md`](docs/retro.md) · [`docs/members/tcaopham216-gif.md`](docs/members/tcaopham216-gif.md) · [`CREDITS.md`](CREDITS.md) · [`LICENSE`](LICENSE)

---

## Bắt buộc (chỉ có thế)

Cách làm việc kỹ thuật là **tự do** (push thẳng, nhánh + PR, pair, có hay không CI…). Cái bắt buộc:

1. **Một repo chung:** trưởng nhóm **fork** repo này, đặt tên `K5-L3B-LAB-Day12-AI-SDLC-<ten-nhom>`, thêm mọi thành viên làm collaborator (*Settings → Collaborators*, quyền Write) và để repo **public** (giảng viên xem được, không cần mời).
2. **Cả nhóm cùng commit** bằng tài khoản GitHub của mình, mỗi người **≥ 3 commit có nội dung** (làm cặp thì ghi `Co-authored-by:`).
3. **Điền [`TEAM.md`](TEAM.md):** danh sách thành viên + thỏa thuận làm việc nhóm; sửa `team_size` trong [`game.contract.json`](game.contract.json). Commit của người không có trong `TEAM.md` không được tính.
4. **Gắn tag** `phase-1` … `phase-4` đúng hạn; chạy được tại từng tag.
5. **Ghi chép tối thiểu:** `docs/verification/phase-n.md`, `docs/clarify.md`, `docs/ai-usage-log.md`, `docs/retro.md`, `docs/members/<handle>.md`.

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
