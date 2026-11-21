"""Test hộp đen đầy đủ cho PRD-0 & Test Contract v1.0 (Phase 1): gather, quan và kiểm lỗi mã 2."""

import json
import os
import unittest

from helpers import Workdir, events, frames, read_jsonl, run_headless, snapshots, write_json


def item(iid, kind, fresh=100):
    return {"id": iid, "kind": kind, "fresh": fresh}


class GatherRulesTests(unittest.TestCase):
    def test_dive_and_surface_events(self):
        with Workdir() as w:
            sc = write_json(w.path("sc.json"), {"gather": {"player": {"pos": [20, 0.4]}, "random_fish": False}})
            inp = write_json(w.path("in.json"), frames(
                {"tick": 0, "move": [0, 1]},
                {"tick": 15, "move": [0, -1]},
            ))
            out = w.path("o.jsonl")
            code, err = run_headless("--mode", "gather", "--seed", "1", "--ticks", "35", "--scenario", sc,
                                     "--inputs", inp, "--snapshot-every", "1", "--out", out)
            self.assertEqual(code, 0, err)
            rows = read_jsonl(out)
            dives = events(rows, "dive")
            surfs = events(rows, "surface")
            self.assertGreaterEqual(len(dives), 1)
            self.assertGreaterEqual(len(surfs), 1)
            self.assertGreater(dives[0]["data"]["pos"][1], 0.5)
            self.assertLessEqual(surfs[0]["data"]["pos"][1], 0.5)

    def test_oxygen_drain_refill_and_empty(self):
        with Workdir() as w:
            sc = write_json(w.path("sc.json"), {
                "gather": {"player": {"pos": [20, 1.0], "oxygen_ticks": 2}, "random_fish": False}
            })
            inp = write_json(w.path("in.json"), frames(
                {"tick": 0, "move": [0, 0]},
                {"tick": 2, "move": [0, -1]},
            ))
            out = w.path("o.jsonl")
            code, err = run_headless("--mode", "gather", "--seed", "1", "--ticks", "25", "--scenario", sc,
                                     "--inputs", inp, "--snapshot-every", "1", "--out", out)
            self.assertEqual(code, 0, err)
            rows = read_jsonl(out)
            snaps = {r["tick"]: r for r in snapshots(rows)}
            self.assertEqual(snaps[1]["player"]["oxygen_ticks"], 1)
            self.assertEqual(snaps[2]["player"]["oxygen_ticks"], 0)
            self.assertEqual(snaps[2]["player"]["zero_oxy_ticks"], 1)
            empty_evs = events(rows, "oxygen_empty")
            self.assertEqual(len(empty_evs), 1)
            self.assertEqual(empty_evs[0]["tick"], 2)
            self.assertEqual(empty_evs[0]["data"], {"oxygen_ticks": 0})
            surf_evs = events(rows, "surface")
            self.assertEqual(len(surf_evs), 1)
            st = surf_evs[0]["tick"]
            self.assertEqual(snaps[st]["player"]["zero_oxy_ticks"], 0)
            self.assertEqual(snaps[st]["player"]["oxygen_ticks"], 6)

    def test_choke_at_t_plus_59_and_surface_avoids_choke(self):
        with Workdir() as w:
            sc = write_json(w.path("sc.json"), {
                "gather": {"player": {"pos": [20, 5.0], "oxygen_ticks": 1, "zero_oxy_ticks": 0, "hp": 3},
                           "random_fish": False}
            })
            out = w.path("o1.jsonl")
            code, err = run_headless("--mode", "gather", "--seed", "1", "--ticks", "65", "--scenario", sc,
                                     "--snapshot-every", "1", "--out", out)
            self.assertEqual(code, 0, err)
            rows = read_jsonl(out)
            self.assertEqual([e["tick"] for e in events(rows, "oxygen_empty")], [1])
            chokes = events(rows, "choke")
            self.assertEqual(len(chokes), 1)
            self.assertEqual(chokes[0]["tick"], 60)  # t + 59 với t = 1
            self.assertEqual(chokes[0]["data"], {"hp": 2})

            # Nổi lên đúng bước đáng lẽ ngạt -> hồi oxy và không ngạt
            sc2 = write_json(w.path("sc2.json"), {
                "gather": {
                    "player": {"pos": [20, 0.55], "vel": [0, -3.0], "oxygen_ticks": 0, "zero_oxy_ticks": 59, "hp": 3},
                    "random_fish": False,
                }
            })
            inp2 = write_json(w.path("in2.json"), frames({"tick": 0, "move": [0, -1]}))
            out2 = w.path("o2.jsonl")
            code, err = run_headless("--mode", "gather", "--seed", "1", "--ticks", "3", "--scenario", sc2,
                                     "--inputs", inp2, "--snapshot-every", "1", "--out", out2)
            self.assertEqual(code, 0, err)
            rows2 = read_jsonl(out2)
            self.assertEqual(events(rows2, "choke"), [])
            self.assertEqual(len(events(rows2, "surface")), 1)
            self.assertEqual(snapshots(rows2)[-1]["player"]["hp"], 3)

    def test_faint_drops_lifo_and_writes_empty_inventory(self):
        with Workdir() as w:
            sc = write_json(w.path("sc.json"), {
                "gather": {
                    "player": {"pos": [20, 10.0], "oxygen_ticks": 0, "zero_oxy_ticks": 59, "hp": 1},
                    "hold": [item("I1", "ca_loc"), item("I2", "bong_sung"), item("I3", "ca_linh")],
                    "random_fish": False,
                }
            })
            inv = w.path("inv.json")
            out = w.path("o.jsonl")
            code, err = run_headless("--mode", "gather", "--seed", "1", "--ticks", "10", "--scenario", sc,
                                     "--inventory-out", inv, "--out", out)
            self.assertEqual(code, 0, err)
            rows = read_jsonl(out)
            self.assertEqual([r["name"] for r in events(rows)], ["choke", "faint", "gather_end"])
            self.assertEqual(events(rows, "faint")[0]["data"], {
                "cause": "choke",
                "lost": [item("I3", "ca_linh", 99.992), item("I2", "bong_sung", 99.992), item("I1", "ca_loc", 99.992)],
                "hp": 0,
            })
            self.assertEqual(events(rows, "gather_end")[0]["data"], {
                "reason": "fainted",
                "inventory": {"items": []},
            })
            self.assertEqual(snapshots(rows)[-1]["hold"], [])
            self.assertEqual(rows[-1]["reason"], "fainted")
            with open(inv, encoding="utf-8") as f:
                self.assertEqual(json.load(f), {"items": []})

    def test_harvest_ready_regrow_and_hold_full(self):
        with Workdir() as w:
            sc = write_json(w.path("sc.json"), {
                "gather": {
                    "player": {"pos": [20, 0]},
                    "nodes": [
                        {"id": "N10", "kind": "bong_dien_dien", "pos": [22, 0], "regrow_ticks": 0},
                        {"id": "N2", "kind": "bong_sung", "pos": [22, 0], "regrow_ticks": 1},
                    ],
                    "random_fish": False,
                }
            })
            # Tick 0: N2 giảm từ 1->0 phát node_regrown, rồi interact chọn N2 vì id_key("N2") < id_key("N10")
            inp = write_json(w.path("in.json"), frames(
                {"tick": 0, "interact": True},
                {"tick": 1, "interact": False},
                {"tick": 2, "interact": True},
            ))
            out = w.path("o.jsonl")
            code, err = run_headless("--mode", "gather", "--seed", "1", "--ticks", "5", "--scenario", sc,
                                     "--inputs", inp, "--snapshot-every", "1", "--out", out)
            self.assertEqual(code, 0, err)
            rows = read_jsonl(out)
            self.assertEqual(events(rows, "node_regrown")[0]["data"], {"node_id": "N2"})
            gathers = events(rows, "gather")
            self.assertEqual(len(gathers), 2)
            self.assertEqual(gathers[0]["tick"], 1)
            self.assertEqual(gathers[0]["data"], {"node_id": "N2", "kind": "bong_sung", "amount": 1})
            self.assertEqual(gathers[1]["data"], {"node_id": "N10", "kind": "bong_dien_dien", "amount": 1})
            snaps = {r["tick"]: r for r in snapshots(rows)}
            n2 = next(n for n in snaps[1]["nodes"] if n["id"] == "N2")
            self.assertEqual(n2["regrow_ticks"], 1200)
            self.assertFalse(n2["ready"])

            # Giỏ đầy khi hái
            sc_full = write_json(w.path("full.json"), {
                "gather": {
                    "player": {"pos": [20, 0]},
                    "hold": [item(f"I{i}", "ca_loc") for i in range(1, 13)],
                    "nodes": [{"id": "N1", "kind": "bong_sung", "pos": [20, 0]}],
                    "random_fish": False,
                }
            })
            inp_full = write_json(w.path("in_full.json"), frames({"tick": 0, "interact": True}))
            out_full = w.path("o_full.jsonl")
            code, err = run_headless("--mode", "gather", "--seed", "1", "--ticks", "1", "--scenario", sc_full,
                                     "--inputs", inp_full, "--out", out_full)
            self.assertEqual(code, 0, err)
            hf = events(read_jsonl(out_full), "hold_full")
            self.assertEqual(len(hf), 1)
            self.assertEqual(hf[0]["data"], {"action": "gather", "node_id": "N1", "required": 1, "free": 0})

    def test_catch_fish_cooldown_hold_full_and_miss(self):
        with Workdir() as w:
            sc = write_json(w.path("sc.json"), {
                "gather": {
                    "player": {"pos": [20, 5]},
                    "random_fish": False,
                    "fish": [
                        {"id": "F10", "kind": "ca_loc", "pos": [22, 5]},
                        {"id": "F2", "kind": "ca_linh", "pos": [22, 5]},
                    ],
                }
            })
            # Tick 0 bắt F2 (yield 3), cd = 30. Tick 29 trượt cooldown. Tick 30 (= 1 + 30 - 1) dùng lại ở step 31.
            inp = write_json(w.path("in.json"), frames(
                {"tick": 0, "catch": True},
                {"tick": 1, "catch": False},
                {"tick": 29, "catch": True},
                {"tick": 30, "catch": False},
                {"tick": 31, "catch": True},
            ))
            # Kiểm đúng biên t + L: bắt ở bước k=0 (t=1), cd=30 -> bước k=29 (tick 30): cd 2->1 (chưa hết);
            # bước k=30 (tick 31 = t + L): cd 1->0 (dùng được!)
            inp_exact = write_json(w.path("in2.json"), frames(
                {"tick": 0, "catch": True},
                {"tick": 1, "catch": False},
                {"tick": 29, "catch": True},
                {"tick": 30, "catch": False},
            ))
            out_early = w.path("early.jsonl")
            code, err = run_headless("--mode", "gather", "--seed", "1", "--ticks", "30", "--scenario", sc,
                                     "--inputs", inp_exact, "--out", out_early)
            self.assertEqual(code, 0, err)
            self.assertEqual([e["data"]["fish_id"] for e in events(read_jsonl(out_early), "fish_caught")], ["F2"])

            inp_ok = write_json(w.path("in_ok.json"), frames(
                {"tick": 0, "catch": True},
                {"tick": 1, "catch": False},
                {"tick": 30, "catch": True},
            ))
            out_ok = w.path("ok.jsonl")
            code, err = run_headless("--mode", "gather", "--seed", "1", "--ticks", "32", "--scenario", sc,
                                     "--inputs", inp_ok, "--out", out_ok)
            self.assertEqual(code, 0, err)
            caught = events(read_jsonl(out_ok), "fish_caught")
            self.assertEqual([e["data"]["fish_id"] for e in caught], ["F2", "F10"])
            self.assertEqual(caught[0]["tick"], 1)
            self.assertEqual(caught[1]["tick"], 31)
            self.assertEqual(caught[0]["data"]["yield"], 3)

            # Thiếu chỗ: F1 gần hơn cần 3 ô (còn 2), F2 cần 1 ô -> không thử F2, giữ F1 và cooldown = 0
            sc_hf = write_json(w.path("sc_hf.json"), {
                "gather": {
                    "player": {"pos": [20, 5]},
                    "hold": [item(f"I{i}", "bong_sung") for i in range(1, 11)],
                    "random_fish": False,
                    "fish": [
                        {"id": "F1", "kind": "ca_linh", "pos": [20, 5]},
                        {"id": "F2", "kind": "ca_loc", "pos": [21, 5]},
                    ],
                }
            })
            inp_hf = write_json(w.path("in_hf.json"), frames({"tick": 0, "catch": True}))
            out_hf = w.path("hf.jsonl")
            code, err = run_headless("--mode", "gather", "--seed", "1", "--ticks", "1", "--scenario", sc_hf,
                                     "--inputs", inp_hf, "--out", out_hf)
            self.assertEqual(code, 0, err)
            rows_hf = read_jsonl(out_hf)
            self.assertEqual(events(rows_hf, "fish_caught"), [])
            self.assertEqual(events(rows_hf, "hold_full")[0]["data"], {
                "action": "catch", "fish_id": "F1", "required": 3, "free": 2,
            })
            self.assertEqual(snapshots(rows_hf)[-1]["player"]["catch_cd_ticks"], 0)
            self.assertEqual(len(snapshots(rows_hf)[-1]["fish"]), 2)

    def test_last_tick_docked_and_harvest_on_time(self):
        with Workdir() as w:
            # E đúng mép bến ở bước cuối vẫn cho docked
            sc_dock = write_json(w.path("d.json"), {
                "gather": {"player": {"pos": [5, 0]}, "hold": [item("I1", "ca_loc")], "time_left_ticks": 1, "random_fish": False}
            })
            inp = write_json(w.path("in.json"), frames({"tick": 0, "interact": True}))
            inv = w.path("inv.json")
            out = w.path("o.jsonl")
            code, err = run_headless("--mode", "gather", "--seed", "1", "--ticks", "5", "--scenario", sc_dock,
                                     "--inputs", inp, "--inventory-out", inv, "--out", out)
            self.assertEqual(code, 0, err)
            rows = read_jsonl(out)
            self.assertEqual(events(rows, "gather_end")[0]["data"]["reason"], "docked")
            self.assertEqual(rows[-1]["reason"], "docked")
            with open(inv, encoding="utf-8") as f:
                saved = json.load(f)
            self.assertEqual(len(saved["items"]), 1)
            self.assertEqual(saved["items"][0]["id"], "I1")
            self.assertEqual(saved["items"][0]["kind"], "ca_loc")
            self.assertAlmostEqual(saved["items"][0]["fresh"], 99.992, places=2)

            # Hái hợp lệ ở bước cuối vẫn vào kho khi hết giờ (tươi = 100 vì hao từ bước sau)
            sc_harv = write_json(w.path("h.json"), {
                "gather": {
                    "player": {"pos": [20, 0]},
                    "nodes": [{"id": "N1", "kind": "bong_sung", "pos": [20, 0]}],
                    "time_left_ticks": 1,
                    "random_fish": False,
                }
            })
            inv2 = w.path("inv2.json")
            out2 = w.path("o2.jsonl")
            code, err = run_headless("--mode", "gather", "--seed", "1", "--ticks", "5", "--scenario", sc_harv,
                                     "--inputs", inp, "--inventory-out", inv2, "--out", out2)
            self.assertEqual(code, 0, err)
            rows2 = read_jsonl(out2)
            self.assertEqual([e["name"] for e in events(rows2)], ["gather", "gather_end"])
            self.assertEqual(events(rows2, "gather_end")[0]["data"]["reason"], "time")
            with open(inv2, encoding="utf-8") as f:
                self.assertEqual(json.load(f), {"items": [item("I1", "bong_sung", 100)]})


class QuanRulesTests(unittest.TestCase):
    def test_customer_schedule_phase_tick_and_no_dish_and_determinism(self):
        with Workdir() as w:
            sc = write_json(w.path("sc.json"), {"quan": {"stock": [], "time_left_ticks": 1200}})
            out1 = w.path("q1.jsonl")
            out2 = w.path("q2.jsonl")
            for p in (out1, out2):
                code, err = run_headless("--mode", "quan", "--seed", "99", "--ticks", "1200",
                                         "--scenario", sc, "--out", p)
                self.assertEqual(code, 0, err)
            with open(out1, "rb") as a, open(out2, "rb") as b:
                self.assertEqual(a.read(), b.read())
            rows = read_jsonl(out1)
            self.assertEqual([e["tick"] for e in events(rows, "no_dish")], [120, 1020])
            self.assertEqual(rows[-1]["reason"], "time")

            # random_customers=false tắt khách tự sinh
            sc_off = write_json(w.path("sc_off.json"), {
                "quan": {"stock": [item(f"I{i}", "ca_loc") for i in range(1, 6)],
                         "random_customers": False, "time_left_ticks": 1200}
            })
            out_off = w.path("q_off.jsonl")
            code, err = run_headless("--mode", "quan", "--seed", "1", "--ticks", "1200",
                                     "--scenario", sc_off, "--out", out_off)
            self.assertEqual(code, 0, err)
            rows_off = read_jsonl(out_off)
            self.assertEqual(events(rows_off, "customer_arrived"), [])
            self.assertEqual(events(rows_off, "no_dish"), [])

    def test_interact_priority_stove_before_table_no_fallthrough(self):
        with Workdir() as w:
            # B1 và T1 cách player đúng 0.5 m -> hòa khoảng cách -> chọn B1 (bếp trước bàn);
            # B1 đang cooking nên không tương tác được -> bỏ lượt (không fallback sang T1).
            sc = write_json(w.path("sc.json"), {
                "quan": {
                    "player": {"pos": [5.5, 5.0]},
                    "stoves": [{"id": "B1", "pos": [5.0, 5.0], "state": "cooking",
                                "dish": {"order_id": "C2", "dish_id": "goi_bong_sung", "base_price": 40},
                                "cook_ticks_left": 100}],
                    "tables": [{"id": "T1", "pos": [6.0, 5.0]}],
                    "hand": {"order_id": "C1", "dish_id": "ca_loc_nuong_trui", "base_price": 60},
                    "customers": [{
                        "id": "C1", "table_id": "T1", "dish_id": "ca_loc_nuong_trui",
                        "order_status": "assigned", "patience_ticks_left": 3000,
                    }, {
                        "id": "C2", "table_id": "T2",  # không có T2 -> dùng scenario riêng chỉ có C1
                    }] if False else [{
                        "id": "C1", "table_id": "T1", "dish_id": "ca_loc_nuong_trui",
                        "order_status": "assigned", "patience_ticks_left": 3000,
                    }],
                    "random_customers": False,
                }
            })
            # Đổi B1 sang idle (nhưng không có khách reserved) để vẫn có đúng 1 khách C1 assigned
            sc = write_json(w.path("sc.json"), {
                "quan": {
                    "player": {"pos": [5.5, 5.0]},
                    "stoves": [{"id": "B1", "pos": [5.0, 5.0], "state": "idle"}],
                    "tables": [{"id": "T1", "pos": [6.0, 5.0]}],
                    "hand": {"order_id": "C1", "dish_id": "ca_loc_nuong_trui", "base_price": 60},
                    "customers": [{
                        "id": "C1", "table_id": "T1", "dish_id": "ca_loc_nuong_trui",
                        "order_status": "assigned", "patience_ticks_left": 3000,
                    }],
                    "random_customers": False,
                }
            })
            inp = write_json(w.path("in.json"), frames({"tick": 0, "interact": True}))
            out = w.path("o.jsonl")
            code, err = run_headless("--mode", "quan", "--seed", "1", "--ticks", "2", "--scenario", sc,
                                     "--inputs", inp, "--out", out)
            self.assertEqual(code, 0, err)
            self.assertEqual(events(read_jsonl(out), "served"), [])

            # Nếu T1 gần hơn một chút -> chọn T1 và served
            sc2 = write_json(w.path("sc2.json"), {
                "quan": {
                    "player": {"pos": [5.6, 5.0]},
                    "stoves": [{"id": "B1", "pos": [5.0, 5.0], "state": "idle"}],
                    "tables": [{"id": "T1", "pos": [6.0, 5.0]}],
                    "hand": {"order_id": "C1", "dish_id": "ca_loc_nuong_trui", "base_price": 60},
                    "customers": [{
                        "id": "C1", "table_id": "T1", "dish_id": "ca_loc_nuong_trui",
                        "order_status": "assigned", "patience_ticks_left": 3000,
                    }],
                    "random_customers": False,
                }
            })
            out2 = w.path("o2.jsonl")
            code, err = run_headless("--mode", "quan", "--seed", "1", "--ticks", "2", "--scenario", sc2,
                                     "--inputs", inp, "--out", out2)
            self.assertEqual(code, 0, err)
            self.assertEqual(len(events(read_jsonl(out2), "served")), 1)

    def test_full_cook_ready_pick_serve_paid_cycle_and_tip_boundary(self):
        with Workdir() as w:
            # Khách C1 gọi lẩu (cook_s=10 -> 600 ticks, price=120), còn đủ kiên nhẫn đúng biên 1800 sau khi trừ bước serve
            # Bắt đầu ở pos B1 [2, 8], interact tại tick 0 -> cook_started (tick 1)
            # Nấu xong ở tick 601 -> dish_ready (ready_ticks = 0), đến tick 602 ready_ticks = 1
            # Pick ở tick 602 (interact tick 601 -> step 602) -> dish_picked
            # Serve ở tick 603? Ta đặt sẵn patience để đúng tick serve sau bước 1 còn đúng 1800 -> boa = 24
            sc = write_json(w.path("sc.json"), {
                "quan": {
                    "player": {"pos": [2, 8]},
                    "stock": {"ca_linh": 3, "bong_dien_dien": 1, "ca_loc": 1},
                    "tables": [{"id": "T1", "pos": [2.5, 8]}],
                    "customers": [{
                        "id": "C1", "table_id": "T1", "dish_id": "lau_ca_linh_dien_dien",
                        "order_tick": 0, "patience_ticks_left": 2403,
                    }],
                    "random_customers": False,
                }
            })
            # Player đứng ở [2.0, 8.0] (dist B1=0, dist T1=0.5 -> B1 luôn ưu tiên hơn T1, ta dịch sang [2.5, 8] khi phục vụ)
            inp = write_json(w.path("in.json"), frames(
                {"tick": 0, "interact": True},       # step 1: cook_started
                {"tick": 1, "interact": False},
                {"tick": 601, "interact": True},     # step 602: ready_ticks lúc này đã thành 1, dish_picked
                {"tick": 602, "interact": False},
                {"tick": 602, "move": [1, 0]},       # di chuyển về phía T1 (đứng hẳn tại [2.5, 8] -> T1 gần hơn)
            ))
            # Thay vì canh di chuyển phức tạp, đặt B1 [2,8], T1 [3,8], player [2,8] đi tới [3,8] sau khi lấy món:
            sc = write_json(w.path("sc_clean.json"), {
                "quan": {
                    "player": {"pos": [2, 8]},
                    "stock": [
                        item("I1", "ca_linh"), item("I2", "ca_linh"), item("I3", "ca_linh"),
                        item("I4", "bong_dien_dien"), item("I5", "ca_loc"),
                    ],
                    "tables": [{"id": "T1", "pos": [3.2, 8]}],
                    "customers": [{
                        "id": "C1", "table_id": "T1", "dish_id": "lau_ca_linh_dien_dien",
                        "order_tick": 0, "patience_ticks_left": 2450,
                    }],
                    "random_customers": False,
                }
            })
            # Tick 602 (step 603): bắt đầu đi sang phải đến tick 620 (~1.2m), dừng ở ~3.1 -> T1 gần hơn B1
            inp_clean = write_json(w.path("in_clean.json"), frames(
                {"tick": 0, "interact": True},       # step 1: cook_started (sau 1 tick hao: fresh=99.996 -> base_price=floor(120*99.99583/100)=119)
                {"tick": 1, "interact": False},
                {"tick": 601, "interact": True},     # step 602: dish_picked
                {"tick": 602, "interact": False, "move": [1, 0]},
                {"tick": 625, "move": [0, 0], "interact": True},  # step 626: served (tip=floor(119*0.2)=23)
            ))
            out = w.path("e2e.jsonl")
            code, err = run_headless("--mode", "quan", "--seed", "1", "--ticks", "1250", "--scenario", sc,
                                     "--inputs", inp_clean, "--snapshot-every", "1", "--out", out)
            self.assertEqual(code, 0, err)
            rows = read_jsonl(out)
            snaps = {r["tick"]: r for r in snapshots(rows)}
            cs = events(rows, "cook_started")
            dr = events(rows, "dish_ready")
            dp = events(rows, "dish_picked")
            sv = events(rows, "served")
            pd = events(rows, "paid")
            self.assertEqual(len(cs), 1)
            self.assertEqual(cs[0]["data"], {
                "stove_id": "B1",
                "order_id": "C1",
                "dish_id": "lau_ca_linh_dien_dien",
                "items": [
                    item("I4", "bong_dien_dien", 99.996),
                    item("I1", "ca_linh", 99.996),
                    item("I2", "ca_linh", 99.996),
                    item("I3", "ca_linh", 99.996),
                ],
                "base_price": 119,
            })
            self.assertEqual(snaps[1]["stock"], [item("I5", "ca_loc", 99.996)])
            self.assertEqual(len(dr), 1)
            self.assertEqual(dr[0]["tick"], 601)
            self.assertEqual(snaps[601]["stoves"][0]["ready_ticks"], 0)
            self.assertEqual(len(dp), 1)
            self.assertEqual(dp[0]["tick"], 602)
            self.assertEqual(len(sv), 1)
            self.assertEqual(sv[0]["data"]["base_price"], 119)
            self.assertEqual(sv[0]["data"]["tip"], 23)
            self.assertEqual(len(pd), 1)
            self.assertEqual(pd[0]["data"], {
                "order_id": "C1", "table_id": "T1", "base_price": 119,
                "tip": 23, "amount": 142, "reason": "finished_eating",
            })
            self.assertEqual(rows[-1]["money"], 142)
            self.assertEqual(rows[-1]["earned"], 142)
            self.assertAlmostEqual(rows[-1]["reputation"], 3.2, places=3)
            self.assertEqual(rows[-1]["score"], 142 + 100 * 3)
            self.assertIn("vel", snaps[0]["player"])

            # Kiểm chính xác biên 1800 vs 1799
            for start_pat, want_tip, want_rep in ((1801, 12, 3.2), (1800, 0, 3.0)):
                sc_b = write_json(w.path(f"b_{start_pat}.json"), {
                    "quan": {
                        "player": {"pos": [9, 2]},
                        "hand": {"order_id": "C1", "dish_id": "ca_loc_nuong_trui", "base_price": 60},
                        "customers": [{
                            "id": "C1", "table_id": "T1", "dish_id": "ca_loc_nuong_trui",
                            "order_status": "assigned", "patience_ticks_left": start_pat,
                        }],
                        "random_customers": False,
                    }
                })
                inp_b = write_json(w.path(f"ib_{start_pat}.json"), frames({"tick": 0, "interact": True}))
                out_b = w.path(f"ob_{start_pat}.jsonl")
                code, err = run_headless("--mode", "quan", "--seed", "1", "--ticks", "610", "--scenario", sc_b,
                                         "--inputs", inp_b, "--out", out_b)
                self.assertEqual(code, 0, err)
                rb = read_jsonl(out_b)
                self.assertEqual(events(rb, "served")[0]["data"]["tip"], want_tip)
                self.assertEqual(events(rb, "paid")[0]["data"]["amount"], 60 + want_tip)
                self.assertAlmostEqual(rb[-1]["reputation"], want_rep, places=3)

    def test_served_on_patience_zero_and_closing_and_rep_clamping(self):
        with Workdir() as w:
            # Phục vụ đúng tick patience về 0 -> vẫn hợp lệ và không mất uy tín
            sc = write_json(w.path("sc.json"), {
                "quan": {
                    "player": {"pos": [9, 2]},
                    "hand": {"order_id": "C1", "dish_id": "ca_loc_nuong_trui", "base_price": 60},
                    "customers": [{
                        "id": "C1", "table_id": "T1", "dish_id": "ca_loc_nuong_trui",
                        "order_status": "assigned", "patience_ticks_left": 1,
                    }],
                    "reputation": 4.9,
                    "random_customers": False,
                }
            })
            inp = write_json(w.path("in.json"), frames({"tick": 0, "interact": True}))
            out = w.path("o.jsonl")
            code, err = run_headless("--mode", "quan", "--seed", "1", "--ticks", "610", "--scenario", sc,
                                     "--inputs", inp, "--out", out)
            self.assertEqual(code, 0, err)
            rows = read_jsonl(out)
            self.assertEqual(events(rows, "customer_left"), [])
            self.assertEqual(events(rows, "served")[0]["data"]["patience_ticks_left"], 0)
            self.assertEqual(events(rows, "paid")[0]["data"]["tip"], 0)

            # Phục vụ đúng bước cuối ca + clamping reputation trần 5.0
            sc_close = write_json(w.path("sc_close.json"), {
                "quan": {
                    "player": {"pos": [9, 2]},
                    "hand": {"order_id": "C1", "dish_id": "ca_loc_nuong_trui", "base_price": 60},
                    "customers": [{
                        "id": "C1", "table_id": "T1", "dish_id": "ca_loc_nuong_trui",
                        "order_status": "assigned", "patience_ticks_left": 3600,
                    }],
                    "time_left_ticks": 1,
                    "reputation": 4.9,
                    "random_customers": False,
                }
            })
            out_c = w.path("oc.jsonl")
            code, err = run_headless("--mode", "quan", "--seed", "1", "--ticks", "5", "--scenario", sc_close,
                                     "--inputs", inp, "--out", out_c)
            self.assertEqual(code, 0, err)
            rc = read_jsonl(out_c)
            self.assertEqual([e["name"] for e in events(rc)], ["served", "paid", "quan_end"])
            self.assertEqual(events(rc, "paid")[0]["data"]["reason"], "closing")
            self.assertAlmostEqual(rc[-1]["reputation"], 5.0, places=3)
            self.assertEqual(rc[-1]["score"], 72 + 500)

    def test_customer_left_patience_and_closing_discard_without_refund(self):
        with Workdir() as w:
            sc = write_json(w.path("sc.json"), {
                "quan": {
                    "stoves": [{"id": "B1", "state": "cooking",
                                "dish": {"order_id": "C1", "dish_id": "ca_loc_nuong_trui", "base_price": 60},
                                "cook_ticks_left": 100}],
                    "customers": [{
                        "id": "C1", "table_id": "T1", "dish_id": "ca_loc_nuong_trui",
                        "order_status": "assigned", "patience_ticks_left": 1,
                    }],
                    "reputation": 0.2,
                    "random_customers": False,
                }
            })
            out = w.path("o.jsonl")
            code, err = run_headless("--mode", "quan", "--seed", "1", "--ticks", "2", "--scenario", sc,
                                     "--snapshot-every", "1", "--out", out)
            self.assertEqual(code, 0, err)
            rows = read_jsonl(out)
            left = events(rows, "customer_left")
            self.assertEqual(len(left), 1)
            self.assertEqual(left[0]["data"], {
                "order_id": "C1", "table_id": "T1", "reason": "patience", "reputation": 0.0,
            })
            last = snapshots(rows)[-1]
            self.assertEqual(last["stoves"][0]["state"], "idle")
            self.assertIsNone(last["stoves"][0]["dish"])
            self.assertEqual(last["stock"], [])
            self.assertEqual(last["customers"], [])

            # Đóng ca với khách còn chờ -> reason closing và không trừ uy tín
            sc_wait = write_json(w.path("sc_w.json"), {
                "quan": {
                    "stock": [item("I1", "ca_loc")],
                    "customers": [{"id": "C1", "table_id": "T1", "dish_id": "ca_loc_nuong_trui"}],
                    "time_left_ticks": 1,
                    "reputation": 3.0,
                    "random_customers": False,
                }
            })
            out_w = w.path("ow.jsonl")
            code, err = run_headless("--mode", "quan", "--seed", "1", "--ticks", "5", "--scenario", sc_wait,
                                     "--out", out_w)
            self.assertEqual(code, 0, err)
            rw = read_jsonl(out_w)
            self.assertEqual([e["name"] for e in events(rw)], ["customer_left", "quan_end"])
            self.assertEqual(events(rw, "customer_left")[0]["data"]["reason"], "closing")
            self.assertAlmostEqual(rw[-1]["reputation"], 3.0, places=3)


class ScenarioConflictExit2Tests(unittest.TestCase):
    def test_quan_conflicts_return_exit_2_without_output(self):
        bad_blocks = [
            # Bếp cooking với cook_ticks_left = 0
            {"stoves": [{"id": "B1", "state": "cooking",
                         "dish": {"order_id": "C1", "dish_id": "ca_loc_nuong_trui", "base_price": 60},
                         "cook_ticks_left": 0}],
             "customers": [{"id": "C1", "table_id": "T1", "dish_id": "ca_loc_nuong_trui", "order_status": "assigned"}]},
            # Bếp idle nhưng có dish
            {"stoves": [{"id": "B1", "state": "idle",
                         "dish": {"order_id": "C1", "dish_id": "ca_loc_nuong_trui", "base_price": 60}}]},
            # Món mồ côi order_id không có khách
            {"hand": {"order_id": "C99", "dish_id": "ca_loc_nuong_trui", "base_price": 60}},
            # Món trên tay lệch dish_id của khách
            {"hand": {"order_id": "C1", "dish_id": "goi_bong_sung", "base_price": 40},
             "customers": [{"id": "C1", "table_id": "T1", "dish_id": "ca_loc_nuong_trui", "order_status": "assigned"}]},
            # Trùng order_id giữa bếp và tay
            {"stoves": [{"id": "B1", "state": "ready",
                         "dish": {"order_id": "C1", "dish_id": "ca_loc_nuong_trui", "base_price": 60}}],
             "hand": {"order_id": "C1", "dish_id": "ca_loc_nuong_trui", "base_price": 60},
             "customers": [{"id": "C1", "table_id": "T1", "dish_id": "ca_loc_nuong_trui", "order_status": "assigned"}]},
            # Đơn assigned nhưng không có món nào
            {"customers": [{"id": "C1", "table_id": "T1", "dish_id": "ca_loc_nuong_trui", "order_status": "assigned"}]},
            # Đơn assigned nhưng reserved khác rỗng
            {"hand": {"order_id": "C1", "dish_id": "ca_loc_nuong_trui", "base_price": 60},
             "stock": [item("I1", "ca_loc")],
             "customers": [{"id": "C1", "table_id": "T1", "dish_id": "ca_loc_nuong_trui",
                            "order_status": "assigned", "reserved": ["I1"]}]},
            # Đơn reserved giữ sai công thức
            {"stock": [item("I1", "ca_loc"), item("I2", "ca_loc")],
             "customers": [{"id": "C1", "table_id": "T1", "dish_id": "ca_loc_nuong_trui",
                            "order_status": "reserved", "reserved": ["I1", "I2"]}]},
            # Đơn reserved giữ vượt stock trong scenario
            {"stock": [],
             "customers": [{"id": "C1", "table_id": "T1", "dish_id": "ca_loc_nuong_trui"}]},
            # Khách eating nhưng order_status != served
            {"customers": [{"id": "C1", "table_id": "T1", "dish_id": "ca_loc_nuong_trui",
                            "state": "eating", "eat_ticks_left": 100, "order_status": "assigned",
                            "base_price": 60, "tip": 0}]},
            # Khách eating nhưng eat_ticks_left = 0
            {"customers": [{"id": "C1", "table_id": "T1", "dish_id": "ca_loc_nuong_trui",
                            "state": "eating", "eat_ticks_left": 0, "base_price": 60, "tip": 0}]},
            # Khách eating thiếu base_price
            {"customers": [{"id": "C1", "table_id": "T1", "dish_id": "ca_loc_nuong_trui",
                            "state": "eating", "eat_ticks_left": 100, "tip": 0}]},
            # Đơn unfulfillable có reserved không rỗng
            {"stock": [item("I1", "ca_loc")],
             "customers": [{"id": "C1", "table_id": "T1", "dish_id": "ca_loc_nuong_trui",
                            "order_status": "unfulfillable", "reserved": ["I1"]}]},
            # reputation ngoài miền [0, 5]
            {"reputation": 5.5},
            {"reputation": -0.1},
        ]
        with Workdir() as w:
            for i, block in enumerate(bad_blocks):
                sc = write_json(w.path(f"bad_{i}.json"), {"quan": block})
                out = w.path(f"out_{i}.jsonl")
                code, _ = run_headless("--mode", "quan", "--seed", "1", "--ticks", "0", "--scenario", sc, "--out", out)
                self.assertEqual(code, 2, f"case {i} phải trả mã 2: {block}")
                self.assertFalse(os.path.exists(out), f"case {i} không được tạo file output")

            # Reserved vượt tồn kho khi cấp qua --inventory
            inv = write_json(w.path("inv.json"), {"items": []})
            sc_inv = write_json(w.path("sc_inv.json"), {
                "quan": {"customers": [{"id": "C1", "table_id": "T1", "dish_id": "ca_loc_nuong_trui"}]}
            })
            out_inv = w.path("out_inv.jsonl")
            code, _ = run_headless("--mode", "quan", "--seed", "1", "--ticks", "0",
                                   "--inventory", inv, "--scenario", sc_inv, "--out", out_inv)
            self.assertEqual(code, 2)
            self.assertFalse(os.path.exists(out_inv))


if __name__ == "__main__":
    unittest.main()
