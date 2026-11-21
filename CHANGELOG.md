# Changelog

## [v1.0.0] — Phase 4: Phát hành chính thức (Test Contract v1.3)

### Added
- **Contract `v1.3` ([`game.contract.json`](game.contract.json)):** Nâng `contract_version` lên `"1.3"`, khai báo `bench_cmd` (`python3 -m chonoi.bench`) và `soak_cmd` (`python3 -m chonoi.soak`) ở gốc, kiểm hợp lệ trong [`chonoi/contract.py`](chonoi/contract.py).
- **Benchmark có render 1280×720 ([`chonoi/bench.py`](chonoi/bench.py)):** Cửa sổ `1280×720` Tkinter (tự chuyển về software framebuffer `1280×720` khi môi trường CI không có display), render cảnh buổi sáng lõi v1.2 (bọt nước mặc định, cá bơi/sinh, Cá Sấu Năm Chèo, Út Sen đứng yên ở bến), làm nóng `3 s` rồi đo `duration` và xuất nguyên tử đúng 5 trường `avg_fps`, `p1_low_fps`, `frames`, `measured_s`, `load_ms`. Kết quả thật `30 s` (`seed=42`): **`73.8149` avg FPS**, **`33.9265` 1% low FPS**, **`1575.97` ms load** (`2215` khung hình).
- **Soak headless nhiều Ngày ([`chonoi/soak.py`](chonoi/soak.py)):** Chạy `N` Ngày liên tiếp trong một tiến trình với bot tất định; [`DaySim`](chonoi/sim/day.py) tự lặp kế hoạch `D1–D5` (`_plan_key`) cho Ngày `6..N` mà vẫn giữ liên tục tiền, `earned`, uy tín, cấp nâng cấp và chuỗi ID cá thể `I*`. Kết quả thật `10 Ngày` (`seed=7`): `days_completed=10`, `crashes=0`, lặp tất định giống nhau `100%`.
- **3 cảnh báo trực quan & Chế độ tương phản cao ([`chonoi/web/index.html`](chonoi/web/index.html)):**
  - Hiển thị đủ **chữ + biểu tượng + viền nét đứt** (xếp chồng không đè) cho: **Thủy quái gần (`⚠ THỦY QUÁI GẦN!`)**, **Oxy sắp hết / Hết oxy (`🫧 OXY SẮP HẾT!` / `☠ HẾT OXY!`)**, và **Khách sắp giận (`🔥 KHÁCH SẮP GIẬN!` + `⚠ SẮP GIẬN!` tại bàn)**.
  - Bật/tắt chế độ tương phản cao qua phím `H`, nút HUD góc phải trên, nút trong Menu/Tạm dừng, hoặc tham số `?hc=1`; lưu bền vững qua `localStorage` (`chonoi_high_contrast`).
- **Đóng gói phát hành & Pháp lý:** Thêm [`tools/package_release.py`](tools/package_release.py) xuất `quan-an-cho-noi-v1.0.0.zip` và `.tar.gz` (kèm `run.sh` / `run.bat`), [`LICENSE`](LICENSE) (MIT) và [`CREDITS.md`](CREDITS.md).
- **Bộ kiểm chứng Phase 4:** [`tests/test_phase4_rules.py`](tests/test_phase4_rules.py), ma trận [`docs/verification/phase-4.md`](docs/verification/phase-4.md), ghi chú phát hành [`docs/release/v1.0.0.md`](docs/release/v1.0.0.md), tổng kết [`docs/retro.md`](docs/retro.md) và [`docs/members/tcaopham216-gif.md`](docs/members/tcaopham216-gif.md).

---

## [Phase 3 · Contract v1.2] — Change Request “Mùa Nước Nổi”

### Breaking Changes (`[THAY THẾ]`)
- **`contract_version` nâng từ `"1.1"` lên `"1.2"`**, bổ sung khối `tuning.freshness` (`initial: 100`, `gather_decay_per_s: 0.5`, `quan_decay_per_s: 0.25`, `spoiled_below: 30`).
- **Kho đếm theo loại → kho cá thể có độ tươi:**
  - Schema cũ (`v1.0`–`v1.1`): `{"items": {"ca_loc": 2}}`
  - Schema mới (`v1.2`): `{"items": [{"id": "I1", "kind": "ca_loc", "fresh": 100}, {"id": "I2", "kind": "ca_loc", "fresh": 97.5}]}`
  - Các file kho đếm cũ, `hold` dạng mảng chuỗi, `stock` dạng object hoặc `reserved` dạng map số lượng đều bị từ chối với **mã thoát `2`** trước khi ghi đầu ra.
- **`gather.hold` và `quan.stock`:** chuyển sang mảng cá thể `{id, kind, fresh}`; ID cá thể `I1, I2, ...` cấp liên tục xuyên pha và Ngày.
- **Giữ chỗ theo ID (`customers[].reserved`):** chuyển từ map `{"ca_loc": 1}` sang mảng ID cá thể `["I1", ...]` (ưu tiên tươi nhất, hòa chọn `id_key` nhỏ hơn).
- **Chốt giá theo độ tươi (`cook_started`):** `base_price = floor(price * avg_fresh / 100)`; boa `floor(base_price * 0.2)` áp trên giá đã chốt. `cook_started.data.items` sắp theo `(kind, id_key)`; `lost` trong `monster_hit` / `faint` xuất mảng cá thể theo thứ tự bỏ LIFO.

### Added
- Hao độ tươi theo tick bằng `fractions.Fraction` (`1/120` mỗi tick ở `gather`, `1/240` mỗi tick ở `quan`; khôi phục lưới `1/240` khi đọc file để giữ chính xác ngưỡng `30`).
- Event `spoiled` (`{"item_id", "kind", "location": "hold" | "stock"}`) phát đúng 1 lần khi đi từ `>= 30` xuống `< 30` trước làm tròn; `pause` đóng băng hao tươi; món chín và hàng ở `Shop` không hao.
- Re-reserve tự động một lần theo `(order_tick, id bàn)` nếu phần giữ có cá thể vừa ươn (nhả hết đơn và giữ lại; thiếu chuyển `order_status: "unfulfillable"`).
- HUD hiển thị thanh độ tươi từng ô giỏ, cảnh báo hàng ươn đỏ và phân tách hàng tươi khả dụng / hàng ươn.

### Hướng dẫn nâng cấp fixture & test cũ lên v1.2+
- File kho mẫu: [`docs/contracts/inventory.sample.json`](docs/contracts/inventory.sample.json) dùng mảng `{"items": [{"id": "I1", "kind": "...", "fresh": ...}]}`.
- Scenario `gather.hold`: dùng `[{"id": "I1", "kind": "ca_loc", "fresh": 100}]`.
- Scenario `quan.stock`: dùng `[{"id": "I1", "kind": "ca_loc", "fresh": 100}]`.
- Scenario `customers[].reserved`: dùng `["I1"]` hoặc bỏ trống để tự cấp tươi nhất theo `(order_tick, table_id)`.

---

## [Phase 2 · Contract v1.1] — Một ngày ở chợ nổi
- Chuẩn hóa bộ số liệu v1.1 (`6` nguyên liệu, `6` món, `N1..N6`, `B1..B2`, `T1..T4`, `8` đàn cá bơi/đổi hướng/phản xạ mép/sinh thêm, Cá Sấu `M1`/`M2`).
- Thêm `--mode day --days 1..5`, `Shop` (`oxygen`/`hp`), `pause`/`resumed`, Menu & HUD ≥ 18 px.

## [Phase 1 · Contract v1.0] — Khởi đầu Quán Ăn Chợ Nổi
- Hoàn thiện hai tiến trình headless `gather` & `quan` nối nhau qua file kho nguyên tử và cửa sổ chơi trực tiếp `chonoi.live`.
