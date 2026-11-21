"""Vòng tick (Contract B v1.1): gather, quan, day và pause/resumed."""

import math
import os

from .errors import BadInput
from .ids import IdAllocator
from .inputs import InputPlayer
from .inventory import write_inventory
from .jsonl import JsonlWriter
from .rng import Streams
from .sim.day import DaySim
from .sim.gather import GatherSim
from .sim.quan import QuanSim


def build_sim(mode, tuning, scenario, seed, inventory, days=1):
    streams, ids = Streams(seed), IdAllocator()
    if mode == "gather":
        return GatherSim(tuning, scenario, streams, ids)
    if mode == "quan":
        return QuanSim(tuning, scenario, streams, ids, inventory=inventory)
    return DaySim(tuning, scenario, streams, ids, days=days)


def _common(sim, tick, sim_tick, phase_tick, tuning, state):
    mult = tuning["score"]["reputation_multiplier"]
    return {
        "type": "snapshot",
        "tick": tick,
        "sim_tick": sim_tick,
        "mode": sim.mode,
        "phase": sim.phase,
        "phase_tick": phase_tick,
        "state": state,
        "time_left_ticks": sim.time_left_ticks,
        "money": sim.money,
        "earned": sim.earned,
        "reputation": sim.reputation,
        "score": sim.earned + mult * math.floor(sim.reputation),
    }


class Session:
    """Một lượt chơi: dựng sim, bước từng tick (hỗ trợ pause/day), lấy snapshot / dòng end."""

    def __init__(self, mode, tuning, scenario, seed, inventory=None, days=1):
        self.mode = mode
        self.tuning = tuning
        self.sim = build_sim(mode, tuning, scenario, seed, inventory, days=days)
        self.tick = 0
        self.sim_tick = 0
        self.paused = False
        self.phase_changed = False

    @property
    def done(self) -> bool:
        return self.sim.done

    def _format_event(self, tick, ev_phase, name, data, ev_day=None):
        row = {"type": "event", "tick": tick, "phase": ev_phase}
        if self.mode == "day":
            row["day"] = ev_day
        row["name"] = name
        row["data"] = data
        return row

    def startup_events(self) -> list:
        if not hasattr(self.sim, "startup_events"):
            return []
        return [
            self._format_event(0, ev_phase, name, data, ev_day)
            for name, data, ev_phase, ev_day in self.sim.startup_events()
        ]

    def snapshot(self) -> dict:
        state = "finished" if self.sim.done else ("paused" if self.paused else "playing")
        s = _common(self.sim, self.tick, self.sim_tick, self.sim.phase_tick, self.tuning, state)
        s.update(self.sim.snapshot())
        return s

    def step(self, inp) -> list:
        """Chạy một bước với `inp` (chonoi.inputs.InputState); xét pause trước gameplay."""
        self.phase_changed = False
        prev_phase = self.sim.phase
        prev_day = getattr(self.sim, "day", None)

        pause_edge = inp.pressed("pause")
        if not self.paused and pause_edge:
            self.paused = True
            self.tick += 1
            return [self._format_event(self.tick, prev_phase, "paused", {}, prev_day)]

        if self.paused and not pause_edge:
            self.tick += 1
            return []

        rows = []
        resumed_now = False
        if self.paused and pause_edge:
            self.paused = False
            resumed_now = True

        raw_events = self.sim.step(inp)
        self.tick += 1
        self.sim_tick += 1

        if resumed_now:
            rows.append(self._format_event(self.tick, prev_phase, "resumed", {}, prev_day))

        for ev in raw_events:
            if len(ev) == 4:
                name, data, ev_phase, ev_day = ev
            else:
                name, data = ev
                ev_phase, ev_day = self.sim.phase, None
            rows.append(self._format_event(self.tick, ev_phase, name, data, ev_day))

        self.phase_changed = (self.sim.phase != prev_phase) or (getattr(self.sim, "day", None) != prev_day)
        return rows

    def end_row(self) -> dict:
        sim = self.sim
        state = "finished" if sim.done else ("paused" if self.paused else "playing")
        score = _common(sim, self.tick, self.sim_tick, sim.phase_tick, self.tuning, state)["score"]
        row = {
            "type": "end",
            "ticks": self.tick,
            "sim_tick": self.sim_tick,
            "mode": sim.mode,
            "state": state,
            "reason": sim.reason if sim.done else "tick_limit",
            "money": sim.money,
            "earned": sim.earned,
            "reputation": sim.reputation,
            "score": score,
        }
        if self.mode == "day":
            row["days_completed"] = sim.days_completed
        return row

    def write_inventory_if_done(self, inventory_out):
        """File kho: ghi MỘT lần khi có gather_end; chưa kết thúc thì giữ nguyên file đích."""
        if self.mode == "gather" and self.sim.done and inventory_out:
            write_inventory(inventory_out, self.sim.inventory_items())


def run(mode, tuning, scenario, seed, frames, ticks, out_path, snapshot_every,
        inventory=None, inventory_out=None, days=1):
    sess = Session(mode, tuning, scenario, seed, inventory=inventory, days=days)
    player = InputPlayer(frames)
    w = JsonlWriter(out_path)
    aborted = False
    try:
        w.write(sess.snapshot())  # tick 0: sau khi dựng scenario, trước mọi input
        for row in sess.startup_events():
            w.write(row)
        last_snapped = 0
        while sess.tick < ticks and not sess.done:
            inp = player.advance(sess.tick)
            for row in sess.step(inp):
                w.write(row)
            if sess.tick % snapshot_every == 0 or sess.done or sess.phase_changed:
                w.write(sess.snapshot())
                last_snapped = sess.tick
        if last_snapped != sess.tick:
            w.write(sess.snapshot())
        w.write(sess.end_row())
    except BadInput:
        aborted = True
        raise
    finally:
        w.close()
        if aborted and os.path.exists(out_path):
            os.unlink(out_path)
    sess.write_inventory_if_done(inventory_out)
    return sess.sim
