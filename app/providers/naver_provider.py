"""네이버클라우드플랫폼 Maps API 제공자.

- 지오코딩: https://maps.apigw.ntruss.com/map-geocode/v2/geocode
- 경로 계산(Directions 5): https://maps.apigw.ntruss.com/map-direction/v1/driving
- 지도 표시: NAVER Maps JS API v3 (oapi.map.naver.com)

네이버클라우드플랫폼 콘솔 > Application 등록에서 발급받은
Client ID / Client Secret이 필요합니다. (2025.7.1부터 무료 이용량 없이 종량 과금)
Directions API는 자동차 경로만 지원합니다 (도보/대중교통 미지원).
"""
from __future__ import annotations

from typing import Any, Dict, List, Tuple

import requests

from .base import GeocodeResult, MapProvider, ProviderError, RouteResult

GEOCODE_URL = "https://maps.apigw.ntruss.com/map-geocode/v2/geocode"
DIRECTIONS_URL = "https://maps.apigw.ntruss.com/map-direction/v1/driving"


class NaverProvider(MapProvider):
    display_name = "네이버 지도"
    key = "naver"

    def __init__(self, client_id: str, client_secret: str, timeout: float = 10.0):
        if not client_id or not client_secret:
            raise ValueError("네이버 지도 API를 사용하려면 Client ID/Secret이 필요합니다.")
        self.client_id = client_id
        self.client_secret = client_secret
        self.timeout = timeout

    def _headers(self) -> Dict[str, str]:
        return {
            "X-NCP-APIGW-API-KEY-ID": self.client_id,
            "X-NCP-APIGW-API-KEY": self.client_secret,
        }

    def geocode(self, query: str) -> List[GeocodeResult]:
        if not query.strip():
            return []
        params = {"query": query}
        try:
            resp = requests.get(
                GEOCODE_URL, params=params, headers=self._headers(), timeout=self.timeout
            )
            resp.raise_for_status()
            data = resp.json()
        except requests.RequestException as e:
            raise ProviderError(f"네이버 지오코딩 요청 실패: {e}") from e

        if data.get("status") != "OK":
            raise ProviderError(f"네이버 지오코딩 오류: {data.get('status')}")

        results = []
        for item in data.get("addresses", []):
            road_addr = item.get("roadAddress") or item.get("jibunAddress", "")
            results.append(
                GeocodeResult(
                    name=road_addr.split(" ")[-1] if road_addr else query,
                    address=road_addr,
                    lat=float(item["y"]),
                    lng=float(item["x"]),
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
        # Directions 5는 자동차 경로만 지원 (lng,lat 순서, 콤마 구분)
        start = f"{origin[1]},{origin[0]}"
        goal = f"{destination[1]},{destination[0]}"
        params = {"start": start, "goal": goal, "option": "trafast"}
        try:
            resp = requests.get(
                DIRECTIONS_URL, params=params, headers=self._headers(), timeout=self.timeout
            )
            resp.raise_for_status()
            data = resp.json()
        except requests.RequestException as e:
            raise ProviderError(f"네이버 경로 요청 실패: {e}") from e

        if data.get("code") != 0:
            raise ProviderError(f"네이버 경로 오류: {data.get('message')}")

        route = data["route"]["trafast"][0]
        summary = route["summary"]
        path_lnglat = route["path"]  # [[lng,lat], ...]
        path = [(lat, lng) for lng, lat in path_lnglat]

        return RouteResult(
            distance_m=summary["distance"],
            duration_s=summary["duration"] / 1000.0,  # ms -> s
            path=path,
        )

    def js_map_config(self) -> Dict[str, Any]:
        return {"type": "naver", "client_id": self.client_id}
