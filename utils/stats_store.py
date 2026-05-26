"""
Persistent bot stats store.
"""

import json
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict


class BotStatsStore:
    """
    Stores counters in a JSON file so values survive bot restarts.
    """

    def __init__(self, file_path: Path):
        self.file_path = file_path
        self._stats: Dict[str, Any] = {
            "bot_answered": 0,
            "admin_answered": 0,
            "unanswered": 0,
            "feedback_helpful": 0,
            "feedback_unhelpful": 0,
            "resolved_tickets": 0,
            "total_response_seconds": 0.0,
            "unanswered_questions": {},
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
                self._stats["feedback_helpful"] = int(loaded.get("feedback_helpful", 0))
                self._stats["feedback_unhelpful"] = int(loaded.get("feedback_unhelpful", 0))
                self._stats["resolved_tickets"] = int(loaded.get("resolved_tickets", 0))
                self._stats["total_response_seconds"] = float(loaded.get("total_response_seconds", 0.0))
                unanswered_questions = loaded.get("unanswered_questions", {})
                if isinstance(unanswered_questions, dict):
                    clean_map: Dict[str, int] = {}
                    for key, value in unanswered_questions.items():
                        q = str(key or "").strip()
                        if not q:
                            continue
                        try:
                            clean_map[q] = int(value)
                        except (TypeError, ValueError):
                            continue
                    self._stats["unanswered_questions"] = clean_map
        except Exception:
            # Keep defaults if file is corrupted.
            pass

    def _save(self) -> None:
        self.file_path.parent.mkdir(parents=True, exist_ok=True)
        self.file_path.write_text(
            json.dumps(self._stats, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def snapshot(self) -> Dict[str, Any]:
        return dict(self._stats)

    def increment_bot_answered(self) -> None:
        self._stats["bot_answered"] += 1
        self._save()

    def increment_admin_answered(self) -> None:
        self._stats["admin_answered"] += 1
        self._save()

    def increment_unanswered(self, question: str | None = None) -> None:
        self._stats["unanswered"] += 1
        q = (question or "").strip()
        if q:
            fq = defaultdict(int, self._stats.get("unanswered_questions", {}))
            fq[q] += 1
            self._stats["unanswered_questions"] = dict(fq)
        self._save()

    def decrement_unanswered(self) -> None:
        self._stats["unanswered"] = max(0, self._stats["unanswered"] - 1)
        self._save()

    def record_ticket_resolution(self, elapsed_seconds: float) -> None:
        self._stats["resolved_tickets"] += 1
        self._stats["total_response_seconds"] += max(0.0, float(elapsed_seconds))
        self._save()

    def increment_feedback_helpful(self) -> None:
        self._stats["feedback_helpful"] += 1
        self._save()

    def increment_feedback_unhelpful(self) -> None:
        self._stats["feedback_unhelpful"] += 1
        self._save()
