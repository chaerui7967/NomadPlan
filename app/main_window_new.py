"""메인 윈도우.

레이아웃:
  +--------------------------+
  |         지도 (상단)        |
  +--------------------------+
  |  총 거리/시간 요약          |
  +--------------------------+
  |   일정 목록 (하단, 추가/삭제) |
  +--------------------------+

메뉴: 설정 > 지도 제공자 설정 (OSM 무료 / 네이버 / Google 선택 및 API 키 입력)
"""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from .itinerary_widget import ItineraryWidget, format_distance, format_duration
from .map_widget import MapWidget
from .providers import MapProvider, resolve_provider
from .settings import AppSettings, SettingsDialog


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("여행 일정 플래너")
        self.resize(1000, 800)

        self.settings = AppSettings()
        self.provider: MapProvider = self._load_provider(notify_fallback=False)

        central = QWidget()
        self.setCentralWidget(central)
        root_layout = QVBoxLayout(central)
        root_layout.setContentsMargins(0, 0, 0, 0)

        splitter = QSplitter(Qt.Horizontal)
        root_layout.addWidget(splitter)

        self.map_widget = MapWidget()
        self.map_widget.set_provider_config(self.provider.js_map_config())
        splitter.addWidget(self.map_widget)

        self._current_path = []  # 현재 전체 경로 좌표 (애니메이션용)

        bottom = QWidget()
        bottom_layout = QVBoxLayout(bottom)

        summary_row = QHBoxLayout()
        self.summary_label = QLabel("일정을 추가하면 총 이동거리/시간이 표시됩니다.")
        self.summary_label.setObjectName("summaryLabel")
        summary_row.addWidget(self.summary_label, stretch=1)

        self.play_btn = QPushButton("▶ 출발")
        self.play_btn.setObjectName("primaryButton")
        self.play_btn.clicked.connect(self._on_play_animation)
        summary_row.addWidget(self.play_btn)

        self.stop_btn = QPushButton("■ 정지")
        self.stop_btn.clicked.connect(self._on_stop_animation)
        summary_row.addWidget(self.stop_btn)

        bottom_layout.addLayout(summary_row)

        self.itinerary_widget = ItineraryWidget(provider_getter=lambda: self.provider)
        self.itinerary_widget.stops_changed.connect(self._on_stops_changed)
        self.itinerary_widget.stop_selected.connect(self._on_stop_selected)
        bottom_layout.addWidget(self.itinerary_widget)
        splitter.addWidget(bottom)

        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 2)
        splitter.setSizes([650, 380])

        self._build_menu()
        self._update_provider_status()

    def _load_provider(self, notify_fallback: bool = True) -> MapProvider:
        provider, warning = resolve_provider(
            self.settings.provider_choice,
            self.settings.naver_client_id,
            self.settings.naver_client_secret,
            self.settings.google_api_key,
        )
        if warning and notify_fallback:
            QMessageBox.warning(self, "지도 제공자 안내", warning)
        return provider

    def _build_menu(self) -> None:
        menu = self.menuBar().addMenu("설정")
        settings_action = menu.addAction("지도 제공자 설정...")
        settings_action.triggered.connect(self._open_settings)

    def _open_settings(self) -> None:
        dialog = SettingsDialog(self.settings, self)
        if dialog.exec():
            self.provider = self._load_provider(notify_fallback=True)
            self.map_widget.set_provider_config(self.provider.js_map_config())
            self.itinerary_widget.set_provider_changed()
            self._update_provider_status()
            QMessageBox.information(
                self, "설정 저장됨", f"지도 제공자가 '{self.provider.display_name}'(으)로 설정되었습니다."
            )

    def _update_provider_status(self) -> None:
        self.setWindowTitle(f"여행 일정 플래너 — {self.provider.display_name}")

    def _on_stop_selected(self, stop) -> None:
        self.map_widget.set_center(stop.lat, stop.lng, zoom=15)

    def _on_play_animation(self) -> None:
        if len(self._current_path) < 2:
            QMessageBox.information(self, "일정 부족", "경로를 그리려면 일정을 2개 이상 추가해주세요.")
            return
        # 실제 이동시간과 무관하게 5~15초 사이로 보기 좋게 재생 (너무 짧거나 길지 않도록)
        duration_ms = max(5000, min(15000, len(self._current_path) * 200))
        self.map_widget.animate_route(self._current_path, duration_ms=duration_ms)

    def _on_stop_animation(self) -> None:
        self.map_widget.stop_animation()

    def _on_stops_changed(self, stops) -> None:
        self.map_widget.render_stops(stops)

        self._current_path = []
        for s in stops:
            if s.path:
                self._current_path.extend(s.path)

        total_distance = sum((s.distance_m or 0) for s in stops)
        total_duration = sum((s.duration_s or 0) for s in stops)
        if stops:
            self.summary_label.setText(
                f"총 {len(stops)}개 지점 · 이동거리 {format_distance(total_distance)} · "
                f"이동시간 {format_duration(total_duration)}"
            )
        else:
            self.summary_label.setText("일정을 추가하면 총 이동거리/시간이 표시됩니다.")