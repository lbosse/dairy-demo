from dataclasses import dataclass, field
from typing import Optional
from collections import deque


@dataclass
class CowState:
    cow_id: int
    posture: str = "STANDING"
    down_since: Optional[float] = None
    alerted: bool = False
    posture_history: deque = field(default_factory=lambda: deque(maxlen=8))


class CowTracker:
    """Tracks per-cow posture state and down-duration across video frames.

    Uses a short frame buffer to smooth out single-frame misclassifications
    before committing a posture change.
    """

    DOWN_THRESHOLD = 5  # frames classified as DOWN before accepting the state

    def __init__(self):
        self._states: dict[int, CowState] = {}

    def update(self, cow_id: int, raw_posture: str, current_time: float) -> float:
        """Update state from one frame. Returns seconds the cow has been down (0 if standing)."""
        if cow_id not in self._states:
            self._states[cow_id] = CowState(cow_id=cow_id)

        state = self._states[cow_id]
        state.posture_history.append(raw_posture)

        # Snap to STANDING immediately — a cow getting up is a definitive signal.
        # Clear history so DOWN must re-accumulate from scratch after any standing frame.
        # Only commit to DOWN after enough frames agree, to filter single-frame noise.
        if raw_posture == "STANDING":
            state.posture_history.clear()
            smoothed = "STANDING"
        else:
            down_votes = sum(1 for p in state.posture_history if p == "DOWN")
            smoothed = "DOWN" if down_votes >= self.DOWN_THRESHOLD else "STANDING"

        if smoothed == "DOWN":
            if state.posture != "DOWN":
                state.down_since = current_time
            state.posture = "DOWN"
            return current_time - state.down_since if state.down_since else 0.0
        else:
            state.posture = "STANDING"
            state.down_since = None
            state.alerted = False
            return 0.0

    def mark_alerted(self, cow_id: int):
        if cow_id in self._states:
            self._states[cow_id].alerted = True

    def was_alerted(self, cow_id: int) -> bool:
        return self._states.get(cow_id, CowState(cow_id=cow_id)).alerted
