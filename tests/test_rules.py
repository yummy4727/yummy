"""rules：表达式求值与规则触发。"""

from __future__ import annotations

from paotuan.workflow.rules import (
    eval_condition,
    negate_condition,
    parse_rules,
    triggered_calls,
)


STATE = {
    "chapter": 1,
    "weather": "stormy",
    "affection": {"butler": 3, "count": 1},
    "inventory": ["邀请函"],
}


def test_basic_comparisons():
    assert eval_condition("chapter == 1", STATE)
    assert not eval_condition("chapter == 2", STATE)
    assert eval_condition("affection.butler >= 3", STATE)
    assert eval_condition("weather == 'stormy'", STATE)
    assert eval_condition("chapter != 2", STATE)


def test_logical_ops():
    assert eval_condition("chapter == 1 and weather == 'stormy'", STATE)
    assert not eval_condition("chapter == 1 and weather == 'sunny'", STATE)
    assert eval_condition("chapter == 2 or weather == 'stormy'", STATE)
    assert eval_condition("not (chapter == 2)", STATE)
    assert eval_condition("not chapter == 2", STATE)


def test_in_operator():
    assert eval_condition("'邀请函' in inventory", STATE)
    assert eval_condition("'礼物' not in inventory", STATE)


def test_missing_field_is_false():
    assert not eval_condition("nonexistent.field > 1", STATE)
    assert not eval_condition("affection.lady > 1", STATE)


def test_invalid_expression_is_false():
    assert not eval_condition("垃圾!!!===invalid", STATE)
    assert not eval_condition("", STATE)
    assert not eval_condition("chapter +", STATE)


def test_negate_condition():
    assert negate_condition("chapter == 1") == "not (chapter == 1)"
    assert negate_condition(None) is None
    # 条件本身带 not 时，else 分支做外层包裹即可（不求化简）
    assert negate_condition("not (chapter == 1)") == "not (not (chapter == 1))"


def test_parse_rules_finds_unconditional_call():
    script = "[脚本: add_affection(target='butler', amount=1)]"
    rules = parse_rules(script)
    calls = triggered_calls(rules, STATE)
    assert [c.fn for c in calls] == ["add_affection"]


def test_conditional_if_else():
    script = (
        "**如果** affection.butler >= 3 **则**\n"
        "  [脚本: unlock_clue(clue='管家的微笑')]\n"
        "**否则**\n"
        "  [脚本: unlock_clue(clue='礼貌的点头')]\n"
        "**结束**\n"
    )
    rules = parse_rules(script)
    calls = triggered_calls(rules, STATE)
    assert [c.kwargs["clue"] for c in calls] == ["管家的微笑"]


def test_conditional_else_when_false():
    state = dict(STATE, affection={"butler": 1, "count": 1})
    script = (
        "**如果** affection.butler >= 3 **则**\n"
        "  [脚本: unlock_clue(clue='A')]\n"
        "**否则**\n"
        "  [脚本: unlock_clue(clue='B')]\n"
        "**结束**\n"
    )
    rules = parse_rules(script)
    calls = triggered_calls(rules, state)
    assert [c.kwargs["clue"] for c in calls] == ["B"]


def test_nested_conditions():
    script = (
        "**如果** chapter == 1 **则**\n"
        "  **如果** weather == 'stormy' **则**\n"
        "    [脚本: unlock_clue(clue='脚印')]\n"
        "  **结束**\n"
        "**结束**\n"
    )
    rules = parse_rules(script)
    assert [c.kwargs["clue"] for c in triggered_calls(rules, STATE)] == ["脚印"]


def test_call_without_parens():
    script = "[脚本: heal]"
    rules = parse_rules(script)
    calls = triggered_calls(rules, STATE)
    assert len(calls) == 1
    assert calls[0].fn == "heal"
    assert calls[0].kwargs == {}