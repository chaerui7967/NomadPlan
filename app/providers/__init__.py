from typing import Optional, Tuple

from .base import GeocodeResult, MapProvider, ProviderError, RouteResult
from .google_provider import GoogleProvider
from .naver_provider import NaverProvider
from .osm_provider import OSMProvider

__all__ = [
    "GeocodeResult",
    "MapProvider",
    "ProviderError",
    "RouteResult",
    "NaverProvider",
    "OSMProvider",
    "GoogleProvider",
    "resolve_provider",
]

CHOICE_OSM = "osm"
CHOICE_NAVER = "naver"
CHOICE_GOOGLE = "google"
# KAKAO_KEY="d64387de212ef1029245ed8d940e222d"

def resolve_provider(
    choice: str,
    naver_client_id: str = "",
    naver_client_secret: str = "",
    google_api_key: str = "",
    KAKAO_KEY: str = "",
) -> Tuple[MapProvider, Optional[str]]:
    """설정에서 선택된 provider를 생성.

    선택한 provider에 필요한 키가 없으면 무료 OSM으로 자동 대체하고,
    그 사실을 알리는 경고 메시지를 두 번째 값으로 반환한다. (없으면 None)
    """
    choice = (choice or CHOICE_OSM).strip().lower()
    naver_client_id = (naver_client_id or "").strip()
    naver_client_secret = (naver_client_secret or "").strip()
    google_api_key = (google_api_key or "").strip()

    if choice == CHOICE_NAVER:
        if naver_client_id and naver_client_secret:
            return NaverProvider(naver_client_id, naver_client_secret, kakao_rest_key=KAKAO_KEY), None
        return OSMProvider(), "네이버 Client ID/Secret이 없어 무료 지도(OSM)로 대체되었습니다."

    if choice == CHOICE_GOOGLE:
        if google_api_key:
            return GoogleProvider(google_api_key), None
        return OSMProvider(), "Google API 키가 없어 무료 지도(OSM)로 대체되었습니다."
    
    return OSMProvider(kakao_rest_key=KAKAO_KEY), None
