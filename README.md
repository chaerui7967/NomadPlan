# 여행 일정 플래너 (PySide6)

지도 위에서 여행 일정을 관리하는 데스크톱 앱입니다.

- **상단**: 지도 (마커 + 이동 경로 표시)
- **하단**: 일정 목록 (카드형 UI, 일정 추가/수정/삭제, 드래그로 순서 변경)
- 지점을 추가/수정하면 이전 지점부터의 **거리/이동시간을 자동 계산**해서 보여줍니다.
- 각 일정 카드의 **[수정]** 버튼으로 주소/도착시각/이동수단/메모를 다시 편집할 수 있습니다.
  (주소를 다시 검색하지 않으면 기존 위치가 그대로 유지됩니다.)
- 상단 메뉴 **설정 > 지도 제공자 설정**에서 사용할 지도를 고를 수 있습니다.
  - **무료 (OpenStreetMap)**: 키 없이 바로 사용 (Nominatim + OSRM)
  - **네이버 지도**: 국내 여행에 적합, Client ID/Secret 필요
  - **Google 지도**: 해외(일본 등) 여행에 적합, API Key 필요
  - 선택한 서비스의 키가 비어 있으면 자동으로 무료 지도로 대체되고 안내 메시지가 뜹니다.
  - 앱 재시작 없이 그 자리에서 즉시 전환됩니다.

## 실행 방법

```bash
pip install -r requirements.txt
python main.py
```

## 네이버 지도 API 키 발급 (선택사항, 국내용)

1. https://www.ncloud.com 에서 [콘솔] 접속 후 로그인
2. Services > Application Services > **Maps** 로 이동, 이용 신청
3. 콘솔에서 **Application 등록** → Geocoding, Directions 5 API를 선택
4. 발급된 **Client ID / Client Secret**을 앱의 [설정 > 지도 제공자 설정]에 입력

> ⚠️ 2025년 7월 1일부터 네이버 지도 API는 무료 이용량 없이 처음부터 종량 과금됩니다.

## Google 지도 API 키 발급 (선택사항, 해외용 — 일본 등)

1. https://console.cloud.google.com 에서 프로젝트 생성 후 **결제 계정 연동** (필수)
2. **API 및 서비스**에서 다음 API를 사용 설정:
   - Geocoding API
   - Routes API (경로/거리 계산 — 기존 Directions API의 후속 API)
   - Maps JavaScript API (지도 표시용)
3. **사용자 인증 정보**에서 API 키 발급 → 앱의 [설정 > 지도 제공자 설정]에 입력

> ⚠️ 매월 $200 크레딧이 제공되지만, 이후로는 요청당 과금됩니다.
> 키 발급 시 사용할 API로 제한을 걸어두는 것을 권장합니다.

## 지도 렌더링이 안 될 때

네이버/Google 지도 JS는 브라우저 환경(도메인 등록)을 전제로 하기 때문에,
로컬 데스크톱 앱에서는 지도 타일이 안 뜰 수 있습니다. 이 경우에도 **주소 검색과
거리/시간 계산은 정상 동작**합니다. 필요하면 지도 표시는 항상 무료 OSM(Leaflet)으로
유지하고 검색/경로만 네이버·Google로 쓰는 하이브리드 방식으로 바꿔드릴 수 있습니다.

## 프로젝트 구조

```
travel_planner/
├── main.py                     # 진입점
├── requirements.txt
└── app/
    ├── models.py                # Stop 데이터 모델
    ├── settings.py               # QSettings 기반 설정 저장 + 설정 다이얼로그
    ├── map_widget.py              # 지도 위젯 (Leaflet / 네이버 지도 JS)
    ├── itinerary_widget.py        # 일정 목록 + 장소 검색/추가 다이얼로그
    ├── main_window.py             # 메인 윈도우 (지도+일정 결합)
    └── providers/
        ├── base.py                # MapProvider 추상 인터페이스
        ├── osm_provider.py         # 무료: Nominatim + OSRM
        ├── naver_provider.py       # 네이버: Geocoding + Directions 5
        ├── google_provider.py      # Google: Geocoding API + Routes API
        └── __init__.py             # resolve_provider() 팩토리
```

## 확장 아이디어

- 날짜별 Day 탭 나누기 (Day 1, Day 2, ...)
- 일정을 JSON으로 저장/불러오기 (여행 계획 파일로 공유)
- 카카오맵 API provider 추가 (`providers/kakao_provider.py`만 추가하고 `create_provider`에 분기 추가하면 됨)
- 대중교통 소요시간 지원 (네이버 Directions는 자동차만 지원하므로 별도 API 필요)
