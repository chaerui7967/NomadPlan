"""네이버클라우드플랫폼 Maps API + 카카오 로컬 API 통합 제공자.

- 주소 검색(네이버 지오코딩): https://maps.apigw.ntruss.com/map-geocode/v2/geocode
- 장소명 검색(카카오 로컬): https://dapi.kakao.com/v2/local/search/keyword.json
- 경로 계산(Directions 5): https://maps.apigw.ntruss.com/map-direction/v1/driving
- 지도 표시: NAVER Maps JS API v3 (oapi.map.naver.com)
"""
from __future__ import annotations

from typing import Any, Dict, List, Tuple

import requests

from .base import GeocodeResult, MapProvider, ProviderError, RouteResult

GEOCODE_URL = "https://maps.apigw.ntruss.com/map-geocode/v2/geocode"
DIRECTIONS_URL = "https://maps.apigw.ntruss.com/map-direction/v1/driving"
KAKAO_KEYWORD_URL = "https://dapi.kakao.com/v2/local/search/keyword.json"  # 📌 카카오 로컬 키워드 검색 URL


class NaverProvider(MapProvider):
    display_name = "네이버 지도 (카카오 검색 통합)"
    key = "naver"

    def __init__(self, client_id: str, client_secret: str, kakao_rest_key: str = "", timeout: float = 10.0):
        if not client_id or not client_secret:
            raise ValueError("네이버 지도 API를 사용하려면 Client ID/Secret이 필요합니다.")
        self.client_id = client_id
        self.client_secret = client_secret
        self.kakao_rest_key = kakao_rest_key  # 📌 카카오 REST API 키 저장
        self.timeout = timeout

    def _headers(self) -> Dict[str, str]:
        return {
            "X-NCP-APIGW-API-KEY-ID": self.client_id,
            "X-NCP-APIGW-API-KEY": self.client_secret,
        }

    def geocode(self, query: str) -> List[GeocodeResult]:
        if not query.strip():
            return []
        
        results = []
        
        # -----------------------------------------------------------------
        # 1. 우선 네이버 클라우드의 '주소 검색(Geocoding)'을 시도합니다.
        # -----------------------------------------------------------------
        params = {"query": query}
        try:
            resp = requests.get(
                GEOCODE_URL, params=params, headers=self._headers(), timeout=self.timeout
            )
            resp.raise_for_status()
            data = resp.json()
            
            if data.get("status") == "OK" and data.get("addresses"):
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
                return results  # 네이버 주소 결과가 있으면 즉시 리턴
        except requests.RequestException:
            pass  # 네이버 요청 실패 시 에러를 내지 않고 카카오 검색으로 넘깁니다.

        # -----------------------------------------------------------------
        # 2. 📌 네이버 주소 결과가 없거나 실패했다면, '카카오 로컬 API'로 장소명 검색을 시도합니다.
        # -----------------------------------------------------------------
        if not self.kakao_rest_key:
            # 카카오 키가 안 넘어왔다면 빈 결과 리턴 (기존 코드 호환용)
            return []

        kakao_headers = {
            "Authorization": f"KakaoAK {self.kakao_rest_key.strip()}"
        }
        kakao_params = {
            "query": query,
            "size": 10  # 최대 10개 항목 검색
        }

        try:
            resp_kakao = requests.get(
                KAKAO_KEYWORD_URL, params=kakao_params, headers=kakao_headers, timeout=self.timeout
            )
            resp_kakao.raise_for_status()
            kakao_data = resp_kakao.json()
            
            # 카카오 결과 파싱 (documents 리스트에 결과가 담겨옴)
            for item in kakao_data.get("documents", []):
                # 카카오 로컬 API는 x가 경도(lng), y가 위도(lat)입니다. (네이버와 반대이므로 주의)
                results.append(
                    GeocodeResult(
                        name=item.get("place_name", query),  # '우진해장국', '제주공항' 등 명확한 이름
                        address=item.get("road_address_name") or item.get("address_name", ""),
                        lat=float(item["y"]),  # 위도
                        lng=float(item["x"]),  # 경도
                        raw=item,
                    )
                )
        except requests.RequestException as e:
            raise ProviderError(f"카카오 장소 검색 요청 실패: {e}") from e
        
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