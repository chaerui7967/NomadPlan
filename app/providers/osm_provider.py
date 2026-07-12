"""무료 오픈소스 지도 제공자.

- 지오코딩: OpenStreetMap Nominatim (https://nominatim.openstreetmap.org)
- 경로 계산: OSRM 공개 데모 서버 (https://router.project-osrm.org)
- 지도 표시: Leaflet.js + OSM 타일

API 키가 필요 없지만, Nominatim은 사용 정책상 요청 속도를 제한하고
User-Agent 헤더를 요구합니다. 개인/저사용량 용도로만 사용하세요.
"""
from __future__ import annotations

from typing import Any, Dict, List, Tuple

import requests

from .base import GeocodeResult, MapProvider, ProviderError, RouteResult

NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
OSRM_URL_TMPL = "https://router.project-osrm.org/route/v1/{profile}/{coords}"

# Nominatim은 User-Agent를 반드시 요구함 (정책 위반 시 차단될 수 있음)
USER_AGENT = "TravelPlannerDesktopApp/1.0 (personal use)"

_MODE_TO_OSRM_PROFILE = {
    "driving": "driving",
    "car": "driving",
    "walking": "foot",
    "walk": "foot",
    "transit": "driving",  # OSRM 공개 서버는 대중교통 프로파일 미지원 -> 대체
    "cycling": "bike",
}


class OSMProvider(MapProvider):
    display_name = "OpenStreetMap (무료)"
    key = "osm"

    def __init__(self, timeout: float = 10.0):
        self.timeout = timeout

    def geocode(self, query: str) -> List[GeocodeResult]:
        if not query.strip():
            return []
        params = {
            "q": query,
            "format": "jsonv2",
            "addressdetails": 1,
            "limit": 8,
        }
        headers = {"User-Agent": USER_AGENT}
        try:
            resp = requests.get(
                NOMINATIM_URL, params=params, headers=headers, timeout=self.timeout
            )
            resp.raise_for_status()
            data = resp.json()
        except requests.RequestException as e:
            raise ProviderError(f"Nominatim 요청 실패: {e}") from e

        results = []
        for item in data:
            results.append(
                GeocodeResult(
                    name=item.get("name") or item.get("display_name", "").split(",")[0],
                    address=item.get("display_name", ""),
                    lat=float(item["lat"]),
                    lng=float(item["lon"]),
                    raw=item,
                )
            )
        return results

    def route(
        self,
        origin: Tuple[float, float],
        destination: Tuple[float, float],
        mode: str = "driving",
    ) -> RouteResult:
        profile = _MODE_TO_OSRM_PROFILE.get(mode, "driving")
        # OSRM은 lng,lat 순서
        coords = f"{origin[1]},{origin[0]};{destination[1]},{destination[0]}"
        url = OSRM_URL_TMPL.format(profile=profile, coords=coords)
        params = {"overview": "full", "geometries": "geojson"}
        try:
            resp = requests.get(url, params=params, timeout=self.timeout)
            resp.raise_for_status()
            data = resp.json()
        except requests.RequestException as e:
            raise ProviderError(f"OSRM 요청 실패: {e}") from e

        if data.get("code") != "Ok" or not data.get("routes"):
            raise ProviderError(f"OSRM 경로 없음: {data.get('message', data.get('code'))}")

        route = data["routes"][0]
        coords_geojson = route["geometry"]["coordinates"]  # [[lng,lat], ...]
        path = [(lat, lng) for lng, lat in coords_geojson]

        return RouteResult(
            distance_m=route["distance"],
            duration_s=route["duration"],
            path=path,
        )

    def js_map_config(self) -> Dict[str, Any]:
        return {"type": "leaflet"}
