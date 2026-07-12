"""지도 제공자(Provider) 공통 인터페이스.

모든 지도/지오코딩/경로 제공자는 이 클래스를 상속해서 구현합니다.
MainWindow / MapWidget / ItineraryWidget는 구체적인 제공자가 무엇인지 몰라도
이 인터페이스만으로 동작합니다. (Naver <-> OSM 전환이 자유로운 이유)
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Tuple


@dataclass
class GeocodeResult:
    """주소 검색(지오코딩) 결과 한 건."""

    name: str          # 장소명 (없으면 주소와 동일)
    address: str       # 정제된 주소
    lat: float
    lng: float
    raw: Dict[str, Any] = field(default_factory=dict)


@dataclass
class RouteResult:
    """두 지점 간 경로 계산 결과."""

    distance_m: float
    duration_s: float
    path: List[Tuple[float, float]]  # [(lat, lng), ...] 폴리라인


class ProviderError(Exception):
    """지오코딩/경로 계산 중 발생하는 오류 (네트워크, 인증, 결과 없음 등)."""


class MapProvider(ABC):
    """지도 제공자 추상 클래스."""

    #: 화면에 표시할 제공자 이름
    display_name: str = "Base"
    #: 설정에서 이 제공자를 가리키는 키
    key: str = "base"

    @abstractmethod
    def geocode(self, query: str) -> List[GeocodeResult]:
        """주소/장소명을 좌표로 변환. 여러 후보를 반환할 수 있음."""
        raise NotImplementedError

    @abstractmethod
    def route(
        self,
        origin: Tuple[float, float],
        destination: Tuple[float, float],
        mode: str = "driving",
    ) -> RouteResult:
        """두 좌표 간 경로/거리/소요시간을 계산."""
        raise NotImplementedError

    @abstractmethod
    def js_map_config(self) -> Dict[str, Any]:
        """지도 위젯(JS)이 필요로 하는 설정값 반환.

        예: {"type": "leaflet"} 또는
            {"type": "naver", "client_id": "..."}
        """
        raise NotImplementedError
