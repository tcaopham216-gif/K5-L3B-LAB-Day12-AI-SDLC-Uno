"""Test hộp đen & đơn vị cho TICKET-03 & Test Contract v1.2 (Phase 3 — Độ tươi cá thể)."""

from fractions import Fraction
import json
import os
import unittest
import urllib.request

from chonoi.contract import load_contract
from chonoi.live import LiveGame, LiveServer
from helpers import Workdir, close, events, frames, read_jsonl, run_headless, snapshots, write_json


def it(iid, kind, fresh=100):
    return {"id": iid, "kind": kind, "fresh": fresh}


class Phase3SchemaAndExit2Tests(unittest.TestCase):
    def test_v12_manifest_freshness_and_reject_old_or_bad_inventory_exit_2(self):
        c = load_contract()
        self.assertIn(c["contract_version"], ("1.2", "1.3"))
        self.assertEqual(c["tuning"]["freshness"], {
            "initial": 100,
            "gather_decay_per_s": 0.5,
            "quan_decay_per_s": 0.25,
            "spoiled_below": 30,
        })

        with Workdir() as w:
            out = w.path("o.jsonl")
            for bad_inv in (
                {"items": {}},
                {"items": {"ca_loc": 1}},
                {"items": [{"id": "I1", "kind": "ca_loc"}]},
                {"items": [{"id": "I1", "kind": "ca_loc", "fresh": 100, "extra": 1}]},
                {"items": [{"id": "", "kind": "ca_loc", "fresh": 100}]},
                {"items": [{"id": "I1", "kind": "ca_loc", "fresh": 100}, {"id": "I1", "kind": "ca_linh", "fresh": 90}]},
                {"items": [{"id": "I1", "kind": "ca_loc", "fresh": True}]},
                {"items": [{"id": "I1", "kind": "ca_loc", "fresh": -0.1}]},
                {"items": [{"id": "I1", "kind": "ca_loc", "fresh": 100.1}]},
            ):
                p = write_json(w.path("inv.json"), bad_inv)
                code, _ = run_headless("--mode", "quan", "--seed", "1", "--ticks", "0", "--inventory", p, "--out", out)
                self.assertEqual(code, 2, bad_inv)
                self.assertFalse(os.path.exists(out))

            bad_scenarios = [
                {"gather": {"hold": ["ca_loc"]}},
                {"gather": {"hold": [it("I1", "ca_loc"), it("I1", "bong_sung")]}},
                {"quan": {"stock": {"ca_loc": 1}}},
                {"quan": {"stock": [it("I1", "ca_loc"), it("I1", "ca_loc")]}},
                {"quan": {"stock": [it("I1", "ca_loc", 100)],
                          "customers": [{"id": "C1", "table_id": "T1", "dish_id": "ca_loc_nuong_trui", "reserved": {"ca_loc": 1}}]}},
                {"quan": {"stock": [it("I1", "ca_loc", 29.5)],
                          "customers": [{"id": "C1", "table_id": "T1", "dish_id": "ca_loc_nuong_trui", "reserved": ["I1"]}]}},
                {"quan": {"stock": [it("I1", "ca_loc", 100)],
                          "customers": [{"id": "C1", "table_id": "T1", "dish_id": "ca_loc_nuong_trui", "reserved": ["I99"]}]}},
                {"quan": {"stock": [it("I1", "ca_loc", 100)],
                          "customers": [
                              {"id": "C1", "table_id": "T1", "dish_id": "ca_loc_nuong_trui", "reserved": ["I1"]},
                              {"id": "C2", "table_id": "T2", "dish_id": "ca_loc_nuong_trui", "reserved": ["I1"]},
                          ]}},
                {"quan": {"stock": [it("I1", "bong_sung", 100)],
                          "customers": [{"id": "C1", "table_id": "T1", "dish_id": "ca_loc_nuong_trui", "reserved": ["I1"]}]}},
                {"quan": {"stock": [it("I1", "ca_loc", 100)],
                          "customers": [{"id": "C1", "table_id": "T1", "dish_id": "ca_loc_nuong_trui",
                                         "order_status": "unfulfillable", "reserved": ["I1"]}]}},
            ]
            for idx, obj in enumerate(bad_scenarios):
                scp = write_json(w.path(f"bs_{idx}.json"), obj)
                mode = "gather" if "gather" in obj else "quan"
                code, _ = run_headless("--mode", mode, "--seed", "1", "--ticks", "0", "--scenario", scp, "--out", out)
                self.assertEqual(code, 2, f"case {idx}: {obj}")
                self.assertFalse(os.path.exists(out))


class GatherFreshnessAndSpoiledTests(unittest.TestCase):
    def test_spoiled_threshold_30_once_sorted_by_id_and_pause_freezes_decay(self):
        with Workdir() as w:
            # Sample chuẩn trong TICKET-03 + kiểm nhiều cá thể cùng vượt ngưỡng phát theo id_key
            sc = write_json(w.path("sc.json"), {
                "gather": {
                    "hold": [it("I10", "bong_sung", 30), it("I1", "ca_linh", 30), it("I2", "ca_loc", 30)],
                    "random_fish": False,
                    "monsters": [],
                }
            })
            inp = write_json(w.path("in.json"), frames(
                {"tick": 1, "pause": True},
                {"tick": 4, "pause": False},
                {"tick": 5, "pause": True},
            ))
            out = w.path("o.jsonl")
            code, err = run_headless("--mode", "gather", "--seed", "1", "--ticks", "8", "--scenario", sc,
                                     "--inputs", inp, "--snapshot-every", "1", "--out", out)
            self.assertEqual(code, 0, err)
            rows = read_jsonl(out)
            sp = events(rows, "spoiled")
            self.assertEqual(len(sp), 3)
            self.assertEqual([e["tick"] for e in sp], [1, 1, 1])
            self.assertEqual([e["data"] for e in sp], [
                {"item_id": "I1", "kind": "ca_linh", "location": "hold"},
                {"item_id": "I2", "kind": "ca_loc", "location": "hold"},
                {"item_id": "I10", "kind": "bong_sung", "location": "hold"},
            ])
            snaps = {r["tick"]: r for r in snapshots(rows)}
            # Pause ở tick 1..5 giữ nguyên độ tươi từ tick 1 sang tick 5
            self.assertEqual(snaps[5]["state"], "paused")
            self.assertEqual(snaps[5]["hold"], snaps[1]["hold"])
            # Resume ở tick 6 -> hao tiếp 1 bước
            self.assertLess(snaps[6]["hold"][0]["fresh"], snaps[5]["hold"][0]["fresh"])

    def test_spoiled_keeps_slot_and_roundtrip_handoff_preserves_threshold_30(self):
        with Workdir() as w:
            # 1) Hàng ươn vẫn chiếm chỗ (hold đủ 12) + hàng mới lấy = 100 và hao từ bước sau
            full_hold = [it(f"I{i}", "ca_linh", 10) for i in range(1, 13)]
            sc_full = write_json(w.path("full.json"), {
                "gather": {
                    "player": {"pos": [12, 0]},
                    "hold": full_hold,
                    "random_fish": False,
                    "monsters": [],
                }
            })
            inp_full = write_json(w.path("ifull.json"), frames({"tick": 0, "interact": True}))
            out_full = w.path("ofull.jsonl")
            code, err = run_headless("--mode", "gather", "--seed", "1", "--ticks", "2", "--scenario", sc_full,
                                     "--inputs", inp_full, "--out", out_full)
            self.assertEqual(code, 0, err)
            self.assertEqual(events(read_jsonl(out_full), "hold_full")[0]["data"]["free"], 0)

            # 2) Giữ ngưỡng 30 chính xác qua file kho: bắt đầu ở 30 + 1/60 = 30.016666666666666,
            # gather chạy 1 bước cập bến mất 1/120 -> xuất inv = 30 + 1/120 = 30.008333...
            # quan chạy từng bước mất 1/240: tick 1 = 30+1/240, tick 2 = 30, tick 3 = 29+239/240 (< 30) -> spoiled đúng tick 3!
            val_start = float(Fraction(30) + Fraction(1, 60))
            sc_rt = write_json(w.path("sc_rt.json"), {
                "gather": {
                    "hold": [it("I1", "ca_loc", val_start)],
                    "random_fish": False,
                    "monsters": [],
                }
            })
            inp_dock = write_json(w.path("idock.json"), frames({"tick": 0, "interact": True}))
            inv = w.path("inv.json")
            out_g = w.path("g.jsonl")
            code, err = run_headless("--mode", "gather", "--seed", "1", "--ticks", "5", "--scenario", sc_rt,
                                     "--inputs", inp_dock, "--inventory-out", inv, "--out", out_g)
            self.assertEqual(code, 0, err)
            out_q = w.path("q.jsonl")
            sc_q = write_json(w.path("sq.json"), {"quan": {"random_customers": False, "time_left_ticks": 20}})
            code, err = run_headless("--mode", "quan", "--seed", "1", "--ticks", "5", "--inventory", inv,
                                     "--scenario", sc_q, "--snapshot-every", "1", "--out", out_q)
            self.assertEqual(code, 0, err)
            sp_q = events(read_jsonl(out_q), "spoiled")
            self.assertEqual(len(sp_q), 1)
            self.assertEqual(sp_q[0]["tick"], 3)
            self.assertEqual(sp_q[0]["data"], {"item_id": "I1", "kind": "ca_loc", "location": "stock"})


class QuanFreshnessReserveAndPriceTests(unittest.TestCase):
    def test_spoiled_emits_first_rereserves_by_order_and_marks_unfulfillable(self):
        with Workdir() as w:
            # Hai đơn C1 (T1) và C2 (T2) cùng giữ cá thể sắp ươn ngay tick 1 (30.0), cộng 1 cá thể dự phòng I5 (95.0):
            # - Ở tick 1, cả I1 và I3 đều vượt ngưỡng 30 -> phát 2 event spoiled theo id (I1 trước I3) RỒI MỚI xử lý đơn!
            # - C1 (T1) nhả [I1, I2] và giữ lại thành công [I2, I5]
            # - C2 (T2) nhả [I3, I4] và hết ca_loc -> chuyển unfulfillable, I4 được trả về kho rỗi!
            # - C3 (T3) giữ thừa không bị ươn giữ nguyên; sau đó thử spawn ở T4 dùng được I4 + ca_loc nếu có.
            sc = write_json(w.path("sc.json"), {
                "quan": {
                    "stock": [
                        it("I1", "ca_loc", 30),
                        it("I2", "bong_dien_dien", 80),
                        it("I3", "ca_loc", 30),
                        it("I4", "bong_dien_dien", 85),
                        it("I5", "ca_loc", 95),
                    ],
                    "customers": [
                        {"id": "C2", "table_id": "T2", "dish_id": "canh_chua_ca_loc", "order_tick": 0, "reserved": ["I3", "I4"]},
                        {"id": "C1", "table_id": "T1", "dish_id": "canh_chua_ca_loc", "order_tick": 0, "reserved": ["I1", "I2"]},
                    ],
                    "random_customers": False,
                    "time_left_ticks": 100,
                }
            })
            out = w.path("o.jsonl")
            code, err = run_headless("--mode", "quan", "--seed", "1", "--ticks", "2", "--scenario", sc,
                                     "--snapshot-every", "1", "--out", out)
            self.assertEqual(code, 0, err)
            rows = read_jsonl(out)
            sp = events(rows, "spoiled")
            self.assertEqual([e["data"]["item_id"] for e in sp], ["I1", "I3"])
            s1 = snapshots(rows)[1]
            c1 = next(c for c in s1["customers"] if c["id"] == "C1")
            c2 = next(c for c in s1["customers"] if c["id"] == "C2")
            self.assertEqual(c1["order_status"], "reserved")
            self.assertEqual(c1["reserved"], ["I2", "I5"])  # Khi C1 xử lý (T1 trước T2), C2 chưa nhả I4 nên C1 giữ lại [I2, I5]
            self.assertEqual(c2["order_status"], "unfulfillable")
            self.assertEqual(c2["reserved"], [])

    def test_reserve_priority_and_fresh_scaled_base_price_and_cooked_no_decay(self):
        with Workdir() as w:
            # Kiểm: chọn tươi nhất rồi id nhỏ (I10 tươi 90 < I2 tươi 90 -> chọn I2; I20 tươi 95 -> ưu tiên I20 trước),
            # và chốt base_price = floor(120 * avg_fresh / 100) với món mixed freshness + boa = floor(base_price * 0.2)
            # Đặt sẵn sao cho sau 1 bước quán (trừ 1/240):
            #   3 ca_linh = 80 + 1/240 -> 80; 1 bong_dien_dien = 60 + 1/240 -> 60 => avg = (80*3+60)/4 = 75 exact -> base_price = 90!
            exact_80 = float(Fraction(80) + Fraction(1, 240))
            exact_60 = float(Fraction(60) + Fraction(1, 240))
            sc = write_json(w.path("sc.json"), {
                "quan": {
                    "player": {"pos": [2, 8]},
                    "stock": [
                        it("I10", "ca_linh", exact_80),
                        it("I2", "ca_linh", exact_80),
                        it("I20", "ca_linh", exact_80),
                        it("I1", "ca_linh", 40),
                        it("I9", "bong_dien_dien", exact_60),
                    ],
                    "tables": [{"id": "T1", "pos": [3.2, 8]}],
                    "customers": [{"id": "C1", "table_id": "T1", "dish_id": "lau_ca_linh_dien_dien", "order_tick": 0}],
                    "random_customers": False,
                    "time_left_ticks": 1400,
                }
            })
            inp = write_json(w.path("in.json"), frames(
                {"tick": 0, "interact": True},
                {"tick": 1, "interact": False},
                {"tick": 601, "interact": True},
                {"tick": 602, "interact": False, "move": [1, 0]},
                {"tick": 625, "move": [0, 0], "interact": True},
            ))
            out = w.path("p.jsonl")
            code, err = run_headless("--mode", "quan", "--seed", "1", "--ticks", "1300", "--scenario", sc,
                                     "--inputs", inp, "--out", out)
            self.assertEqual(code, 0, err)
            rows = read_jsonl(out)
            cs = events(rows, "cook_started")[0]["data"]
            self.assertEqual(cs["base_price"], 90)
            # Items phải sắp theo kind rồi id_key: bong_dien_dien (I9), ca_linh (I2, I10, I20 - không lấy I1 vì I1 chỉ 40)
            self.assertEqual([(x["kind"], x["id"]) for x in cs["items"]], [
                ("bong_dien_dien", "I9"),
                ("ca_linh", "I2"),
                ("ca_linh", "I10"),
                ("ca_linh", "I20"),
            ])
            sv = events(rows, "served")[0]["data"]
            self.assertEqual(sv["base_price"], 90)
            self.assertEqual(sv["tip"], 18)
            self.assertEqual(rows[-1]["money"], 108)
            self.assertEqual(rows[-1]["score"], 108 + 300)


class DayModeFreshnessAndLiveTests(unittest.TestCase):
    def test_day_id_continuity_no_handoff_decay_and_shop_no_decay(self):
        with Workdir() as w:
            # Day 1: hold có I1, thu thêm 1 nút N1 -> thành I2. Cập bến -> chuyển sang quán ở cùng tick KHÔNG hao thêm độ tươi!
            # Shop 5 tick: stock giữ nguyên độ tươi không hao!
            # Day 2: template hold [I1] được cấp id mới tiếp nối (I3), còn thu N1 thành I4!
            sc = write_json(w.path("sc.json"), {
                "gather": {
                    "player": {"pos": [12, 0]},
                    "hold": [it("I1", "ca_loc", 100)],
                    "random_fish": False,
                    "monsters": [],
                    "time_left_ticks": 3,
                },
                "quan": {"time_left_ticks": 2, "random_customers": False},
            })
            inp = write_json(w.path("in.json"), frames(
                {"tick": 0, "interact": True},  # N1 -> I2
                {"tick": 5, "shop_done": True}, # đóng Shop Day 1
                {"tick": 6, "shop_done": False},
                {"tick": 12, "shop_done": True},
            ))
            out = w.path("d2.jsonl")
            code, err = run_headless("--mode", "day", "--seed", "1", "--days", "2", "--ticks", "30",
                                     "--scenario", sc, "--inputs", inp, "--snapshot-every", "1", "--out", out)
            self.assertEqual(code, 0, err)
            rows = read_jsonl(out)
            snaps = {r["tick"]: r for r in snapshots(rows)}
            # Day 1 gather_end ở tick 3 chuyển sang quan cùng tick 3: kiểm stock ở tick 3 == inventory lúc end!
            g1_end = [e for e in events(rows, "gather_end") if e["day"] == 1][0]["data"]["inventory"]["items"]
            self.assertEqual([x["id"] for x in g1_end], ["I1", "I2"])
            self.assertEqual(snaps[3]["phase"], "quan")
            self.assertEqual(snaps[3]["stock"], g1_end)

            # Quan kết thúc ở tick 5 -> vào Shop tick 5, giữ sang tick 6 nếu chưa đóng -> kiểm không hao trong Shop
            self.assertEqual(snaps[5]["phase"], "shop")
            shop_end_snap = next(s for s in snapshots(rows) if s["day"] == 1 and s["phase"] == "shop")
            # Day 2 gather tick 6 bắt đầu với I3 (template hold) thay vì I1
            d2_g = next(s for s in snapshots(rows) if s["day"] == 2 and s["phase"] == "gather" and s["phase_tick"] == 0)
            self.assertEqual([x["id"] for x in d2_g["hold"]], ["I3"])

            # Kiểm riêng Shop không hao qua nhiều tick bằng sc2
            sc2 = write_json(w.path("sc2.json"), {
                "gather": {"hold": [it("I1", "ca_loc", 90)], "time_left_ticks": 1, "random_fish": False, "monsters": []},
                "quan": {"time_left_ticks": 1, "random_customers": False},
            })
            out2 = w.path("dshop.jsonl")
            code, err = run_headless("--mode", "day", "--seed", "1", "--days", "1", "--ticks", "120",
                                     "--scenario", sc2, "--snapshot-every", "1", "--out", out2)
            self.assertEqual(code, 0, err)
            sn2 = snapshots(read_jsonl(out2))
            shop_snaps = [s for s in sn2 if s["phase"] == "shop"]
            self.assertGreater(len(shop_snaps), 10)
            self.assertEqual(shop_snaps[0]["stock"], shop_snaps[-1]["stock"])

    def test_live_server_v12_freshness_metadata(self):
        tuning = load_contract()["tuning"]
        sc = {"hold": [it("I1", "ca_loc", 80)], "random_fish": False, "monsters": []}
        server = LiveServer(LiveGame("gather", tuning, sc, 1), port=0)
        server.start()
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{server.port}/state", timeout=5) as r:
                st = json.loads(r.read())
            self.assertEqual(st["meta"]["freshness"], tuning["freshness"])
            self.assertIsInstance(st["hold"], list)
            self.assertEqual(st["hold"][0]["id"], "I1")
        finally:
            server.stop()


if __name__ == "__main__":
    unittest.main()
