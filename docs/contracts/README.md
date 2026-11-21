# Hợp đồng tích hợp — Phase 2 (Test Contract v1.1)

Cập nhật từ v1.0 tại kickoff Phase 2 cho đủ lõi 3 chế độ `gather`, `quan`, `day` (Shop, vòng ngày D1–D5, pause) trên cả headless và trình duyệt chơi thử.

## 1. Schema file kho (`gather` → `quan`, mục G v1.0 & 4.1 v1.1)

- Cấu trúc JSON duy nhất: `{"items": {<ingredient_id>: <int >= 0>}}` (kho rỗng: `{"items": {}}`).
- Hợp lệ 6 loại nguyên liệu Phase 2 (`KINDS_P2`): `ca_loc`, `ca_linh`, `ca_keo`, `bong_dien_dien`, `bong_sung`, `keo_neo`.
- Chế độ `gather` / `quan` độc lập vẫn dùng cờ `--inventory-out` / `--inventory`; chế độ `day` tự bàn giao trong bộ nhớ theo cùng schema đếm (ngất `fainted` vẫn mở quán với kho `{}`).
- File kho mẫu hợp lệ: [`docs/contracts/inventory.sample.json`](inventory.sample.json) (`{"items":{"bong_sung":2,"ca_loc":1}}`).

## 2. Giao diện chuyển pha & `sim/*` ↔ `client/ui`

- **`GET /state`** (UI chỉ đọc snapshot + metadata):
  - Chung: `tick`, `sim_tick`, `mode`, `phase` (`gather` | `quan` | `shop`), `phase_tick`, `state` (`playing` | `paused` | `finished`), `time_left_ticks`, `money`, `earned`, `reputation`, `score`, `meta`, `events`, `finished`, `reason`, `error`.
  - Riêng `day`: `day` (`1..5`), `day_plan` (`{"dishes", "ingredients"}`), `upgrades` (đã mua), `active_upgrades` (đang hiệu lực trong Ngày).
  - `gather`: thêm `player.invuln_ticks`, `fish[].age_ticks`, `monsters[]` (`id`, `kind`, `pos`, `waypoints`, `target_idx`, `state`, `state_ticks_left`, `recoil_dir`).
  - `quan`: giữ v1.0 (`2` bếp `B1..B2`, `4` bàn `T1..T4`, `6` món menu; lọc theo `day_plan.dishes` khi ở `day`).
  - `shop`: thêm `stock` dư từ `quan` và `time_left_ticks` (`600` tick tối đa).
- **`POST /input`**: gửi `{"move": [x, y], "interact": bool, "catch": bool, "pause": bool, "shop_done": bool, "attack": bool, "photo": bool, "buy": "<str>"}` (`buy` chạy đúng 1 lần khi gửi).
- **`POST /ui_pause`**: tạm dừng/tiếp tục vòng lặp trình duyệt cho các màn hình Menu / Intro / Tổng kết ngày.
- **`POST /restart`**: đặt lại lượt chơi về tick 0.

## 3. Sự kiện chuẩn bổ sung (Contract v1.1)

| Pha | Event `name` | `data` bắt buộc | Phát khi |
|---|---|---|---|
| Mọi pha | `day_start` | `{}` | Bắt đầu một Ngày mới (`tick: 0` D1 hoặc sau đóng Shop) |
| Mọi pha | `day_plan` | `{"dishes", "ingredients"}` | Công bố thực đơn & nguyên liệu cần lấy đầu Ngày |
| Mọi pha | `phase_start` | `{}` | Đổi sang pha `gather`, `quan` hoặc `shop` (`phase_tick: 0`) |
| Mọi pha | `paused` / `resumed` | `{}` | Cạnh lên `pause` tắt/mở đóng băng `sim_tick`, `phase_tick` & timer |
| `gather` | `monster_hit` | `{"monster_id", "hp", "lost", "pos"}` | Chạm Cá Sấu khi dưới `d >= 10` và hết bất tử (rơi LIFO `floor(len/2)`) |
| `gather` | `fish_spawned` | `{"id", "kind", "pos"}` | Sinh đàn cá mới lúc `phase_tick = 360*k` nếu dưới trần `12` |
| `gather` | `faint` | `{"cause": "choke"\|"monster", "lost", "hp": 0}` | Máu về `0` do ngạt hoặc chạm thủy quái |
| `shop` | `bought` | `{"upgrade", "level", "price", "money"}` | Mua nâng cấp `oxygen`/`hp` thành công (áp dụng từ Ngày kế) |
| `shop` | `buy_failed` | `{"action", "reason"}` | `funds` / `max_level` / `unknown` |
| `shop` | `shop_end` | `{"reason": "done"\|"time"}` | Đóng Shop (tăng `days_completed` trước khi sang Ngày kế hoặc hết game) |
