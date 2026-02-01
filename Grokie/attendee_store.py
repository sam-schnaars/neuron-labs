"""
Event attendee profile storage.
Local JSON-backed store, Supabase-ready interface.
"""

import json
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Dict, List, Optional
from datetime import datetime


@dataclass
class AttendeeProfile:
    """Schema for an event attendee. Same shape used for local store and future Supabase."""
    full_name: str
    email: str
    description: str  # who they are
    who_they_want_to_meet: str
    picture: Optional[str] = None  # URL or path
    linkedin: Optional[str] = None
    metadata: Optional[Dict] = None
    created_at: Optional[str] = None

    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.utcnow().isoformat() + "Z"

    def to_dict(self) -> dict:
        return asdict(self)


def _normalize_email(email: str) -> str:
    return (email or "").strip().lower()


class AttendeeStore:
    """Abstract interface for attendee storage. Implementations: LocalAttendeeStore, later SupabaseAttendeeStore."""

    def add_profile(self, profile: AttendeeProfile) -> bool:
        raise NotImplementedError

    def get_profile(self, email: str) -> Optional[AttendeeProfile]:
        raise NotImplementedError

    def get_profile_by_name(self, name: str) -> Optional[AttendeeProfile]:
        raise NotImplementedError

    def list_profiles(self) -> List[AttendeeProfile]:
        raise NotImplementedError

    def list_profiles_ordered_by_match(self, query: str) -> List[AttendeeProfile]:
        """Return profiles ordered by relevance to query (description, who_they_want_to_meet). Best match first."""
        raise NotImplementedError


class LocalAttendeeStore(AttendeeStore):
    """JSON-file-backed attendee store. In-memory dict keyed by normalized email."""

    def __init__(self, data_path: Optional[Path] = None):
        if data_path is None:
            data_path = Path(__file__).resolve().parent / "event_data" / "attendees.json"
        self._path = Path(data_path)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._by_email: Dict[str, AttendeeProfile] = {}
        self._load()

    def _load(self) -> None:
        if not self._path.exists():
            self._by_email = {}
            return
        try:
            raw = json.loads(self._path.read_text(encoding="utf-8"))
            self._by_email = {}
            for item in raw.get("profiles", []):
                p = AttendeeProfile(
                    full_name=item["full_name"],
                    email=item["email"],
                    description=item.get("description", ""),
                    who_they_want_to_meet=item.get("who_they_want_to_meet", ""),
                    picture=item.get("picture"),
                    linkedin=item.get("linkedin"),
                    metadata=item.get("metadata"),
                    created_at=item.get("created_at"),
                )
                self._by_email[_normalize_email(p.email)] = p
        except Exception as e:
            print(f"⚠️ Could not load attendees from {self._path}: {e}")
            self._by_email = {}

    def _save(self) -> None:
        payload = {
            "profiles": [
                p.to_dict()
                for p in sorted(self._by_email.values(), key=lambda x: (x.created_at or ""))
            ]
        }
        self._path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    def add_profile(self, profile: AttendeeProfile) -> bool:
        key = _normalize_email(profile.email)
        if not key:
            return False
        self._by_email[key] = profile
        self._save()
        return True

    def get_profile(self, email: str) -> Optional[AttendeeProfile]:
        key = _normalize_email(email)
        return self._by_email.get(key)

    def get_profile_by_name(self, name: str) -> Optional[AttendeeProfile]:
        if not name or not name.strip():
            return None
        q = name.strip().lower()
        for p in self._by_email.values():
            if q in (p.full_name or "").lower():
                return p
        return None

    def list_profiles(self) -> List[AttendeeProfile]:
        return list(self._by_email.values())

    def list_profiles_ordered_by_match(self, query: str) -> List[AttendeeProfile]:
        """Return profiles ordered by relevance to query. Best match first. Empty query returns default order."""
        all_profiles = list(self._by_email.values())
        if not query or not query.strip():
            return all_profiles
        q = query.strip().lower()
        words = set(w for w in q.split() if len(w) > 1)

        def score(p: AttendeeProfile) -> int:
            text = f" {(p.description or '').lower()} {(p.who_they_want_to_meet or '').lower()} {(p.full_name or '').lower()} "
            # Full phrase match wins most
            if q in text:
                return 100
            # Word matches
            return sum(10 for w in words if w in text)

        return sorted(all_profiles, key=score, reverse=True)
