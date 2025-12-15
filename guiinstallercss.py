#!/usr/bin/env python3
"""
QSS style definitions for the ED Colonization Assistant GUI installer.

This module isolates the dark and light theme QSS strings so that the main
`guiinstaller.py` script can remain more focused on application logic.

Usage (from guiinstaller.py):

    from guiinstallercss import DARK_QSS, LIGHT_QSS
"""

DARK_QSS = """
QMainWindow {
    background-color: #151020;
    color: #f5f5f7;
}

QToolBar {
    background-color: #1e1630;
    border-bottom: 1px solid #2b2040;
}

QStatusBar {
    background-color: #1e1630;
    color: #f5f5f7;
    border-top: 1px solid #2b2040;
}

QLabel#titleLabel {
    color: #f5f5f7;
    font-size: 22px;
    font-weight: 600;
    padding-bottom: 4px;
}

QLabel {
    color: #d0cfe8;
}

QTextEdit {
    background-color: #1c142a;
    color: #f5f5f7;
    border: 1px solid #3a275e;
    border-radius: 8px;
}

/* Primary action buttons as rounded pills */
QPushButton#installButton,
QPushButton#repairButton,
QPushButton#uninstallButton {
    min-height: 40px;
    padding: 8px 18px;
    border-radius: 20px;
    font-weight: 600;
    border: none;
}

/* Install: strong purple -> orange gradient */
QPushButton#installButton {
    color: #f5f5f7;
    background-color: qlineargradient(spread:pad, x1:0, y1:0, x2:1, y2:1,
                                      stop:0 #8e6bff, stop:1 #ff9f1c);
}

QPushButton#installButton:hover {
    background-color: qlineargradient(spread:pad, x1:0, y1:0, x2:1, y2:1,
                                      stop:0 #a389ff, stop:1 #ffb347);
}

QPushButton#installButton:pressed {
    background-color: qlineargradient(spread:pad, x1:0, y1:1, x2:1, y2:0,
                                      stop:0 #6c5ce7, stop:1 #ff851b);
}

/* Repair: slightly softer gradient */
QPushButton#repairButton {
    color: #f5f5f7;
    background-color: qlineargradient(spread:pad, x1:0, y1:0, x2:1, y2:1,
                                      stop:0 #5a3fd8, stop:1 #f6b26b);
}

QPushButton#repairButton:hover {
    background-color: qlineargradient(spread:pad, x1:0, y1:0, x2:1, y2:1,
                                      stop:0 #7461e3, stop:1 #ffd28c);
}

QPushButton#repairButton:pressed {
    background-color: qlineargradient(spread:pad, x1:0, y1:1, x2:1, y2:0,
                                      stop:0 #4b32c2, stop:1 #e69138);
}

/* Uninstall: outlined orange pill on dark background */
QPushButton#uninstallButton {
    background-color: transparent;
    color: #ffb347;
    border: 1px solid #ff9f1c;
}

QPushButton#uninstallButton:hover {
    background-color: rgba(255, 159, 28, 0.08);
}

QPushButton#uninstallButton:pressed {
    background-color: rgba(255, 159, 28, 0.18);
}

/* Theme toggle slider (header) */
QSlider#themeSwitch {
    min-width: 60px;
}

/* Groove: pill-shaped track */
QSlider#themeSwitch::groove:horizontal {
    border: 1px solid #6a4fbf;
    border-radius: 11px;
    height: 22px;
    background: #2a203f;
    margin: 0px;
}

/* Handle: circular thumb that slides left/right */
QSlider#themeSwitch::handle:horizontal {
    background: #ffffff;
    border-radius: 9px;
    width: 20px;
    margin: 1px; /* keeps handle fully inside 22px-high groove */
}
"""

LIGHT_QSS = """
QMainWindow {
    background-color: #f4f7fb;
    color: #1f2933;
}

QToolBar {
    background-color: #e3edf9;
    border-bottom: 1px solid #c7d7f0;
}

QStatusBar {
    background-color: #e3edf9;
    color: #1f2933;
    border-top: 1px solid #c7d7f0;
}

QLabel#titleLabel {
    color: #1f2933;
    font-size: 22px;
    font-weight: 600;
    padding-bottom: 4px;
}

QLabel {
    color: #334e68;
}

QTextEdit {
    background-color: #ffffff;
    color: #1f2933;
    border: 1px solid #c7d7f0;
    border-radius: 8px;
}

/* Primary action buttons as rounded pills */
QPushButton#installButton,
QPushButton#repairButton,
QPushButton#uninstallButton {
    min-height: 40px;
    padding: 8px 18px;
    border-radius: 20px;
    font-weight: 600;
    border: none;
}

/* Install: light blue -> light orange gradient */
QPushButton#installButton {
    color: #ffffff;
    background-color: qlineargradient(spread:pad, x1:0, y1:0, x2:1, y2:1,
                                      stop:0 #4f8df5, stop:1 #ffb347);
}

QPushButton#installButton:hover {
    background-color: qlineargradient(spread:pad, x1:0, y1:0, x2:1, y2:1,
                                      stop:0 #6da1f7, stop:1 #ffd08a);
}

QPushButton#installButton:pressed {
    background-color: qlineargradient(spread:pad, x1:0, y1:1, x2:1, y2:0,
                                      stop:0 #3478f0, stop:1 #ff9f1c);
}

/* Repair: softer blue/orange */
QPushButton#repairButton {
    color: #ffffff;
    background-color: qlineargradient(spread:pad, x1:0, y1:0, x2:1, y2:1,
                                      stop:0 #3b7dd8, stop:1 #f9c784);
}

QPushButton#repairButton:hover {
    background-color: qlineargradient(spread:pad, x1:0, y1:0, x2:1, y2:1,
                                      stop:0 #5a93e3, stop:1 #ffe0a8);
}

QPushButton#repairButton:pressed {
    background-color: qlineargradient(spread:pad, x1:0, y1:1, x2:1, y2:0,
                                      stop:0 #2f64b3, stop:1 #f2a654);
}

/* Uninstall: subtle outlined orange pill */
QPushButton#uninstallButton {
    background-color: transparent;
    color: #e67e22;
    border: 1px solid #f5a623;
}

QPushButton#uninstallButton:hover {
    background-color: rgba(245, 166, 35, 0.10);
}

QPushButton#uninstallButton:pressed {
    background-color: rgba(245, 166, 35, 0.20);
}

/* Theme toggle slider (header) */
QSlider#themeSwitch {
    min-width: 60px;
}

/* Groove: pill-shaped track */
QSlider#themeSwitch::groove:horizontal {
    border: 1px solid #90b4ff;
    border-radius: 11px;
    height: 22px;
    background: #d0e2ff;
    margin: 0px;
}

/* Handle: circular thumb that slides left/right */
QSlider#themeSwitch::handle:horizontal {
    background: #4f8df5;
    border-radius: 9px;
    width: 20px;
    margin: 1px; /* keeps handle fully inside 22px-high groove */
}
"""
