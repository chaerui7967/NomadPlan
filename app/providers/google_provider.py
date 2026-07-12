"""Google Maps Platform 제공자.

- 지오코딩: Geocoding API (https://maps.googleapis.com/maps/api/geocode/json)
- 경로 계산: Routes API (https://routes.googleapis.com/directions/v2:computeRoutes)
  ※ 기존 Directions API는 Legacy로 전환되어, 신규 프로젝트에는 Routes API 사용을 권장하고 있어 이를 사용.
- 지도 표시: Google Maps JavaScript API (maps.googleapis.com/maps/api/js)

Google Cloud Console에서 프로젝트를 만들고 결제를 연동한 뒤,
"Geocoding API", "Routes API", "Maps JavaScript API"를 사용 설정하고 발급받은
API 키가 필요합니다. (해외/일본 등에서 국내 지도 API보다 커버리지가 넓음)
"""
from __future__ import annotations

from typing import Any, Dict, List, Tuple

import requests

from .base import GeocodeResult, MapProvider, ProviderError, RouteResult

GEOCODE_URL = "https://maps.googleapis.com/maps/api/geocode/json"
ROUTES_URL = "https://routes.googleapis.com/directions/v2:computeRoutes"

_MODE_TO_GOOGLE_TRAVEL_MODE = {
    "driving": "DRIVE",
    "car": "DRIVE",
    "walking": "WALK",
    "walk": "WALK",
    "transit": "TRANSIT",
    "cycling": "BICYCLE",
}


def _decode_polyline(encoded: str) -> List[Tuple[float, float]]:
    """Google의 인코딩된 폴리라인 문자열을 (lat, lng) 리스트로 디코딩."""
    points: List[Tuple[float, float]] = []
    index = lat = lng = 0
    length = len(encoded)

    while index < length:
        for is_lat in (True, False):
            shift = result = 0
            while True:
                b = ord(encoded[index]) - 63
                index += 1
                result |= (b & 0x1F) << shift
                shift += 5
                if b < 0x20:
                    break
            delta = ~(result >> 1) if (result & 1) else (result >> 1)
            if is_lat:
                lat += delta
            else:
                lng += delta
        points.append((lat / 1e5, lng / 1e5))
    return points


class GoogleProvider(MapProvider):
    display_name = "Google 지도"
    key = "google"

    def __init__(self, api_key: str, timeout: float = 10.0):
        if not api_key:
            raise ValueError("Google 지도 API를 사용하려면 API 키가 필요합니다.")
        self.api_key = api_key
        self.timeout = timeout

    def geocode(self, query: str) -> List[GeocodeResult]:
        if not query.strip():
            return []
        params = {"address": query, "key": self.api_key}
        try:
            resp = requests.get(GEOCODE_URL, params=params, timeout=self.timeout)
            resp.raise_for_status()
            data = resp.json()
        except requests.RequestException as e:
            raise ProviderError(f"Google 지오코딩 요청 실패: {e}") from e

        status = data.get("status")
        if status == "ZERO_RESULTS":
            return []
        if status != "OK":
            raise ProviderError(f"Google 지오코딩 오류: {status} {data.get('error_message', '')}")

        results = []
        for item in data.get("results", []):
            loc = item["geometry"]["location"]
            name = item.get("formatted_address", "").split(",")[0]
            results.append(
                GeocodeResult(
                    name=name,
                    address=item.get("formatted_address", ""),
                    lat=loc["lat"],
                    lng=loc["lng"],
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
        travel_mode = _MODE_TO_GOOGLE_TRAVEL_MODE.get(mode, "DRIVE")
        body: Dict[str, Any] = {
            "origin": {"location": {"latLng": {"latitude": origin[0], "longitude": origin[1]}}},
            "destination": {
                "location": {"latLng": {"latitude": destination[0], "longitude": destination[1]}}
            },
            "travelMode": travel_mode,
        }
        if travel_mode == "DRIVE":
            body["routingPreference"] = "TRAFFIC_AWARE"

        headers = {
            "Content-Type": "application/json",
            "X-Goog-Api-Key": self.api_key,
            "X-Goog-FieldMask": "routes.duration,routes.distanceMeters,routes.polyline.encodedPolyline",
        }
        try:
            resp = requests.post(ROUTES_URL, json=body, headers=headers, timeout=self.timeout)
            resp.raise_for_status()
            data = resp.json()
        except requests.RequestException as e:
            raise ProviderError(f"Google 경로(Routes API) 요청 실패: {e}") from e

        routes = data.get("routes")
        if not routes:
            raise ProviderError("Google Routes API: 경로를 찾지 못했습니다.")

        route = routes[0]
        duration_str = route.get("duration", "0s")  # 예: "1234s"
        duration_s = float(duration_str.rstrip("s")) if duration_str.endswith("s") else float(duration_str)
        encoded = route.get("polyline", {}).get("encodedPolyline", "")
        path = _decode_polyline(encoded) if encoded else [origin, destination]

        return RouteResult(
            distance_m=float(route.get("distanceMeters", 0)),
            duration_s=duration_s,
            path=path,
        )

    def js_map_config(self) -> Dict[str, Any]:
        return {"type": "google", "api_key": self.api_key}
