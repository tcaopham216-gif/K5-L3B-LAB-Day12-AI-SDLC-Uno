"""Test hộp đen & đơn vị cho TICKET-04 & Test Contract v1.3 (Phase 4 — Phát hành v1.0.0)."""

import json
import math
import os
import shlex
import subprocess
import unittest
import urllib.request
import zipfile

from chonoi.contract import load_contract
from chonoi.ids import IdAllocator
from chonoi.live import LiveGame, LiveServer
from chonoi.rng import Streams
from chonoi.sim.day import DaySim
from helpers import ROOT, Workdir, headless_cmd, read_jsonl


def _cmd_from_contract(key: str):
    with open(os.path.join(ROOT, "game.contract.json"), encoding="utf-8") as f:
        return shlex.split(json.load(f)[key])


def _get_bytes(url: str):
    with urllib.request.urlopen(url, timeout=5) as r:
        return r.status, r.read()


class Phase4ContractAndToolsTests(unittest.TestCase):
    def test_v13_manifest_commands_and_files(self):
        c = load_contract()
        self.assertEqual(c["contract_version"], "1.3")
        self.assertEqual(c["bench_cmd"], "python3 -m chonoi.bench")
        self.assertEqual(c["soak_cmd"], "python3 -m chonoi.soak")
        self.assertEqual(c["extensions"], [])

        lic = os.path.join(ROOT, "LICENSE")
        cred = os.path.join(ROOT, "CREDITS.md")
        self.assertTrue(os.path.isfile(lic))
        self.assertTrue(os.path.isfile(cred))
        with open(lic, encoding="utf-8") as f:
            self.assertIn("MIT License", f.read())
        with open(cred, encoding="utf-8") as f:
            self.assertIn("Canvas", f.read())

    def test_day_sim_cycles_day_plan_on_days_6_to_10(self):
        tuning = load_contract()["tuning"]
        sim = DaySim(tuning, {}, Streams(7), IdAllocator(), days=10)
        for d in range(6, 11):
            self.assertEqual(sim._plan_payload(d), sim._plan_payload(d - 5))

    def test_bench_cli_exit_2_and_schema_math(self):
        bench_cmd = _cmd_from_contract("bench_cmd")
        with Workdir() as w:
            out = w.path("bench.json")
            for bad_args in (
                ["--seed", "abc", "--duration", "0.2", "--out", out],
                ["--seed", "42", "--duration", "0", "--out", out],
                ["--seed", "42", "--duration", "-1", "--out", out],
                ["--seed", "42", "--duration", "0.2", "--warmup", "-1", "--out", out],
            ):
                p = subprocess.run([*bench_cmd, *bad_args], cwd=ROOT, capture_output=True, text=True)
                self.assertEqual(p.returncode, 2, bad_args)
                self.assertFalse(os.path.exists(out))

            p = subprocess.run(
                [*bench_cmd, "--seed", "42", "--warmup", "0.05", "--duration", "0.25", "--renderer", "software", "--out", out],
                cwd=ROOT, capture_output=True, text=True,
            )
            self.assertEqual(p.returncode, 0, p.stderr)
            self.assertTrue(os.path.isfile(out))
            with open(out, encoding="utf-8") as f:
                data = json.load(f)
            self.assertEqual(set(data.keys()), {"avg_fps", "p1_low_fps", "frames", "measured_s", "load_ms"})
            self.assertIsInstance(data["frames"], int)
            self.assertGreaterEqual(data["frames"], 1)
            self.assertGreaterEqual(data["measured_s"], 0.2)
            self.assertLess(abs(data["avg_fps"] - (data["frames"] / data["measured_s"])), 0.001)
            self.assertGreater(data["p1_low_fps"], 0)
            self.assertLessEqual(data["p1_low_fps"], data["avg_fps"] + 1e-6)
            self.assertGreaterEqual(data["load_ms"], 0)

    def test_soak_cli_exit_2_10_days_and_determinism(self):
        soak_cmd = _cmd_from_contract("soak_cmd")
        with Workdir() as w:
            out_a = w.path("soak_a.json")
            out_b = w.path("soak_b.json")
            for bad_args in (
                ["--seed", "7", "--days", "0", "--out", out_a],
                ["--seed", "7", "--days", "-3", "--out", out_a],
                ["--days", "2", "--out", out_a],
            ):
                p = subprocess.run([*soak_cmd, *bad_args], cwd=ROOT, capture_output=True, text=True)
                self.assertEqual(p.returncode, 2, bad_args)
                self.assertFalse(os.path.exists(out_a))

            p1 = subprocess.run([*soak_cmd, "--seed", "7", "--days", "10", "--out", out_a],
                                cwd=ROOT, capture_output=True, text=True)
            self.assertEqual(p1.returncode, 0, p1.stderr)
            p2 = subprocess.run([*soak_cmd, "--seed", "7", "--days", "10", "--out", out_b],
                                cwd=ROOT, capture_output=True, text=True)
            self.assertEqual(p2.returncode, 0, p2.stderr)

            with open(out_a, encoding="utf-8") as f:
                da = json.load(f)
            with open(out_b, encoding="utf-8") as f:
                db = json.load(f)
            for d in (da, db):
                self.assertEqual(set(d.keys()), {"days", "days_completed", "crashes", "results", "duration_s"})
                self.assertEqual(d["days"], 10)
                self.assertEqual(d["days_completed"], 10)
                self.assertEqual(d["crashes"], 0)
                self.assertEqual([r["day"] for r in d["results"]], list(range(1, 11)))
                for r in d["results"]:
                    self.assertEqual(set(r.keys()), {"day", "earned", "reputation", "score"})
            self.assertGreater(da["results"][-1]["earned"], 0)
            self.assertGreater(da["results"][-1]["score"], 0)
            self.assertEqual(da["results"], db["results"])

    def test_accessible_alerts_and_high_contrast_in_live_ui(self):
        html_path = os.path.join(ROOT, "chonoi", "web", "index.html")
        with open(html_path, encoding="utf-8") as f:
            html_src = f.read()
        for token in (
            "toggleHighContrast",
            "chonoi_high_contrast",
            "body.hc",
            'params.get("hc") === "1"',
            "THỦY QUÁI GẦN",
            "OXY SẮP HẾT",
            "KHÁCH SẮP GIẬN",
            "hc-hud-btn",
        ):
            self.assertIn(token, html_src)

        tuning = load_contract()["tuning"]
        # 1. Gather scenario kích hoạt cùng lúc cảnh báo Thủy quái gần + Oxy sắp hết
        g_sc = {"player": {"pos": [60, 22], "oxygen_ticks": 300, "hp": 3}}
        srv_g = LiveServer(LiveGame("gather", tuning, g_sc, 1), port=0)
        srv_g.start()
        try:
            base = f"http://127.0.0.1:{srv_g.port}"
            code_h, body_h = _get_bytes(base + "/")
            self.assertEqual(code_h, 200)
            self.assertIn(b"hc-hud-btn", body_h)
            code_s, body_s = _get_bytes(base + "/state")
            self.assertEqual(code_s, 200)
            st = json.loads(body_s)
            detect_r = st["meta"]["gather_cfg"]["monsters"]["species"]["ca_sau"]["detect_radius"]
            self.assertTrue(any(math.dist(m["pos"], st["player"]["pos"]) <= detect_r for m in st["monsters"]))
            self.assertLess(st["player"]["oxygen_ticks"], st["player"]["oxygen_max_ticks"] * 0.25)
        finally:
            srv_g.stop()

        # 2. Quan scenario kích hoạt cảnh báo Khách sắp giận
        q_sc = {
            "stock": [{"id": "I1", "kind": "ca_loc", "fresh": 100}],
            "customers": [{
                "id": "C1",
                "table_id": "T1",
                "dish_id": "ca_loc_nuong_trui",
                "patience_ticks_left": 300,
                "reserved": ["I1"],
            }],
        }
        srv_q = LiveServer(LiveGame("quan", tuning, q_sc, 1), port=0)
        srv_q.start()
        try:
            st_q = json.loads(_get_bytes(f"http://127.0.0.1:{srv_q.port}/state")[1])
            pat_max = st_q["meta"]["quan_cfg"]["patience_s"] * 60
            self.assertLess(st_q["customers"][0]["patience_ticks_left"], pat_max * 0.25)
        finally:
            srv_q.stop()

    def test_release_packager_builds_runnable_bundle(self):
        pkg_script = os.path.join(ROOT, "tools", "package_release.py")
        with Workdir() as w:
            dist_dir = w.path("dist")
            p = subprocess.run(
                [headless_cmd()[0], pkg_script, "--out-dir", dist_dir, "--version", "1.0.0"],
                cwd=ROOT, capture_output=True, text=True,
            )
            self.assertEqual(p.returncode, 0, p.stderr)
            zpath = os.path.join(dist_dir, "quan-an-cho-noi-v1.0.0.zip")
            tpath = os.path.join(dist_dir, "quan-an-cho-noi-v1.0.0.tar.gz")
            self.assertTrue(os.path.isfile(zpath))
            self.assertTrue(os.path.isfile(tpath))

            extract_dir = w.path("unzipped")
            with zipfile.ZipFile(zpath, "r") as zf:
                names = zf.namelist()
                self.assertFalse(any("__pycache__" in n for n in names))
                zf.extractall(extract_dir)

            bundle_root = os.path.join(extract_dir, "quan-an-cho-noi-v1.0.0")
            for rel in ("run.sh", "run.bat", "game.contract.json", "LICENSE", "CREDITS.md", "chonoi/web/index.html"):
                self.assertTrue(os.path.isfile(os.path.join(bundle_root, rel)), rel)

            out_jsonl = w.path("bundle_gather.jsonl")
            p_run = subprocess.run(
                [*headless_cmd(), "--mode", "gather", "--seed", "1", "--ticks", "10", "--out", out_jsonl],
                cwd=bundle_root, capture_output=True, text=True,
            )
            self.assertEqual(p_run.returncode, 0, p_run.stderr)
            rows = read_jsonl(out_jsonl)
            self.assertEqual(rows[-1]["type"], "end")


if __name__ == "__main__":
    unittest.main()
