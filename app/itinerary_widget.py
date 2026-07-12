"""일정(방문 순서) 목록을 보여주고 관리하는 위젯.

- 상단 '+ 일정 추가' 버튼 -> 주소/장소 검색 다이얼로그
- 각 카드의 '수정' 버튼 -> 같은 다이얼로그를 기존 값으로 채워서 재사용
- 각 카드 클릭 -> 해당 위치로 지도 이동/확대
- 각 카드의 ▲▼ 버튼으로 순서 변경 (QListWidget의 drag 방식 대신 사용:
  커스텀 위젯을 QListWidget에 넣으면 스크롤바 등장/소멸 시 sizeHint가
  어긋나 카드가 잘리는 고질적인 문제가 있어, QScrollArea + QVBoxLayout으로
  구성해 각 카드가 항상 자기 내용에 맞게 높이를 잡도록 함)
- 항목 추가/수정/삭제/순서 변경 시 자동으로 구간별 경로를 재계산해서 지도에 반영
"""
from __future__ import annotations

from typing import Callable, List, Optional

from PySide6.QtCore import QTime, Qt, Signal
from PySide6.QtWidgets import (
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
    QScrollArea,
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
                background-color: #0078D7;
                color: white;
            }
            QListWidget::item:hover {
                background-color: #cfe4fb;
                color: black;
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
            stop.id = self.existing_stop.id
        return stop


class StopRowWidget(QFrame):
    """리스트의 한 항목(1개 Stop)을 카드 형태로 표시하는 커스텀 위젯.

    QScrollArea 안의 QVBoxLayout에 직접 들어가기 때문에, 텍스트가 길어져도
    (메모 추가 등) 항상 필요한 높이만큼 스스로 늘어나며 잘리지 않는다.
    """

    remove_clicked = Signal()
    edit_clicked = Signal()
    card_clicked = Signal()
    move_up_clicked = Signal()
    move_down_clicked = Signal()

    def __init__(self, index: int, stop: Stop, is_first: bool, is_last: bool, parent=None):
        super().__init__(parent)
        self.setObjectName("stopCard")
        self.setCursor(Qt.PointingHandCursor)

        outer = QHBoxLayout(self)
        outer.setContentsMargins(12, 10, 12, 10)
        outer.setSpacing(10)

        # 순서 배지 + 위/아래 이동 버튼
        order_col = QVBoxLayout()
        order_col.setSpacing(2)
        order_label = QLabel(str(index + 1))
        order_label.setObjectName("orderBadge")
        order_label.setFixedSize(26, 26)
        order_col.addWidget(order_label)

        move_row = QHBoxLayout()
        move_row.setSpacing(2)
        up_btn = QPushButton("▲")
        up_btn.setObjectName("moveButton")
        up_btn.setFixedSize(22, 20)
        up_btn.setEnabled(not is_first)
        up_btn.clicked.connect(self.move_up_clicked.emit)
        down_btn = QPushButton("▼")
        down_btn.setObjectName("moveButton")
        down_btn.setFixedSize(22, 20)
        down_btn.setEnabled(not is_last)
        down_btn.clicked.connect(self.move_down_clicked.emit)
        move_row.addWidget(up_btn)
        move_row.addWidget(down_btn)
        order_col.addLayout(move_row)
        outer.addLayout(order_col)

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
        mode_badge.setStyleSheet(
            f"background-color: {color}; border-radius: 8px; padding: 2px 8px; "
            f"font-size: 11px; font-weight: 600; color: white;"
        )
        title_row.addWidget(mode_badge)
        title_row.addStretch(1)
        text_col.addLayout(title_row)

        subtitle_lines = [stop.address]
        line2 = []
        if stop.arrival_time:
            line2.append(f"도착 {stop.arrival_time}")
        if index > 0:
            line2.append(
                f"이전 지점에서 {format_distance(stop.distance_m)} · {format_duration(stop.duration_s)}"
            )
        if line2:
            subtitle_lines.append(" · ".join(line2))
        if stop.note:
            subtitle_lines.append(f"메모: {stop.note}")

        sub_label = QLabel("\n".join(subtitle_lines))
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

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.card_clicked.emit()
        super().mousePressEvent(event)


class ItineraryWidget(QWidget):
    """일정 목록 + 추가/수정/삭제/순서 변경 + 구간 경로 재계산."""

    stops_changed = Signal(list)
    stop_selected = Signal(object)

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

        reset_btn = QPushButton("초기화")
        reset_btn.setObjectName("dangerButton")
        reset_btn.clicked.connect(self.clear_all_stops)
        header.addWidget(reset_btn)

        add_btn = QPushButton("+ 일정 추가")
        add_btn.setObjectName("primaryButton")
        add_btn.clicked.connect(self.open_add_dialog)
        header.addWidget(add_btn)
        layout.addLayout(header)

        # QListWidget 대신 QScrollArea + QVBoxLayout 사용:
        # 커스텀 카드 위젯을 QListWidget에 넣으면 스크롤바 등장/소멸 시
        # sizeHint 동기화가 어긋나 카드가 잘리는 문제가 있어, 각 카드가
        # 스스로 필요한 높이를 갖도록 이 구조로 변경.
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setFrameShape(QFrame.NoFrame)

        self.cards_container = QWidget()
        self.cards_layout = QVBoxLayout(self.cards_container)
        self.cards_layout.setContentsMargins(0, 0, 4, 0)
        self.cards_layout.setSpacing(6)
        self.cards_layout.addStretch(1)  # 항상 마지막에 유지되는 spacer

        self.scroll_area.setWidget(self.cards_container)
        layout.addWidget(self.scroll_area)

    # ---- 공개 API ----

    def clear_all_stops(self) -> None:
        if not self.stops:
            return
        reply = QMessageBox.question(
            self,
            "일정 초기화",
            "전체 일정을 삭제할까요? 되돌릴 수 없습니다.",
            QMessageBox.Yes | QMessageBox.Cancel,
        )
        if reply == QMessageBox.Yes:
            self.stops = []
            self._recompute_and_refresh()

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

    def move_stop(self, stop_id: str, delta: int) -> None:
        idx = next((i for i, s in enumerate(self.stops) if s.id == stop_id), None)
        if idx is None:
            return
        new_idx = idx + delta
        if 0 <= new_idx < len(self.stops):
            self.stops[idx], self.stops[new_idx] = self.stops[new_idx], self.stops[idx]
            self._recompute_and_refresh()

    # ---- 내부 구현 ----

    def _recompute_and_refresh(self) -> None:
        self._recompute_routes()
        self._rebuild_cards()
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

    def _rebuild_cards(self) -> None:
        # 마지막 stretch item(항상 count-1 위치)을 제외하고 기존 카드 위젯 제거
        while self.cards_layout.count() > 1:
            item = self.cards_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()

        n = len(self.stops)
        for i, stop in enumerate(self.stops):
            row_widget = StopRowWidget(i, stop, is_first=(i == 0), is_last=(i == n - 1))
            row_widget.remove_clicked.connect(
                lambda checked=False, sid=stop.id: self.remove_stop(sid)
            )
            row_widget.edit_clicked.connect(
                lambda checked=False, sid=stop.id: self.open_edit_dialog(sid)
            )
            row_widget.card_clicked.connect(
                lambda checked=False, s=stop: self.stop_selected.emit(s)
            )
            row_widget.move_up_clicked.connect(
                lambda checked=False, sid=stop.id: self.move_stop(sid, -1)
            )
            row_widget.move_down_clicked.connect(
                lambda checked=False, sid=stop.id: self.move_stop(sid, +1)
            )
            # addStretch가 마지막(count-1)에 있으므로 그 앞에 순서대로 삽입
            self.cards_layout.insertWidget(self.cards_layout.count() - 1, row_widget)

    def set_provider_changed(self) -> None:
        """설정에서 provider가 바뀌었을 때 호출: 기존 좌표는 유지한 채 경로만 재계산."""
        self._recompute_and_refresh()