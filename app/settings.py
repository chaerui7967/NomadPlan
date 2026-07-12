"""앱 설정 저장/불러오기 (QSettings 사용, OS별 표준 위치에 자동 저장됨).

macOS: ~/Library/Preferences/com.travelplanner.TravelPlanner.plist
Windows: 레지스트리
Linux: ~/.config/TravelPlanner/TravelPlanner.conf
"""
from __future__ import annotations

from PySide6.QtCore import QSettings
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QLineEdit,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from .providers import CHOICE_GOOGLE, CHOICE_NAVER, CHOICE_OSM

ORG_NAME = "TravelPlanner"
APP_NAME = "TravelPlanner"

KEY_PROVIDER_CHOICE = "provider/choice"
KEY_NAVER_CLIENT_ID = "naver/client_id"
KEY_NAVER_CLIENT_SECRET = "naver/client_secret"
KEY_GOOGLE_API_KEY = "google/api_key"


class AppSettings:
    """QSettings 래퍼. 지도 제공자 선택 및 API 키를 담당."""

    def __init__(self):
        self._qs = QSettings(ORG_NAME, APP_NAME)

    @property
    def provider_choice(self) -> str:
        return self._qs.value(KEY_PROVIDER_CHOICE, CHOICE_OSM, type=str)

    @provider_choice.setter
    def provider_choice(self, value: str) -> None:
        self._qs.setValue(KEY_PROVIDER_CHOICE, value)

    @property
    def naver_client_id(self) -> str:
        return self._qs.value(KEY_NAVER_CLIENT_ID, "", type=str)

    @naver_client_id.setter
    def naver_client_id(self, value: str) -> None:
        self._qs.setValue(KEY_NAVER_CLIENT_ID, value)

    @property
    def naver_client_secret(self) -> str:
        return self._qs.value(KEY_NAVER_CLIENT_SECRET, "", type=str)

    @naver_client_secret.setter
    def naver_client_secret(self, value: str) -> None:
        self._qs.setValue(KEY_NAVER_CLIENT_SECRET, value)

    @property
    def google_api_key(self) -> str:
        return self._qs.value(KEY_GOOGLE_API_KEY, "", type=str)

    @google_api_key.setter
    def google_api_key(self, value: str) -> None:
        self._qs.setValue(KEY_GOOGLE_API_KEY, value)

    def sync(self) -> None:
        self._qs.sync()


_CHOICES = [
    (CHOICE_OSM, "무료 (OpenStreetMap)"),
    (CHOICE_NAVER, "네이버 지도 (국내용)"),
    (CHOICE_GOOGLE, "Google 지도 (해외용, 일본 등)"),
]


class SettingsDialog(QDialog):
    """지도 제공자를 선택하고, 각 제공자별 API 키를 입력하는 설정 창."""

    def __init__(self, settings: AppSettings, parent=None):
        super().__init__(parent)
        self.settings = settings
        self.setWindowTitle("설정 - 지도 제공자")
        self.setMinimumWidth(440)

        layout = QVBoxLayout(self)

        info = QLabel(
            "사용할 지도 서비스를 선택하세요. 국내 여행은 네이버 지도, "
            "해외(일본 등) 여행은 Google 지도를 추천합니다.\n"
            "선택한 서비스의 키가 비어 있으면 자동으로 무료 지도로 대체됩니다."
        )
        info.setWordWrap(True)
        layout.addWidget(info)

        self.provider_combo = QComboBox()
        for choice_key, label in _CHOICES:
            self.provider_combo.addItem(label, userData=choice_key)
        layout.addWidget(self.provider_combo)

        self.stack = QStackedWidget()
        layout.addWidget(self.stack)

        # 0: OSM (안내 문구만)
        osm_page = QWidget()
        osm_layout = QVBoxLayout(osm_page)
        osm_layout.addWidget(QLabel("별도 설정이 필요 없습니다. API 키 없이 바로 사용 가능합니다."))
        self.stack.addWidget(osm_page)

        # 1: 네이버
        naver_page = QWidget()
        naver_form = QFormLayout(naver_page)
        self.naver_client_id_edit = QLineEdit(self.settings.naver_client_id)
        self.naver_client_id_edit.setPlaceholderText("Naver Client ID")
        self.naver_client_secret_edit = QLineEdit(self.settings.naver_client_secret)
        self.naver_client_secret_edit.setPlaceholderText("Naver Client Secret")
        self.naver_client_secret_edit.setEchoMode(QLineEdit.Password)
        naver_form.addRow("Client ID", self.naver_client_id_edit)
        naver_form.addRow("Client Secret", self.naver_client_secret_edit)
        naver_note = QLabel("※ 2025.7.1부터 무료 이용량 없이 종량 과금됩니다.")
        naver_note.setWordWrap(True)
        naver_note.setStyleSheet("color: #888; font-size: 11px;")
        naver_form.addRow(naver_note)
        self.stack.addWidget(naver_page)

        # 2: 구글
        google_page = QWidget()
        google_form = QFormLayout(google_page)
        self.google_api_key_edit = QLineEdit(self.settings.google_api_key)
        self.google_api_key_edit.setPlaceholderText("Google Maps Platform API Key")
        self.google_api_key_edit.setEchoMode(QLineEdit.Password)
        google_form.addRow("API Key", self.google_api_key_edit)
        google_note = QLabel(
            "Google Cloud Console에서 Geocoding API, Routes API, Maps JavaScript API를 "
            "사용 설정하고 발급받은 키를 입력하세요. (결제 계정 연동 필요, 월 $200 크레딧 제공)"
        )
        google_note.setWordWrap(True)
        google_note.setStyleSheet("color: #888; font-size: 11px;")
        google_form.addRow(google_note)
        self.stack.addWidget(google_page)

        self.provider_combo.currentIndexChanged.connect(self.stack.setCurrentIndex)

        # 저장된 선택값으로 초기화
        current_choice = self.settings.provider_choice
        idx = next((i for i, (k, _) in enumerate(_CHOICES) if k == current_choice), 0)
        self.provider_combo.setCurrentIndex(idx)
        self.stack.setCurrentIndex(idx)

        buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self._on_save)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _on_save(self) -> None:
        self.settings.provider_choice = self.provider_combo.currentData()
        self.settings.naver_client_id = self.naver_client_id_edit.text().strip()
        self.settings.naver_client_secret = self.naver_client_secret_edit.text().strip()
        self.settings.google_api_key = self.google_api_key_edit.text().strip()
        self.settings.sync()
        self.accept()
