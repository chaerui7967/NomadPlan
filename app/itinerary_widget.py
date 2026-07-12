"""일정(방문 순서) 목록을 보여주고 관리하는 위젯.

- 상단 '+ 일정 추가' 버튼 -> 주소/장소 검색 다이얼로그
- 각 카드의 '수정' 버튼 -> 같은 다이얼로그를 기존 값으로 채워서 재사용
- 목록의 각 항목: 순서, 이름/주소, 도착 예정시각, 이동수단, 이전 지점부터의 거리/소요시간
- 항목 추가/수정/삭제/순서 변경 시 자동으로 구간별 경로를 재계산해서 지도에 반영
"""
from __future__ import annotations

from typing import Callable, List, Optional

from PySide6.QtCore import QTime, Qt, Signal
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QTimeEdit,
    QVBoxLayout,
    QWidget,
)

from .models import Stop
from .providers.base import GeocodeResult, MapProvider, ProviderError
from .styles import MODE_COLORS

_MODE_LABELS = {
    "driving": "자동차",
    "walking": "도보",
    "transit": "대중교통",
}


def format_duration(seconds: Optional[float]) -> str:
    if seconds is None:
        return "-"
    minutes = int(round(seconds / 60))
    if minutes < 60:
        return f"{minutes}분"
    h, m = divmod(minutes, 60)
    return f"{h}시간 {m}분" if m else f"{h}시간"


def format_distance(meters: Optional[float]) -> str:
    if meters is None:
        return "-"
    if meters < 1000:
        return f"{int(meters)}m"
    return f"{meters / 1000:.1f}km"


class StopDialog(QDialog):
    """주소/장소를 검색해서 일정을 추가하거나, 기존 일정을 수정하는 다이얼로그.

    existing_stop이 주어지면 '수정' 모드로 동작하며, 사용자가 다시 검색하지 않으면
    기존 위치(이름/주소/좌표)를 그대로 유지하고 도착시각/이동수단/메모만 바꿀 수 있다.
    """

    def __init__(
        self,
        provider: MapProvider,
        existing_stop: Optional[Stop] = None,
        parent=None,
    ):
        super().__init__(parent)
        self.provider = provider
        self.existing_stop = existing_stop
        self.selected_result: Optional[GeocodeResult] = None

        is_edit = existing_stop is not None
        self.setWindowTitle("일정 수정" if is_edit else "일정 추가")
        self.setMinimumWidth(440)

        layout = QVBoxLayout(self)

        search_row = QHBoxLayout()
        self.query_edit = QLineEdit()
        self.query_edit.setPlaceholderText("주소 또는 장소명을 입력하세요 (예: 서울역, 강남대로 123)")
        if is_edit:
            self.query_edit.setText(existing_stop.address)
        self.query_edit.returnPressed.connect(self._on_search)
        search_btn = QPushButton("검색")
        search_btn.clicked.connect(self._on_search)
        search_row.addWidget(self.query_edit)
        search_row.addWidget(search_btn)
        layout.addLayout(search_row)

        if is_edit:
            hint = QLabel("주소를 바꾸지 않고 저장하면 기존 위치가 그대로 유지됩니다.")
            hint.setStyleSheet("color: #888; font-size: 11px;")
            layout.addWidget(hint)

        self.result_list = QListWidget()
        self.result_list.setMaximumHeight(160)
        self.result_list.itemDoubleClicked.connect(lambda _: None)
        self.result_list.setStyleSheet("""
            QListWidget::item:selected {
                background-color: #0078D7;  /* 선택되었을 때의 배경색 (진한 파란색) */
                color: white;               /* 선택되었을 때의 글자색 (흰색) */
            }
            QListWidget::item:hover {
                background-color: #0078D7;  /* 마우스를 올렸을 때의 배경색 (연한 회색) */
                color: black;               /* 마우스를 올렸을 때의 글자색 (검은색) */
            }
        """)
        layout.addWidget(self.result_list)

        options_row = QHBoxLayout()
        options_row.addWidget(QLabel("도착 예정시각"))
        self.time_edit = QTimeEdit()
        self.time_edit.setDisplayFormat("HH:mm")
        if is_edit and existing_stop.arrival_time:
            h, m = existing_stop.arrival_time.split(":")
            self.time_edit.setTime(QTime(int(h), int(m)))
        options_row.addWidget(self.time_edit)

        options_row.addWidget(QLabel("이동수단"))
        self.mode_combo = QComboBox()
        for key, label in _MODE_LABELS.items():
            self.mode_combo.addItem(label, userData=key)
        if is_edit:
            idx = self.mode_combo.findData(existing_stop.travel_mode)
            if idx >= 0:
                self.mode_combo.setCurrentIndex(idx)
        options_row.addWidget(self.mode_combo)
        layout.addLayout(options_row)

        note_row = QHBoxLayout()
        note_row.addWidget(QLabel("메모"))
        self.note_edit = QLineEdit()
        self.note_edit.setPlaceholderText("선택사항 (예: 예약 필요, 준비물 등)")
        if is_edit:
            self.note_edit.setText(existing_stop.note)
        note_row.addWidget(self.note_edit)
        layout.addLayout(note_row)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self._accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self._results: List[GeocodeResult] = []

    def _on_search(self) -> None:
        query = self.query_edit.text().strip()
        if not query:
            return
        self.result_list.clear()
        try:
            self._results = self.provider.geocode(query)
        except ProviderError as e:
            QMessageBox.warning(self, "검색 실패", str(e))
            return

        if not self._results:
            QMessageBox.information(self, "검색 결과 없음", "일치하는 장소를 찾지 못했습니다.")
            return

        for r in self._results:
            item = QListWidgetItem(f"{r.name}\n{r.address}")
            self.result_list.addItem(item)
        self.result_list.setCurrentRow(0)

    def _accept(self) -> None:
        row = self.result_list.currentRow()
        if 0 <= row < len(self._results):
            self.selected_result = self._results[row]
        elif self.existing_stop is None:
            QMessageBox.information(self, "장소 검색 필요", "장소를 검색하고 목록에서 선택하세요.")
            return
        # existing_stop이 있고 새로 검색/선택하지 않았다면 기존 위치를 그대로 사용
        self.accept()

    def get_stop(self) -> Optional[Stop]:
        arrival_time = self.time_edit.time().toString("HH:mm")
        travel_mode = self.mode_combo.currentData()
        note = self.note_edit.text().strip()

        if self.selected_result:
            r = self.selected_result
            name, address, lat, lng = r.name, r.address, r.lat, r.lng
        elif self.existing_stop:
            name = self.existing_stop.name
            address = self.existing_stop.address
            lat = self.existing_stop.lat
            lng = self.existing_stop.lng
        else:
            return None

        stop = Stop(
            name=name,
            address=address,
            lat=lat,
            lng=lng,
            arrival_time=arrival_time,
            travel_mode=travel_mode,
            note=note,
        )
        if self.existing_stop:
            stop.id = self.existing_stop.id  # 기존 항목을 그대로 치환하기 위해 id 유지
        return stop


class StopRowWidget(QFrame):
    """리스트의 한 행(1개 Stop)을 카드 형태로 표시하는 커스텀 위젯."""

    remove_clicked = Signal()
    edit_clicked = Signal()

    def __init__(self, index: int, stop: Stop, parent=None):
        super().__init__(parent)
        self.setObjectName("stopCard")

        outer = QHBoxLayout(self)
        outer.setContentsMargins(12, 10, 12, 10)
        outer.setSpacing(10)

        order_label = QLabel(str(index + 1))
        order_label.setObjectName("orderBadge")
        order_label.setFixedSize(26, 26)
        outer.addWidget(order_label)

        text_col = QVBoxLayout()
        text_col.setSpacing(3)

        title_row = QHBoxLayout()
        title_row.setSpacing(8)
        name_label = QLabel(stop.name)
        name_label.setObjectName("stopTitle")
        title_row.addWidget(name_label)

        mode_badge = QLabel(_MODE_LABELS.get(stop.travel_mode, stop.travel_mode))
        mode_badge.setObjectName("modeBadge")
        color = MODE_COLORS.get(stop.travel_mode, "#666")
        mode_badge.setStyleSheet(f"background-color: {color}; border-radius: 8px; padding: 2px 8px; "
                                  f"font-size: 11px; font-weight: 600; color: white;")
        title_row.addWidget(mode_badge)
        title_row.addStretch(1)
        text_col.addLayout(title_row)

        subtitle_parts = [stop.address]
        if stop.arrival_time:
            subtitle_parts.append(f"도착 {stop.arrival_time}")
        if index > 0:
            subtitle_parts.append(
                f"이전 지점에서 {format_distance(stop.distance_m)} · {format_duration(stop.duration_s)}"
            )
        if stop.note:
            subtitle_parts.append(f"메모: {stop.note}")
        sub_label = QLabel(" · ".join(subtitle_parts))
        sub_label.setObjectName("stopSubtitle")
        sub_label.setWordWrap(True)
        text_col.addWidget(sub_label)

        outer.addLayout(text_col, stretch=1)

        btn_col = QVBoxLayout()
        btn_col.setSpacing(4)
        edit_btn = QPushButton("수정")
        edit_btn.setObjectName("editButton")
        edit_btn.setFixedWidth(56)
        edit_btn.clicked.connect(self.edit_clicked.emit)
        btn_col.addWidget(edit_btn)

        remove_btn = QPushButton("삭제")
        remove_btn.setObjectName("dangerButton")
        remove_btn.setFixedWidth(56)
        remove_btn.clicked.connect(self.remove_clicked.emit)
        btn_col.addWidget(remove_btn)
        outer.addLayout(btn_col)


class ItineraryWidget(QWidget):
    """일정 목록 + 추가/수정/삭제/순서 변경 + 구간 경로 재계산."""

    #: 일정이 바뀔 때마다 (추가/수정/삭제/순서변경/경로재계산 후) 전체 stops 리스트와 함께 발생
    stops_changed = Signal(list)

    def __init__(self, provider_getter: Callable[[], MapProvider], parent=None):
        super().__init__(parent)
        self._provider_getter = provider_getter
        self.stops: List[Stop] = []

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        header = QHBoxLayout()
        title = QLabel("여행 일정")
        title.setObjectName("itineraryHeader")
        header.addWidget(title)
        header.addStretch(1)
        add_btn = QPushButton("+ 일정 추가")
        add_btn.setObjectName("primaryButton")
        add_btn.clicked.connect(self.open_add_dialog)
        header.addWidget(add_btn)
        layout.addLayout(header)

        self.list_widget = QListWidget()
        self.list_widget.setDragDropMode(QAbstractItemView.InternalMove)
        self.list_widget.setSpacing(6)
        self.list_widget.model().rowsMoved.connect(self._on_rows_moved)
        layout.addWidget(self.list_widget)

    # ---- 공개 API ----

    def open_add_dialog(self) -> None:
        provider = self._provider_getter()
        dialog = StopDialog(provider, existing_stop=None, parent=self)
        if dialog.exec() == QDialog.Accepted:
            stop = dialog.get_stop()
            if stop:
                self.stops.append(stop)
                self._recompute_and_refresh()

    def open_edit_dialog(self, stop_id: str) -> None:
        existing = next((s for s in self.stops if s.id == stop_id), None)
        if existing is None:
            return
        provider = self._provider_getter()
        dialog = StopDialog(provider, existing_stop=existing, parent=self)
        if dialog.exec() == QDialog.Accepted:
            updated = dialog.get_stop()
            if updated:
                self.stops = [updated if s.id == stop_id else s for s in self.stops]
                self._recompute_and_refresh()

    def remove_stop(self, stop_id: str) -> None:
        self.stops = [s for s in self.stops if s.id != stop_id]
        self._recompute_and_refresh()

    # ---- 내부 구현 ----

    def _on_rows_moved(self, *args) -> None:
        new_order: List[Stop] = []
        by_id = {s.id: s for s in self.stops}
        for i in range(self.list_widget.count()):
            item = self.list_widget.item(i)
            stop_id = item.data(Qt.UserRole)
            if stop_id in by_id:
                new_order.append(by_id[stop_id])
        if len(new_order) == len(self.stops):
            self.stops = new_order
            self._recompute_and_refresh()

    def _recompute_and_refresh(self) -> None:
        self._recompute_routes()
        self._rebuild_list()
        self.stops_changed.emit(self.stops)

    def _recompute_routes(self) -> None:
        provider = self._provider_getter()
        for i, stop in enumerate(self.stops):
            if i == 0:
                stop.distance_m = None
                stop.duration_s = None
                stop.path = []
                continue
            prev = self.stops[i - 1]
            try:
                result = provider.route(
                    (prev.lat, prev.lng), (stop.lat, stop.lng), mode=stop.travel_mode
                )
                stop.distance_m = result.distance_m
                stop.duration_s = result.duration_s
                stop.path = result.path
            except ProviderError as e:
                stop.distance_m = None
                stop.duration_s = None
                stop.path = [(prev.lat, prev.lng), (stop.lat, stop.lng)]
                QMessageBox.warning(
                    self, "경로 계산 실패", f"'{prev.name}' -> '{stop.name}' 구간: {e}"
                )

    def _rebuild_list(self) -> None:
        self.list_widget.blockSignals(True)
        self.list_widget.clear()
        for i, stop in enumerate(self.stops):
            item = QListWidgetItem()
            item.setData(Qt.UserRole, stop.id)
            row_widget = StopRowWidget(i, stop)
            row_widget.remove_clicked.connect(
                lambda checked=False, sid=stop.id: self.remove_stop(sid)
            )
            row_widget.edit_clicked.connect(
                lambda checked=False, sid=stop.id: self.open_edit_dialog(sid)
            )
            item.setSizeHint(row_widget.sizeHint())
            self.list_widget.addItem(item)
            self.list_widget.setItemWidget(item, row_widget)
        self.list_widget.blockSignals(False)

    def set_provider_changed(self) -> None:
        """설정에서 provider가 바뀌었을 때 호출: 기존 좌표는 유지한 채 경로만 재계산."""
        self._recompute_and_refresh()
