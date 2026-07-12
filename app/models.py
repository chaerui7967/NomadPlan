"""데이터 모델 정의."""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import List, Optional, Tuple


@dataclass
class Stop:
    """여행 일정의 한 지점(장소)."""

    name: str
    address: str
    lat: float
    lng: float
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:8])
    arrival_time: Optional[str] = None  # "HH:MM" 형식, 사용자가 직접 지정
    travel_mode: str = "driving"  # driving / walking / transit
    note: str = ""

    # 이전 지점 -> 이 지점까지의 이동 정보 (경로 계산 후 채워짐)
    distance_m: Optional[float] = None
    duration_s: Optional[float] = None
    path: List[Tuple[float, float]] = field(default_factory=list)  # [(lat, lng), ...]

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "address": self.address,
            "lat": self.lat,
            "lng": self.lng,
            "arrival_time": self.arrival_time,
            "travel_mode": self.travel_mode,
            "note": self.note,
            "distance_m": self.distance_m,
            "duration_s": self.duration_s,
            "path": self.path,
        }

    @staticmethod
    def from_dict(d: dict) -> "Stop":
        s = Stop(
            name=d.get("name", ""),
            address=d.get("address", ""),
            lat=d.get("lat", 0.0),
            lng=d.get("lng", 0.0),
            id=d.get("id", uuid.uuid4().hex[:8]),
            arrival_time=d.get("arrival_time"),
            travel_mode=d.get("travel_mode", "driving"),
            note=d.get("note", ""),
        )
        s.distance_m = d.get("distance_m")
        s.duration_s = d.get("duration_s")
        s.path = [tuple(p) for p in d.get("path", [])]
        return s
