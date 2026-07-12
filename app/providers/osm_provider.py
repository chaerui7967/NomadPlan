"""무료 오픈소스 지도 제공자 + 카카오 장소 검색 하이브리드 통합 프로바이더.

- 해외/기본 주소 검색: OpenStreetMap Nominatim (https://nominatim.openstreetmap.org)
- 국내 장소명/POI 검색: 카카오 로컬 API (https://dapi.kakao.com/v2/local/search/keyword.json)
- 글로벌 경로 계산: OSRM 공개 데모 서버 (https://router.project-osrm.org)
- 지도 표시: Leaflet.js + OSM 타일

[작동 매커니즘]
검색어 입력 시 1차로 글로벌 OSM 엔진(Nominatim)을 통해 검색을 시도합니다.
해외 유명 장소나 표준 주소는 여기서 처리되어 즉시 반환됩니다.
만약 한국 내부의 상호명(예: 우진해장국)이라 OSM이 찾지 못하면, 
2차로 카카오 로컬 API가 바톤을 이어받아 정확한 국내 장소와 좌표를 찾아냅니다.
"""
from __future__ import annotations

from typing import Any, Dict, List, Tuple

import requests

from .base import GeocodeResult, MapProvider, ProviderError, RouteResult

NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
KAKAO_KEYWORD_URL = "https://dapi.kakao.com/v2/local/search/keyword.json"
OSRM_URL_TMPL = "https://router.project-osrm.org/route/v1/{profile}/{coords}"

# Nominatim 필수 헤더 (정책 위반으로 인한 차단 방지)
USER_AGENT = "TravelPlannerHybridApp/1.0 (personal use)"

_MODE_TO_OSRM_PROFILE = {
    "driving": "driving",
    "car": "driving",
    "walking": "foot",
    "walk": "foot",
    "transit": "driving",  # OSRM 공개 서버는 대중교통 미지원으로 자동차 대체
    "cycling": "bike",
}


class OSMProvider(MapProvider):
    display_name = "OpenStreetMap (하이브리드 글로벌)"
    key = "osm"

    def __init__(self, kakao_rest_key: str = "", timeout: float = 10.0):
        """프로바이더 초기화.
        
        국내 장소 검색 보완을 위해 카카오 개발자 센터에서 발급받은 'REST API 키'가 필요합니다.
        """
        self.kakao_rest_key = kakao_rest_key.strip()
        self.timeout = timeout

    def geocode(self, query: str) -> List[GeocodeResult]:
        if not query.strip():
            return []
        results = []

        # -----------------------------------------------------------------
        # 단계 1: 글로벌 OSM Nominatim 엔진으로 1차 검색 (해외 장소/표준 주소 타겟)
        # -----------------------------------------------------------------
        params = {
            "q": query,
            "format": "jsonv2",
            "addressdetails": 1,
            "limit": 5,
        }
        headers = {"User-Agent": USER_AGENT}
        try:
            resp = requests.get(
                NOMINATIM_URL, params=params, headers=headers, timeout=self.timeout
            )
            resp.raise_for_status()
            data = resp.json()
            
            if data:
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
                # 💡 OSM 결과가 존재한다면 (해외 장소거나 명확한 주소인 경우) 
                # 뒤쪽 카카오 API를 호출하지 않고 즉시 결과를 반환하여 트래픽을 아낍니다.
                return results  
        except requests.RequestException:
            # 네트워크 에러나 OSM 서버 일시 다운 시 에러로 앱이 죽지 않고 
            # 카카오 검색으로 넘어가서 유연하게 버틸 수 있도록 예외를 넘깁니다.
            pass

        # -----------------------------------------------------------------
        # 단계 2: OSM 결과가 없거나 실패한 경우, 카카오 로컬 API로 2차 검색 (국내 POI 타겟)
        # -----------------------------------------------------------------
        if not self.kakao_rest_key:
            return []  # 카카오 키가 주입되지 않았다면 그대로 빈 리스트 리턴

        kakao_headers = {
            "Authorization": f"KakaoAK {self.kakao_rest_key}"
        }
        kakao_params = {
            "query": query,
            "size": 10
        }

        try:
            resp_kakao = requests.get(
                KAKAO_KEYWORD_URL, params=kakao_params, headers=kakao_headers, timeout=self.timeout
            )
            resp_kakao.raise_for_status()
            kakao_data = resp_kakao.json()
            
            for item in kakao_data.get("documents", []):
                # ⚠️ 카카오 로컬 API의 x는 경도(lng), y는 위도(lat)입니다.
                # GeocodeResult 구조에 맞게 순서를 스왑하여 안전하게 매핑합니다.
                results.append(
                    GeocodeResult(
                        name=item.get("place_name", query),  # '제주공항', '우진해장국' 등 직관적인 상호명
                        address=item.get("road_address_name") or item.get("address_name", ""),
                        lat=float(item["y"]),
                        lng=float(item["x"]),
                        raw=item,
                    )
                )
        except requests.RequestException as e:
            raise ProviderError(f"하이브리드 카카오 장소 검색 요청 실패: {e}") from e
        
        return results

    def route(
        self,
        origin: Tuple[float, float],
        destination: Tuple[float, float],
        mode: str = "driving",
    ) -> RouteResult:
        """OSRM 공개 엔진을 활용한 글로벌 경로 계산 알고리즘."""
        profile = _MODE_TO_OSRM_PROFILE.get(mode, "driving")
        # OSRM은 표준 경위도 순서 포맷인 [lng, lat]를 사용합니다.
        coords = f"{origin[1]},{origin[0]};{destination[1]},{destination[0]}"
        url = OSRM_URL_TMPL.format(profile=profile, coords=coords)
        params = {"overview": "full", "geometries": "geojson"}
        try:
            resp = requests.get(url, params=params, timeout=self.timeout)
            resp.raise_for_status()
            data = resp.json()
        except requests.RequestException as e:
            raise ProviderError(f"OSRM 글로벌 경로 요청 실패: {e}") from e

        if data.get("code") != "Ok" or not data.get("routes"):
            raise ProviderError(f"OSRM 경로 매칭 실패: {data.get('message', data.get('code'))}")

        route = data["routes"][0]
        coords_geojson = route["geometry"]["coordinates"]  # [[lng, lat], ...]
        path = [(lat, lng) for lng, lat in coords_geojson]  # 내부 UI 컴포넌트용 (lat, lng) 변환

        return RouteResult(
            distance_m=route["distance"],
            duration_s=route["duration"],
            path=path,
        )

    def js_map_config(self) -> Dict[str, Any]:
        """Leaflet 타일 기반 지도를 렌더링하도록 뷰포트에 설정 전달."""
        return {"type": "leaflet"}