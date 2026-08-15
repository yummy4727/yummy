"""游戏状态管理。"""

from .manager import StateManager
from .persistence import load_state, save_state
from .watcher import StateChange, StateWatcher

__all__ = ["StateManager", "StateWatcher", "StateChange", "load_state", "save_state"]