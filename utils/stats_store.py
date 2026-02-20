"""
Persistent bot stats store.
"""

import json
from pathlib import Path
from typing import Dict


class BotStatsStore:
    """
    Stores counters in a JSON file so values survive bot restarts.
    """

    def __init__(self, file_path: Path):
        self.file_path = file_path
        self._stats: Dict[str, int] = {
            "bot_answered": 0,
            "admin_answered": 0,
            "unanswered": 0,
        }
        self._load()

    def _load(self) -> None:
        if not self.file_path.exists():
            self._save()
            return

        try:
            loaded = json.loads(self.file_path.read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                self._stats["bot_answered"] = int(loaded.get("bot_answered", 0))
                self._stats["admin_answered"] = int(loaded.get("admin_answered", 0))
                self._stats["unanswered"] = int(loaded.get("unanswered", 0))
        except Exception:
            # Keep defaults if file is corrupted.
            pass

    def _save(self) -> None:
        self.file_path.parent.mkdir(parents=True, exist_ok=True)
        self.file_path.write_text(
            json.dumps(self._stats, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def snapshot(self) -> Dict[str, int]:
        return dict(self._stats)

    def increment_bot_answered(self) -> None:
        self._stats["bot_answered"] += 1
        self._save()

    def increment_admin_answered(self) -> None:
        self._stats["admin_answered"] += 1
        self._save()

    def increment_unanswered(self) -> None:
        self._stats["unanswered"] += 1
        self._save()

    def decrement_unanswered(self) -> None:
        self._stats["unanswered"] = max(0, self._stats["unanswered"] - 1)
        self._save()

