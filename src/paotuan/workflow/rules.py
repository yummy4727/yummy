"""M1 规则触发引擎：解析 story_script.md 的结构化标记并用最小表达式求值器求值。

支持：
- 脚本调用标记  [脚本: fn(kwargs)]
- 条件块        **如果** <条件> **则** ... **否则** ... **结束**

条件仅支持：状态字段比较（数字/字符串/布尔）、and/or/not、括号。
任何求值失败都视为「条件不满足」（安全降级，不影响文本生成）。
不使用 eval——全部经由显式解析器求值。
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

_CALL_RE = re.compile(r"\[脚本:\s*([A-Za-z_][A-Za-z0-9_]*)\s*(\([^]]*\))?\]")
_IF_RE = re.compile(r"^\s*\*\*如果\*\*\s*(.+?)\s*\*\*则\*\*")
_ELSE_RE = re.compile(r"^\s*\*\*否则\*\*")
_END_RE = re.compile(r"^\s*\*\*结束\*\*")


# ---------------------------------------------------------------- 表达式求值器


class _TokenType:
    OP = "op"
    NUM = "num"
    STR = "str"
    IDENT = "ident"
    KW = "kw"
    LPAREN = "lparen"
    RPAREN = "rparen"


@dataclass
class _Token:
    kind: str
    value: object
    pos: int


_TOKEN_RE = re.compile(
    r"""
    \s+ |                                  # 空白
    (?P<num>-?\d+(?:\.\d+)?) |             # 数字
    (?P<str>"[^"]*"|'[^']*') |             # 字符串
    (?P<ident>[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)*) |  # 点分路径
    (?P<op><=|>=|==|!=|<|>) |              # 比较符
    (?P<paren>[()]) |
    (?P<other>.)
    """,
    re.VERBOSE,
)


def _tokenize(expr: str) -> list[_Token]:
    tokens: list[_Token] = []
    for m in _TOKEN_RE.finditer(expr):
        if m.group("other"):
            raise ValueError(f"无法识别的字符: {m.group('other')!r}")
        if m.group("num") is not None:
            raw = m.group("num")
            tokens.append(_Token(_TokenType.NUM, float(raw) if "." in raw else int(raw), m.start()))
        elif m.group("str") is not None:
            raw = m.group("str")[1:-1]
            tokens.append(_Token(_TokenType.STR, raw, m.start()))
        elif m.group("ident") is not None:
            raw = m.group("ident")
            if raw in ("and", "or", "not", "in", "true", "false", "null"):
                tokens.append(_Token(_TokenType.KW, raw, m.start()))
            else:
                tokens.append(_Token(_TokenType.IDENT, raw, m.start()))
        elif m.group("op") is not None:
            tokens.append(_Token(_TokenType.OP, m.group("op"), m.start()))
        elif m.group("paren") == "(":
            tokens.append(_Token(_TokenType.LPAREN, "(", m.start()))
        elif m.group("paren") == ")":
            tokens.append(_Token(_TokenType.RPAREN, ")", m.start()))
    return tokens


# AST
class _Node:
    pass


@dataclass
class _Or(_Node):
    left: _Node
    right: _Node


@dataclass
class _And(_Node):
    left: _Node
    right: _Node


@dataclass
class _Not(_Node):
    node: _Node


@dataclass
class _Compare(_Node):
    left: object
    op: str
    right: object


@dataclass
class _PathRef:
    """标识符（状态点分路径），区别于字符串字面量。"""

    path: str


class _Parser:
    def __init__(self, tokens: list[_Token]):
        self.tokens = tokens
        self.pos = 0

    def peek(self) -> _Token | None:
        return self.tokens[self.pos] if self.pos < len(self.tokens) else None

    def advance(self) -> _Token:
        tok = self.tokens[self.pos]
        self.pos += 1
        return tok

    def match_kw(self, kw: str) -> bool:
        tok = self.peek()
        if tok and tok.kind == _TokenType.KW and tok.value == kw:
            self.pos += 1
            return True
        return False

    def parse(self) -> _Node:
        return self._parse_or()

    def _parse_or(self) -> _Node:
        left = self._parse_and()
        while self.match_kw("or"):
            left = _Or(left, self._parse_and())
        return left

    def _parse_and(self) -> _Node:
        left = self._parse_not()
        while self.match_kw("and"):
            left = _And(left, self._parse_not())
        return left

    def _parse_not(self) -> _Node:
        if self.match_kw("not"):
            return _Not(self._parse_not())
        return self._parse_comparison()

    def _parse_comparison(self) -> _Node:
        left = self._parse_operand()
        tok = self.peek()
        op = None
        if tok and tok.kind == _TokenType.OP:
            op = self.advance().value
        elif tok and tok.kind == _TokenType.KW and tok.value == "in":
            op = "in"
            self.advance()
        elif tok and tok.kind == _TokenType.KW and tok.value == "not":
            self.advance()
            if not self.match_kw("in"):
                raise ValueError("'not' 后必须是 'in'")
            op = "not in"
        if op is None:
            return _Compare(left, "==", True)
        right = self._parse_operand()
        return _Compare(left, op, right)

    def _parse_operand(self) -> object:
        tok = self.peek()
        if tok is None:
            raise ValueError("表达式意外结束")
        if tok.kind == _TokenType.LPAREN:
            self.advance()
            node = self._parse_or()
            if not self.match_paren(")"):
                raise ValueError("缺少右括号")
            return node
        self.advance()
        if tok.kind == _TokenType.IDENT:
            return _PathRef(tok.value)
        if tok.kind in (_TokenType.NUM, _TokenType.STR):
            return tok.value
        if tok.kind == _TokenType.KW:
            if tok.value == "true":
                return True
            if tok.value == "false":
                return False
            if tok.value == "null":
                return None
        raise ValueError(f"意外的操作数: {tok.value!r}")

    def match_paren(self, kind: str) -> bool:
        tok = self.peek()
        if tok and tok.kind == _TokenType.RPAREN and kind == ")":
            self.pos += 1
            return True
        return False


def _get_path(state: dict, path: str) -> object:
    cur: object = state
    for part in path.split("."):
        if isinstance(cur, dict) and part in cur:
            cur = cur[part]
        elif isinstance(cur, (list, tuple)) and part.isdigit() and int(part) < len(cur):
            cur = cur[int(part)]
        else:
            raise KeyError(path)
    return cur


def _compare(a: object, op: str, b: object) -> bool:
    if op == "in":
        return a in b if isinstance(b, (list, tuple, dict, str)) else False
    if op == "not in":
        return not _compare(a, "in", b)
    if a is None or b is None:
        if op == "==":
            return a is None and b is None
        if op == "!=":
            return a is not None or b is not None
        return False
    if isinstance(a, bool) or isinstance(b, bool):
        if not (isinstance(a, bool) and isinstance(b, bool)):
            return False
    elif type(a) is not type(b) and not (
        isinstance(a, (int, float)) and isinstance(b, (int, float))
    ):
        return False
    if op == "==":
        return a == b
    if op == "!=":
        return a != b
    if isinstance(a, (int, float)) and isinstance(b, (int, float)):
        if op == "<":
            return a < b
        if op == "<=":
            return a <= b
        if op == ">":
            return a > b
        if op == ">=":
            return a >= b
    return False


def eval_ast(node: _Node, state: dict) -> bool:
    """求值 AST。任何异常（缺字段/类型不符）返回 False。"""
    try:
        return _eval(node, state)
    except Exception:  # noqa: BLE001
        return False


def _eval(node: _Node, state: dict) -> bool:
    if isinstance(node, _Or):
        return _eval(node.left, state) or _eval(node.right, state)
    if isinstance(node, _And):
        return _eval(node.left, state) and _eval(node.right, state)
    if isinstance(node, _Not):
        return not _eval(node.node, state)
    if isinstance(node, _Compare):
        left = _resolve_operand(node.left, state)
        right = _resolve_operand(node.right, state)
        return _compare(left, node.op, right)
    raise ValueError(f"未知节点: {node!r}")


def _resolve_operand(value: object, state: dict) -> object:
    """把操作数解析为实际值：_PathRef → 状态查找，_Node → 子表达式。"""
    if isinstance(value, _PathRef):
        return _get_path(state, value.path)
    if isinstance(value, _Node):
        return _eval(value, state)
    return value


def eval_condition(expr: str, state: dict) -> bool:
    """解析并求值条件表达式；任何错误均返回 False。"""
    try:
        node = _Parser(_tokenize(expr)).parse()
    except Exception:  # noqa: BLE001
        return False
    return eval_ast(node, state)


def negate_condition(expr: str | None) -> str | None:
    if expr is None:
        return None
    return f"not ({expr})"


# ---------------------------------------------------------------- story_script 解析


@dataclass
class ScriptCall:
    function: str
    kwargs: dict = field(default_factory=dict)

    @property
    def fn(self) -> str:
        return self.function


@dataclass
class Rule:
    """一条待求值规则：condition 为 None 表示无条件触发。"""

    condition: str | None
    call: ScriptCall
    line: int


def _parse_call(text: str, line: int) -> Rule | None:
    """解析 'fn(a=1, b="x")'，返回 Rule（无条件的脚本调用）。"""
    text = text.strip()
    m = re.match(r"^([A-Za-z_][A-Za-z0-9_]*)\s*(?:\((.*)\))?$", text)
    if not m:
        return None
    fn = m.group(1)
    kwargs: dict = {}
    if m.group(2) and m.group(2).strip():
        for part in _split_args(m.group(2)):
            part = part.strip()
            if "=" not in part:
                return None
            key, _, val = part.partition("=")
            key = key.strip()
            parsed = _parse_literal(val.strip())
            if parsed is _UNPARSED:
                return None
            kwargs[key] = parsed
    return Rule(condition=None, call=ScriptCall(function=fn, kwargs=kwargs), line=line)


_UNPARSED = object()


def _parse_literal(text: str) -> object:
    if text in ("true", "True"):
        return True
    if text in ("false", "False"):
        return False
    if text in ("null", "None"):
        return None
    if (text.startswith('"') and text.endswith('"')) or (
        text.startswith("'") and text.endswith("'")
    ):
        return text[1:-1]
    if re.fullmatch(r"-?\d+", text):
        return int(text)
    if re.fullmatch(r"-?\d+\.\d+", text):
        return float(text)
    return _UNPARSED


def _split_args(text: str) -> list[str]:
    """按逗号切分参数，忽略引号内的逗号。"""
    parts: list[str] = []
    buf: list[str] = []
    in_quote: str | None = None
    for ch in text:
        if in_quote:
            buf.append(ch)
            if ch == in_quote:
                in_quote = None
        elif ch in ('"', "'"):
            in_quote = ch
            buf.append(ch)
        elif ch == ",":
            parts.append("".join(buf))
            buf = []
        else:
            buf.append(ch)
    if in_quote:
        raise ValueError("引号未闭合")
    parts.append("".join(buf))
    return parts


def parse_rules(story_script_md: str) -> list[Rule]:
    """从 story_script.md 提取全部规则（含条件作用域）。"""
    rules: list[Rule] = []
    cond_stack: list[str | None] = []

    for lineno, raw in enumerate(story_script_md.splitlines(), 1):
        line = raw.strip()
        if not line:
            continue

        if m := _IF_RE.match(line):
            cond_stack.append(m.group(1).strip())
            continue
        if _ELSE_RE.match(line):
            if cond_stack:
                top = cond_stack.pop()
                cond_stack.append(negate_condition(top))
            continue
        if _END_RE.match(line):
            if cond_stack:
                cond_stack.pop()
            continue

        for m in _CALL_RE.finditer(raw):
            body = m.group(2)
            call_text = m.group(1) + (body if body else "")
            rule = _parse_call(call_text, lineno)
            if rule is None:
                continue
            active = [c for c in cond_stack if c is not None]
            if active:
                rule.condition = "(" + ") and (".join(active) + ")"
            rules.append(rule)

    return rules


def triggered_calls(rules: list[Rule], state: dict) -> list[ScriptCall]:
    """返回当前状态下应执行的脚本调用（保持出现顺序，去重相邻同函数）。"""
    calls: list[ScriptCall] = []
    last_fn: str | None = None
    for rule in rules:
        if rule.condition is not None and not eval_condition(rule.condition, state):
            continue
        if rule.call.function == last_fn:
            continue
        last_fn = rule.call.function
        calls.append(rule.call)
    return calls
