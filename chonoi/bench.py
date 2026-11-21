"""Benchmark hiệu năng cảnh lặn có render 1280x720 (Contract v1.3).

Chạy:
    python3 -m chonoi.bench --seed 42 --duration 30 --out bench.json

Xuất đúng 5 trường JSON nguyên tử: avg_fps, p1_low_fps, frames, measured_s, load_ms.
Dùng Tkinter 1280x720 làm backend mặc định và tự rơi về software framebuffer
1280x720 khi môi trường headless không có display (CI).
"""

import time

_MODULE_START = time.perf_counter()

import argparse
import json
import math
import os
import sys
import tempfile

from .contract import load_contract
from .errors import BadInput
from .ids import IdAllocator
from .inputs import InputState
from .rng import Streams
from .sim.gather import GatherSim

WIDTH = 1280
HEIGHT = 720
DT_STEP = 1.0 / 60.0
FIVE_KEYS = ("avg_fps", "p1_low_fps", "frames", "measured_s", "load_ms")

KIND_HEX = {
    "ca_loc": "#7c9a52",
    "ca_linh": "#d6e6f2",
    "ca_keo": "#d9a066",
    "bong_dien_dien": "#f2c230",
    "bong_sung": "#e8799c",
    "keo_neo": "#8fcf6b",
}
KIND_RGB = {
    "ca_loc": (124, 154, 82),
    "ca_linh": (214, 230, 242),
    "ca_keo": (217, 160, 102),
    "bong_dien_dien": (242, 194, 48),
    "bong_sung": (232, 121, 156),
    "keo_neo": (143, 207, 107),
}


class _Parser(argparse.ArgumentParser):
    def error(self, message):
        self.print_usage(sys.stderr)
        sys.stderr.write(f"lỗi: {message}\n")
        sys.exit(2)


def _int(name):
    def conv(s):
        try:
            return int(s)
        except ValueError:
            raise argparse.ArgumentTypeError(f"{name} phải là số nguyên")
    return conv


def _float(name):
    def conv(s):
        try:
            val = float(s)
        except ValueError:
            raise argparse.ArgumentTypeError(f"{name} phải là số")
        if not math.isfinite(val):
            raise argparse.ArgumentTypeError(f"{name} phải hữu hạn")
        return val
    return conv


def _atomic_write_json(path: str, payload: dict):
    parent = os.path.dirname(os.path.abspath(path))
    if parent:
        os.makedirs(parent, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=".bench-", suffix=".tmp", dir=parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as f:
            json.dump(payload, f, ensure_ascii=False, separators=(",", ":"))
            f.write("\n")
        os.replace(tmp, path)
    except BaseException:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise


def _scene_geom(bounds):
    X = bounds["x"][1]
    D = bounds["d"][1]
    sky = 6.0
    top = 96.0
    bottom = 76.0
    s = max(1.0, min((WIDTH - 24.0) / (X + 4.0), (HEIGHT - top - bottom) / (D + sky + 1.0)))
    ox = (WIDTH - s * (X + 4.0)) / 2.0 + 2.0 * s
    oy = top + sky * s
    return X, D, top, bottom, s, ox, oy


class _TkGatherRenderer:
    """Renderer Tkinter 1280x720 dùng item pool (không tạo/xóa item mỗi khung)."""

    def __init__(self, tuning):
        import tkinter as tk

        self._tk = tk
        self._closed = False
        g = tuning["gather"]
        bounds = g["bounds"]
        X, D, top, bottom, s, ox, oy = _scene_geom(bounds)
        self._geom = (X, D, top, bottom, s, ox, oy)
        self._spoiled_below = float(tuning["freshness"]["spoiled_below"])

        root = tk.Tk()
        root.title("Quán Ăn Chợ Nổi — Bench 1280x720")
        root.geometry(f"{WIDTH}x{HEIGHT}+40+40")
        root.resizable(False, False)
        root.protocol("WM_DELETE_WINDOW", self._on_close)
        cv = tk.Canvas(root, width=WIDTH, height=HEIGHT, bg="#10161c", highlightthickness=0)
        cv.pack(fill="both", expand=False)
        self.root = root
        self.cv = cv

        def sx(x):
            return ox + x * s

        def sy(d):
            return oy + d * s

        self._sx = sx
        self._sy = sy

        # Tầng nền trời & nước phân tầng độ sâu
        cv.create_rectangle(0, top, WIDTH, oy, fill="#cfeaf5", outline="")
        water_bands = ("#49b0dc", "#3790bd", "#236c94", "#164e73", "#0c3554", "#071f36")
        for idx, col in enumerate(water_bands):
            d0 = D * idx / len(water_bands)
            d1 = D * (idx + 1) / len(water_bands)
            cv.create_rectangle(sx(0), sy(d0), sx(X), sy(d1), fill=col, outline="")
        cv.create_line(sx(0), oy, sx(X), oy, fill="#e9f7ff", width=2)
        for d in (10, 20, 30):
            if d <= D:
                cv.create_line(sx(0), sy(d), sx(X), sy(d), fill="#3b6e8c", width=1)
                cv.create_text(sx(0) + 8, sy(d) - 10, text=f"{d}m", anchor="w",
                               fill="#b8d9eb", font=("Arial", 13, "bold"))

        # Bến cố định
        dp = g["dock_pos"]
        dr = g["dock_radius"]
        cv.create_rectangle(sx(dp[0] - 1.5), sy(-0.7), sx(dp[0] + 1.5), sy(0.2), fill="#8d6e4b", outline="")
        cv.create_polygon(
            sx(dp[0] - 1.8), sy(-0.7),
            sx(dp[0]), sy(-2.5),
            sx(dp[0] + 1.8), sy(-0.7),
            fill="#b9503a", outline=""
        )
        cv.create_oval(sx(dp[0] - dr), sy(dp[1] - dr), sx(dp[0] + dr), sy(dp[1] + dr),
                       outline="#ffe696", dash=(6, 4), width=2)
        cv.create_text(sx(dp[0]), sy(-3.1), text="Bến", fill="#5a3a22", font=("Arial", 14, "bold"))

        # Bọt nước nhẹ (hiệu ứng mặc định)
        self._bubbles = []
        for i in range(18):
            bx = sx(6 + i * 5.2)
            by = sy(3 + (i * 5) % 24)
            bid = cv.create_oval(bx - 3, by - 3, bx + 3, by + 3, outline="#d6f2ff", width=1)
            self._bubbles.append((bid, 6 + i * 5.2, 3 + (i * 5) % 24, 0.8 + (i % 4) * 0.25))

        # Pool nút hái
        self._node_pool = []
        for _ in range(max(6, len(g["nodes"]))):
            oid = cv.create_oval(-20, -20, -10, -10, fill="#8fcf6b", outline="#102027", width=1)
            tid = cv.create_text(-20, -20, text="", fill="#102027", font=("Arial", 12, "bold"))
            self._node_pool.append((oid, tid))

        # Pool đàn cá
        self._fish_pool = []
        for _ in range(max(16, int(g["fish_max"]) + 4)):
            body = cv.create_oval(-30, -30, -10, -20, fill="#d6e6f2", outline="#102027", width=1)
            tail = cv.create_polygon(-30, -25, -38, -30, -38, -20, fill="#d6e6f2", outline="")
            lbl = cv.create_text(-20, -40, text="", fill="#eef7fc", font=("Arial", 11))
            self._fish_pool.append((body, tail, lbl))

        # Pool thủy quái Cá Sấu
        self._monster_pool = []
        for _ in range(max(4, len(g["monsters"]["spawns"]) + 2)):
            body = cv.create_oval(-50, -50, -20, -30, fill="#5d8c4a", outline="#1b2e13", width=2)
            lbl = cv.create_text(-35, -60, text="", fill="#ffebee", font=("Arial", 12, "bold"))
            self._monster_pool.append((body, lbl))

        # Út Sen
        self._player_ring = cv.create_oval(-20, -20, -10, -10, outline="#ffffff", width=1)
        self._player_body = cv.create_oval(-20, -20, -10, -10, fill="#ff8a3d", outline="#ffffff", width=2)
        self._player_dir = cv.create_line(-20, -20, -10, -10, fill="#ffffff", width=3)

        # HUD trên + thanh oxy + giỏ dưới
        self._hud_time = cv.create_text(16, 28, anchor="w", text="⏱ 03:00", fill="#f0f5f9", font=("Arial", 18, "bold"))
        cv.create_rectangle(220, 12, 480, 42, fill="#08121c", outline="#8fb3c9", width=2)
        self._oxy_fill = cv.create_rectangle(222, 14, 478, 40, fill="#29b6f6", outline="")
        self._oxy_txt = cv.create_text(350, 27, text="Oxy 30s", fill="#ffffff", font=("Arial", 14, "bold"))
        self._hud_hp = cv.create_text(508, 28, anchor="w", text="♥ ♥ ♥", fill="#ff6b81", font=("Arial", 18, "bold"))
        self._hud_depth = cv.create_text(16, 62, anchor="w", text="Sâu: 0.0m (Nông)", fill="#b9cad8", font=("Arial", 14))
        self._hud_hold = cv.create_text(16, HEIGHT - 18, anchor="w", text="Giỏ 0/12", fill="#e0ebf2", font=("Arial", 14))

        cap = int(g["hold_capacity"])
        sz = min(34, max(20, (WIDTH - 420) / cap - 4))
        y0 = HEIGHT - bottom + 10
        self._slots = []
        for i in range(cap):
            x0 = 16 + i * (sz + 4)
            cv.create_rectangle(x0, y0, x0 + sz, y0 + sz, fill="#243442", outline="#455a64")
            fill_id = cv.create_rectangle(x0 + 3, y0 + 3, x0 + sz - 3, y0 + sz - 3, fill="", outline="")
            fbar_id = cv.create_rectangle(x0 + 3, y0 + sz - 6, x0 + sz - 3, y0 + sz - 2, fill="", outline="")
            self._slots.append((fill_id, fbar_id, x0, y0, sz))

    def _on_close(self):
        self._closed = True

    def render(self, sim, t_rel: float):
        if self._closed:
            return
        sx, sy = self._sx, self._sy
        _, D, _, _, s, _, _ = self._geom

        # Bọt nước chuyển động nhẹ
        for bid, x0, d0, spd in self._bubbles:
            d = (d0 - t_rel * spd) % (D - 1.0) + 0.5
            bx = sx(x0 + math.sin(t_rel * 2.0 + x0) * 0.4)
            by = sy(d)
            self.cv.coords(bid, bx - 3, by - 3, bx + 3, by + 3)

        # Nút hái
        nodes = sim.nodes
        for i, (oid, tid) in enumerate(self._node_pool):
            if i < len(nodes):
                n = nodes[i]
                nx, ny = sx(n["pos"][0]), sy(n["pos"][1])
                col = KIND_HEX.get(n["kind"], "#bbbbbb")
                self.cv.coords(oid, nx - 1.0 * s, ny - 0.55 * s, nx + 1.0 * s, ny + 0.35 * s)
                self.cv.itemconfigure(oid, fill=col, state="normal")
                self.cv.coords(tid, nx, ny - 0.9 * s)
                self.cv.itemconfigure(tid, text=n["id"], state="normal")
            else:
                self.cv.itemconfigure(oid, state="hidden")
                self.cv.itemconfigure(tid, state="hidden")

        # Đàn cá
        fishes = sim.fish
        for i, (body, tail, lbl) in enumerate(self._fish_pool):
            if i < len(fishes):
                f = fishes[i]
                fx, fy = sx(f["pos"][0]), sy(f["pos"][1])
                ang = math.radians(f.get("heading_deg", 0.0))
                dx = math.cos(ang)
                dy = math.sin(ang)
                col = KIND_HEX.get(f["kind"], "#d6e6f2")
                self.cv.coords(body, fx - 0.9 * s, fy - 0.45 * s, fx + 0.9 * s, fy + 0.45 * s)
                self.cv.itemconfigure(body, fill=col, state="normal")
                tx0, ty0 = fx - dx * 0.85 * s, fy - dy * 0.85 * s
                px, py = -dy * 0.4 * s, dx * 0.4 * s
                self.cv.coords(
                    tail,
                    tx0, ty0,
                    tx0 - dx * 0.55 * s + px, ty0 - dy * 0.55 * s + py,
                    tx0 - dx * 0.55 * s - px, ty0 - dy * 0.55 * s - py,
                )
                self.cv.itemconfigure(tail, fill=col, state="normal")
                self.cv.coords(lbl, fx, fy - 0.85 * s)
                self.cv.itemconfigure(lbl, text=f["id"], state="normal")
            else:
                self.cv.itemconfigure(body, state="hidden")
                self.cv.itemconfigure(tail, state="hidden")
                self.cv.itemconfigure(lbl, state="hidden")

        # Cá Sấu Năm Chèo
        monsters = sim.monsters
        for i, (body, lbl) in enumerate(self._monster_pool):
            if i < len(monsters):
                m = monsters[i]
                mx, my = sx(m["pos"][0]), sy(m["pos"][1])
                col = "#e53935" if m["state"] == "chase" else ("#b388ff" if m["state"] == "recoil" else "#5d8c4a")
                self.cv.coords(body, mx - 1.5 * s, my - 0.65 * s, mx + 1.5 * s, my + 0.65 * s)
                self.cv.itemconfigure(body, fill=col, state="normal")
                self.cv.coords(lbl, mx, my - 1.05 * s)
                self.cv.itemconfigure(lbl, text=m["id"] + ("!" if m["state"] == "chase" else ""), state="normal")
            else:
                self.cv.itemconfigure(body, state="hidden")
                self.cv.itemconfigure(lbl, state="hidden")

        # Út Sen
        px, py = sx(sim.pos[0]), sy(sim.pos[1])
        rr = (sim.t["interact_radius"] if sim._at_surface() else sim.t["catch_radius"]) * s
        self.cv.coords(self._player_ring, px - rr, py - rr, px + rr, py + rr)
        self.cv.coords(self._player_body, px - 0.65 * s, py - 0.65 * s, px + 0.65 * s, py + 0.65 * s)
        ang = math.radians(sim.heading)
        self.cv.coords(self._player_dir, px, py, px + math.cos(ang) * 0.95 * s, py + math.sin(ang) * 0.95 * s)

        # HUD
        sec_left = math.ceil(sim.time_left_ticks / 60.0)
        self.cv.itemconfigure(self._hud_time, text=f"⏱ {sec_left // 60}:{sec_left % 60:02d}")
        frac = max(0.0, min(1.0, sim.oxygen_ticks / max(1, sim.oxygen_max)))
        self.cv.coords(self._oxy_fill, 222, 14, 222 + 256 * frac, 40)
        self.cv.itemconfigure(self._oxy_txt, text=f"Oxy {math.ceil(sim.oxygen_ticks / 60.0)}s")
        hp_s = " ".join("♥" if i < sim.hp else "♡" for i in range(sim.hp_max))
        self.cv.itemconfigure(self._hud_hp, text=hp_s)
        zone = "Nông" if sim.pos[1] < 10 else ("Giữa" if sim.pos[1] < 20 else "Sâu")
        self.cv.itemconfigure(self._hud_depth, text=f"Sâu: {sim.pos[1]:.1f}m ({zone})")

        hold = sim.hold
        for i, (fill_id, fbar_id, x0, y0, sz) in enumerate(self._slots):
            if i < len(hold):
                it = hold[i]
                fval = float(it["fresh"])
                col = KIND_HEX.get(it["kind"], "#bbbbbb")
                bcol = "#e53935" if fval < self._spoiled_below else ("#ffb300" if fval < 50 else "#66bb6a")
                self.cv.itemconfigure(fill_id, fill=col, state="normal")
                self.cv.coords(fbar_id, x0 + 3, y0 + sz - 6, x0 + 3 + max(2, (sz - 6) * (fval / 100.0)), y0 + sz - 2)
                self.cv.itemconfigure(fbar_id, fill=bcol, state="normal")
            else:
                self.cv.itemconfigure(fill_id, state="hidden")
                self.cv.itemconfigure(fbar_id, state="hidden")
        self.cv.itemconfigure(self._hud_hold, text=f"Giỏ {len(hold)}/{len(self._slots)}")

        try:
            self.root.update()
        except self._tk.TclError:
            self._closed = True

    def close(self):
        if not self._closed:
            self._closed = True
            try:
                self.root.destroy()
            except Exception:
                pass


class _SoftwareGatherRenderer:
    """Framebuffer RGB 1280x720 thuần Python (fallback khi chạy CI không có display)."""

    def __init__(self, tuning):
        g = tuning["gather"]
        self._geom = _scene_geom(g["bounds"])
        self._stride = WIDTH * 3
        self._base = bytearray(WIDTH * HEIGHT * 3)
        self._frame = bytearray(WIDTH * HEIGHT * 3)
        self._spoiled_below = float(tuning["freshness"]["spoiled_below"])

        _, D, top, _, s, ox, oy = self._geom
        X = g["bounds"]["x"][1]
        sx0 = max(0, int(ox))
        sx1 = min(WIDTH, int(ox + X * s))
        oy_i = max(0, int(oy))
        top_i = max(0, int(top))
        self._fill_rect(self._base, 0, 0, WIDTH, HEIGHT, (16, 22, 28))
        self._fill_rect(self._base, 0, top_i, WIDTH, oy_i, (207, 234, 245))
        bands = ((73, 176, 220), (35, 108, 148), (7, 31, 54))
        for idx, rgb in enumerate(bands):
            y0 = int(oy + D * (idx / 3.0) * s)
            y1 = int(oy + D * ((idx + 1) / 3.0) * s)
            self._fill_rect(self._base, sx0, y0, sx1, y1, rgb)
        dp = g["dock_pos"]
        dx0 = int(ox + (dp[0] - 1.5) * s)
        dx1 = int(ox + (dp[0] + 1.5) * s)
        self._fill_rect(self._base, dx0, int(oy - 1.5 * s), dx1, int(oy + 0.2 * s), (141, 110, 75))

    def _fill_rect(self, buf: bytearray, x0: int, y0: int, x1: int, y1: int, rgb):
        x0 = max(0, x0)
        x1 = min(WIDTH, x1)
        y0 = max(0, y0)
        y1 = min(HEIGHT, y1)
        if x1 <= x0 or y1 <= y0:
            return
        row = bytes(rgb) * (x1 - x0)
        span = (x1 - x0) * 3
        for y in range(y0, y1):
            off = y * self._stride + x0 * 3
            buf[off:off + span] = row

    def render(self, sim, t_rel: float):
        buf = self._frame
        buf[:] = self._base
        _, D, _, bottom, s, ox, oy = self._geom
        for i in range(18):
            bx = int(ox + (6 + i * 5.2 + math.sin(t_rel * 2.0 + i) * 0.4) * s)
            d = ((3 + (i * 5) % 24) - t_rel * (0.8 + (i % 4) * 0.25)) % (D - 1.0) + 0.5
            by = int(oy + d * s)
            self._fill_rect(buf, bx - 3, by - 3, bx + 3, by + 3, (214, 242, 255))
        for n in sim.nodes:
            nx, ny = int(ox + n["pos"][0] * s), int(oy + n["pos"][1] * s)
            self._fill_rect(buf, nx - 10, ny - 5, nx + 10, ny + 5, KIND_RGB.get(n["kind"], (180, 180, 180)))
        for f in sim.fish:
            fx, fy = int(ox + f["pos"][0] * s), int(oy + f["pos"][1] * s)
            self._fill_rect(buf, fx - 9, fy - 5, fx + 9, fy + 5, KIND_RGB.get(f["kind"], (214, 230, 242)))
        for m in sim.monsters:
            mx, my = int(ox + m["pos"][0] * s), int(oy + m["pos"][1] * s)
            col = (229, 57, 53) if m["state"] == "chase" else (93, 140, 74)
            self._fill_rect(buf, mx - 16, my - 7, mx + 16, my + 7, col)
        px, py = int(ox + sim.pos[0] * s), int(oy + sim.pos[1] * s)
        self._fill_rect(buf, px - 7, py - 7, px + 7, py + 7, (255, 138, 61))
        frac = max(0.0, min(1.0, sim.oxygen_ticks / max(1, sim.oxygen_max)))
        self._fill_rect(buf, 220, 12, 220 + int(260 * frac), 40, (41, 182, 246))
        y0 = int(HEIGHT - bottom + 10)
        for idx, it in enumerate(sim.hold[:12]):
            x0 = 16 + idx * 38
            self._fill_rect(buf, x0, y0, x0 + 34, y0 + 34, KIND_RGB.get(it["kind"], (180, 180, 180)))
            bcol = (229, 57, 53) if float(it["fresh"]) < self._spoiled_below else (102, 187, 106)
            self._fill_rect(buf, x0, y0 + 30, x0 + 34, y0 + 34, bcol)

    def close(self):
        pass


def _make_renderer(tuning, choice: str):
    if choice in ("auto", "tk"):
        try:
            return _TkGatherRenderer(tuning)
        except Exception:
            if choice == "tk":
                raise
    return _SoftwareGatherRenderer(tuning)


def run_benchmark(seed: int, duration_s: float, out_path: str, warmup_s: float = 3.0,
                  renderer_choice: str = "auto", t_launch: float = None) -> dict:
    t0 = _MODULE_START if t_launch is None else t_launch
    tuning = load_contract()["tuning"]
    idle = InputState((0.0, 0.0), {}, set())

    def new_sim():
        return GatherSim(tuning, {}, Streams(seed), IdAllocator(), day=1)

    sim = new_sim()
    renderer = _make_renderer(tuning, renderer_choice)
    dts = []
    meas_start = 0.0
    prev = 0.0

    try:
        # Khung đầu tiên hoàn tất -> chốt load_ms
        sim.step(idle)
        renderer.render(sim, 0.0)
        first_frame = time.perf_counter()
        load_ms = (first_frame - t0) * 1000.0

        # Làm nóng (mặc định 3 s)
        acc = 0.0
        last = first_frame
        while (last - first_frame) < warmup_s:
            now = time.perf_counter()
            frame_dt = min(0.1, max(0.0, now - last))
            last = now
            acc += frame_dt
            steps = 0
            while acc >= DT_STEP and steps < 5:
                if sim.done:
                    sim = new_sim()
                sim.step(idle)
                acc -= DT_STEP
                steps += 1
            renderer.render(sim, last - first_frame)

        # Đo duration_s giây
        meas_start = time.perf_counter()
        prev = meas_start
        while True:
            now = time.perf_counter()
            if (now - meas_start) >= duration_s and dts:
                break
            frame_dt = min(0.1, max(0.0, now - prev))
            acc += frame_dt
            steps = 0
            while acc >= DT_STEP and steps < 5:
                if sim.done:
                    sim = new_sim()
                sim.step(idle)
                acc -= DT_STEP
                steps += 1
            renderer.render(sim, prev - first_frame)
            after = time.perf_counter()
            dts.append(max(1e-7, after - prev))
            prev = after
    finally:
        renderer.close()

    frames = len(dts)
    measured_s = round(max(1e-6, prev - meas_start), 4)
    avg_fps = frames / measured_s
    k = max(1, math.ceil(0.01 * frames))
    slowest = sorted(dts, reverse=True)[:k]
    p1_low_fps = k / sum(slowest)

    result = {
        "avg_fps": round(avg_fps, 4),
        "p1_low_fps": round(p1_low_fps, 4),
        "frames": frames,
        "measured_s": measured_s,
        "load_ms": round(load_ms, 3),
    }
    _atomic_write_json(out_path, result)
    return result


def main(argv=None) -> int:
    p = _Parser(prog="chonoi.bench")
    p.add_argument("--seed", required=True, type=_int("seed"))
    p.add_argument("--duration", required=True, type=_float("duration"))
    p.add_argument("--out", required=True)
    p.add_argument("--warmup", type=_float("warmup"), default=3.0)
    p.add_argument("--renderer", choices=["auto", "tk", "software"], default="auto")
    a = p.parse_args(argv)
    try:
        if a.duration <= 0:
            raise BadInput("--duration phải > 0")
        if a.warmup < 0:
            raise BadInput("--warmup phải >= 0")
        if not str(a.out).strip():
            raise BadInput("--out không được rỗng")
        run_benchmark(a.seed, a.duration, a.out, warmup_s=a.warmup, renderer_choice=a.renderer)
    except BadInput as e:
        sys.stderr.write(f"đầu vào sai: {e}\n")
        return 2
    except OSError as e:
        sys.stderr.write(f"lỗi ghi: {e}\n")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
