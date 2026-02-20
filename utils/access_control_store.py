"""
Persistent access control store for admin/owner roles.
"""

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Set


def _to_int_set(values: Iterable[Any]) -> Set[int]:
    parsed: Set[int] = set()
    for value in values:
        try:
            parsed.add(int(value))
        except (TypeError, ValueError):
            continue
    return parsed


class AccessControlStore:
    """
    Stores admin/owner IDs in JSON so role changes survive restarts.
    """

    def __init__(self, file_path: Path, seed_admin_ids: Iterable[int], seed_owner_ids: Iterable[int]):
        self.file_path = file_path
        self._admins: Dict[int, Dict[str, Any]] = {}
        self._owners: Dict[int, Dict[str, Any]] = {}
        self._seed_admin_ids = _to_int_set(seed_admin_ids)
        self._seed_owner_ids = _to_int_set(seed_owner_ids)
        self._load()

    def _now(self) -> str:
        return datetime.now(timezone.utc).isoformat()

    def _entry(
        self,
        user_id: int,
        username: Optional[str] = None,
        first_name: Optional[str] = None,
        added_by: Optional[int] = None,
    ) -> Dict[str, Any]:
        data: Dict[str, Any] = {
            "id": int(user_id),
            "username": username or "",
            "first_name": first_name or "",
            "added_at": self._now(),
        }
        if added_by is not None:
            data["added_by"] = int(added_by)
        return data

    def _save(self) -> None:
        self.file_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "admins": list(self._admins.values()),
            "owners": list(self._owners.values()),
        }
        self.file_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    def _load(self) -> None:
        if self.file_path.exists():
            try:
                loaded = json.loads(self.file_path.read_text(encoding="utf-8"))
                for row in loaded.get("admins", []):
                    user_id = int(row.get("id"))
                    self._admins[user_id] = {
                        "id": user_id,
                        "username": str(row.get("username", "") or ""),
                        "first_name": str(row.get("first_name", "") or ""),
                        "added_at": str(row.get("added_at", "") or ""),
                        "added_by": row.get("added_by"),
                    }
                for row in loaded.get("owners", []):
                    user_id = int(row.get("id"))
                    self._owners[user_id] = {
                        "id": user_id,
                        "username": str(row.get("username", "") or ""),
                        "first_name": str(row.get("first_name", "") or ""),
                        "added_at": str(row.get("added_at", "") or ""),
                        "added_by": row.get("added_by"),
                    }
            except Exception:
                # Keep defaults and re-seed below.
                self._admins = {}
                self._owners = {}

        if not self._seed_owner_ids and self._seed_admin_ids:
            # Safety fallback: if no owner is configured, start with first admin(s).
            self._seed_owner_ids = set(self._seed_admin_ids)

        for owner_id in self._seed_owner_ids:
            self._owners.setdefault(owner_id, self._entry(owner_id))
        for admin_id in self._seed_admin_ids:
            self._admins.setdefault(admin_id, self._entry(admin_id))

        self._save()

    def is_owner(self, user_id: int) -> bool:
        return int(user_id) in self._owners

    def is_admin(self, user_id: int) -> bool:
        uid = int(user_id)
        return uid in self._admins or uid in self._owners

    def admin_ids(self, include_owners: bool = True) -> List[int]:
        ids = set(self._admins.keys())
        if include_owners:
            ids |= set(self._owners.keys())
        return sorted(ids)

    def owner_ids(self) -> List[int]:
        return sorted(self._owners.keys())

    def add_admin(
        self,
        user_id: int,
        username: Optional[str] = None,
        first_name: Optional[str] = None,
        added_by: Optional[int] = None,
    ) -> bool:
        uid = int(user_id)
        if uid in self._admins:
            self.touch_user(uid, username=username, first_name=first_name)
            return False
        self._admins[uid] = self._entry(uid, username=username, first_name=first_name, added_by=added_by)
        self._save()
        return True

    def remove_admin(self, user_id: int) -> bool:
        uid = int(user_id)
        if uid not in self._admins:
            return False
        self._admins.pop(uid, None)
        self._save()
        return True

    def touch_user(self, user_id: int, username: Optional[str] = None, first_name: Optional[str] = None) -> None:
        uid = int(user_id)
        changed = False
        if uid in self._admins:
            if username and self._admins[uid].get("username") != username:
                self._admins[uid]["username"] = username
                changed = True
            if first_name and self._admins[uid].get("first_name") != first_name:
                self._admins[uid]["first_name"] = first_name
                changed = True
        if uid in self._owners:
            if username and self._owners[uid].get("username") != username:
                self._owners[uid]["username"] = username
                changed = True
            if first_name and self._owners[uid].get("first_name") != first_name:
                self._owners[uid]["first_name"] = first_name
                changed = True
        if changed:
            self._save()

    def list_admins_with_meta(self) -> List[Dict[str, Any]]:
        rows: Dict[int, Dict[str, Any]] = {}
        for uid, row in self._admins.items():
            rows[uid] = {
                "id": uid,
                "username": row.get("username", ""),
                "first_name": row.get("first_name", ""),
                "is_owner": False,
            }
        for uid, row in self._owners.items():
            base = rows.get(uid, {"id": uid, "username": "", "first_name": "", "is_owner": False})
            if row.get("username"):
                base["username"] = row.get("username", "")
            if row.get("first_name"):
                base["first_name"] = row.get("first_name", "")
            base["is_owner"] = True
            rows[uid] = base
        return [rows[k] for k in sorted(rows.keys())]
