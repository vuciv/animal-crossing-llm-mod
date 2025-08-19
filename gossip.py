import json
import os
import random
import time
from typing import Dict, List, Optional, Tuple


DEFAULT_STATE_PATH = os.environ.get("GOSSIP_STATE_PATH", os.path.join(os.getcwd(), "gossip_state.json"))
RUMOR_TOPIC = os.environ.get(
    "GOSSIP_TOPIC",
    "Tom Nook's loan terms are exploitative and the town's economy is unfair.",
)


def _now_ts() -> float:
    return time.time()


def _clamp(value: int, lo: int = 0, hi: int = 100) -> int:
    return max(lo, min(hi, value))


def load_state(villager_names: Optional[List[str]] = None, path: str = DEFAULT_STATE_PATH) -> Dict:
    state: Dict = {
        "rumor_topic": RUMOR_TOPIC,
        "villager_rumor_level": {},
        "global_rumor_level": 0,
        "last_updated": _now_ts(),
    }
    try:
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                disk = json.load(f)
                if isinstance(disk, dict):
                    state.update(disk)
    except Exception:
        pass

    if villager_names:
        for name in villager_names:
            state["villager_rumor_level"].setdefault(name, 0)
    return state


def save_state(state: Dict, path: str = DEFAULT_STATE_PATH) -> None:
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(state, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


def seed_if_needed(villager_names: List[str], force: bool = False) -> None:
    """Seed initial rumor distribution once or when force=True.

    Controlled by env GOSSIP_SEED (default "1").
    """
    allow = os.environ.get("GOSSIP_SEED", "1") == "1"
    if not (allow or force):
        return
    state = load_state(villager_names)
    if state.get("global_rumor_level", 0) > 0 and not force:
        return
    state["global_rumor_level"] = 10
    for name in random.sample(villager_names, min(3, len(villager_names))):
        state["villager_rumor_level"][name] = 20
    state["last_updated"] = _now_ts()
    save_state(state)


def observe_interaction(speaker: Optional[str], amount: int = 7, villager_names: Optional[List[str]] = None) -> None:
    """When a villager speaks, increase their exposure to the rumor."""
    if not speaker:
        return
    state = load_state(villager_names)
    levels = state.setdefault("villager_rumor_level", {})
    levels[speaker] = _clamp(levels.get(speaker, 0) + amount)
    # Nudge global level slightly
    state["global_rumor_level"] = _clamp(state.get("global_rumor_level", 0) + 1)
    state["last_updated"] = _now_ts()
    save_state(state)


def spread(villager_names: List[str], tick: int = 1) -> None:
    """Slowly spread rumor to random villagers; accelerate with higher global level."""
    if not villager_names:
        return
    state = load_state(villager_names)
    levels: Dict[str, int] = state.setdefault("villager_rumor_level", {})
    global_level = state.get("global_rumor_level", 0)

    # Number of contacts per tick scales with global level
    contacts = max(1, global_level // 20)
    for _ in range(contacts):
        name = random.choice(villager_names)
        bump = 1 + (global_level // 33)
        levels[name] = _clamp(levels.get(name, 0) + bump)

    # Gentle natural rise of global level
    state["global_rumor_level"] = _clamp(global_level + tick)
    state["last_updated"] = _now_ts()
    save_state(state)


def _stage_for(level: int) -> int:
    # Map 0..100 to stages 0..5
    bins = [0, 10, 25, 45, 70, 90, 101]
    for i in range(len(bins) - 1):
        if bins[i] <= level < bins[i + 1]:
            return i
    return 5


def get_context_for(speaker: Optional[str], villager_names: Optional[List[str]] = None) -> Dict[str, object]:
    """Return a compact gossip context for prompts.

    Keys:
      - topic: str
      - global_stage: int (0..5)
      - speaker_stage: int (0..5)
      - hot_villagers: List[str] (names with high rumor level)
    """
    state = load_state(villager_names)
    levels: Dict[str, int] = state.get("villager_rumor_level", {})
    gl = state.get("global_rumor_level", 0)
    gv_names = villager_names or list(levels.keys())

    top: List[Tuple[str, int]] = []
    for name in gv_names:
        top.append((name, levels.get(name, 0)))
    top.sort(key=lambda x: x[1], reverse=True)
    hot = [n for (n, lvl) in top[:3] if lvl >= 25]

    speaker_level = levels.get(speaker or "", 0)
    return {
        "topic": state.get("rumor_topic", RUMOR_TOPIC),
        "global_stage": _stage_for(gl),
        "speaker_stage": _stage_for(speaker_level),
        "hot_villagers": hot,
    }


