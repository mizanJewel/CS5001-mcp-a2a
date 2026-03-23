"""
Agent State - Persists state between CLI commands
"""

import json
import os
from pathlib import Path


class AgentState:
    def __init__(self, path: str = ".agent_state.json"):
        self.path = Path(path)

    def save(self, data: dict):
        """Save state to disk."""
        try:
            self.path.write_text(json.dumps(data, indent=2))
        except Exception as e:
            print(f"[Warning] Could not save state: {e}")

    def load(self) -> dict:
        """Load state from disk."""
        try:
            if self.path.exists():
                return json.loads(self.path.read_text())
        except Exception:
            pass
        return {}

    def clear(self):
        """Clear state."""
        if self.path.exists():
            self.path.unlink()
