"""Render Wrath 3.3.5a spell description templates ($s1, $d, ${$58647m1/-10}, ...).

Pure logic: numbers come from a lookup object (see ClientDefinitions.spell_numbers). Anything
that cannot be resolved offline (conditionals such as $?s123[a][b], player-dependent values
like $SPH) is left in the text and reported through the "unresolved" flag, never guessed.
"""

from __future__ import annotations

import ast
import operator
import re
from dataclasses import dataclass, field
from typing import Callable, Optional, Protocol


@dataclass(frozen=True)
class SpellNumbers:
    spell_id: int
    base_points: tuple[int, int, int] = (0, 0, 0)
    die_sides: tuple[int, int, int] = (0, 0, 0)
    radius_index: tuple[int, int, int] = (0, 0, 0)
    amplitude_ms: tuple[int, int, int] = (0, 0, 0)
    chain_targets: tuple[int, int, int] = (0, 0, 0)
    multiple_value: tuple[float, float, float] = (0.0, 0.0, 0.0)
    duration_index: int = 0
    proc_chance: int = 0
    proc_charges: int = 0
    stack_amount: int = 0

    def min_value(self, i: int) -> int:
        return self.base_points[i] + 1

    def max_value(self, i: int) -> int:
        return self.base_points[i] + max(self.die_sides[i], 1)


class SpellSource(Protocol):
    def spell_numbers(self, spell_id: int) -> Optional[SpellNumbers]: ...
    def duration_ms(self, index: int) -> Optional[int]: ...
    def radius_yards(self, index: int) -> Optional[float]: ...


@dataclass
class Rendered:
    text: str
    unresolved: bool = False
    notes: list[str] = field(default_factory=list)


def _fmt(value: float) -> str:
    if abs(value - round(value)) < 1e-9:
        return str(int(round(value)))
    return f"{value:.2f}".rstrip("0").rstrip(".")


def format_duration(ms: int) -> str:
    if ms < 0:
        return "until cancelled"
    seconds = ms / 1000
    if seconds < 60:
        unit, value = "sec", seconds
    elif seconds < 3600:
        unit, value = "min", seconds / 60
    elif seconds < 86400:
        unit, value = "hour", seconds / 3600
    else:
        unit, value = "day", seconds / 86400
    return f"{_fmt(value)} {unit}"


_OPS = {ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul,
        ast.Div: operator.truediv}


def _safe_eval(expr: str) -> float:
    def walk(node: ast.AST) -> float:
        if isinstance(node, ast.Expression):
            return walk(node.body)
        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
            return node.value
        if isinstance(node, ast.BinOp) and type(node.op) in _OPS:
            return _OPS[type(node.op)](walk(node.left), walk(node.right))
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.USub, ast.UAdd)):
            v = walk(node.operand)
            return -v if isinstance(node.op, ast.USub) else v
        raise ValueError("unsupported expression")
    return walk(ast.parse(expr, mode="eval"))


_VAR = re.compile(r"\$(?:(?P<op>[/*])(?P<opval>\d+);)?(?P<sid>\d+)?(?P<var>[smMotadxhnuqeb])(?P<idx>[1-3])?")
_EXPR = re.compile(r"\$\{(?P<body>[^{}]*)\}(?:\.(?P<dec>\d))?")
_PLURAL = re.compile(r"\$l(?P<one>[^:;]*):(?P<many>[^;]*);")


class _Unresolved(Exception):
    pass


def render_description(template: str, spell_id: int, source: SpellSource) -> Rendered:
    notes: list[str] = []

    def numeric(match: re.Match[str]) -> float:
        sid = int(match.group("sid")) if match.group("sid") else spell_id
        var = match.group("var")
        idx = int(match.group("idx") or 1) - 1
        nums = source.spell_numbers(sid)
        if nums is None:
            raise _Unresolved(f"spell {sid} not found")
        if var == "m":
            value: float = nums.min_value(idx)
        elif var == "M":
            value = nums.max_value(idx)
        elif var == "s":
            value = abs(nums.min_value(idx))
        elif var == "t":
            value = nums.amplitude_ms[idx] / 1000
        elif var == "x":
            value = nums.chain_targets[idx]
        elif var == "e":
            value = nums.multiple_value[idx]
        elif var == "h":
            value = nums.proc_chance
        elif var == "n":
            value = nums.proc_charges
        elif var == "u":
            value = nums.stack_amount
        elif var == "d":
            ms = source.duration_ms(nums.duration_index)
            if ms is None:
                raise _Unresolved("duration")
            value = ms / 1000
        elif var == "a":
            yards = source.radius_yards(nums.radius_index[idx])
            if yards is None:
                raise _Unresolved("radius")
            value = yards
        elif var == "o":
            ms = source.duration_ms(nums.duration_index)
            amp = nums.amplitude_ms[idx]
            if not ms or not amp:
                raise _Unresolved("periodic total")
            value = abs(nums.min_value(idx)) * (ms / amp)
        else:
            raise _Unresolved(f"variable {var}")
        op, opval = match.group("op"), match.group("opval")
        if op == "/":
            value /= int(opval)
        elif op == "*":
            value *= int(opval)
        return value

    def expr_sub(match: re.Match[str]) -> str:
        try:
            body = _VAR.sub(lambda m: repr(numeric(m)), match.group("body"))
            value = _safe_eval(body)
        except (_Unresolved, ValueError, SyntaxError, ZeroDivisionError) as exc:
            notes.append(f"expression {match.group(0)}: {exc}")
            return match.group(0)
        if match.group("dec"):
            return f"{value:.{int(match.group('dec'))}f}"
        return _fmt(value)

    def var_sub(match: re.Match[str]) -> str:
        try:
            value = numeric(match)
        except _Unresolved as exc:
            notes.append(f"{match.group(0)}: {exc}")
            return match.group(0)
        var = match.group("var")
        if var == "d":
            ms = source.duration_ms(source.spell_numbers(int(match.group("sid") or spell_id)).duration_index)  # type: ignore[union-attr]
            return format_duration(ms or 0)
        if var == "s":
            nums = source.spell_numbers(int(match.group("sid") or spell_id))
            i = int(match.group("idx") or 1) - 1
            if nums and nums.die_sides[i] > 1 and not match.group("op"):
                return f"{abs(nums.min_value(i))} to {abs(nums.max_value(i))}"
        return _fmt(value)

    text = _EXPR.sub(expr_sub, template)
    text = _VAR.sub(var_sub, text)
    text = text.replace("$$", "$")
    # Plural helper: "$lday:days;" depends on the number just before it.
    def plural(match: re.Match[str]) -> str:
        before = text[: match.start()].rstrip()
        m = re.search(r"([\d.]+)\s*$", before)
        one = m is not None and m.group(1) == "1"
        return match.group("one") if one else match.group("many")
    text = _PLURAL.sub(plural, text)
    unresolved = "$" in text
    if unresolved:
        notes.append("template still contains unresolved markers")
    return Rendered(text, unresolved, notes)
