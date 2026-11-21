"""Test hộp đen đầy đủ cho TICKET-02 & Test Contract v1.1 (Phase 2)."""

import json
import math
import os
import time
import unittest
import urllib.request

from chonoi.contract import load_contract
from chonoi.live import LiveGame, LiveServer
from helpers import Workdir, close, events, frames, read_jsonl, run_headless, snapshots, write_json


def _post_json(url, obj):
    req = urllib.request.Request(
        url, data=json.dumps(obj).encode("utf-8"), method="POST",
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=5) as r:
        return r.status, json.loads(r.read())


class Phase2TuningAndSetupTests(unittest.TestCase):
    def test_v11_manifest_standard_values_and_gather_setup(self):
        c = load_contract()
        self.assertEqual(c["contract_version"], "1.1")
        t = c["tuning"]
        g, q, m = t["gather"], t["quan"], t["menu"]
        self.assertEqual(len(g["nodes"]), 6)
        self.assertEqual({n["kind"] for n in g["nodes"]}, {"bong_dien_dien", "bong_sung", "keo_neo"})
        self.assertEqual(g["fish_yield"], {"ca_linh": 3, "ca_loc": 1, "ca_keo": 2})
        self.assertEqual(g["fish_initial"], 8)
        self.assertEqual([s["id"] for s in q["stoves"]], ["B1", "B2"])
        self.assertEqual([tb["id"] for tb in q["tables"]], ["T1", "T2", "T3", "T4"])
        self.assertEqual(len(m), 6)
        self.assertEqual(len(t["day_plan"]), 5)

        with Workdir() as w:
            out = w.path("g.jsonl")
            code, err = run_headless("--mode", "gather", "--seed", "7", "--ticks", "0", "--out", out)
            self.assertEqual(code, 0, err)
            s0 = snapshots(read_jsonl(out))[0]
            self.assertEqual(len(s0["fish"]), 8)
            pts = [tuple(f["pos"]) for f in s0["fish"]]
            self.assertEqual(len(set(pts)), 8)
            for i in range(len(pts)):
                for j in range(i + 1, len(pts)):
                    self.assertGreater(math.dist(pts[i], pts[j]), 1.0)
            self.assertTrue(all(f["age_ticks"] == 0 for f in s0["fish"]))
            self.assertEqual([x["id"] for x in s0["monsters"]], ["M1"])

    def test_ca_keo_keo_neo_inventory_handoff_and_lau_mam_in_quan(self):
        with Workdir() as w:
            sc_g = write_json(w.path("sg.json"), {
                "gather": {
                    "player": {"pos": [76, 0]},
                    "hold": ["ca_linh", "ca_linh", "bong_dien_dien"],
                    "fish": [{"id": "F1", "kind": "ca_keo", "pos": [76, 5]}],
                    "monsters": [],
                }
            })
            # Tick 0: hái N5 (keo_neo); tick 1: đi xuống d; sau 15 tick ở dưới nước: catch F1 (ca_keo x2); sau đó về bến
            # Cho đơn giản test tích hợp 2 bước: hái N5 rồi sang test cầm cá kèo về bến
            inp_g = write_json(w.path("ig.json"), frames(
                {"tick": 0, "interact": True},
                {"tick": 1, "interact": False, "move": [0, 1]},
                {"tick": 40, "move": [0, 0], "catch": True},
            ))
            inv = w.path("kho.json")
            out_g = w.path("g.jsonl")
            sc_g2 = write_json(w.path("sg2.json"), {
                "gather": {
                    "player": {"pos": [76, 0]},
                    "hold": ["ca_linh", "ca_linh", "bong_dien_dien"],
                    "fish": [{"id": "F1", "kind": "ca_keo", "pos": [76, 2]}],
                    "random_fish": False,
                    "monsters": [],
                    "time_left_ticks": 60,
                }
            })
            code, err = run_headless("--mode", "gather", "--seed", "1", "--ticks", "60", "--scenario", sc_g2,
                                     "--inputs", inp_g, "--inventory-out", inv, "--out", out_g)
            self.assertEqual(code, 0, err)
            with open(inv, encoding="utf-8") as f:
                saved = json.load(f)
            self.assertEqual(saved, {"items": {"bong_dien_dien": 1, "ca_keo": 2, "ca_linh": 2, "keo_neo": 1}})

            sc_q = write_json(w.path("sq.json"), {
                "quan": {
                    "player": {"pos": [5, 8]},
                    "customers": [{"id": "C1", "table_id": "T1", "dish_id": "lau_mam", "order_tick": 0}],
                    "random_customers": False,
                    "time_left_ticks": 1500,
                }
            })
            inp_q = write_json(w.path("iq.json"), frames(
                {"tick": 0, "interact": True},      # B2 nấu lau_mam (12s = 720 tick)
                {"tick": 1, "interact": False},
                {"tick": 725, "interact": True},    # nhấc lau_mam lên tay
            ))
            out_q = w.path("q.jsonl")
            code, err = run_headless("--mode", "quan", "--seed", "1", "--ticks", "800", "--inventory", inv,
                                     "--scenario", sc_q, "--inputs", inp_q, "--snapshot-every", "1", "--out", out_q)
            self.assertEqual(code, 0, err)
            rows = read_jsonl(out_q)
            cs = events(rows, "cook_started")
            self.assertEqual(cs[0]["data"]["stove_id"], "B2")
            self.assertEqual(cs[0]["data"]["dish_id"], "lau_mam")
            self.assertEqual(cs[0]["data"]["base_price"], 200)
            self.assertEqual(snapshots(rows)[1]["stock"], {"ca_keo": 1})


class FishSwimAndSpawnTests(unittest.TestCase):
    def test_fish_swim_turn_at_120_and_edge_corner_reflection(self):
        with Workdir() as w:
            # F1 ở giữa để đo tốc độ 1.5 m/s & đổi hướng đúng bước bơi 120 (trước khi đi)
            # F2 chạm góc [96, 3] với heading 315° -> phản xạ cả x và d thành 135°
            # F3 chạm đúng mép trái x=4 vừa khít sau 1 bước (4.025, heading 180) -> bật 0° ngay bước đó
            sc = write_json(w.path("sc.json"), {
                "gather": {
                    "fish": [
                        {"id": "F1", "kind": "ca_linh", "pos": [50, 7], "heading_deg": 0, "age_ticks": 118},
                        {"id": "F2", "kind": "ca_linh", "pos": [95.99, 3.01], "heading_deg": 315, "age_ticks": 0},
                        {"id": "F3", "kind": "ca_linh", "pos": [4.025, 6.0], "heading_deg": 180, "age_ticks": 0},
                    ],
                    "monsters": [],
                }
            })
            out = w.path("o.jsonl")
            code, err = run_headless("--mode", "gather", "--seed", "12", "--ticks", "3", "--scenario", sc,
                                     "--snapshot-every", "1", "--out", out)
            self.assertEqual(code, 0, err)
            snaps = {r["tick"]: r for r in snapshots(read_jsonl(out))}
            f1_1 = next(f for f in snaps[1]["fish"] if f["id"] == "F1")
            f1_2 = next(f for f in snaps[2]["fish"] if f["id"] == "F1")
            self.assertEqual(f1_1["age_ticks"], 119)
            self.assertAlmostEqual(f1_1["pos"][0], 50.025, places=3)
            self.assertEqual(f1_2["age_ticks"], 120)
            self.assertNotAlmostEqual(f1_2["heading_deg"], 0.0, places=2)
            # Ở tick 2 (bước bơi 120): đổi hướng TRƯỚC khi đi nên d phải thay đổi theo heading mới
            self.assertAlmostEqual(math.dist(f1_1["pos"], f1_2["pos"]), 0.025, places=3)

            f2_1 = next(f for f in snaps[1]["fish"] if f["id"] == "F2")
            self.assertAlmostEqual(f2_1["heading_deg"], 135.0, places=1)
            self.assertLessEqual(f2_1["pos"][0], 96.0)
            self.assertGreaterEqual(f2_1["pos"][1], 3.0)

            f3_1 = next(f for f in snaps[1]["fish"] if f["id"] == "F3")
            self.assertAlmostEqual(f3_1["pos"][0], 4.0, places=3)
            self.assertAlmostEqual(f3_1["heading_deg"], 0.0, places=1)

    def test_fish_spawn_schedule_360k_max_12_and_catch_before_swim(self):
        with Workdir() as w:
            # 8 đàn ban đầu -> tại tick 360 sinh đàn F9 (sau khi cá cũ bơi), cá mới đứng yên ở tick 360
            # Chạy tới 1800 tick: sinh đủ tối đa 12 đàn (F9, F10, F11, F12) và tick 1800 không sinh thêm
            out = w.path("spawn.jsonl")
            code, err = run_headless("--mode", "gather", "--seed", "3", "--ticks", "1800", "--snapshot-every", "360",
                                     "--out", out)
            self.assertEqual(code, 0, err)
            rows = read_jsonl(out)
            sp_evs = events(rows, "fish_spawned")
            self.assertEqual([e["tick"] for e in sp_evs], [360, 720, 1080, 1440])
            snaps = {r["tick"]: r for r in snapshots(rows)}
            self.assertEqual(len(snaps[360]["fish"]), 9)
            f9_at_360 = next(f for f in snaps[360]["fish"] if f["id"] == "F9")
            self.assertEqual(f9_at_360["age_ticks"], 0)
            self.assertEqual(len(snaps[1800]["fish"]), 12)

            # Bắt cá dùng vị trí TRƯỚC khi cá bơi ở tick 0
            sc_c = write_json(w.path("sc_c.json"), {
                "gather": {
                    "player": {"pos": [20.0, 5.0]},
                    "fish": [{"id": "F1", "kind": "ca_loc", "pos": [22.0, 8.0], "heading_deg": 0}],  # dist = 3.0 > 2.0
                    "monsters": [],
                }
            })
            sc_c2 = write_json(w.path("sc_c2.json"), {
                "gather": {
                    "player": {"pos": [20.0, 5.0]},
                    "fish": [{"id": "F1", "kind": "ca_linh", "pos": [22.0, 5.0], "heading_deg": 0}],  # dist = 2.0 -> sau khi bơi sẽ thành 2.025 > 2.0
                    "monsters": [],
                }
            })
            inp_c = write_json(w.path("in_c.json"), frames({"tick": 0, "catch": True}))
            out_c = w.path("c.jsonl")
            code, err = run_headless("--mode", "gather", "--seed", "1", "--ticks", "1", "--scenario", sc_c2,
                                     "--inputs", inp_c, "--out", out_c)
            self.assertEqual(code, 0, err)
            self.assertEqual(len(events(read_jsonl(out_c), "fish_caught")), 1)


class MonsterCaSauTests(unittest.TestCase):
    def test_patrol_detect_chase_exit_and_depth_clamp(self):
        with Workdir() as w:
            # Người chơi ở d = 12, x = 52 (cách M1 [60, 24] > 10m -> ban đầu patrol)
            # Sau đó bơi về [60, 14] (cách <= 10m và d >= 10) -> chase, rồi nổi lên d < 10 -> về patrol
            sc = write_json(w.path("sc.json"), {
                "gather": {
                    "player": {"pos": [60, 12]},  # cách [60, 24] đúng 12m > 10m
                    "random_fish": False,
                }
            })
            inp = write_json(w.path("in.json"), frames(
                {"tick": 0, "move": [0, 1]},   # lặn xuống sâu hơn (< 10m từ M1)
                {"tick": 45, "move": [0, -1]}, # nổi lên d < 10 để kiểm thoát chase
            ))
            out = w.path("m.jsonl")
            code, err = run_headless("--mode", "gather", "--seed", "1", "--ticks", "180", "--scenario", sc,
                                     "--inputs", inp, "--snapshot-every", "1", "--out", out)
            self.assertEqual(code, 0, err)
            snaps = snapshots(read_jsonl(out))
            self.assertEqual(snaps[1]["monsters"][0]["state"], "patrol")
            self.assertTrue(any(s["monsters"][0]["state"] == "chase" for s in snaps))
            self.assertEqual(snaps[-1]["monsters"][0]["state"], "patrol")
            self.assertGreaterEqual(snaps[-1]["monsters"][0]["pos"][1], 10.0)

    def test_hit_lifo_invuln_recoil_tie_break_and_monster_faint(self):
        with Workdir() as w:
            # Trùng tâm exact overlap -> recoil_dir phải là +x [1.0, 0.0], hồi recoil đủ 60 bước không hit ở bước 60
            sc = write_json(w.path("sc.json"), {
                "gather": {
                    "player": {"pos": [50, 20], "hp": 3},
                    "hold": ["ca_loc", "bong_sung", "keo_neo"],  # 3 món -> mất floor(3/2)=1 (keo_neo)
                    "random_fish": False,
                    "monsters": [
                        {"id": "M10", "kind": "ca_sau", "pos": [50, 20], "waypoints": [[48, 20], [52, 20]]},
                        {"id": "M2", "kind": "ca_sau", "pos": [50, 20], "waypoints": [[48, 20], [52, 20]]},
                    ],
                }
            })
            out = w.path("hit.jsonl")
            code, err = run_headless("--mode", "gather", "--seed", "1", "--ticks", "65", "--scenario", sc,
                                     "--snapshot-every", "1", "--out", out)
            self.assertEqual(code, 0, err)
            rows = read_jsonl(out)
            hits = events(rows, "monster_hit")
            # Chỉ hit 1 lần ở tick 1 chọn M2 (id_key M2 < M10); các tick sau invuln=90 nên không hit tiếp
            self.assertEqual(len(hits), 1)
            self.assertEqual(hits[0]["tick"], 1)
            self.assertEqual(hits[0]["data"], {
                "monster_id": "M2", "hp": 2, "lost": ["keo_neo"], "pos": [50.0, 20.0],
            })
            snaps = {r["tick"]: r for r in snapshots(rows)}
            m2_t1 = next(m for m in snaps[1]["monsters"] if m["id"] == "M2")
            self.assertEqual(m2_t1["state"], "recoil")
            self.assertEqual(m2_t1["recoil_dir"], [1.0, 0.0])
            self.assertEqual(m2_t1["state_ticks_left"], 60)
            m2_t61 = next(m for m in snaps[61]["monsters"] if m["id"] == "M2")
            self.assertEqual(m2_t61["state"], "patrol")
            self.assertIsNone(m2_t61["recoil_dir"])
            self.assertAlmostEqual(m2_t61["pos"][0], 52.0, places=2)

            # Kiểm faint bởi thủy quái -> mất nửa LIFO trong monster_hit, nửa còn lại LIFO trong faint, kho rỗng
            sc_f = write_json(w.path("sc_f.json"), {
                "gather": {
                    "player": {"pos": [50, 20], "hp": 1},
                    "hold": ["ca_loc", "bong_sung", "ca_linh"],
                    "random_fish": False,
                    "monsters": [
                        {"id": "M1", "kind": "ca_sau", "pos": [50, 20], "waypoints": [[50, 20], [52, 20]]},
                    ],
                }
            })
            inv = w.path("f_inv.json")
            out_f = w.path("f.jsonl")
            code, err = run_headless("--mode", "gather", "--seed", "1", "--ticks", "5", "--scenario", sc_f,
                                     "--inventory-out", inv, "--out", out_f)
            self.assertEqual(code, 0, err)
            rf = read_jsonl(out_f)
            self.assertEqual([e["name"] for e in events(rf)], ["monster_hit", "faint", "gather_end"])
            self.assertEqual(events(rf, "monster_hit")[0]["data"]["lost"], ["ca_linh"])
            self.assertEqual(events(rf, "faint")[0]["data"], {
                "cause": "monster", "lost": ["bong_sung", "ca_loc"], "hp": 0,
            })
            self.assertEqual(events(rf, "gather_end")[0]["data"], {
                "reason": "fainted", "inventory": {"items": {}},
            })
            with open(inv, encoding="utf-8") as f:
                self.assertEqual(json.load(f), {"items": {}})


class PauseAndResumeTests(unittest.TestCase):
    def test_pause_freezes_sim_tick_timers_and_ignores_actions_across_modes(self):
        with Workdir() as w:
            # Pause trong Shop của --mode day: đứng yên timer shop, bỏ qua buy khi đang pause, resume mua & đóng ngay
            sc = write_json(w.path("sc.json"), {
                "day": {"money": 200, "earned": 200},
                "gather": {"time_left_ticks": 1, "random_fish": False, "monsters": []},
                "quan": {"time_left_ticks": 1, "random_customers": False},
            })
            # Tick 0: gather hết giờ -> mở quan; Tick 1: quan hết giờ -> mở Shop (tick 2 snapshot phase=shop)
            # Tick 2: pause=True -> bước 3 paused (sim_tick đứng ở 2)
            # Tick 3: vẫn pause (giữ True), gửi interact/buy -> bỏ qua
            # Tick 4: pause=False
            # Tick 5: pause=True (resumed!) + buy="oxygen" + shop_done=True -> chạy ngay bước 6!
            inp = write_json(w.path("in.json"), frames(
                {"tick": 2, "pause": True, "interact": True},
                {"tick": 3, "buy": "oxygen"},
                {"tick": 4, "pause": False, "interact": False},
                {"tick": 5, "pause": True, "buy": "oxygen", "shop_done": True},
            ))
            out = w.path("p.jsonl")
            code, err = run_headless("--mode", "day", "--seed", "1", "--days", "1", "--ticks", "20",
                                     "--scenario", sc, "--inputs", inp, "--snapshot-every", "1", "--out", out)
            self.assertEqual(code, 0, err)
            rows = read_jsonl(out)
            snaps = {r["tick"]: r for r in snapshots(rows)}
            # Sau tick 2->3 paused: sim_tick đứng yên tại 2, state="paused"
            self.assertEqual(snaps[3]["state"], "paused")
            self.assertEqual(snaps[3]["sim_tick"], 2)
            self.assertEqual(snaps[3]["time_left_ticks"], 600)
            self.assertEqual(snaps[5]["sim_tick"], 2)
            self.assertEqual(snaps[5]["upgrades"], {})
            # Tick 6: resumed -> chạy buy & shop_done ngay trong tick 6
            evs_t6 = [r for r in events(rows) if r["tick"] == 6]
            self.assertEqual([e["name"] for e in evs_t6], ["resumed", "bought", "shop_end"])
            self.assertEqual(rows[-1]["ticks"], 6)
            self.assertEqual(rows[-1]["sim_tick"], 3)
            self.assertEqual(rows[-1]["days_completed"], 1)
            self.assertEqual(rows[-1]["reason"], "days_complete")


class DayModeAndShopTests(unittest.TestCase):
    def test_day_plan_filtering_faint_opens_quan_and_no_dish(self):
        with Workdir() as w:
            # Ngày 1 plan chỉ có ca_loc_nuong_trui & goi_bong_sung; có sẵn ca_keo (nấu được ca_keo_nuong ngoài plan)
            # nhưng phải phát no_dish vì ngoài day_plan!
            sc = write_json(w.path("sc.json"), {
                "gather": {"hold": ["ca_keo", "ca_keo"], "random_fish": False, "monsters": []},
                "quan": {"time_left_ticks": 150},
            })
            inp = write_json(w.path("in.json"), frames({"tick": 0, "interact": True}))  # tick 1 docked -> mở quán
            out = w.path("d1.jsonl")
            code, err = run_headless("--mode", "day", "--seed", "1", "--days", "1", "--ticks", "200",
                                     "--scenario", sc, "--inputs", inp, "--snapshot-every", "1", "--out", out)
            self.assertEqual(code, 0, err)
            rows = read_jsonl(out)
            tick0_evs = [e["name"] for e in events(rows) if e["tick"] == 0]
            self.assertEqual(tick0_evs, ["day_start", "day_plan", "phase_start"])
            snaps = {r["tick"]: r for r in snapshots(rows)}
            self.assertEqual(snaps[1]["phase"], "quan")
            self.assertEqual(snaps[1]["phase_tick"], 0)
            self.assertEqual(events(rows, "no_dish")[0]["tick"], 121)

            # Ngất buổi sáng vẫn mở quán buổi tối với kho rỗng
            sc_faint = write_json(w.path("sf.json"), {
                "gather": {
                    "player": {"pos": [20, 10], "hp": 1, "oxygen_ticks": 0, "zero_oxy_ticks": 59},
                    "hold": ["ca_loc"],
                    "random_fish": False,
                    "monsters": [],
                },
                "quan": {"time_left_ticks": 5, "random_customers": False},
            })
            out_f = w.path("df.jsonl")
            code, err = run_headless("--mode", "day", "--seed", "1", "--days", "1", "--ticks", "20",
                                     "--scenario", sc_faint, "--snapshot-every", "1", "--out", out_f)
            self.assertEqual(code, 0, err)
            rf = read_jsonl(out_f)
            evs1 = [e["name"] for e in events(rf) if e["tick"] == 1]
            self.assertEqual(evs1, ["choke", "faint", "gather_end", "phase_start"])
            self.assertEqual(snapshots(rf)[1]["phase"], "quan")
            self.assertEqual(snapshots(rf)[1]["stock"], {})

    def test_shop_buy_failures_same_tick_close_timeout_and_multiday_upgrades(self):
        with Workdir() as w:
            # 3 Ngày:
            # Ngày 1: money=200, earned=200. Ở Shop thử buy "weapon" (unknown), buy "hp" (funds), buy "oxygen" (200 -> lvl 1, money=0),
            # buy "oxygen" (funds). Đợi hết 600 tick tự đóng Shop (reason="time").
            # Ngày 2: kiểm active_upgrades={"oxygen":1}, oxygen_max_ticks=2700; nhận money=250 đầu? Không, kiếm thêm từ khách!
            # Cho sẵn money đầu = 850 để mua cả oxygen lvl1 (200) ở Ngày 1 và hp lvl1 (250) + oxygen lvl2 (400) ở Ngày 2!
            # Ngày 3: active_upgrades={"oxygen":2, "hp":1} -> oxygen_max_ticks=3600, hp_max=4, và quái M1+M2 cùng có mặt!
            sc = write_json(w.path("sc3.json"), {
                "day": {"money": 850, "earned": 850},
                "gather": {"time_left_ticks": 1, "random_fish": False},
                "quan": {"time_left_ticks": 1, "random_customers": False},
            })
            # Tick 0->1: gather hết giờ -> mở quan; Tick 1->2: quan hết giờ -> mở shop (N1);
            # Trong Shop N1:
            #   tick 2 (shop step 1): buy "weapon" -> buy_failed(unknown)
            #   tick 3 (shop step 2): buy "oxygen" -> bought lvl 1 (200k, money=650)
            #   tick 4..601: chạy hết 600 tick Shop tự đóng ở tick 602 -> mở Ngày 2 gather (phase_tick=0)!
            # Ngày 2 gather: tick 602->603 hết giờ -> mở quan N2; tick 603->604 hết giờ -> mở Shop N2;
            #   tick 604: buy "hp" -> bought lvl 1 (250k, money=400)
            #   tick 605: buy "oxygen" -> bought lvl 2 (400k, money=0)
            #   tick 606: buy "oxygen" -> buy_failed(max_level) + shop_done=True -> đóng Shop N2 -> mở Ngày 3!
            # Ngày 3: tick 607->608 gather -> quan; tick 608->609 quan -> shop N3; tick 609: shop_done -> finish!
            inp = write_json(w.path("in3.json"), frames(
                {"tick": 2, "buy": "weapon"},
                {"tick": 3, "buy": "oxygen"},
                {"tick": 604, "buy": "hp"},
                {"tick": 605, "buy": "oxygen"},
                {"tick": 606, "buy": "oxygen", "shop_done": True},
                {"tick": 607, "shop_done": False},
                {"tick": 609, "shop_done": True},
            ))
            out = w.path("d3.jsonl")
            code, err = run_headless("--mode", "day", "--seed", "1", "--days", "3", "--ticks", "1000",
                                     "--scenario", sc, "--inputs", inp, "--snapshot-every", "1", "--out", out)
            self.assertEqual(code, 0, err)
            rows = read_jsonl(out)
            fails = events(rows, "buy_failed")
            self.assertEqual([e["data"] for e in fails], [
                {"action": "weapon", "reason": "unknown"},
                {"action": "oxygen", "reason": "max_level"},
            ])
            bought = events(rows, "bought")
            self.assertEqual(len(bought), 3)
            shop_ends = events(rows, "shop_end")
            self.assertEqual([e["data"]["reason"] for e in shop_ends], ["time", "done", "done"])

            snaps = snapshots(rows)
            d1_shop = next(s for s in snaps if s["day"] == 1 and s["phase"] == "shop" and s["upgrades"] == {"oxygen": 1})
            self.assertEqual(d1_shop["active_upgrades"], {})
            d2_g = next(s for s in snaps if s["day"] == 2 and s["phase"] == "gather")
            self.assertEqual(d2_g["active_upgrades"], {"oxygen": 1})
            self.assertEqual(d2_g["player"]["oxygen_max_ticks"], 2700)
            self.assertEqual(d2_g["player"]["hp_max"], 3)
            d3_g = next(s for s in snaps if s["day"] == 3 and s["phase"] == "gather")
            self.assertEqual(d3_g["active_upgrades"], {"oxygen": 2, "hp": 1})
            self.assertEqual(d3_g["player"]["oxygen_max_ticks"], 3600)
            self.assertEqual(d3_g["player"]["hp_max"], 4)
            self.assertEqual([m["id"] for m in d3_g["monsters"]], ["M1", "M2"])
            self.assertEqual(rows[-1]["days_completed"], 3)
            self.assertEqual(rows[-1]["reason"], "days_complete")
            self.assertEqual(rows[-1]["money"], 0)
            self.assertEqual(rows[-1]["earned"], 850)

    def test_day_determinism_and_full_day_performance_under_20s(self):
        with Workdir() as w:
            out1, out2 = w.path("d1.jsonl"), w.path("d2.jsonl")
            t0 = time.perf_counter()
            code, err = run_headless("--mode", "day", "--seed", "5", "--days", "1", "--ticks", "22200", "--out", out1)
            elapsed = time.perf_counter() - t0
            self.assertEqual(code, 0, err)
            self.assertLess(elapsed, 20.0, f"1 Ngày chạy mất {elapsed:.2f}s (> 20s)")

            code, err = run_headless("--mode", "day", "--seed", "5", "--days", "1", "--ticks", "22200", "--out", out2)
            self.assertEqual(code, 0, err)
            with open(out1, "rb") as a, open(out2, "rb") as b:
                self.assertEqual(a.read(), b.read())
            rows = read_jsonl(out1)
            self.assertEqual(rows[-1]["reason"], "days_complete")
            self.assertEqual(rows[-1]["days_completed"], 1)


class Phase2Exit2AndLiveTests(unittest.TestCase):
    def test_v11_cli_and_scenario_conflicts_exit_2_without_output(self):
        with Workdir() as w:
            out = w.path("out.jsonl")
            for args in (
                ["--mode", "gather", "--days", "1"],
                ["--mode", "quan", "--days", "1"],
                ["--mode", "day", "--days", "0"],
                ["--mode", "day", "--days", "6"],
                ["--mode", "day", "--inventory", write_json(w.path("i.json"), {"items": {}})],
                ["--mode", "day", "--inventory-out", w.path("io.json")],
            ):
                code, _ = run_headless(*args, "--seed", "1", "--ticks", "0", "--out", out)
                self.assertEqual(code, 2, args)
                self.assertFalse(os.path.exists(out), args)

            bad_scenarios = [
                {"day": {"money": 100}},
                {"day": {"money": 200, "earned": 100}},
                {"day": {"day_plan": [{"day": 1, "dishes": {"ca_loc_nuong_trui": 2}, "ingredients": {"ca_loc": 1}}]}},
                {"quan": {"stock": {}}},
                {"quan": {"reputation": 4.0}},
                {"quan": {"customers": [{"id": "C1", "table_id": "T1", "dish_id": "lau_mam"}]}},
                {"gather": {"monsters": [{"id": "M1", "kind": "ca_sau", "pos": [60, 24], "waypoints": [[60, 24], [64, 24]], "state": "recoil", "state_ticks_left": 0, "recoil_dir": [1, 0]}]}},
                {"gather": {"monsters": [{"id": "M1", "kind": "ca_sau", "pos": [60, 24], "waypoints": [[60, 24], [64, 24]], "state": "recoil", "state_ticks_left": 5, "recoil_dir": [2, 0]}]}},
                {"gather": {"monsters": [{"id": "M1", "kind": "ca_sau", "pos": [60, 24], "waypoints": [[60, 24], [64, 24]], "state": "patrol", "recoil_dir": [1, 0]}]}},
                {"gather": {"monsters": [{"id": "M1", "kind": "ca_sau", "pos": [60, 5], "waypoints": [[60, 24], [64, 24]]}]}},
            ]
            for idx, sc_obj in enumerate(bad_scenarios):
                scp = write_json(w.path(f"bad_{idx}.json"), sc_obj)
                code, _ = run_headless("--mode", "day", "--seed", "1", "--ticks", "0", "--scenario", scp, "--out", out)
                self.assertEqual(code, 2, f"scenario {idx}: {sc_obj}")
                self.assertFalse(os.path.exists(out))

            # Khách trong quan vượt kho thực khi mở quán từ gather -> exit 2 và không giữ file output
            sc_handoff = write_json(w.path("sh.json"), {
                "gather": {"hold": [], "random_fish": False, "monsters": []},
                "quan": {"customers": [{"id": "C1", "table_id": "T1", "dish_id": "ca_loc_nuong_trui"}]},
            })
            inp_dock = write_json(w.path("idock.json"), frames({"tick": 0, "interact": True}))
            code, _ = run_headless("--mode", "day", "--seed", "1", "--ticks", "5", "--scenario", sc_handoff,
                                   "--inputs", inp_dock, "--out", out)
            self.assertEqual(code, 2)
            self.assertFalse(os.path.exists(out))

            # buy sai kiểu hoặc rỗng -> exit 2
            for bad_inp in ({"frames": [{"tick": 0, "buy": ""}]}, {"frames": [{"tick": 0, "buy": 123}]}):
                bip = write_json(w.path("bi.json"), bad_inp)
                code, _ = run_headless("--mode", "day", "--seed", "1", "--ticks", "0", "--inputs", bip, "--out", out)
                self.assertEqual(code, 2, bad_inp)

    def test_live_server_day_mode_and_pause_shop_inputs(self):
        tuning = load_contract()["tuning"]
        sc = {
            "day": {"money": 200, "earned": 200},
            "gather": {"time_left_ticks": 45, "random_fish": False, "monsters": []},
            "quan": {"time_left_ticks": 1, "random_customers": False},
        }
        server = LiveServer(LiveGame("day", tuning, sc, 1, days=2), port=0)
        server.start()
        try:
            base = f"http://127.0.0.1:{server.port}"
            with urllib.request.urlopen(base + "/state", timeout=5) as r:
                st = json.loads(r.read())
            self.assertEqual(st["mode"], "day")
            self.assertEqual(st["day"], 1)
            self.assertIn("day_plan", st)
            self.assertEqual(st["upgrades"], {})
            self.assertEqual(st["active_upgrades"], {})

            # Cập bến ngay ở Ngày 1 bằng interact rồi đợi mở Shop (quan chỉ dài 1 tick)
            _post_json(base + "/input", {"interact": True})
            _post_json(base + "/input", {"interact": False})
            deadline = time.time() + 3.0
            while time.time() < deadline:
                with urllib.request.urlopen(base + "/state", timeout=5) as r:
                    st = json.loads(r.read())
                if st["phase"] == "shop":
                    break
                time.sleep(0.01)
            self.assertEqual(st["phase"], "shop")

            self.assertEqual(_post_json(base + "/input", {"buy": "oxygen", "shop_done": True})[0], 200)
            deadline = time.time() + 3.0
            while time.time() < deadline:
                with urllib.request.urlopen(base + "/state", timeout=5) as r:
                    st2 = json.loads(r.read())
                if st2["day"] == 2 and st2["phase"] == "gather":
                    break
                time.sleep(0.01)
            self.assertEqual(st2["day"], 2)
            self.assertEqual(st2["phase"], "gather")
            self.assertEqual(st2["active_upgrades"], {"oxygen": 1})
            self.assertEqual(st2["player"]["oxygen_max_ticks"], 2700)
        finally:
            server.stop()


if __name__ == "__main__":
    unittest.main()
