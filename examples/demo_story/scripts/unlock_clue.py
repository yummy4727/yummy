def run(state: dict, **kwargs):
    """解锁一条线索。"""
    clue_name = kwargs.get("clue")
    clues = state.setdefault("clues_unlocked", [])
    if clue_name and clue_name not in clues:
        clues.append(clue_name)
        state["_system_message"] = f"【系统】获得新线索：{clue_name}"
    return state
