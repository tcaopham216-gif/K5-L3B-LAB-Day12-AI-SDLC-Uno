# Changelog

## [1.2.0] — Phase 3: Change Request “Mùa Nước Nổi” (Test Contract v1.2)

### Breaking Changes (`[THAY THẾ]`)
- **`contract_version` nâng từ `"1.1"` lên `"1.2"`**, bổ sung khối `tuning.freshness` (`initial: 100`, `gather_decay_per_s: 0.5`, `quan_decay_per_s: 0.25`, `spoiled_below: 30`).
- **Kho đếm theo loại → kho cá thể có độ tươi:**
  - Schema cũ (`v1.0`–`v1.1`): `{"items": {"ca_loc": 2}}`
  - Schema mới (`v1.2`): `{"items": [{"id": "I1", "kind": "ca_loc", "fresh": 100}, {"id": "I2", "kind": "ca_loc", "fresh": 97.5}]}`
  - Các file kho đếm cũ, `hold` dạng mảng chuỗi, `stock` dạng object hoặc `reserved` dạng map số lượng đều bị từ chối với **mã thoát `2`** trước khi ghi đầu ra.
- **`gather.hold` và `quan.stock`:** chuyển sang mảng cá thể `{id, kind, fresh}`; ID cá thể `I1, I2, ...` cấp liên tục xuyên pha và Ngày.
- **Giữ chỗ theo ID (`customers[].reserved`):** chuyển từ map `{"ca_loc": 1}` sang mảng ID cá thể `["I1", ...]` (ưu tiên tươi nhất, hòa chọn `id_key` nhỏ hơn).
- **Chốt giá theo độ tươi (`cook_started`):** `base_price` không còn cố định theo giá niêm yết mà được tính khi bắt đầu nấu: `floor(price * avg_fresh / 100)`; boa `floor(base_price * 0.2)` áp trên giá đã chốt. `cook_started.data.items` chuyển sang mảng cá thể sắp theo `(kind, id_key)`. `lost` trong `monster_hit` / `faint` chuyển sang mảng cá thể theo thứ tự bỏ LIFO.

### Added
- Hao độ tươi theo tick bằng `fractions.Fraction` (`1/120` mỗi tick ở `gather`, `1/240` mỗi tick ở `quan`; khôi phục lưới `1/240` khi đọc file để giữ chính xác ngưỡng `30`).
- Event mới `spoiled` (`{"item_id", "kind", "location": "hold" | "stock"}`) phát đúng 1 lần khi đi từ `>= 30` xuống `< 30` trước làm tròn; `pause` đóng băng hao tươi; món chín và hàng ở `Shop` không hao.
- Re-reserve tự động một lần theo `(order_tick, id bàn)` nếu phần giữ có cá thể vừa ươn (nhả hết đơn và giữ lại; thiếu chuyển `order_status: "unfulfillable"`).
- HUD `chonoi/web/index.html` hiển thị thanh độ tươi từng ô giỏ, cảnh báo hàng ươn đỏ và phân tách hàng tươi khả dụng / hàng ươn ở kho quán & `Shop`.

### Hướng dẫn nâng cấp fixture & test cũ lên v1.2
- File kho mẫu: [`docs/contracts/inventory.sample.json`](docs/contracts/inventory.sample.json) chuyển sang mảng `{"items": [{"id": "I1", "kind": "...", "fresh": ...}]}`.
- Scenario `gather.hold`: đổi `["ca_loc"]` thành `[{"id": "I1", "kind": "ca_loc", "fresh": 100}]`.
- Scenario `quan.stock`: đổi `{"ca_loc": 1}` thành `[{"id": "I1", "kind": "ca_loc", "fresh": 100}]`.
- Scenario `customers[].reserved`: đổi `{"ca_loc": 1}` thành `["I1"]` hoặc bỏ trống để tự cấp tươi nhất theo `(order_tick, table_id)`.

## [1.1.0] — Phase 2: Một ngày ở chợ nổi (Test Contract v1.1)
- Chuẩn hóa bộ số liệu v1.1 (`6` nguyên liệu, `6` món, `N1..N6`, `B1..B2`, `T1..T4`, `8` đàn cá bơi/sinh, Cá Sấu `M1`/`M2`).
- Thêm `--mode day --days 1..5`, `Shop` (`oxygen`/`hp`), `pause`/`resumed`, Menu & HUD ≥ 18 px.

## [1.0.0] — Phase 1: Quán Ăn Chợ Nổi (Test Contract v1.0)
- Hoàn thiện hai tiến trình `gather` & `quan` nối nhau qua file kho nguyên tử.
