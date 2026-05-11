# bidking_manual_tk.py

import tkinter as tk
from tkinter import ttk

from bidking_lib import area_dict


class ManualInputDialogTk:
    def __init__(self, parent, state):
        self.parent = parent
        self.state = state
        self.result = False

        self.win = tk.Toplevel(parent)
        self.win.title("手动补充信息")
        self.win.geometry("430x650")
        self.win.attributes("-topmost", True)

        self.inputs = {}

        tip = tk.Label(
            self.win,
            text="空着代表不修改；填 0 代表该项为 0；未知就别填。",
            anchor="w"
        )
        tip.pack(fill="x", padx=10, pady=6)

        container = tk.Frame(self.win)
        container.pack(fill="both", expand=True, padx=10, pady=5)

        canvas = tk.Canvas(container)
        scrollbar = ttk.Scrollbar(container, orient="vertical", command=canvas.yview)
        self.form_frame = tk.Frame(canvas)

        self.form_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )

        canvas.create_window((0, 0), window=self.form_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        # 地图选择
        tk.Label(self.form_frame, text="地图").grid(row=0, column=0, sticky="w", pady=3)

        self.map_var = tk.StringVar()

        self.map_options = ["不修改地图"]
        self.map_value_dict = {"不修改地图": None}

        selected = "不修改地图"

        for name, mid in area_dict.items():
            text = f"{name} ({mid})"
            self.map_options.append(text)
            self.map_value_dict[text] = mid

            if state.maptype == mid:
                selected = text

        self.map_var.set(selected)

        map_combo = ttk.Combobox(
            self.form_frame,
            textvariable=self.map_var,
            values=self.map_options,
            state="readonly",
            width=28
        )
        map_combo.grid(row=0, column=1, sticky="w", pady=3)

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

        for idx, (key, label) in enumerate(fields, start=1):
            tk.Label(self.form_frame, text=label).grid(row=idx, column=0, sticky="w", pady=3)

            entry = tk.Entry(self.form_frame, width=30)

            old = state.formatted_info.get(key, 0)
            if old not in [0, None, ""]:
                entry.insert(0, "")
                entry.config(fg="black")
                entry.insert(0, "")
                entry.tooltip_value = old
            else:
                entry.tooltip_value = None

            placeholder = f"当前：{old}" if old not in [0, None, ""] else "未知"
            entry.insert(0, "")
            entry.config()
            entry.grid(row=idx, column=1, sticky="w", pady=3)

            # 旁边显示当前值
            tk.Label(
                self.form_frame,
                text=placeholder,
                fg="gray"
            ).grid(row=idx, column=2, sticky="w", padx=5)

            self.inputs[key] = entry

        btn_frame = tk.Frame(self.win)
        btn_frame.pack(fill="x", padx=10, pady=8)

        btn_save = tk.Button(btn_frame, text="保存并重新估值", command=self.on_save)
        btn_cancel = tk.Button(btn_frame, text="取消", command=self.on_cancel)

        btn_save.pack(side="left", padx=5)
        btn_cancel.pack(side="left", padx=5)

        self.win.transient(parent)
        self.win.grab_set()

    def on_save(self):
        self.apply_to_state()
        self.result = True
        self.win.destroy()

    def on_cancel(self):
        self.result = False
        self.win.destroy()

    def apply_to_state(self):
        selected = self.map_var.get()
        map_id = self.map_value_dict.get(selected)

        if map_id is not None:
            self.state.maptype = int(map_id)

            for name, mid in area_dict.items():
                if mid == map_id:
                    self.state.map_name = name
                    break

        for key, entry in self.inputs.items():
            text = entry.get().strip()

            if text == "":
                continue

            try:
                value = float(text)
            except ValueError:
                continue

            self.state.formatted_info[key] = value

    def show(self):
        self.parent.wait_window(self.win)
        return self.result
