"""Joystick move entry: piece → file → rank (→ origin → promotion), legal moves only.

Each step only offers choices that still lead to a legal move. A step with exactly one
choice is filled in automatically (except the first step, so a move is never entered with
zero presses). The predicted move's piece, file, rank, origin and promotion are
pre-selected, and accept_prediction() enters it in one go (long-press OK).
"""
from __future__ import annotations

from dataclasses import dataclass, field

import chess

ORDER = [chess.PAWN, chess.KNIGHT, chess.BISHOP, chess.ROOK, chess.QUEEN, chess.KING]
PROMOTION_ORDER = [chess.QUEEN, chess.ROOK, chess.BISHOP, chess.KNIGHT]
CASTLE_SHORT = "O-O"
CASTLE_LONG = "O-O-O"
PIECE_NAMES = {chess.PAWN: "Pawn", chess.KNIGHT: "Knight", chess.BISHOP: "Bishop",
               chess.ROOK: "Rook", chess.QUEEN: "Queen", chess.KING: "King"}

Kind = int | str   # a piece type, or CASTLE_SHORT / CASTLE_LONG


def castling_move(board: chess.Board, which: str) -> chess.Move | None:
    for move in board.legal_moves:
        if board.is_castling(move) and board.is_kingside_castling(move) == (which == CASTLE_SHORT):
            return move
    return None


def piece_moves(board: chess.Board, kind: int) -> list[chess.Move]:
    """Legal non-castling moves of one piece type."""
    return [m for m in board.legal_moves
            if not board.is_castling(m) and board.piece_type_at(m.from_square) == kind]


def piece_options(board: chess.Board) -> list[Kind]:
    kinds = {board.piece_type_at(m.from_square) for m in board.legal_moves if not board.is_castling(m)}
    opts: list[Kind] = [k for k in ORDER if k in kinds]
    opts += [c for c in (CASTLE_SHORT, CASTLE_LONG) if castling_move(board, c) is not None]
    return opts


def file_options(board: chess.Board, kind: int) -> list[int]:
    """Files of the destination squares, a → h."""
    return sorted({chess.square_file(m.to_square) for m in piece_moves(board, kind)})


def rank_options(board: chess.Board, kind: int, file: int) -> list[int]:
    return sorted({chess.square_rank(m.to_square) for m in piece_moves(board, kind)
                   if chess.square_file(m.to_square) == file})


def origin_options(board: chess.Board, kind: int, to_square: int) -> list[int]:
    """Squares the piece can come from (2+ means 'Which knight?'), sorted by file then rank."""
    origins = {m.from_square for m in piece_moves(board, kind) if m.to_square == to_square}
    return sorted(origins, key=lambda s: (chess.square_file(s), chess.square_rank(s)))


def promotion_options(board: chess.Board, kind: int, from_square: int, to_square: int) -> list[int]:
    promos = {m.promotion for m in piece_moves(board, kind)
              if m.from_square == from_square and m.to_square == to_square and m.promotion}
    return [p for p in PROMOTION_ORDER if p in promos]


def kind_of(board: chess.Board, move: chess.Move) -> Kind:
    if board.is_castling(move):
        return CASTLE_SHORT if board.is_kingside_castling(move) else CASTLE_LONG
    piece = board.piece_type_at(move.from_square)
    assert piece is not None
    return piece


def kind_label(kind: Kind) -> str:
    if isinstance(kind, str):
        return kind
    return chess.piece_symbol(kind).upper()


@dataclass
class Step:
    name: str                  # "piece" | "file" | "rank" | "origin" | "promo"
    options: list
    index: int = 0
    auto: bool = False         # filled in automatically (only one choice)

    @property
    def value(self):
        return self.options[self.index]

    def labels(self) -> list[str]:
        if self.name == "piece":
            return [kind_label(k) for k in self.options]
        if self.name == "file":
            return [chess.FILE_NAMES[f] for f in self.options]
        if self.name == "rank":
            return [chess.RANK_NAMES[r] for r in self.options]
        if self.name == "origin":
            return [chess.square_name(s) for s in self.options]
        return [chess.piece_symbol(p).upper() for p in self.options]


@dataclass
class EntryState:
    board: chess.Board
    predicted: chess.Move | None = None
    stack: list[Step] = field(default_factory=list)
    picks: dict[str, object] = field(default_factory=dict)   # step name → chosen value
    result: chess.Move | None = None

    def __post_init__(self) -> None:
        self.board = self.board.copy(stack=False)
        if self.predicted is not None and self.predicted not in self.board.legal_moves:
            self.predicted = None
        self._push("piece", piece_options(self.board), allow_auto=False)

    # --- what's on screen ------------------------------------------------------------
    @property
    def step(self) -> Step:
        return self.stack[-1]

    def chosen(self, name: str):
        return self.picks.get(name)

    @property
    def kind(self) -> Kind | None:
        return self.chosen("piece")

    def prompt(self) -> str:
        """'Pawn → ?', 'Pawn → e?', 'Which N → d7?', 'Promote e8 to'."""
        kind = self.kind
        name = self.step.name
        if name == "piece":
            return "Piece?"
        piece = PIECE_NAMES[kind]
        if name == "file":
            return f"{piece} → ?"
        if name == "rank":
            return f"{piece} → {chess.FILE_NAMES[self.chosen('file')]}?"
        to_sq = self._to_square()
        if name == "origin":
            return f"Which {kind_label(kind)} → {chess.square_name(to_sq)}?"
        return f"Promote {chess.square_name(to_sq)} to"

    # --- cursor ----------------------------------------------------------------------
    def move_cursor(self, delta: int) -> None:
        step = self.step
        step.index = (step.index + delta) % len(step.options)

    def back(self) -> bool:
        """Go back one choice. False when already at the first step."""
        if len(self.stack) == 1:
            return False
        self.result = None
        self.picks.pop(self.stack.pop().name, None)
        while len(self.stack) > 1 and self.stack[-1].auto:
            self.picks.pop(self.stack.pop().name, None)
        self.picks.pop(self.step.name, None)   # the step we're back on is open again
        return True

    def ok(self) -> chess.Move | None:
        """Take the highlighted choice; returns the move once it is complete."""
        if self.result is not None:
            return self.result
        self._advance()
        return self.result

    def accept_prediction(self) -> chess.Move | None:
        if self.predicted is None:
            return None
        self.result = self.predicted
        return self.result

    # --- internals -------------------------------------------------------------------
    def _to_square(self) -> int:
        return chess.square(self.chosen("file"), self.chosen("rank"))

    def _preselect(self, name: str, options: list):
        """The option the predicted move would pick at this step, if it is still on track."""
        p = self.predicted
        if p is None:
            return None
        pk = kind_of(self.board, p)
        if name == "piece":
            return pk
        if pk != self.kind:
            return None
        if name == "file":
            return chess.square_file(p.to_square)
        if name == "rank":
            return chess.square_rank(p.to_square) if chess.square_file(p.to_square) == self.chosen("file") else None
        if p.to_square != self._to_square():
            return None
        if name == "origin":
            return p.from_square
        return p.promotion if p.from_square == self._from_square() else None

    def _push(self, name: str, options: list, allow_auto: bool = True) -> None:
        if not options:
            raise ValueError(f"no options for step {name}")
        pre = self._preselect(name, options)
        index = options.index(pre) if pre in options else 0
        if name == "promo" and pre not in options and chess.QUEEN in options:
            index = options.index(chess.QUEEN)
        self.stack.append(Step(name, options, index, auto=allow_auto and len(options) == 1))
        if self.stack[-1].auto:
            self._advance()

    def _from_square(self) -> int:
        origin = self.chosen("origin")
        if origin is not None:
            return origin
        return origin_options(self.board, self.kind, self._to_square())[0]

    def _advance(self) -> None:
        step = self.step
        value = step.value
        self.picks[step.name] = value
        if step.name == "piece":
            if isinstance(value, str):
                self.result = castling_move(self.board, value)
                return
            self._push("file", file_options(self.board, value))
        elif step.name == "file":
            self._push("rank", rank_options(self.board, self.kind, value))
        elif step.name == "rank":
            self._push("origin", origin_options(self.board, self.kind, self._to_square()))
        elif step.name == "origin":
            promos = promotion_options(self.board, self.kind, value, self._to_square())
            if promos:
                self._push("promo", promos, allow_auto=False)
            else:
                self.result = chess.Move(value, self._to_square())
        elif step.name == "promo":
            self.result = chess.Move(self._from_square(), self._to_square(), promotion=value)
