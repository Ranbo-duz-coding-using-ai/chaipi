"""Engine worker: one thread that owns Stockfish.

Commands are latest-wins: search()/ponder() replace whatever is queued and stop whatever is
running, so the UI never waits behind a stale search. Every command gets a tag; results
carry it, and the app ignores tags it no longer cares about.

    search(board, preset)  timed (or infinite, for Manual) search → EngineInfo… EngineDone
    ponder(board)          infinite analysis on the opponent's turn (prediction + warm hash)
    stop()                 finish the running search now; its EngineDone still arrives ("play now")
    cancel()               stop and discard

If Stockfish dies (SF19 exits on any invalid input), the worker relaunches it, re-applies
the options and re-runs the interrupted command, then reports EngineRestarted.
"""
from __future__ import annotations

import logging
import queue
import shutil
import threading
import time
from collections import deque
from dataclasses import dataclass

import chess
import chess.engine

from chaipi.events import (EngineDone, EngineFailed, EngineInfo, EngineReady, EngineRestarted,
                           Line, Snapshot)

log = logging.getLogger(__name__)


@dataclass
class _Command:
    tag: int
    kind: str                       # "search" | "ponder"
    board: chess.Board
    limit: chess.engine.Limit | None
    multipv: int
    options: dict


def snapshot_from(analysis: chess.engine.AnalysisResult | chess.engine.SimpleAnalysisResult) -> Snapshot:
    infos = [i for i in analysis.multipv if i] or [analysis.info]
    first = infos[0] if infos else {}
    lines = tuple(Line(score=i.get("score"), wdl=i.get("wdl"), pv=tuple(i.get("pv", ()))) for i in infos)
    return Snapshot(
        depth=int(first.get("depth", 0) or 0),
        seldepth=int(first.get("seldepth", 0) or 0),
        nodes=int(first.get("nodes", 0) or 0),
        nps=int(first.get("nps", 0) or 0),
        time=float(first.get("time", 0.0) or 0.0),
        lines=lines,
    )


class EngineWorker:
    def __init__(self, path: str, out: queue.Queue, options: dict | None = None, nice: int = 0,
                 info_hz: float = 5.0, restart_max: int = 5, restart_window_s: float = 60.0):
        self.path = path
        self.nice = nice
        self.name = ""
        self._out = out
        self._options = dict(options or {})
        self._interval = 1.0 / info_hz if info_hz > 0 else 0.0
        self._restart_max = restart_max
        self._restart_window = restart_window_s
        self._restarts: deque[float] = deque()

        self._cv = threading.Condition()
        self._tag = 0
        self._pending: _Command | None = None
        self._current: chess.engine.SimpleAnalysisResult | None = None
        self._stop_flag = False
        self._closing = False
        self._engine: chess.engine.SimpleEngine | None = None
        self._supported: set[str] = set()
        self._thread = threading.Thread(target=self._run, name="engine", daemon=True)

    # --- API (any thread) ------------------------------------------------------------
    def start(self) -> None:
        self._thread.start()

    @property
    def alive(self) -> bool:
        return self._thread.is_alive()

    def search(self, board: chess.Board, limit: chess.engine.Limit | None,
               multipv: int = 1, options: dict | None = None) -> int:
        return self._submit("search", board, limit, multipv, options)

    def ponder(self, board: chess.Board, multipv: int = 1, options: dict | None = None) -> int:
        return self._submit("ponder", board, None, multipv, options)

    def stop(self) -> None:
        with self._cv:
            self._stop_current_locked()

    def cancel(self) -> None:
        with self._cv:
            self._tag += 1
            self._pending = None
            self._stop_current_locked()

    def close(self, timeout: float = 5.0) -> None:
        with self._cv:
            self._closing = True
            self._pending = None
            self._stop_current_locked()
            self._cv.notify_all()
        if self._thread.is_alive():
            self._thread.join(timeout)

    # --- internals -------------------------------------------------------------------
    def _submit(self, kind: str, board: chess.Board, limit, multipv: int, options: dict | None) -> int:
        with self._cv:
            self._tag += 1
            self._pending = _Command(self._tag, kind, board.copy(), limit, max(1, multipv), dict(options or {}))
            self._stop_current_locked()
            self._cv.notify_all()
            return self._tag

    def _stop_current_locked(self) -> None:
        self._stop_flag = True
        if self._current is not None:
            try:
                self._current.stop()
            except Exception:  # engine already gone; the worker notices on its own
                pass

    def _superseded_locked(self, cmd: _Command) -> bool:
        return self._closing or self._pending is not None or cmd.tag != self._tag

    def _emit(self, event) -> None:
        self._out.put(event)

    def _command_line(self) -> list[str]:
        if self.nice and shutil.which("nice"):
            return ["nice", "-n", str(self.nice), self.path]
        return [self.path]

    def _launch(self) -> None:
        engine = chess.engine.SimpleEngine.popen_uci(self._command_line(), timeout=15)
        self._supported = {name.lower() for name in engine.options}
        opts = self._known(self._options)
        if opts:
            engine.configure(opts)
        self._engine = engine
        self.name = engine.id.get("name", "engine")
        log.info("engine started: %s (%s) options=%s", self.name, " ".join(self._command_line()), opts)

    def _known(self, options: dict) -> dict:
        """Drop options this engine doesn't declare (python-chess would raise on them)."""
        return {k: v for k, v in options.items() if k.lower() in self._supported}

    def _quit_engine(self) -> None:
        engine, self._engine = self._engine, None
        if engine is None:
            return
        try:
            engine.quit()
        except Exception:
            try:
                engine.close()
            except Exception:
                pass

    def _run(self) -> None:
        try:
            self._launch()
        except Exception as e:  # missing binary, bad path, …
            log.exception("engine launch failed")
            self._emit(EngineFailed(f"{type(e).__name__}: {e}"))
            return
        self._emit(EngineReady(self.name))
        try:
            while True:
                with self._cv:
                    while self._pending is None and not self._closing:
                        self._cv.wait()
                    if self._closing:
                        break
                    cmd, self._pending = self._pending, None
                    self._stop_flag = False
                if not self._execute(cmd):
                    break
        finally:
            self._quit_engine()
            log.info("engine worker stopped")

    def _execute(self, cmd: _Command) -> bool:
        """Run one command, restarting the engine if it dies. False = give up for good."""
        while True:
            try:
                self._analyse(cmd)
                return True
            except (chess.engine.EngineTerminatedError, chess.engine.EngineError, OSError) as e:
                with self._cv:
                    self._current = None
                    if self._closing:
                        return False
                log.warning("engine died during %s: %s", cmd.kind, e)
                if not self._restart(f"{type(e).__name__}: {e}"):
                    return False
                with self._cv:
                    if self._superseded_locked(cmd):
                        return True          # a newer command is waiting; don't re-run this one

    def _restart(self, reason: str) -> bool:
        now = time.monotonic()
        while self._restarts and now - self._restarts[0] > self._restart_window:
            self._restarts.popleft()
        if len(self._restarts) >= self._restart_max:
            self._emit(EngineFailed(f"engine keeps dying ({reason})"))
            return False
        self._restarts.append(now)
        self._quit_engine()
        try:
            self._launch()
        except Exception as e:
            log.exception("engine relaunch failed")
            self._emit(EngineFailed(f"relaunch failed: {e}"))
            return False
        self._emit(EngineRestarted(reason))
        return True

    def _analyse(self, cmd: _Command) -> None:
        assert self._engine is not None
        analysis = self._engine.analysis(cmd.board, cmd.limit, multipv=cmd.multipv,
                                         options=self._known(cmd.options), info=chess.engine.INFO_ALL)
        with self._cv:
            self._current = analysis
            if self._stop_flag or self._superseded_locked(cmd):
                analysis.stop()
        last = 0.0
        try:
            for _ in analysis:
                now = time.monotonic()
                if now - last >= self._interval:
                    last = now
                    self._emit(EngineInfo(cmd.tag, cmd.kind, snapshot_from(analysis)))
            best = analysis.wait()
        finally:
            with self._cv:
                self._current = None
        snap = snapshot_from(analysis)
        move = best.move if best is not None else None
        if move is None and snap.pv:
            move = snap.pv[0]
        if move is not None and move not in cmd.board.legal_moves:
            log.error("engine returned illegal move %s", move)
            move = None
        self._emit(EngineDone(cmd.tag, cmd.kind, move, snap))
