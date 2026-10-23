"""One game: board, sides, mode, per-ply history (with engine suggestions), undo, result, PGN."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

import chess
import chess.engine
import chess.pgn

from chaipi.game.storage import CURRENT_VERSION

MODES = ("advisor", "opponent", "analysis")
SOURCES = ("suggestion", "entry", "predicted", "voice")

_TERMINATION_TEXT = {
    chess.Termination.CHECKMATE: "Checkmate",
    chess.Termination.STALEMATE: "Stalemate",
    chess.Termination.INSUFFICIENT_MATERIAL: "Insufficient material",
    chess.Termination.SEVENTYFIVE_MOVES: "75-move rule",
    chess.Termination.FIVEFOLD_REPETITION: "Fivefold repetition",
    chess.Termination.FIFTY_MOVES: "50-move rule",
    chess.Termination.THREEFOLD_REPETITION: "Threefold repetition",
}


def color_name(color: chess.Color) -> str:
    return "White" if color == chess.WHITE else "Black"


def fmt_score(score: chess.engine.Score | None) -> str:
    """'+0.42' (pawns), 'M4' (mate in 4 for this side), '-M3' (mated in 3)."""
    if score is None:
        return ""
    mate = score.mate()
    if mate is not None:
        return f"M{mate}" if mate > 0 else f"-M{-mate}"
    return f"{score.score() / 100:+.2f}"


def fmt_wdl(wdl: chess.engine.Wdl | None) -> str:
    """Per-mille win/draw/loss as 'W58 D35 L7'."""
    if wdl is None:
        return ""
    total = wdl.total() or 1000
    w, d, l = (round(100 * x / total) for x in (wdl.wins, wdl.draws, wdl.losses))
    return f"W{w} D{d} L{l}"


def move_number_label(board: chess.Board) -> str:
    """'12.' when White is to move, '12…' when Black is."""
    return f"{board.fullmove_number}{'.' if board.turn == chess.WHITE else '…'}"


@dataclass
class Suggestion:
    """The engine's choice in one position. Scores are stored from White's point of view."""
    uci: str
    cp: int | None = None
    mate: int | None = None
    depth: int | None = None
    wdl: tuple[int, int, int] | None = None   # White's W/D/L per mille

    @classmethod
    def from_engine(cls, move: chess.Move, score: chess.engine.PovScore | None,
                    wdl: chess.engine.PovWdl | None, depth: int | None) -> Suggestion:
        cp = mate = None
        if score is not None:
            white = score.white()
            mate = white.mate()
            cp = None if mate is not None else white.score()
        w = None
        if wdl is not None:
            ww = wdl.white()
            w = (ww.wins, ww.draws, ww.losses)
        return cls(uci=move.uci(), cp=cp, mate=mate, depth=depth or None, wdl=w)

    @property
    def move(self) -> chess.Move:
        return chess.Move.from_uci(self.uci)

    def score(self, pov: chess.Color = chess.WHITE) -> chess.engine.Score | None:
        if self.mate is not None:
            s: chess.engine.Score = chess.engine.Mate(self.mate)
        elif self.cp is not None:
            s = chess.engine.Cp(self.cp)
        else:
            return None
        return s if pov == chess.WHITE else -s

    def to_dict(self) -> dict:
        d = {"uci": self.uci, "cp": self.cp, "mate": self.mate, "depth": self.depth}
        if self.wdl is not None:
            d["wdl"] = list(self.wdl)
        return d

    @classmethod
    def from_dict(cls, d: dict) -> Suggestion:
        wdl = d.get("wdl")
        return cls(uci=d["uci"], cp=d.get("cp"), mate=d.get("mate"), depth=d.get("depth"),
                   wdl=tuple(wdl) if wdl else None)


@dataclass
class Ply:
    uci: str
    source: str = "entry"
    suggestion: Suggestion | None = None   # what the engine suggested before this move, if anything

    @property
    def followed(self) -> bool:
        return self.suggestion is not None and self.suggestion.uci == self.uci

    def to_dict(self) -> dict:
        d: dict = {"uci": self.uci, "source": self.source}
        if self.suggestion is not None:
            d["suggestion"] = self.suggestion.to_dict()
        return d

    @classmethod
    def from_dict(cls, d: dict) -> Ply:
        s = d.get("suggestion")
        return cls(uci=d["uci"], source=d.get("source", "entry"),
                   suggestion=Suggestion.from_dict(s) if s else None)


@dataclass
class Session:
    game_number: int
    user_color: chess.Color = chess.WHITE
    mode: str = "advisor"
    preset_key: str = "deep"
    preset_label: str = "Deep 12s"
    elo: int | None = None
    started_at: datetime = field(default_factory=lambda: datetime.now().replace(microsecond=0))
    start_fen: str = chess.STARTING_FEN
    player_name: str = "You"
    opponent_name: str = "Opponent"
    engine_name: str = "Stockfish 19"
    plies: list[Ply] = field(default_factory=list)
    result: str = "*"
    termination: str | None = None

    def __post_init__(self) -> None:
        if self.mode not in MODES:
            raise ValueError(f"unknown mode {self.mode!r}")
        self.board = chess.Board(self.start_fen)
        for ply in self.plies:   # replay (resume): stop at the first move that doesn't fit
            move = chess.Move.from_uci(ply.uci)
            if move not in self.board.legal_moves:
                raise ValueError(f"illegal move {ply.uci} at ply {len(self.board.move_stack) + 1}")
            self.board.push(move)

    # --- whose turn is it? -----------------------------------------------------------
    @property
    def engine_color(self) -> chess.Color | None:
        """The side the engine searches for: yours in Advisor, its own in Opponent."""
        if self.mode == "advisor":
            return self.user_color
        if self.mode == "opponent":
            return not self.user_color
        return None

    @property
    def is_over(self) -> bool:
        return self.result != "*"

    @property
    def engine_to_move(self) -> bool:
        return not self.is_over and self.engine_color is not None and self.board.turn == self.engine_color

    @property
    def user_turn(self) -> bool:
        return self.board.turn == self.user_color

    @property
    def last_move(self) -> chess.Move | None:
        return self.board.move_stack[-1] if self.board.move_stack else None

    # --- changing the game -----------------------------------------------------------
    def push(self, move: chess.Move, source: str = "entry", suggestion: Suggestion | None = None) -> Ply:
        if self.is_over:
            raise ValueError("game is over")
        if move not in self.board.legal_moves:
            raise ValueError(f"illegal move {move.uci()} in {self.board.fen()}")
        ply = Ply(uci=move.uci(), source=source, suggestion=suggestion)
        self.board.push(move)
        self.plies.append(ply)
        self.check_over()
        return ply

    def undo(self) -> list[Ply]:
        """Step back to the last position where the user had to enter something.

        Advisor/Analysis: every ply was a user input, so one ply. Opponent: also take back
        the engine's own reply. Undoing a finished game re-opens it.
        """
        popped: list[Ply] = []
        if not self.plies:
            return popped
        self.result, self.termination = "*", None
        popped.append(self._pop())
        while self.plies and self.mode == "opponent" and self.engine_to_move:
            popped.append(self._pop())
        return popped

    def _pop(self) -> Ply:
        self.board.pop()
        return self.plies.pop()

    def check_over(self) -> bool:
        # Not outcome(claim_draw=True): that also ends the game when a repetition is merely
        # *reachable* with one more move. Here the third occurrence has to be on the board.
        outcome = self.board.outcome()
        if outcome is None and self.board.is_repetition(3):
            outcome = chess.Outcome(chess.Termination.THREEFOLD_REPETITION, None)
        if outcome is None and self.board.is_fifty_moves():
            outcome = chess.Outcome(chess.Termination.FIFTY_MOVES, None)
        if outcome is None:
            return False
        self.result = outcome.result()
        self.termination = _TERMINATION_TEXT.get(outcome.termination, outcome.termination.name.title())
        return True

    def resign(self, color: chess.Color) -> None:
        self.result = "0-1" if color == chess.WHITE else "1-0"
        self.termination = f"{color_name(color)} resigned"

    def agree_draw(self) -> None:
        self.result, self.termination = "1/2-1/2", "Draw agreed"

    # --- summaries -------------------------------------------------------------------
    def followed_stats(self) -> tuple[int, int]:
        with_suggestion = [p for p in self.plies if p.suggestion is not None]
        return sum(p.followed for p in with_suggestion), len(with_suggestion)

    def result_text(self) -> str:
        """'you win 1-0' / 'you lose 0-1' / 'draw ½-½' from the user's side."""
        if self.result == "1/2-1/2":
            return "draw ½-½"
        if self.result == "*":
            return "in progress"
        user_won = (self.result == "1-0") == (self.user_color == chess.WHITE)
        return f"{'you win' if user_won else 'you lose'} {self.result}"

    @property
    def filename(self) -> str:
        return (f"{self.game_number:04d}_{self.started_at:%Y-%m-%d_%H%M}_"
                f"{color_name(self.user_color)}_{self.mode.title()}.txt")

    # --- PGN -------------------------------------------------------------------------
    def _comment(self, board: chess.Board, ply: Ply) -> str:
        s = ply.suggestion
        if s is None:
            return ""
        try:
            sf_san = board.san(s.move)
        except (ValueError, AssertionError):
            sf_san = s.uci
        score = fmt_score(s.score(chess.WHITE))
        detail = " ".join(x for x in (score, f"d{s.depth}" if s.depth else "") if x)
        if ply.followed:
            return f"sf {sf_san} {detail}".strip()
        you = board.san(chess.Move.from_uci(ply.uci))
        return f"you: {you} · sf: {sf_san} {detail}".strip()

    def pgn(self) -> str:
        game = chess.pgn.Game()
        h = game.headers
        h["Event"] = "ChAIpi casual game"
        h["Site"] = "ChAIpi"
        h["Date"] = f"{self.started_at:%Y.%m.%d}"
        h["Round"] = str(self.game_number)
        h["White"] = self.player_name if self.user_color == chess.WHITE else self.opponent_name
        h["Black"] = self.opponent_name if self.user_color == chess.WHITE else self.player_name
        h["Result"] = self.result
        h["Time"] = f"{self.started_at:%H:%M:%S}"
        h["Mode"] = self.mode.title()
        h["Engine"] = self.engine_name
        h["Preset"] = self.preset_label
        if self.termination:
            h["Termination"] = self.termination
        followed, total = self.followed_stats()
        h["FollowedSuggestions"] = f"{followed}/{total}"

        board = chess.Board(self.start_fen)
        if self.start_fen != chess.STARTING_FEN:
            game.setup(board)
        node: chess.pgn.GameNode = game
        for ply in self.plies:
            move = chess.Move.from_uci(ply.uci)
            comment = self._comment(board, ply)
            node = node.add_variation(move)
            if comment:
                node.comment = comment
            board.push(move)
        exporter = chess.pgn.StringExporter(headers=True, variations=False, comments=True, columns=80)
        return game.accept(exporter) + "\n"

    # --- resume ----------------------------------------------------------------------
    def to_dict(self) -> dict:
        return {
            "version": CURRENT_VERSION,
            "game_number": self.game_number,
            "started_at": self.started_at.isoformat(),
            "start_fen": self.start_fen,
            "user_color": color_name(self.user_color).lower(),
            "mode": self.mode,
            "preset": self.preset_key,
            "preset_label": self.preset_label,
            "elo": self.elo,
            "player_name": self.player_name,
            "opponent_name": self.opponent_name,
            "engine_name": self.engine_name,
            "filename": self.filename,
            "fen": self.board.fen(),
            "plies": [p.to_dict() for p in self.plies],
            "result": self.result,
            "termination": self.termination,
        }

    @classmethod
    def from_dict(cls, d: dict) -> Session:
        return cls(
            game_number=int(d["game_number"]),
            user_color=chess.WHITE if d.get("user_color", "white") == "white" else chess.BLACK,
            mode=d.get("mode", "advisor"),
            preset_key=d.get("preset", "deep"),
            preset_label=d.get("preset_label", ""),
            elo=d.get("elo"),
            started_at=datetime.fromisoformat(d["started_at"]),
            start_fen=d.get("start_fen", chess.STARTING_FEN),
            player_name=d.get("player_name", "You"),
            opponent_name=d.get("opponent_name", "Opponent"),
            engine_name=d.get("engine_name", "Stockfish 19"),
            plies=[Ply.from_dict(p) for p in d.get("plies", [])],
            result=d.get("result", "*"),
            termination=d.get("termination"),
        )
