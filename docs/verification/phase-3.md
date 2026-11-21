# Ma trận truy vết Phase 3 (TICKET-03 — Change Request “Mùa Nước Nổi”, Contract v1.2)

> Bộ kiểm chứng tự động chạy bằng `PYTHONPATH=tests:. python3 -m unittest discover -s tests -v`: **64 / 64 tests PASS (`55.725s`, `OK`)**, xem [`docs/proof/phase-3/test_output.txt`](../proof/phase-3/test_output.txt). Nhóm `Uno` có 1 thành viên (`team_size: 1`, `"extensions": []`) nên chỉ làm phần **Lõi** (không bật Mở rộng `current` / `reservations`).

## 1. Bảng AC → bằng chứng → kết quả

| AC | Nội dung kiểm chứng | Bằng chứng (link `docs/proof/phase-3/...`) | Kết quả (trung thực) |
|---|---|---|---|
| `AC-P3-01` | Nâng manifest lên `contract_version: "1.2"` + `tuning.freshness` (`100, 0.5, 0.25, 30`); từ chối kho đếm cũ / ID trùng / `fresh` sai với mã thoát `2` trước khi ghi file | [`test_output.txt`](../proof/phase-3/test_output.txt) (`Phase3SchemaAndExit2Tests.*`) · `test_inv_bad_schema_exit_2` | **Đạt.** |
| `AC-P3-02` | Bàn giao file `--inventory-out` → `--inventory` đúng schema cá thể `{id, kind, fresh}`, giữ cả hàng ươn & độ chính xác `1/240` tại ngưỡng `30` (`--ticks` chạm trước không ghi file) | [`handoff_gather.jsonl`](../proof/phase-3/handoff_gather.jsonl) · [`handoff_inventory.json`](../proof/phase-3/handoff_inventory.json) · [`handoff_quan.jsonl`](../proof/phase-3/handoff_quan.jsonl) · [`test_output.txt`](../proof/phase-3/test_output.txt) | **Đạt** — `fresh: 99.99166666666666` trong kho khớp `99.992` trên `gather_end` và tick 0 `quan`; ca round-trip ngưỡng `30 + 1/120` ươn đúng tick `3` ở quán. |
| `AC-P3-03` | `gather` hao `0.5/s` từ bước sau khi nhặt/bắt (`fresh = 100`), ngưỡng `30` phát `spoiled` đúng 1 lần theo `id_key`, hàng ươn vẫn chiếm chỗ (`hold_full`), `pause` dừng hao | [`spoiled_threshold.jsonl`](../proof/phase-3/spoiled_threshold.jsonl) · [`test_output.txt`](../proof/phase-3/test_output.txt) (`GatherFreshnessAndSpoiledTests.*`) | **Đạt** — mẫu `fresh: 30` phát `spoiled` đúng tại tick `1` với `fresh: 29.992`. |
| `AC-P3-04` | Cấp ID `I1, I2,...` liên tục; `monster_hit` / `faint` giữ LIFO với mảng cá thể `{id, kind, fresh}` (ngất ghi kho rỗng `{"items":[]}`) | [`test_output.txt`](../proof/phase-3/test_output.txt) (`MonsterCaSauTests.*`, `GatherRulesTests.test_faint_*`) | **Đạt.** |
| `AC-P3-05` | `quan` hao `0.25/s` mọi cá thể trong `stock` (kể cả `reserved`), phát hết `spoiled` theo `id_key` **trước** khi xử lý giữ chỗ; `pause` & món đã nấu không hao | [`test_output.txt`](../proof/phase-3/test_output.txt) (`QuanFreshnessReserveAndPriceTests.*`) | **Đạt.** |
| `AC-P3-06` | Giữ chỗ theo ID tươi nhất (hòa `id_key`); khi cá thể giữ vừa ươn thì nhả toàn bộ đơn và giữ lại một lần theo `(order_tick, id bàn)`, thiếu → `unfulfillable` | [`test_output.txt`](../proof/phase-3/test_output.txt) (`QuanFreshnessReserveAndPriceTests.test_spoiled_emits_first_rereserves_by_order_and_marks_unfulfillable`) | **Đạt.** |
| `AC-P3-07` | Tiêu đúng ID giữ chỗ tại `cook_started` (`items` sắp theo `kind` rồi `id_key`), chốt `base_price = floor(price * avg_fresh / 100)`, boa áp trên `base_price` đã chốt | [`test_output.txt`](../proof/phase-3/test_output.txt) (`QuanFreshnessReserveAndPriceTests.test_reserve_priority_and_fresh_scaled_base_price_and_cooked_no_decay`) | **Đạt.** |
| `AC-P3-08` | `--mode day`: Ngày đầu giữ nguyên ID mẫu `gather.hold`, Ngày sau cấp ID mới liên tục; chuyển pha `gather → quan` cùng tick không hao thêm; kho dư `Shop` không hao | [`day2_freshness.jsonl`](../proof/phase-3/day2_freshness.jsonl) · [`test_output.txt`](../proof/phase-3/test_output.txt) (`DayModeFreshnessAndLiveTests.*`) | **Đạt.** |
| `AC-P3-09` | Live HTTP API (`/state` trả `meta.freshness`, `hold`/`stock` cá thể) & HUD (`chonoi/web/index.html`) hiển thị thanh độ tươi từng ô giỏ, cảnh báo hàng ươn đỏ & kho khả dụng trừ giữ chỗ | [`test_output.txt`](../proof/phase-3/test_output.txt) (`DayModeFreshnessAndLiveTests.test_live_server_v12_freshness_metadata`, `LiveServerTest`) · [`chonoi/web/index.html`](../../chonoi/web/index.html) | **Đạt.** |
| `AC-P3-10` | Hồi quy toàn bộ test P1–P2 còn hiệu lực & hoàn thiện tài liệu ADR-0001, `CHANGELOG.md`, `verification/phase-3.md` | [`docs/adr/0001-freshness-item-instances.md`](../adr/0001-freshness-item-instances.md) · [`CHANGELOG.md`](../../CHANGELOG.md) · [`test_output.txt`](../proof/phase-3/test_output.txt) | **Đạt (`64/64` OK).** |

## 2. Lý do cập nhật các fixture P1–P2 sang Contract v1.2

Do `[THAY THẾ]` trong TICKET-03 đổi schema kho sang mảng cá thể, đổi `customers[].reserved` sang mảng ID và đổi `base_price` theo độ tươi trung bình, các assertion ở test P1–P2 cũ được cập nhật tương ứng như sau (giữ nguyên toàn bộ hành vi không đổi):

1. [`tests/test_smoke_p1.py`](../../tests/test_smoke_p1.py):
   - Chuyển `gather.hold`, `quan.stock` và file `--inventory` sang mảng cá thể `{id, kind, fresh}`.
   - `test_inv_bad_schema_exit_2`: bổ sung khẳng định các schema kho đếm cũ (`{"items":{}}`, `{"items":{"ca_loc":1}}`) trả mã thoát `2`.
   - `test_time_ends_gather_and_keeps_hold` & `test_inv_01_gather_writes_inventory_quan_reads_it`: đối chiếu `id`, `kind` và `fresh` (sau số tick hao ở `gather`) khớp chính xác với snapshot tick 0 của `quan`.
2. [`tests/test_python_starter_units.py`](../../tests/test_python_starter_units.py):
   - `test_session_steps_gather_and_dock`: đổi `hold` từ `["ca_loc"]` sang `[{"id": "I1", "kind": "ca_loc", "fresh": 100}]`.
3. [`tests/test_phase1_rules.py`](../../tests/test_phase1_rules.py):
   - Cập nhật `hold`, `stock`, `reserved` sang schema v1.2; `faint.lost` và `cook_started.items` đối chiếu mảng cá thể.
   - `test_full_cook_ready_pick_serve_paid_cycle_and_tip_boundary`: sau 1 tick hao quán (`fresh = 99.996`), `lau_ca_linh_dien_dien` chốt `base_price = floor(120 * 23999 / 24000 / 100) = 119`, boa `floor(119 * 0.2) = 23`, tổng thu `142`, điểm `442`.
4. [`tests/test_phase2_rules.py`](../../tests/test_phase2_rules.py):
   - `test_v11_manifest_standard_values_and_gather_setup`: chấp nhận `contract_version` in `("1.1", "1.2")`.
   - Cập nhật `hold`/`stock`/`lost` sang cá thể v1.2; trong `test_ca_keo_keo_neo_inventory_handoff_and_lau_mam_in_quan`, sau 60 tick sáng + 1 tick quán, `lau_mam` chốt `base_price = 199`.
