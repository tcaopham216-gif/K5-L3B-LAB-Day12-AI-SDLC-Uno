"""Cửa sổ chơi trực tiếp bằng TRÌNH DUYỆT (Test Contract v1.1), dùng thư viện chuẩn Python.

    python3 -m chonoi.live --mode gather|quan|day [--days 5] [--seed N] [--port 8000]
"""

import argparse
import json
import os
import sys
import threading
import time
import traceback
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from .contract import load_contract
from .errors import BadInput
from .inputs import BUTTONS_V11, LiveInputs
from .inventory import read_inventory
from .runner import Session
from .scenario import load_scenario

WEB_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "web")
TICK_S = 1.0 / 60.0
MAX_BODY = 4096
RECENT_EVENTS = 40


class LiveGame:
    """Một lượt chơi + luồng nền bước 60 tick/s. Mọi truy cập trạng thái đi qua khóa."""

    def __init__(self, mode, tuning, scenario, seed, inventory=None, inventory_out=None, days=1):
        self._args = (mode, tuning, scenario, seed, inventory, days)
        self.mode = mode
        self.tuning = tuning
        self.inventory_out = inventory_out
        self.days = days
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._thread = None
        self._reset()

    def _reset(self):
        mode, tuning, scenario, seed, inventory, days = self._args
        self.session = Session(mode, tuning, scenario, seed, inventory=inventory, days=days)
        self.inputs = LiveInputs()
        self.events = list(self.session.startup_events())
        self._saved = False
        self.ui_paused = False
        self.error = None
        self.dish_sales = {}
        self._reset_day_stats(self.session.sim.reputation)
        self.handoff_stock = {}

    def _reset_day_stats(self, rep_start):
        self.day_stats = {
            "served_count": 0,
            "left_count": 0,
            "shift_earned": 0,
            "shift_tips": 0,
            "rep_start": float(rep_start),
            "rep_end": float(rep_start),
        }

    # --- luồng nền ----------------------------------------------------------------
    def start(self):
        self._thread = threading.Thread(target=self._loop, name="chonoi-sim", daemon=True)
        self._thread.start()

    def stop(self):
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=2)

    def _loop(self):
        nxt = time.perf_counter()
        while not self._stop.is_set():
            nxt += TICK_S
            with self._lock:
                try:
                    self._tick_once()
                except Exception:
                    self.error = traceback.format_exc()
                    sys.stderr.write(self.error)
                    self.session.sim.done = True
                    self.session.sim.reason = "error"
            delay = nxt - time.perf_counter()
            if delay > 0:
                self._stop.wait(delay)
            elif delay < -0.25:
                nxt = time.perf_counter()

    def _track_events(self, rows):
        for row in rows:
            name = row["name"]
            data = row["data"]
            if name == "day_start":
                self._reset_day_stats(self.session.sim.reputation)
            elif name == "gather_end":
                self.handoff_stock = dict(data.get("inventory", {}).get("items", {}))
            elif name == "served":
                self.day_stats["served_count"] += 1
                did = data.get("dish_id")
                if did:
                    self.dish_sales[did] = self.dish_sales.get(did, 0) + 1
            elif name == "paid":
                self.day_stats["shift_earned"] += int(data.get("amount", 0))
                self.day_stats["shift_tips"] += int(data.get("tip", 0))
            elif name == "customer_left" and data.get("reason") == "patience":
                self.day_stats["left_count"] += 1
            elif name == "quan_end":
                self.day_stats["rep_end"] = float(data.get("reputation", self.session.sim.reputation))

    def _tick_once(self):
        s = self.session
        if s.done or self.ui_paused:
            return
        rows = s.step(self.inputs.advance())
        if rows:
            self._track_events(rows)
            self.events.extend(rows)
            del self.events[:-RECENT_EVENTS]
        if s.done and not self._saved:
            self._saved = True
            if self.inventory_out:
                try:
                    s.write_inventory_if_done(self.inventory_out)
                except OSError as e:
                    sys.stderr.write(f"lỗi ghi kho: {e}\n")

    # --- API cho handler -----------------------------------------------------------
    def state_json(self) -> bytes:
        with self._lock:
            snap = self.session.snapshot()
            phase = snap["phase"]
            meta = dict(self.tuning.get(phase, {}))
            meta["menu"] = self.tuning["menu"]
            meta["shop"] = self.tuning["shop"]
            meta["gather_cfg"] = {
                "interact_radius": self.tuning["gather"]["interact_radius"],
                "dock_pos": self.tuning["gather"]["dock_pos"],
                "dock_radius": self.tuning["gather"]["dock_radius"],
                "monsters": self.tuning["gather"]["monsters"],
            }
            meta["quan_cfg"] = {
                "patience_s": self.tuning["quan"]["patience_s"],
                "bounds": self.tuning["quan"]["bounds"],
            }
            snap["meta"] = meta
            snap["events"] = list(self.events)
            snap["finished"] = self.session.done
            snap["reason"] = self.session.sim.reason if self.session.done else None
            snap["error"] = self.error
            snap["ui_paused"] = self.ui_paused
            snap["ui_stats"] = {
                "day": dict(self.day_stats),
                "handoff_stock": dict(self.handoff_stock),
                "dish_sales": dict(self.dish_sales),
            }
            return json.dumps(snap, ensure_ascii=False, separators=(",", ":")).encode("utf-8")

    def set_input(self, body: dict):
        move = body.get("move")
        if move is not None:
            ok = (isinstance(move, list) and len(move) == 2 and
                  all(isinstance(c, (int, float)) and not isinstance(c, bool) and abs(c) <= 1 for c in move))
            if not ok:
                raise ValueError("move phải là [a, b] trong [-1, 1]")
        buttons = {}
        for b in BUTTONS_V11:
            if b in body:
                if not isinstance(body[b], bool):
                    raise ValueError(f"{b} phải là boolean")
                buttons[b] = body[b]
        buy = None
        if "buy" in body and body["buy"] is not None:
            if not isinstance(body["buy"], str) or len(body["buy"]) == 0:
                raise ValueError("buy phải là chuỗi khác rỗng")
            buy = body["buy"]
        with self._lock:
            self.inputs.set(move, buy=buy, **buttons)

    def set_ui_pause(self, paused: bool):
        with self._lock:
            self.ui_paused = bool(paused)

    def restart(self):
        with self._lock:
            self._reset()


class _Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    game: LiveGame = None

    def log_message(self, fmt, *args):
        pass

    def _send(self, code, body: bytes, ctype="application/json; charset=utf-8"):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        path = self.path.split("?", 1)[0]
        if path == "/state":
            self._send(200, self.game.state_json())
        elif path in ("/", "/index.html"):
            try:
                with open(os.path.join(WEB_DIR, "index.html"), "rb") as f:
                    self._send(200, f.read(), "text/html; charset=utf-8")
            except OSError:
                self._send(404, b'{"error":"thieu index.html"}')
        else:
            self._send(404, b'{"error":"khong co"}')

    def do_POST(self):
        path = self.path.split("?", 1)[0]
        try:
            n = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            n = -1
        if n < 0 or n > MAX_BODY:
            self._send(400, b'{"error":"body sai"}')
            return
        raw = self.rfile.read(n) if n else b""
        try:
            if path == "/input":
                body = json.loads(raw.decode("utf-8") or "{}")
                if not isinstance(body, dict):
                    raise ValueError("body phải là object")
                self.game.set_input(body)
            elif path == "/ui_pause":
                body = json.loads(raw.decode("utf-8") or "{}")
                if not isinstance(body, dict) or not isinstance(body.get("paused"), bool):
                    raise ValueError("paused phải là boolean")
                self.game.set_ui_pause(body["paused"])
            elif path == "/restart":
                self.game.restart()
            else:
                self._send(404, b'{"error":"khong co"}')
                return
        except (ValueError, UnicodeDecodeError) as e:
            self._send(400, json.dumps({"error": str(e)}).encode("utf-8"))
            return
        self._send(200, b'{"ok":true}')


class LiveServer:
    """Máy chủ + mô phỏng. port=0 -> cổng ngẫu nhiên (đọc `.port`)."""

    def __init__(self, game: LiveGame, host="127.0.0.1", port=8000):
        handler = type("Handler", (_Handler,), {"game": game})
        self.game = game
        self.httpd = ThreadingHTTPServer((host, port), handler)
        self.httpd.daemon_threads = True
        self.host = host
        self.port = self.httpd.server_address[1]
        self._thread = None

    @property
    def url(self):
        return f"http://{self.host}:{self.port}/"

    def start(self):
        self.game.start()
        self._thread = threading.Thread(target=self.httpd.serve_forever, name="chonoi-http", daemon=True)
        self._thread.start()

    def stop(self):
        self.httpd.shutdown()
        self.httpd.server_close()
        if self._thread:
            self._thread.join(timeout=2)
        self.game.stop()


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="chonoi.live", description="Chơi trực tiếp trên trình duyệt (v1.1).")
    p.add_argument("--mode", required=True, choices=["gather", "quan", "day"])
    p.add_argument("--days", type=int, default=None, help="số Ngày với --mode day (1-5, mặc định 5)")
    p.add_argument("--seed", type=int, default=1)
    p.add_argument("--port", type=int, default=8000, help="0 = cổng ngẫu nhiên")
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--scenario")
    p.add_argument("--inventory", help="chỉ với quan: nạp kho từ file")
    p.add_argument("--inventory-out", dest="inventory_out", help="chỉ với gather: ghi kho khi kết thúc buổi")
    a = p.parse_args(argv)
    try:
        if a.days is not None and a.mode != "day":
            raise BadInput("--days chỉ dùng với --mode day")
        days = (5 if a.days is None else a.days) if a.mode == "day" else 1
        if a.mode == "day" and not (1 <= days <= 5):
            raise BadInput("--days phải trong [1, 5]")
        if a.inventory and a.mode != "quan":
            raise BadInput("--inventory chỉ dùng với quan")
        if a.inventory_out and a.mode != "gather":
            raise BadInput("--inventory-out chỉ dùng với gather")
        tuning = load_contract()["tuning"]
        scenario = load_scenario(a.scenario, a.mode, tuning)
        inventory = read_inventory(a.inventory) if a.inventory else None
        if inventory is not None and a.mode == "quan" and "stock" in scenario:
            raise BadInput("vừa có quan.stock vừa có --inventory")
        game = LiveGame(a.mode, tuning, scenario, a.seed, inventory, a.inventory_out, days=days)
        server = LiveServer(game, a.host, a.port)
    except BadInput as e:
        sys.stderr.write(f"đầu vào sai: {e}\n")
        return 2
    except OSError as e:
        sys.stderr.write(f"không mở được cổng {a.port}: {e}\n")
        return 1
    server.start()
    print(f"Mở trình duyệt tại {server.url}  (chế độ {a.mode}, seed {a.seed}). Ctrl+C để dừng.", flush=True)
    try:
        while True:
            time.sleep(0.5)
    except KeyboardInterrupt:
        pass
    finally:
        server.stop()
    return 0


if __name__ == "__main__":
    sys.exit(main())
