# Hợp đồng tích hợp — Phase 1 (Test Contract v1.0)

Chốt tại kickoff Phase 1 cho hai buổi `gather` (buổi sáng) và `quan` (buổi tối), dùng chung cho headless và cửa sổ chơi trực tiếp.

## 1. Schema file kho (`gather` → `quan`, mục G)

- Cấu trúc JSON duy nhất: `{"items": {<ingredient_id>: <int >= 0>}}` (kho rỗng: `{"items": {}}`).
- Hợp lệ 4 loại nguyên liệu: `ca_loc`, `ca_linh`, `bong_dien_dien`, `bong_sung` (không áp trần `hold_capacity` lên kho quán).
- Bên ghi bỏ các khóa có lượng bằng `0`, sắp khóa theo thứ tự bảng chữ cái, ghi nguyên tử qua file tạm cùng thư mục chỉ **một lần** khi có `gather_end` (ngất `fainted` → ghi rỗng `{"items": {}}`; chạm `--ticks` trước khi kết thúc → không tạo/ghi đè).
- Bên đọc từ chối JSON sai schema, khóa lạ hoặc số lượng âm/không phải số nguyên với mã thoát `2`.
- File kho mẫu hợp lệ: [`docs/contracts/inventory.sample.json`](inventory.sample.json) (`{"items":{"bong_sung":2,"ca_loc":1}}`).

## 2. Giao diện giữa `sim/*` và `client/ui`

- **`GET /state`** (UI chỉ đọc snapshot + metadata, không giữ logic luật):
  - Chung: `tick`, `sim_tick`, `mode`, `phase`, `phase_tick`, `state`, `time_left_ticks`, `money`, `earned`, `reputation`, `score`, `meta`, `events`, `finished`, `reason`, `error`.
  - `gather`: `player` (`pos`, `vel`, `heading_deg`, `oxygen_ticks`, `oxygen_max_ticks`, `hp`, `hp_max`, `zero_oxy_ticks`, `invuln_ticks`, `catch_cd_ticks`, `at_surface`), `hold`, `hold_count`, `hold_capacity`, `nodes[]` (`id`, `pos`, `kind`, `ready`, `regrow_ticks`), `fish[]` (`id`, `pos`, `kind`, `heading_deg`).
  - `quan`: `player` (`pos`, `vel`), `stock`, `hand`, `stoves[]` (`id`, `pos`, `state`, `dish`, `cook_ticks_left`, `ready_ticks`), `tables[]` (`id`, `pos`, `customer_id`), `customers[]` (`id`, `table_id`, `dish_id`, `order_tick`, `state`, `patience_ticks_left`, `eat_ticks_left`, `order_status`, `reserved`, `base_price`, `tip`).
- **`POST /input`**: gửi `{"move": [x, y], "interact": bool, "catch": bool}` (`[x, d]` ở `gather`, `[x, z]` ở `quan`, cạnh lên ở `interact`/`catch`).
- **`POST /restart`**: đặt lại lượt chơi về tick 0 với cùng seed/scenario.

## 3. Danh sách sự kiện chuẩn (Contract E)

| Buổi | Event `name` | `data` bắt buộc | Phát khi |
|---|---|---|---|
| `gather` | `node_regrown` | `{"node_id"}` | `regrow_ticks` giảm từ `1` về `0` |
| `gather` | `dive` | `{"pos"}` | Đổi từ mặt nước (`d <= surface_depth`) xuống dưới nước |
| `gather` | `surface` | `{"pos"}` | Đổi từ dưới nước lên mặt nước |
| `gather` | `oxygen_empty` | `{"oxygen_ticks": 0}` | Oxy giảm từ dương xuống `0` khi ở dưới nước |
| `gather` | `choke` | `{"hp"}` | `zero_oxy_ticks` đủ `choke_interval_ticks`, trừ 1 Máu |
| `gather` | `faint` | `{"cause": "choke", "lost", "hp": 0}` | Máu về `0`, mất giỏ theo thứ tự LIFO |
| `gather` | `gather` | `{"node_id", "kind", "amount"}` | Hái nút `ready` thành công ở mặt nước |
| `gather` | `fish_caught` | `{"fish_id", "kind", "yield"}` | Bắt đàn cá thành công dưới nước |
| `gather` | `hold_full` | `{"action", "node_id" \| "fish_id", "required", "free"}` | Không đủ chỗ trống khi hái hoặc bắt cá |
| `gather` | `gather_end` | `{"reason", "inventory"}` | Kết thúc buổi sáng (`docked`, `fainted`, `time`) |
| `quan` | `dish_ready` | `{"stove_id", "order_id", "dish_id"}` | Bếp đang nấu có `cook_ticks_left` về `0` |
| `quan` | `cook_started` | `{"stove_id", "order_id", "dish_id", "items", "base_price"}` | Bắt đầu nấu đơn `reserved` cũ nhất |
| `quan` | `dish_picked` | `{"stove_id", "order_id", "dish_id"}` | Nhấc món `ready` lên tay trống |
| `quan` | `served` | `{"order_id", "table_id", "dish_id", "patience_ticks_left", "base_price", "tip"}` | Giao đúng món cho khách `waiting` |
| `quan` | `paid` | `{"order_id", "table_id", "base_price", "tip", "amount", "reason"}` | Khách ăn xong (`finished_eating`) hoặc đóng ca (`closing`) |
| `quan` | `customer_left` | `{"order_id", "table_id", "reason", "reputation"}` | Khách chờ hết kiên nhẫn (`patience`) hoặc đóng ca (`closing`) |
| `quan` | `quan_end` | `{"reason": "time", "money", "earned", "shift_earned", "reputation"}` | Hết ca quán và đã dọn xong khách |
| `quan` | `customer_arrived` | `{"order_id", "table_id", "dish_id"}` | Khách mới vào bàn trống và chọn được món nấu được |
| `quan` | `no_dish` | `{}` | Đến lịch khách và còn bàn trống nhưng không đủ nguyên liệu khả dụng |
