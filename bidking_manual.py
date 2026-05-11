# bidking_manual.py

from PySide6.QtWidgets import (
    QDialog,
    QFormLayout,
    QLineEdit,
    QPushButton,
    QHBoxLayout,
    QVBoxLayout,
    QComboBox,
    QLabel,
)

from bidking_lib import area_dict


class ManualInputDialog(QDialog):
    def __init__(self, state, parent=None):
        super().__init__(parent)

        self.state = state

        self.setWindowTitle("手动补充信息")
        self.resize(420, 620)

        self.inputs = {}

        layout = QVBoxLayout()

        tip = QLabel("空着代表不修改；填 0 代表该项为 0；未知就别填。")
        layout.addWidget(tip)

        form = QFormLayout()

        # 地图下拉框
        self.map_combo = QComboBox()
        self.map_combo.addItem("不修改地图", None)

        selected_index = 0
        for idx, (name, mid) in enumerate(area_dict.items(), start=1):
            self.map_combo.addItem(f"{name} ({mid})", mid)
            if state.maptype == mid:
                selected_index = idx

        self.map_combo.setCurrentIndex(selected_index)
        form.addRow("地图", self.map_combo)

        fields = [
            ("total_amounts", "总件数"),
            ("total_slots", "总格数"),
            ("total_avgslot", "总平均格"),

            ("red_amounts", "红 件数"),
            ("red_slots", "红 总格"),
            ("red_avgslot", "红 平均格"),

            ("gold_amounts", "金 件数"),
            ("gold_slots", "金 总格"),
            ("gold_avgslot", "金 平均格"),

            ("purple_amounts", "紫 件数"),
            ("purple_slots", "紫 总格"),
            ("purple_avgslot", "紫 平均格"),

            ("blue_amounts", "蓝 件数"),
            ("blue_slots", "蓝 总格"),
            ("blue_avgslot", "蓝 平均格"),

            ("green&white_amounts", "绿白 件数"),
            ("green&white_slots", "绿白 总格"),
            ("green&white_avgslot", "绿白 平均格"),
        ]

        for key, label in fields:
            edit = QLineEdit()
            old_value = state.formatted_info.get(key, 0)

            if old_value not in [0, None, ""]:
                edit.setPlaceholderText(f"当前：{old_value}")
            else:
                edit.setPlaceholderText("未知")

            self.inputs[key] = edit
            form.addRow(label, edit)

        layout.addLayout(form)

        btn_row = QHBoxLayout()

        self.btn_save = QPushButton("保存并重新估值")
        self.btn_cancel = QPushButton("取消")

        self.btn_save.clicked.connect(self.accept)
        self.btn_cancel.clicked.connect(self.reject)

        btn_row.addWidget(self.btn_save)
        btn_row.addWidget(self.btn_cancel)

        layout.addLayout(btn_row)

        self.setLayout(layout)

    def apply_to_state(self):
        """
        把手动填写内容写入 state。
        """
        map_id = self.map_combo.currentData()
        if map_id is not None:
            self.state.maptype = int(map_id)

            # 反查地图名
            for name, mid in area_dict.items():
                if mid == map_id:
                    self.state.map_name = name
                    break

        for key, edit in self.inputs.items():
            text = edit.text().strip()

            if text == "":
                continue

            try:
                value = float(text)
            except ValueError:
                continue

            self.state.formatted_info[key] = value
