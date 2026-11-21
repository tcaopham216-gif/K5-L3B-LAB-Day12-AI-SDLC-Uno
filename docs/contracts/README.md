# Hợp đồng tích hợp — Phase 3 (Test Contract v1.2)

Cập nhật từ v1.1 theo Change Request **Mùa Nước Nổi**: thay kho đếm theo loại bằng **kho cá thể có độ tươi**. Nhóm `Uno` (`team_size: 1`) chỉ triển khai phần Lõi (`"extensions": []`).

## 1. Schema file kho cá thể v1.2 (`gather` → `quan`)

- Cấu trúc JSON duy nhất:
  ```json
  {"items":[{"id":"I1","kind":"ca_loc","fresh":100},{"id":"I2","kind":"bong_sung","fresh":97.5}]}
  ```
- Kho rỗng: `{"items":[]}`.
- Ràng buộc từng cá thể: đúng 3 khóa `{"id", "kind", "fresh"}`; `id` chuỗi duy nhất khác rỗng; `kind` thuộc `KINDS_P2`; `fresh` hữu hạn trong `[0, 100]`.
- **Từ chối v1.0/v1.1:** File kho đếm dạng `{"items":{"ca_loc":1}}` hoặc thiếu trường cá thể bị từ chối ngay với **mã thoát `2`** trước khi ghi output.
- Bên ghi xuất theo `id_key(id)`, giữ nguyên mọi cá thể kể cả hàng ươn (`fresh < 30`) với đủ độ chính xác để giữ nhánh ngưỡng `30` khi đọc lại.
- File kho mẫu v1.2: [`docs/contracts/inventory.sample.json`](inventory.sample.json).

## 2. Quy tắc độ tươi, giữ chỗ & giá chốt (`tuning.freshness`)

- Hằng số chuẩn: `initial: 100`, `gather_decay_per_s: 0.5` (`1/120`/tick), `quan_decay_per_s: 0.25` (`1/240`/tick), `spoiled_below: 30`. Hàng vừa hái/bắt có `fresh = 100` và hao từ **bước kế tiếp**. `pause` dừng hao; món đã nấu và kho dư ở `Shop` không hao; bàn giao `gather → quan` không hao thêm ở tick chuyển pha.
- So ngưỡng `fresh < 30` trước làm tròn xuất JSONL. Khi cá thể đi từ `>= 30` xuống `< 30`, phát `spoiled` **đúng một lần** (sắp theo `id_key`). Hàng ươn vẫn chiếm chỗ trong giỏ/kho nhưng không dùng nấu.
- **Giữ chỗ theo ID (`customers[].reserved`):** chọn các cá thể tươi nhất (`fresh >= 30`), hòa chọn `id_key` nhỏ hơn. Ở mỗi tick quán, hao toàn bộ kho và phát hết `spoiled` trước, rồi xử lý các đơn `waiting` + `reserved` có hàng vừa ươn theo `(order_tick, id bàn)`: nhả hết phần giữ của đơn và thử giữ lại một lần; thiếu → `order_status: "unfulfillable"`.
- **Giá chốt theo tươi (`cook_started`):** tiêu đúng các ID đang giữ (mảng `items` sắp theo `kind` rồi `id_key`), tính:
  $$\text{base\_price} = \left\lfloor \text{giá niêm yết} \times \frac{\text{trung bình fresh các cá thể}}{100} \right\rfloor$$
  Boa khi `served` tính `floor(base_price * 0.2)` trên `base_price` đã chốt.

## 3. Khác biệt Schema Scenario / Snapshot / Event từ v1.2

- `gather.hold`, `quan.stock`, `shop.stock`, `gather_end.data.inventory.items`, `cook_started.data.items` và `lost` trong `monster_hit`/`faint`: mảng cá thể `{id, kind, fresh}` (riêng `hold` và `lost` theo thứ tự nhặt / LIFO; `stock` và `inventory` theo `id_key`; `cook_started.items` theo `kind` rồi `id_key`).
- `customers[].reserved`: mảng ID cá thể `["I1", ...]`.
- `IdAllocator("I")` cấp ID liên tục xuyên pha và Ngày (`I1, I2,...`); trong `day`, Ngày 1 giữ nguyên ID mẫu `gather.hold`, Ngày ≥ 2 cấp ID mới cho `gather.hold` mẫu.
- Event mới **`spoiled`**: `{"item_id": "I1", "kind": "ca_linh", "location": "hold" | "stock"}`.
