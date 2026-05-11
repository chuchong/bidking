# bidking_gui.py

import traceback

from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QTextEdit,
    QLabel,
    QApplication,
    QCheckBox,
)
from PySide6.QtCore import Qt, QTimer

from bidking_state import BidKingState
from bidking_runner import (
    find_bidking_hwnd,
    scan_ocr_into_state,
    estimate_from_state,
    format_state_result,
    format_raw_ocr_text,
    safe_traceback,
)
from bidking_manual import ManualInputDialog


class BidKingOverlay(QWidget):
    def __init__(self):
        super().__init__()

        self.state = BidKingState()
        self.hwnd = None

        self.setWindowTitle("竞拍之王估值助手")

        # 置顶窗口
        self.setWindowFlags(
            Qt.WindowStaysOnTopHint |
            Qt.Tool
        )

        self.resize(620, 820)
        self.move(20, 80)

        # 透明度
        self.setWindowOpacity(0.94)

        self.build_ui()

        self.output.setText(
            "竞拍之王估值助手已启动。\n\n"
            "推荐游戏使用【无边框窗口化】。\n\n"
            "使用顺序：\n"
            "1. 点击【查找窗口】\n"
            "2. 点击【截图识别并估值】\n"
            "3. OCR 不完整时点【手动补充】\n"
            "4. 新一局点【重置本局】\n"
        )

    def build_ui(self):
        main_layout = QVBoxLayout()

        title = QLabel("竞拍之王估值助手")
        title.setStyleSheet("font-size: 18px; font-weight: bold;")
        main_layout.addWidget(title)

        self.output = QTextEdit()
        self.output.setReadOnly(True)
        self.output.setStyleSheet("""
            QTextEdit {
                font-family: Microsoft YaHei;
                font-size: 13px;
                background-color: #111111;
                color: #DDDDDD;
            }
        """)
        main_layout.addWidget(self.output)

        row1 = QHBoxLayout()

        self.btn_find = QPushButton("查找窗口")
        self.btn_scan = QPushButton("截图识别并估值")
        self.btn_estimate = QPushButton("重新估值")

        row1.addWidget(self.btn_find)
        row1.addWidget(self.btn_scan)
        row1.addWidget(self.btn_estimate)

        main_layout.addLayout(row1)

        row2 = QHBoxLayout()

        self.btn_manual = QPushButton("手动补充")
        self.btn_reset = QPushButton("重置本局")
        self.btn_show_ocr = QPushButton("显示OCR文本")

        row2.addWidget(self.btn_manual)
        row2.addWidget(self.btn_reset)
        row2.addWidget(self.btn_show_ocr)

        main_layout.addLayout(row2)

        row3 = QHBoxLayout()

        self.btn_clear = QPushButton("清空显示")
        self.btn_top = QPushButton("重新置顶")
        self.btn_exit = QPushButton("退出")

        row3.addWidget(self.btn_clear)
        row3.addWidget(self.btn_top)
        row3.addWidget(self.btn_exit)

        main_layout.addLayout(row3)

        row4 = QHBoxLayout()

        self.checkbox_compact = QCheckBox("紧凑透明")
        self.checkbox_compact.setChecked(False)

        row4.addWidget(self.checkbox_compact)
        row4.addStretch()

        main_layout.addLayout(row4)

        self.setLayout(main_layout)

        self.btn_find.clicked.connect(self.on_find_window)
        self.btn_scan.clicked.connect(self.on_scan)
        self.btn_estimate.clicked.connect(self.on_estimate)
        self.btn_manual.clicked.connect(self.on_manual)
        self.btn_reset.clicked.connect(self.on_reset)
        self.btn_show_ocr.clicked.connect(self.on_show_ocr)
        self.btn_clear.clicked.connect(self.output.clear)
        self.btn_top.clicked.connect(self.on_retop)
        self.btn_exit.clicked.connect(self.close)
        self.checkbox_compact.stateChanged.connect(self.on_toggle_compact)

    def append_error(self, e):
        self.output.append("\n发生错误：")
        self.output.append(str(e))
        self.output.append("\n详细错误：")
        self.output.append(traceback.format_exc())

    def on_find_window(self):
        try:
            self.hwnd = find_bidking_hwnd()
            if self.hwnd:
                self.output.setText(f"已找到 BidKing 窗口。\nhwnd = {self.hwnd}")
            else:
                self.output.setText("没有找到 BidKing 窗口。请确认游戏已启动，窗口标题为 BidKing。")
        except Exception as e:
            self.append_error(e)

    def ensure_hwnd(self):
        if not self.hwnd:
            self.hwnd = find_bidking_hwnd()

        if not self.hwnd:
            raise RuntimeError("没有找到 BidKing 窗口。")

    def on_scan(self):
        try:
            self.ensure_hwnd()

            self.output.setText("正在截图 OCR，请稍等...")
            QApplication.processEvents()

            scan_ocr_into_state(self.hwnd, self.state)

            self.output.setText("OCR 完成，正在估值...")
            QApplication.processEvents()

            estimate_from_state(self.state)

            text = format_state_result(self.state)
            self.output.setText(text)

        except Exception as e:
            self.append_error(e)

    def on_estimate(self):
        try:
            self.output.setText("正在重新估值...")
            QApplication.processEvents()

            estimate_from_state(self.state)

            text = format_state_result(self.state)
            self.output.setText(text)

        except Exception as e:
            self.append_error(e)

    def on_manual(self):
        try:
            dlg = ManualInputDialog(self.state, self)

            if dlg.exec():
                dlg.apply_to_state()

                self.output.setText("已保存手动补充信息，正在重新估值...")
                QApplication.processEvents()

                estimate_from_state(self.state)

                text = format_state_result(self.state)
                self.output.setText(text)

        except Exception as e:
            self.append_error(e)

    def on_reset(self):
        self.state.reset()
        self.output.setText(
            "已重置本局。\n\n"
            "可以重新点击【截图识别并估值】。"
        )

    def on_show_ocr(self):
        self.output.setText(format_raw_ocr_text(self.state))

    def on_retop(self):
        self.setWindowFlags(
            Qt.WindowStaysOnTopHint |
            Qt.Tool
        )
        self.show()
        self.raise_()
        self.activateWindow()

    def on_toggle_compact(self):
        if self.checkbox_compact.isChecked():
            self.setWindowOpacity(0.72)
            self.resize(520, 700)
        else:
            self.setWindowOpacity(0.94)
            self.resize(620, 820)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_F5:
            self.on_scan()
        elif event.key() == Qt.Key_F6:
            self.on_estimate()
        elif event.key() == Qt.Key_F7:
            self.on_manual()
        elif event.key() == Qt.Key_F8:
            self.on_reset()
        else:
            super().keyPressEvent(event)
