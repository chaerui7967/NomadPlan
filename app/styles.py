"""앱 전역 QSS 스타일시트.

일정 카드, 버튼, 입력창 등을 좀 더 보기 좋게 꾸미기 위한 스타일 모음.
main.py에서 QApplication.setStyleSheet(APP_STYLE)로 적용한다.
"""

PRIMARY = "#2d6cdf"
PRIMARY_DARK = "#1f56c2"
DANGER = "#e5484d"
DANGER_DARK = "#c93a3f"
BG = "#f5f6f8"
CARD_BG = "#ffffff"
BORDER = "#e3e5e9"
TEXT_MUTED = "#6b7280"

APP_STYLE = f"""
QMainWindow, QWidget {{
    background-color: {BG};
    font-family: -apple-system, "Segoe UI", "Malgun Gothic", sans-serif;
    font-size: 13px;
    color: #1f2430;
}}

QListWidget {{
    background-color: transparent;
    border: none;
}}

QListWidget::item {{
    background: transparent;
    border: none;
    margin: 4px 2px;
}}

QListWidget::item:selected {{
    background: transparent;
}}

QFrame#stopCard {{
    background-color: {CARD_BG};
    border: 1px solid {BORDER};
    border-radius: 10px;
}}

QFrame#stopCard:hover {{
    border: 1px solid {PRIMARY};
}}

QLabel#orderBadge {{
    background-color: {PRIMARY};
    color: white;
    border-radius: 13px;
    font-weight: 700;
    qproperty-alignment: AlignCenter;
}}

QLabel#stopTitle {{
    font-size: 14px;
    font-weight: 700;
    color: #1f2430;
}}

QLabel#stopSubtitle {{
    color: {TEXT_MUTED};
    font-size: 11px;
}}

QLabel#modeBadge {{
    border-radius: 8px;
    padding: 2px 8px;
    font-size: 11px;
    font-weight: 600;
    color: white;
}}

QLabel#summaryLabel {{
    background-color: #eef2fb;
    border: 1px solid #dbe4f7;
    border-radius: 8px;
    padding: 8px 12px;
    color: #33456b;
    font-weight: 600;
    margin: 6px;
}}

QLabel#itineraryHeader {{
    font-size: 15px;
    font-weight: 700;
    padding: 4px 2px;
}}

QPushButton {{
    border-radius: 8px;
    padding: 6px 14px;
    background-color: #eef0f4;
    border: 1px solid {BORDER};
}}

QPushButton:hover {{
    background-color: #e4e7ec;
}}

QPushButton#primaryButton {{
    background-color: {PRIMARY};
    color: white;
    border: none;
    font-weight: 700;
    padding: 8px 16px;
}}

QPushButton#primaryButton:hover {{
    background-color: {PRIMARY_DARK};
}}

QPushButton#dangerButton {{
    background-color: transparent;
    color: {DANGER};
    border: 1px solid {DANGER};
    padding: 4px 10px;
}}

QPushButton#dangerButton:hover {{
    background-color: {DANGER};
    color: white;
}}

QPushButton#editButton {{
    background-color: transparent;
    color: {PRIMARY};
    border: 1px solid {PRIMARY};
    padding: 4px 10px;
}}

QPushButton#editButton:hover {{
    background-color: {PRIMARY};
    color: white;
}}

QLineEdit, QComboBox, QTimeEdit {{
    background-color: white;
    border: 1px solid {BORDER};
    border-radius: 8px;
    padding: 6px 10px;
    selection-background-color: {PRIMARY};
}}

QTimeEdit {{
    padding-right: 22px;
}}

QAbstractSpinBox::up-button, QTimeEdit::up-button {{
    subcontrol-origin: border;
    subcontrol-position: top right;
    width: 18px;
    border-left: 1px solid {BORDER};
    border-top-right-radius: 8px;
    background-color: #f5f6f8;
}}

QAbstractSpinBox::down-button, QTimeEdit::down-button {{
    subcontrol-origin: border;
    subcontrol-position: bottom right;
    width: 18px;
    border-left: 1px solid {BORDER};
    border-bottom-right-radius: 8px;
    background-color: #f5f6f8;
}}

QAbstractSpinBox::up-button:hover, QAbstractSpinBox::down-button:hover,
QTimeEdit::up-button:hover, QTimeEdit::down-button:hover {{
    background-color: #e4e7ec;
}}

QAbstractSpinBox::up-arrow, QTimeEdit::up-arrow {{
    image: none;
    width: 0;
    height: 0;
    border-left: 4px solid transparent;
    border-right: 4px solid transparent;
    border-bottom: 5px solid #555;
}}

QAbstractSpinBox::down-arrow, QTimeEdit::down-arrow {{
    image: none;
    width: 0;
    height: 0;
    border-left: 4px solid transparent;
    border-right: 4px solid transparent;
    border-top: 5px solid #555;
}}

QLineEdit:focus, QComboBox:focus, QTimeEdit:focus {{
    border: 1px solid {PRIMARY};
}}

QDialog {{
    background-color: {BG};
}}

QMenuBar {{
    background-color: {CARD_BG};
    border-bottom: 1px solid {BORDER};
}}

QSplitter::handle {{
    background-color: {BORDER};
}}
"""

MODE_COLORS = {
    "driving": "#2d6cdf",
    "walking": "#16a34a",
    "transit": "#d97706",
}
