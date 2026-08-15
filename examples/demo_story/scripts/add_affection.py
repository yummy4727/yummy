def run(state: dict, **kwargs):
    """增加对指定角色的好感度。"""
    target = kwargs.get("target")
    amount = kwargs.get("amount", 1)
    affection = state.setdefault("affection", {})
    if target:
        affection[target] = affection.get(target, 0) + amount
        state.setdefault("affection", affection)["count"] = affection.get("count", 0) + 1
    return state
