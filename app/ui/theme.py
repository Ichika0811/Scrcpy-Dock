"""Global Qt stylesheet for Scrcpy Dock."""

from __future__ import annotations

ACCENT = "#5eead4"
ACCENT_DARK = "#2dd4bf"
BLUE = "#78a9ff"
TEXT = "#eaf1fa"
MUTED = "#7d8da3"
FAINT = "#526176"
DANGER = "#fb7185"
WARNING = "#fbbf24"

APP_QSS = r"""
* {
    font-family: "Segoe UI Variable Text", "Segoe UI", "Microsoft YaHei UI", "Microsoft YaHei", sans-serif;
    font-size: 12px;
    color: #dbe5f1;
    outline: none;
}
QMainWindow, QWidget#Root {
    background: #070b12;
}
QWidget#TitleStrip {
    background: #080d15;
}
QWidget#Workspace {
    background: qradialgradient(cx:0.2, cy:-0.1, radius:1.2, fx:0.2, fy:-0.1,
        stop:0 rgba(45, 212, 191, 26), stop:0.36 rgba(7, 11, 18, 0), stop:1 #070b12);
}
QWidget#RailLeft {
    background: #0a1019;
    border-right: 1px solid rgba(148, 163, 184, 24);
}
QWidget#RailRight {
    background: #0b121c;
    border-left: 1px solid rgba(148, 163, 184, 24);
}
QWidget#RailHeader {
    background: transparent;
    border-bottom: 1px solid rgba(148, 163, 184, 18);
}
QWidget#RailCaption {
    background: rgba(3, 7, 13, 28);
    border-bottom: 1px solid rgba(148, 163, 184, 16);
}
QWidget#RailFooter {
    background: rgba(2, 6, 12, 30);
    border-top: 1px solid rgba(148, 163, 184, 18);
}
QScrollArea#RailScroll, QScrollArea#RailScroll > QWidget > QWidget {
    background: transparent;
    border: none;
}
QScrollArea#TerminalTabs, QScrollArea#TerminalTabs > QWidget > QWidget {
    background: transparent;
    border: none;
}

/* ----------------------------------------------------------------- texts */
QLabel[role="eyebrow"] {
    color: #526176;
    font-size: 8px;
    font-weight: 700;
}
QLabel[role="railTitle"] {
    color: #edf4fc;
    font-size: 14px;
    font-weight: 600;
}
QLabel[role="caption"] {
    color: #5b6a7f;
    font-size: 9px;
}
QLabel[role="muted"] {
    color: #7d8da3;
}
QLabel[role="faint"] {
    color: #526176;
    font-size: 10px;
}
QLabel[role="mono"] {
    font-family: "Cascadia Mono", "Cascadia Code", Consolas, monospace;
    font-size: 10px;
}
QLabel[role="section"] {
    color: #526176;
    font-size: 9px;
    font-weight: 700;
}
QLabel[role="sectionGold"] {
    color: #bb9d5d;
    font-size: 9px;
    font-weight: 700;
}
QLabel[role="toolName"] {
    color: #d9e3ef;
    font-size: 12px;
    font-weight: 600;
}
QLabel[role="toolPath"] {
    color: #4d5c70;
    font-family: "Cascadia Mono", "Cascadia Code", Consolas, monospace;
    font-size: 8px;
}
QLabel[role="badge"] {
    color: #9cb2ca;
    font-family: "Cascadia Mono", "Cascadia Code", Consolas, monospace;
    font-size: 9px;
    font-weight: 700;
}
QLabel[role="autoTag"] {
    color: #5eead4;
    border: 1px solid rgba(94, 234, 212, 40);
    border-radius: 3px;
    padding: 0 4px;
    font-size: 7px;
    background: rgba(94, 234, 212, 12);
}
QLabel[role="customTag"] {
    color: #c5ab72;
    border: 1px solid rgba(251, 191, 36, 34);
    border-radius: 3px;
    padding: 0 4px;
    font-size: 7px;
    background: rgba(251, 191, 36, 10);
}
QLabel[role="versionPill"] {
    color: #8bd7c9;
    border: 1px solid rgba(94, 234, 212, 34);
    border-radius: 4px;
    padding: 1px 6px;
    font-family: "Cascadia Mono", "Cascadia Code", Consolas, monospace;
    font-size: 8px;
    background: rgba(94, 234, 212, 10);
}
QLabel[role="countBadge"] {
    color: #728399;
    border: 1px solid rgba(148, 163, 184, 30);
    border-radius: 4px;
    padding: 0 4px;
    font-family: "Cascadia Mono", "Cascadia Code", Consolas, monospace;
    font-size: 8px;
    background: rgba(148, 163, 184, 8);
}
QLabel[role="statusText"] {
    font-size: 9px;
    color: #7d8da3;
}
QLabel[role="statusText"][state="running"] { color: #86dcb8; }
QLabel[role="statusText"][state="connecting"],
QLabel[role="statusText"][state="starting"],
QLabel[role="statusText"][state="stopping"] { color: #d3ad64; }
QLabel[role="statusText"][state="failed"] { color: #e499a4; }

/* ----------------------------------------------------------------- dots */
QLabel#StatusDot {
    min-width: 6px;
    max-width: 6px;
    min-height: 6px;
    max-height: 6px;
    border-radius: 3px;
    background: #49596d;
}
QLabel#StatusDot[state="running"] {
    background: #4ade80;
}
QLabel#StatusDot[state="connecting"],
QLabel#StatusDot[state="starting"],
QLabel#StatusDot[state="stopping"] {
    background: #fbbf24;
}
QLabel#StatusDot[state="failed"] { background: #fb7185; }
QLabel#StatusDot[state="error"] { background: #fb7185; }
QLabel#StatusDot[state="online"] { background: #4ade80; }
QLabel#StatusDot[state="offline"] { background: #fbbf24; }
QLabel#StatusDot[state="idle"] { background: #3f4e62; }

/* --------------------------------------------------------------- buttons */
QPushButton {
    border: none;
    background: transparent;
    padding: 0;
    color: #8c9cb1;
}
QPushButton:hover {
    color: #e8f0f9;
}
QPushButton[kind="icon"] {
    min-width: 29px;
    max-width: 29px;
    min-height: 29px;
    max-height: 29px;
    border: 1px solid rgba(148, 163, 184, 33);
    border-radius: 7px;
    color: #66778d;
    background: rgba(148, 163, 184, 6);
    font-family: "Segoe UI Symbol", "Segoe UI", sans-serif;
    font-size: 14px;
}
QPushButton[kind="icon"]:hover {
    color: #e8f0f9;
    border-color: rgba(148, 163, 184, 60);
    background: rgba(148, 163, 184, 18);
}
QPushButton[kind="add"] {
    min-width: 29px;
    max-width: 29px;
    min-height: 29px;
    max-height: 29px;
    border: 1px solid rgba(94, 234, 212, 42);
    border-radius: 7px;
    color: #5eead4;
    background: rgba(94, 234, 212, 12);
    font-family: "Segoe UI Symbol", "Segoe UI", sans-serif;
    font-size: 18px;
}
QPushButton[kind="add"]:hover {
    color: #c0fff6;
    border-color: rgba(94, 234, 212, 90);
    background: rgba(94, 234, 212, 26);
}
QPushButton[kind="primary"] {
    color: #04302a;
    border: 1px solid rgba(94, 234, 212, 120);
    border-radius: 7px;
    padding: 0 12px;
    min-height: 30px;
    font-size: 10px;
    font-weight: 600;
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #84f4e1, stop:1 #4fe3c9);
}
QPushButton[kind="primary"]:hover {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #9cfaeb, stop:1 #61ead2);
}
QPushButton[kind="ghost"] {
    color: #aab8c9;
    border: 1px solid rgba(148, 163, 184, 33);
    border-radius: 6px;
    padding: 0 10px;
    min-height: 29px;
    font-size: 9px;
    background: rgba(148, 163, 184, 8);
}
QPushButton[kind="ghost"]:hover {
    border-color: rgba(148, 163, 184, 60);
    background: rgba(148, 163, 184, 18);
}
QPushButton[kind="danger"] {
    color: #e8a3ad;
    border: 1px solid rgba(251, 113, 133, 45);
    border-radius: 6px;
    padding: 0 10px;
    min-height: 29px;
    font-size: 9px;
    background: rgba(251, 113, 133, 15);
}
QPushButton[kind="danger"]:hover {
    color: #ffc2ca;
    border-color: rgba(251, 113, 133, 85);
    background: rgba(251, 113, 133, 28);
}
QPushButton[kind="term"] {
    min-height: 27px;
    border: 1px solid rgba(148, 163, 184, 20);
    border-radius: 6px;
    padding: 0;
    color: #7f91a7;
    background: rgba(148, 163, 184, 5);
    font-family: "Segoe UI Symbol", "Segoe UI", sans-serif;
    font-size: 13px;
}
QPushButton[kind="term"]:hover {
    color: #dbe6f2;
    border-color: rgba(148, 163, 184, 45);
    background: rgba(148, 163, 184, 16);
}
QPushButton[kind="termDanger"]:hover {
    color: #ffb3bd;
    border-color: rgba(251, 113, 133, 42);
    background: rgba(251, 113, 133, 18);
}
QPushButton[kind="favorite"] {
    min-width: 22px;
    max-width: 22px;
    min-height: 22px;
    max-height: 22px;
    border-radius: 5px;
    color: #66788e;
    font-family: "Segoe UI Symbol", "Segoe UI", sans-serif;
    font-size: 15px;
}
QPushButton[kind="favorite"]:hover {
    color: #fbbf24;
    background: rgba(251, 191, 36, 14);
}
QPushButton[kind="favorite"][favorite="true"] {
    color: #fbbf24;
}
QPushButton[kind="tabAdd"] {
    min-width: 38px;
    max-width: 38px;
    min-height: 31px;
    max-height: 31px;
    border: 1px solid rgba(148, 163, 184, 30);
    border-radius: 7px;
    color: #7d8da3;
    background: rgba(148, 163, 184, 8);
    font-family: "Segoe UI Symbol", "Segoe UI", sans-serif;
    font-size: 18px;
}
QPushButton[kind="tabAdd"]:hover {
    color: #5eead4;
    border-color: rgba(94, 234, 212, 50);
    background: rgba(94, 234, 212, 12);
}
QPushButton[kind="link"] {
    color: #65778c;
    font-size: 9px;
    text-align: left;
    padding: 0;
}
QPushButton[kind="link"]:hover {
    color: #5eead4;
}
QPushButton:disabled {
    color: #3f4c5e;
}

/* ------------------------------------------------------------- tool cards */
QFrame#ToolCard {
    background: transparent;
    border: 1px solid transparent;
    border-radius: 8px;
}
QFrame#ToolCard:hover {
    background: rgba(148, 163, 184, 10);
    border-color: rgba(148, 163, 184, 20);
}
QFrame#ToolCard[active="true"] {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 rgba(94, 234, 212, 24), stop:1 rgba(94, 234, 212, 3));
    border-color: rgba(94, 234, 212, 45);
}
QFrame#ToolCard[missing="true"] {
    background: rgba(251, 113, 133, 6);
}
QLabel#ToolAdb {
    color: #4d5e72;
    font-size: 7px;
}
QLabel#ToolAdb[ok="true"] { color: #628d7b; }
QLabel#CurrentMark {
    color: rgba(94, 234, 212, 165);
    font-size: 7px;
}

/* ---------------------------------------------------------- network cards */
QFrame#NetworkCard {
    background: transparent;
    border: 1px solid transparent;
    border-radius: 8px;
}
QFrame#NetworkCard:hover {
    background: rgba(148, 163, 184, 7);
    border-color: rgba(148, 163, 184, 18);
}
QFrame#NetworkCard[current="true"] {
    border-color: rgba(120, 169, 255, 48);
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 rgba(120, 169, 255, 16), stop:1 rgba(120, 169, 255, 2));
}
QFrame#NetworkHeader {
    background: transparent;
    border: none;
}
QLabel#NetworkName {
    color: #d3deeb;
    font-size: 11px;
    font-weight: 600;
}
QLabel#NetworkIp {
    color: #4e5d71;
    font-family: "Cascadia Mono", "Cascadia Code", Consolas, monospace;
    font-size: 8px;
}
QLabel#PortCount {
    color: #67788e;
    border: 1px solid rgba(148, 163, 184, 28);
    border-radius: 4px;
    padding: 1px 5px;
    font-family: "Cascadia Mono", "Cascadia Code", Consolas, monospace;
    font-size: 7px;
    background: rgba(148, 163, 184, 7);
}
QLabel#Chevron {
    color: #46556a;
    font-family: "Segoe UI Symbol", "Segoe UI", sans-serif;
    font-size: 10px;
}
QFrame#PortRow {
    background: transparent;
    border: 1px solid transparent;
    border-radius: 6px;
}
QFrame#PortRow:hover {
    background: rgba(148, 163, 184, 12);
    border-color: rgba(148, 163, 184, 22);
}
QFrame#PortRow[active="true"] {
    background: rgba(94, 234, 212, 10);
    border-color: rgba(94, 234, 212, 42);
}
QLabel#PortNumber {
    color: #b9c7d7;
    font-family: "Cascadia Mono", "Cascadia Code", Consolas, monospace;
    font-size: 10px;
    font-weight: 600;
}
QLabel#PortDevice {
    color: #5c6e84;
    font-size: 8px;
}
QLabel#PortSource {
    color: #3f4d5f;
    font-size: 7px;
}
QLabel#PortArrow {
    color: #3e4e62;
    font-family: "Segoe UI Symbol", "Segoe UI", sans-serif;
    font-size: 11px;
}
QFrame#PortRow:hover QLabel#PortArrow {
    color: #5eead4;
}
QFrame#NetworkEmpty {
    border: 1px dashed rgba(148, 163, 184, 25);
    border-radius: 6px;
    background: transparent;
}
QFrame#RailEmpty {
    background: rgba(148, 163, 184, 6);
    border: 1px dashed rgba(148, 163, 184, 28);
    border-radius: 9px;
}
QFrame#RailEmpty QPushButton[kind="primary"] {
    color: #04302a;
    border: 1px solid rgba(94, 234, 212, 120);
    border-radius: 7px;
    padding: 0 12px;
    min-height: 30px;
    font-size: 10px;
    font-weight: 600;
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #84f4e1, stop:1 #4fe3c9);
}
QFrame#RailEmpty QPushButton[kind="link"] {
    color: #5b6c80;
    font-size: 8px;
}
QLabel#RailEmptyIcon {
    min-width: 38px;
    max-width: 38px;
    min-height: 38px;
    max-height: 38px;
    border-radius: 10px;
    color: #5eead4;
    background: rgba(94, 234, 212, 13);
    font-family: "Cascadia Mono", "Cascadia Code", Consolas, monospace;
    font-size: 15px;
}
QLabel#RailEmptyTitle {
    color: #d3deeb;
    font-size: 11px;
    font-weight: 600;
}
QLabel#RailEmptyText {
    color: #526176;
    font-size: 9px;
}
QFrame#AdbPill {
    background: rgba(148, 163, 184, 7);
    border: 1px solid rgba(148, 163, 184, 22);
    border-radius: 7px;
}
QFrame#AdbPill:hover {
    background: rgba(148, 163, 184, 14);
    border-color: rgba(148, 163, 184, 38);
}

/* ------------------------------------------------------------------ tabs */
QWidget#TabBar {
    background: rgba(7, 12, 19, 120);
    border-bottom: 1px solid rgba(148, 163, 184, 30);
}
QFrame#TerminalTab {
    background: transparent;
    border: 1px solid transparent;
    border-bottom: 0;
    border-top-left-radius: 7px;
    border-top-right-radius: 7px;
}
QFrame#TerminalTab:hover {
    background: rgba(148, 163, 184, 9);
}
QFrame#TerminalTab[active="true"] {
    background: #0b121c;
    border-color: rgba(148, 163, 184, 34);
}
QLabel#TabVersion {
    color: #aebccd;
    font-size: 8px;
    font-weight: 600;
}
QFrame#TerminalTab[active="true"] QLabel#TabVersion {
    color: #5eead4;
}
QFrame#TerminalTab[notool="true"] QLabel#TabVersion {
    color: #a17880;
}
QLabel#TabTarget {
    color: #4c5b6f;
    font-family: "Cascadia Mono", "Cascadia Code", Consolas, monospace;
    font-size: 7px;
}
QPushButton#TabClose {
    min-width: 17px;
    max-width: 17px;
    min-height: 17px;
    max-height: 17px;
    border-radius: 4px;
    color: transparent;
    font-family: "Segoe UI Symbol", "Segoe UI", sans-serif;
    font-size: 10px;
}
QFrame#TerminalTab:hover QPushButton#TabClose,
QFrame#TerminalTab[active="true"] QPushButton#TabClose {
    color: #5b6b80;
}
QPushButton#TabClose:hover {
    color: #edf4fc;
    background: rgba(148, 163, 184, 32);
}

/* ------------------------------------------------------------- terminal */
QWidget#TerminalWorkspace {
    background: qradialgradient(cx:0.5, cy:-0.2, radius:1.1, fx:0.5, fy:-0.2,
        stop:0 rgba(45, 212, 191, 12), stop:0.55 rgba(7, 11, 18, 0), stop:1 #080d15);
}
QFrame#TerminalShell {
    background: #060a11;
    border: 1px solid rgba(148, 163, 184, 32);
    border-radius: 10px;
}
QFrame#TerminalHeader {
    background: rgba(10, 16, 25, 210);
    border-bottom: 1px solid rgba(148, 163, 184, 22);
}
QLabel#TerminalIcon {
    min-width: 32px;
    max-width: 32px;
    min-height: 32px;
    max-height: 32px;
    border: none;
    background: transparent;
}
QLabel#TerminalTitle {
    color: #eef5fc;
    font-size: 12px;
    font-weight: 600;
}
QLabel#TerminalSub {
    color: #516075;
    font-size: 8px;
}
QLabel#TerminalSubMono {
    color: #677a91;
    font-family: "Cascadia Mono", "Cascadia Code", Consolas, monospace;
    font-size: 8px;
}
QLabel#StatusPill {
    border: 1px solid rgba(148, 163, 184, 28);
    border-radius: 9px;
    padding: 2px 7px;
    color: #66788d;
    font-size: 8px;
}
QLabel#StatusPill[state="running"] {
    color: #86dcb8;
    border-color: rgba(74, 222, 128, 28);
    background: rgba(74, 222, 128, 9);
}
QLabel#StatusPill[state="connecting"],
QLabel#StatusPill[state="starting"],
QLabel#StatusPill[state="stopping"] {
    color: #dbbe7c;
    border-color: rgba(251, 191, 36, 30);
    background: rgba(251, 191, 36, 10);
}
QLabel#StatusPill[state="failed"] {
    color: #e99ba6;
    border-color: rgba(251, 113, 133, 32);
    background: rgba(251, 113, 133, 11);
}
QTextEdit#Console {
    background: #060a11;
    border: none;
    padding: 8px 13px 18px 13px;
    selection-background-color: #1d6155;
    selection-color: #f2fffd;
}
QFrame#CommandBar {
    background: rgba(3, 7, 13, 80);
    border-top: 1px solid rgba(148, 163, 184, 20);
}
QLabel#CommandPrompt {
    color: #5eead4;
    font-family: "Cascadia Mono", "Cascadia Code", Consolas, monospace;
    font-size: 9px;
}
QLineEdit#CommandText {
    border: none;
    background: transparent;
    color: #d7e3f1;
    font-family: "Cascadia Mono", "Cascadia Code", Consolas, monospace;
    font-size: 9px;
    padding: 2px 0;
    selection-background-color: #1d6155;
}
QLineEdit#CommandText:focus {
    border-bottom: 1px solid rgba(94, 234, 212, 70);
}
QLineEdit#CommandText::placeholder {
    color: #38485c;
}
QFrame#TerminalFooter {
    background: rgba(3, 7, 13, 78);
    border-top: 1px solid rgba(148, 163, 184, 18);
}
QLabel#TerminalFooterText {
    color: #435166;
    font-family: "Cascadia Mono", "Cascadia Code", Consolas, monospace;
    font-size: 7px;
}
QFrame#IdlePanel {
    background: transparent;
}
QLabel#IdleIcon {
    min-width: 62px;
    max-width: 62px;
    min-height: 62px;
    max-height: 62px;
    border: none;
    background: transparent;
}
QLabel#IdleTitle {
    color: #eef5fc;
    font-size: 17px;
    font-weight: 600;
}
QLabel#IdleText {
    color: #526176;
    font-size: 10px;
}
QFrame#IdleStep {
    background: rgba(148, 163, 184, 5);
    border: 1px solid rgba(148, 163, 184, 24);
    border-radius: 7px;
}
QLabel#IdleStepIndex {
    color: #5eead4;
    border: 1px solid rgba(94, 234, 212, 32);
    border-radius: 8px;
    min-width: 16px;
    max-width: 16px;
    min-height: 16px;
    max-height: 16px;
    font-family: "Cascadia Mono", "Cascadia Code", Consolas, monospace;
    font-size: 7px;
}
QLabel#IdleStepText {
    color: #596b80;
    font-size: 8px;
}
QFrame#ErrorBanner {
    background: rgba(251, 113, 133, 14);
    border: 1px solid rgba(251, 113, 133, 35);
    border-radius: 5px;
}
QLabel#ErrorText {
    color: #dda1a9;
    font-size: 9px;
}
QFrame#ProgressBanner {
    background: rgba(251, 191, 36, 12);
    border: 1px solid rgba(251, 191, 36, 30);
    border-radius: 5px;
}
QLabel#ProgressText {
    color: #b99a62;
    font-size: 8px;
}

/* ------------------------------------------------------------------ toast */
QFrame#Toast {
    background: rgba(16, 24, 36, 248);
    border: 1px solid rgba(148, 163, 184, 60);
    border-radius: 8px;
}
QFrame#Toast[kind="error"] {
    border-color: rgba(251, 113, 133, 75);
}
QFrame#Toast[kind="success"] {
    border-color: rgba(74, 222, 128, 55);
}
QFrame#Toast[kind="warning"] {
    border-color: rgba(251, 191, 36, 60);
}
QLabel#ToastTitle {
    color: #f0f6fd;
    font-size: 10px;
    font-weight: 600;
}
QLabel#ToastText {
    color: #8393a8;
    font-size: 9px;
}
QLabel#ToastIcon {
    min-width: 22px;
    max-width: 22px;
    min-height: 22px;
    max-height: 22px;
    border-radius: 5px;
    color: #5eead4;
    background: rgba(94, 234, 212, 14);
    font-family: "Segoe UI Symbol", "Segoe UI", sans-serif;
    font-size: 13px;
}
QFrame#Toast[kind="error"] QLabel#ToastIcon {
    color: #fb7185;
    background: rgba(251, 113, 133, 18);
}
QFrame#Toast[kind="warning"] QLabel#ToastIcon {
    color: #fbbf24;
    background: rgba(251, 191, 36, 16);
}
QFrame#Toast[kind="success"] QLabel#ToastIcon {
    color: #4ade80;
    background: rgba(74, 222, 128, 14);
}

/* --------------------------------------------------------------- dialogs */
QDialog#AppDialog {
    background: #0f1723;
}
QWidget#DialogHeader {
    background: transparent;
    border-bottom: 1px solid rgba(148, 163, 184, 20);
}
QLabel#DialogTitle {
    color: #f0f6fd;
    font-size: 15px;
    font-weight: 600;
}
QLabel#DialogDescription {
    color: #526176;
    font-size: 9px;
}
QWidget#DialogBody {
    background: transparent;
}
QScrollArea#DialogScroll, QScrollArea#DialogScroll > QWidget > QWidget {
    background: transparent;
    border: none;
}
QFrame#DialogFooter {
    background: rgba(2, 6, 11, 40);
    border-top: 1px solid rgba(148, 163, 184, 20);
}
QLabel#FieldLabel {
    color: #7d8da3;
    font-size: 9px;
    font-weight: 500;
}
QLineEdit, QSpinBox, QComboBox, QTextEdit {
    background: rgba(4, 9, 15, 160);
    border: 1px solid rgba(148, 163, 184, 35);
    border-radius: 6px;
    padding: 0 9px;
    color: #dbe5f1;
    selection-background-color: #1d6155;
}
QLineEdit, QSpinBox, QComboBox {
    min-height: 31px;
    max-height: 31px;
    font-size: 10px;
}
QTextEdit {
    padding: 7px 9px;
    font-size: 9px;
}
QLineEdit:hover, QSpinBox:hover, QComboBox:hover, QTextEdit:hover {
    border-color: rgba(148, 163, 184, 60);
}
QLineEdit:focus, QSpinBox:focus, QComboBox:focus, QTextEdit:focus {
    border-color: rgba(94, 234, 212, 100);
    background: rgba(4, 9, 15, 220);
}
QLineEdit[mono="true"] {
    font-family: "Cascadia Mono", "Cascadia Code", Consolas, monospace;
}
QLineEdit:disabled {
    color: #526176;
    background: rgba(4, 9, 15, 90);
}
QComboBox::drop-down {
    border: none;
    width: 20px;
}
QComboBox QAbstractItemView {
    background: #111b28;
    border: 1px solid rgba(148, 163, 184, 55);
    selection-background-color: rgba(94, 234, 212, 25);
    selection-color: #eaf1fa;
    outline: none;
}
QSpinBox::up-button, QSpinBox::down-button {
    width: 16px;
    border: none;
    background: rgba(148, 163, 184, 12);
}
QCheckBox {
    color: #a6b4c6;
    font-size: 9px;
    spacing: 7px;
}
QCheckBox::indicator {
    width: 13px;
    height: 13px;
    border: 1px solid rgba(148, 163, 184, 55);
    border-radius: 3px;
    background: rgba(4, 9, 15, 180);
}
QCheckBox::indicator:checked {
    background: #5eead4;
    border-color: #5eead4;
}
QFrame#SettingsGroup {
    background: rgba(148, 163, 184, 5);
    border: 1px solid rgba(148, 163, 184, 20);
    border-radius: 8px;
}
QLabel#GroupTitle {
    color: #aab8ca;
    font-size: 9px;
    font-weight: 600;
}
QLabel#FormHelp {
    color: #4e5d71;
    font-size: 8px;
}
QFrame#InlineNote {
    background: rgba(148, 163, 184, 7);
    border: 1px solid rgba(148, 163, 184, 22);
    border-radius: 6px;
}
QLabel#InlineNoteText {
    color: #5b6b7f;
    font-size: 8px;
}
QLabel#ModalError {
    color: #e49aa4;
    background: rgba(251, 113, 133, 14);
    border: 1px solid rgba(251, 113, 133, 38);
    border-radius: 6px;
    padding: 6px 8px;
    font-size: 8px;
}
QFrame#ConfirmIcon {
    min-width: 34px;
    max-width: 34px;
    min-height: 34px;
    max-height: 34px;
    border-radius: 8px;
    color: #fbbf24;
    background: rgba(251, 191, 36, 16);
    font-family: "Segoe UI Symbol", "Segoe UI", sans-serif;
    font-size: 16px;
}
QFrame#ConfirmIcon[danger="true"] {
    color: #fb7185;
    background: rgba(251, 113, 133, 18);
}
QLabel#ConfirmTitle {
    color: #eaf1fa;
    font-size: 11px;
    font-weight: 600;
}
QLabel#ConfirmText {
    color: #7d8da3;
    font-size: 9px;
}
QLabel#AboutAppName {
    color: #f0f7ff;
    font-family: "Segoe UI Variable Display", "Segoe UI", "Microsoft YaHei UI", sans-serif;
    font-size: 20px;
    font-weight: 650;
}
QLabel#AboutVersion {
    color: #5eead4;
    font-family: "Cascadia Mono", "Cascadia Code", Consolas, monospace;
    font-size: 9px;
}
QLabel#AboutSubtitle {
    color: #526176;
    font-size: 9px;
}

/* ------------------------------------------------------------------- menu */
QMenu {
    background: #101925;
    border: 1px solid rgba(148, 163, 184, 60);
    border-radius: 6px;
    padding: 4px;
}
QMenu::item {
    color: #b9c6d7;
    padding: 6px 22px 6px 26px;
    border-radius: 4px;
    font-size: 9px;
}
QMenu::item:selected {
    color: #eaf1fa;
    background: rgba(148, 163, 184, 22);
}
QMenu::item:disabled {
    color: #455365;
}
QMenu::separator {
    height: 1px;
    background: rgba(148, 163, 184, 22);
    margin: 4px 8px;
}
QProgressBar {
    background: rgba(148, 163, 184, 20);
    border: none;
    border-radius: 2px;
}
QProgressBar::chunk {
    background: #5eead4;
    border-radius: 2px;
}

/* ---------------------------------------------------------------- scroll */
QScrollBar:vertical {
    width: 8px;
    background: transparent;
    margin: 2px;
}
QScrollBar::handle:vertical {
    background: rgba(148, 163, 184, 45);
    border-radius: 4px;
    min-height: 24px;
}
QScrollBar::handle:vertical:hover {
    background: rgba(148, 163, 184, 80);
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical,
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
    background: transparent;
    height: 0;
}
QScrollBar:horizontal {
    height: 8px;
    background: transparent;
    margin: 2px;
}
QScrollBar::handle:horizontal {
    background: rgba(148, 163, 184, 45);
    border-radius: 4px;
    min-width: 24px;
}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal,
QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {
    background: transparent;
    width: 0;
}
QToolTip {
    background: #101925;
    color: #c9d5e3;
    border: 1px solid rgba(148, 163, 184, 60);
    padding: 5px 7px;
    font-size: 9px;
}
"""
