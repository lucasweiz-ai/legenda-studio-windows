from __future__ import annotations

from PySide6.QtCore import QSettings


THEME_SYSTEM = "system"
THEME_LIGHT = "light"
THEME_DARK = "dark"


def windows_uses_dark_theme() -> bool:
    settings = QSettings(
        r"HKEY_CURRENT_USER\Software\Microsoft\Windows\CurrentVersion\Themes\Personalize",
        QSettings.Format.NativeFormat,
    )
    return int(settings.value("AppsUseLightTheme", 1)) == 0


def resolved_theme(preference: str) -> str:
    if preference == THEME_SYSTEM:
        return THEME_DARK if windows_uses_dark_theme() else THEME_LIGHT
    return THEME_DARK if preference == THEME_DARK else THEME_LIGHT


def application_stylesheet(theme: str) -> str:
    dark = theme == THEME_DARK
    background = "#151515" if dark else "#F3F4F6"
    surface = "#202020" if dark else "#FFFFFF"
    raised = "#292929" if dark else "#F8F9FA"
    ink = "#F5F5F5" if dark else "#111111"
    muted = "#C3C3C3" if dark else "#4B5563"
    border = "#444444" if dark else "#D1D5DB"
    hover = "#343434" if dark else "#ECEFF3"
    disabled = "#747474" if dark else "#8A929E"
    return f"""
        QMainWindow, QDialog, QWidget {{
            background: {background}; color: {ink}; font-family: "Segoe UI"; font-size: 13px;
        }}
        QFrame#surface, QTableWidget, QListWidget {{
            background: {surface}; border: 1px solid {border};
        }}
        QLabel[muted="true"] {{ color: {muted}; }}
        QLabel[heading="true"] {{ font-size: 16px; font-weight: 700; }}
        QPushButton {{
            min-height: 34px; background: {surface}; color: {ink};
            border: 1px solid {border}; padding: 0 13px;
        }}
        QPushButton:hover {{ background: {hover}; border-color: #F7C600; }}
        QPushButton:focus, QComboBox:focus, QListWidget:focus, QTableWidget:focus {{
            border: 2px solid #F7C600;
        }}
        QPushButton:pressed {{ background: #F7C600; color: #111111; }}
        QPushButton:disabled {{ color: {disabled}; background: {raised}; border-color: {border}; }}
        QPushButton[primary="true"] {{
            background: #F7C600; color: #111111; border: 1px solid #D9AE00; font-weight: 700;
        }}
        QPushButton[primary="true"]:hover {{ background: #E4B700; }}
        QPushButton[danger="true"] {{ color: {ink}; border-color: #DC3B3B; }}
        QComboBox {{
            min-height: 34px; background: {surface}; color: {ink};
            border: 1px solid {border}; padding: 0 10px;
        }}
        QComboBox QAbstractItemView {{ background: {surface}; color: {ink}; selection-background-color: #F7C600; selection-color: #111111; }}
        QTableWidget {{ gridline-color: {border}; selection-background-color: #F7C600; selection-color: #111111; }}
        QHeaderView::section {{
            background: {raised}; color: {ink}; padding: 9px; border: 0; border-bottom: 1px solid {border};
        }}
        QSlider::groove:horizontal {{ height: 5px; background: {border}; }}
        QSlider::handle:horizontal {{ width: 14px; margin: -6px 0; background: #F7C600; border: 1px solid #111111; }}
        QProgressBar {{
            min-height: 16px; background: {raised}; color: {ink}; border: 1px solid {border}; text-align: center;
        }}
        QProgressBar::chunk {{ background: #F7C600; }}
        QToolTip {{ background: {surface}; color: {ink}; border: 1px solid #F7C600; padding: 5px; }}
        QStatusBar {{ background: {surface}; border-top: 1px solid {border}; }}
    """

