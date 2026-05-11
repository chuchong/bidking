# bidking_gui_tk.py

import tkinter as tk
from tkinter import ttk
import traceback

from bidking_state import BidKingState
from bidking_runner import (
    find_bidking_hwnd,
    scan_ocr_into_state,
    estimate_from_state,
    format_state_result,
    format_raw_ocr_text,
)
from bidking_lib import area_dict, init_formatted_info


class BidKingOverlayTk:
    def __init__(self, root):
        self.root = root
        self.state = BidKingState()
        self.hwnd = None

        self.manual_entries = {}
        self.price_constraint_entries = {}

        self.root.title("竞拍之王估值助手")
        self.root.geometry("800x930+20+30")
        self.root.attributes("-topmost", True)
        self.root.attributes("-alpha", 0.94)

        self.build_ui()

        self.write(
            "竞拍之王估值助手已启动。\n\n"
            "现在底部是【当前值编辑模式】：\n"
            "1. OCR 后会自动把识别值填进输入框\n"
            "2. 识别错了，直接在输入框里改\n"
            "3. 点【按输入框估值】\n\n"
            "建议：中文 OCR 不靠谱时，把 OCR 只当自动填数字的辅助。\n\n"
            "快捷键：\n"
            "F5 截图OCR并填入\n"
            "F6 按输入框估值\n"
            "F8 重置本局\n"
            "回车：按输入框估值\n"
        )

    def build_ui(self):
        title = tk.Label(
            self.root,
            text="竞拍之王估值助手",
            font=("Microsoft YaHei", 16, "bold")
        )
        title.pack(fill="x", padx=8, pady=4)

        self.text = tk.Text(
            self.root,
            font=("Microsoft YaHei", 10),
            bg="#111111",
            fg="#DDDDDD",
            insertbackground="white",
            wrap="word",
            height=21
        )
        self.text.pack(fill="both", expand=True, padx=8, pady=4)

        row1 = tk.Frame(self.root)
        row1.pack(fill="x", padx=8, pady=3)

        tk.Button(row1, text="查找窗口", command=self.on_find_window).pack(side="left", padx=3)
        tk.Button(row1, text="截图OCR并填入 F5", command=self.on_scan).pack(side="left", padx=3)
        tk.Button(row1, text="按输入框估值 F6/回车", command=self.on_estimate_from_inputs).pack(side="left", padx=3)

        row2 = tk.Frame(self.root)
        row2.pack(fill="x", padx=8, pady=3)

        tk.Button(row2, text="重置本局 F8", command=self.on_reset).pack(side="left", padx=3)
        tk.Button(row2, text="只清空输入框", command=self.clear_all_input_boxes).pack(side="left", padx=3)
        tk.Button(row2, text="清空OCR识别值", command=self.clear_ocr_values).pack(side="left", padx=3)
        tk.Button(row2, text="显示OCR文本", command=self.on_show_ocr).pack(side="left", padx=3)
        tk.Button(row2, text="清空显示", command=self.clear).pack(side="left", padx=3)
        tk.Button(row2, text="重新置顶", command=self.on_retop).pack(side="left", padx=3)
        tk.Button(row2, text="退出", command=self.root.destroy).pack(side="left", padx=3)

        row3 = tk.Frame(self.root)
        row3.pack(fill="x", padx=8, pady=3)

        self.compact_var = tk.BooleanVar(value=False)
        tk.Checkbutton(
            row3,
            text="紧凑透明",
            variable=self.compact_var,
            command=self.on_toggle_compact
        ).pack(side="left", padx=3)

        self.build_manual_panel()

        self.root.bind("<F5>", lambda e: self.on_scan())
        self.root.bind("<F6>", lambda e: self.on_estimate_from_inputs())
        self.root.bind("<F8>", lambda e: self.on_reset())
        self.root.bind("<Return>", lambda e: self.on_estimate_from_inputs())

    def build_manual_panel(self):
        outer = tk.LabelFrame(
            self.root,
            text="当前值编辑区：OCR 错了直接改这里；空框=未知；均价约束填 0=取消",
            font=("Microsoft YaHei", 10, "bold")
        )
        outer.pack(fill="x", padx=8, pady=6)

        top = tk.Frame(outer)
        top.pack(fill="x", padx=6, pady=4)

        tk.Label(top, text="地图").pack(side="left", padx=2)

        self.map_var = tk.StringVar()
        self.map_options = ["未知/不修改"]
        self.map_value_dict = {"未知/不修改": None}

        for name, mid in area_dict.items():
            text = f"{name} ({mid})"
            self.map_options.append(text)
            self.map_value_dict[text] = mid

        self.map_var.set("未知/不修改")

        self.map_combo = ttk.Combobox(
            top,
            textvariable=self.map_var,
            values=self.map_options,
            state="readonly",
            width=30
        )
        self.map_combo.pack(side="left", padx=4)

        tk.Label(top, text="均价容忍 ±").pack(side="left", padx=8)

        self.tolerance_entry = tk.Entry(top, width=6)
        self.tolerance_entry.insert(0, "15")
        self.tolerance_entry.pack(side="left", padx=2)

        tk.Label(top, text="%").pack(side="left", padx=2)

        tk.Label(
            top,
            text="提示：建议只让 OCR 帮你填数字，中文错了别信。",
            fg="gray"
        ).pack(side="left", padx=12)

        grid = tk.Frame(outer)
        grid.pack(fill="x", padx=6, pady=4)

        headers = ["项目", "件数", "总格", "平均格", "价值均价约束"]
        for col, h in enumerate(headers):
            tk.Label(
                grid,
                text=h,
                font=("Microsoft YaHei", 9, "bold"),
                width=13
            ).grid(row=0, column=col, padx=2, pady=2)

        self.rows = [
            ("total", "总计", "total_amounts", "total_slots", "total_avgslot", None),
            ("red", "红", "red_amounts", "red_slots", "red_avgslot", "6"),
            ("gold", "金", "gold_amounts", "gold_slots", "gold_avgslot", "5"),
            ("purple", "紫", "purple_amounts", "purple_slots", "purple_avgslot", "4"),
            ("blue", "蓝", "blue_amounts", "blue_slots", "blue_avgslot", "3"),
            ("greenwhite", "绿白", "green&white_amounts", "green&white_slots", "green&white_avgslot", "1&2"),
        ]

        for r, row in enumerate(self.rows, start=1):
            _, label, amount_key, slot_key, avg_key, rarity_key = row

            tk.Label(grid, text=label, width=13).grid(row=r, column=0, padx=2, pady=2)

            e_amount = tk.Entry(grid, width=13)
            e_slot = tk.Entry(grid, width=13)
            e_avg = tk.Entry(grid, width=13)

            e_amount.grid(row=r, column=1, padx=2, pady=2)
            e_slot.grid(row=r, column=2, padx=2, pady=2)
            e_avg.grid(row=r, column=3, padx=2, pady=2)

            self.manual_entries[amount_key] = e_amount
            self.manual_entries[slot_key] = e_slot
            self.manual_entries[avg_key] = e_avg

            if rarity_key is not None:
                e_price = tk.Entry(grid, width=16)
                e_price.grid(row=r, column=4, padx=2, pady=2)
                self.price_constraint_entries[rarity_key] = e_price
            else:
                tk.Label(grid, text="-", width=13).grid(row=r, column=4, padx=2, pady=2)

        bottom = tk.Frame(outer)
        bottom.pack(fill="x", padx=6, pady=4)

        tk.Button(
            bottom,
            text="用 state 当前值填入输入框",
            command=self.fill_inputs_from_state
        ).pack(side="left", padx=3)

        tk.Button(
            bottom,
            text="按输入框估值",
            command=self.on_estimate_from_inputs
        ).pack(side="left", padx=3)

    def write(self, msg):
        self.text.delete("1.0", tk.END)
        self.text.insert(tk.END, msg)
        self.text.see(tk.END)

    def append(self, msg):
        self.text.insert(tk.END, msg)
        self.text.see(tk.END)

    def clear(self):
        self.text.delete("1.0", tk.END)

    def append_error(self, e):
        self.append("\n发生错误：\n")
        self.append(str(e))
        self.append("\n\n详细错误：\n")
        self.append(traceback.format_exc())

    def parse_float_or_zero(self, text):
        text = str(text).strip().replace(",", "")
        if text == "":
            return 0

        try:
            return float(text)
        except Exception:
            return 0

    def format_box_value(self, v):
        if v in [None, "", 0]:
            return ""

        try:
            f = float(v)
            if f == 0:
                return ""
            if f.is_integer():
                return str(int(f))
            return str(f)
        except Exception:
            return str(v)

    def clear_all_input_boxes(self):
        for e in self.manual_entries.values():
            e.delete(0, tk.END)

        for e in self.price_constraint_entries.values():
            e.delete(0, tk.END)

        self.map_var.set("未知/不修改")

    def clear_ocr_values(self):
        """
        清掉 OCR 识别出来的拍卖信息，但保留均价约束输入框。
        """
        self.state.info_list = []
        self.state.formatted_info = init_formatted_info()
        self.state.raw_ocr_text = ""

        for e in self.manual_entries.values():
            e.delete(0, tk.END)

        self.write("已清空 OCR 识别值。均价约束未清空。")

    def fill_inputs_from_state(self):
        """
        把 state 当前值直接填到输入框。
        OCR 后自动调用。
        """
        info = self.state.formatted_info

        # 地图
        if self.state.maptype:
            selected = "未知/不修改"

            for name, mid in area_dict.items():
                if mid == self.state.maptype:
                    selected = f"{name} ({mid})"
                    break

            self.map_var.set(selected)
        else:
            self.map_var.set("未知/不修改")

        for key, entry in self.manual_entries.items():
            entry.delete(0, tk.END)
            val = info.get(key, 0)
            text = self.format_box_value(val)
            if text:
                entry.insert(0, text)

        # 均价约束
        for rarity_key, entry in self.price_constraint_entries.items():
            entry.delete(0, tk.END)
            val = self.state.rarity_avg_price_constraint.get(rarity_key)
            text = self.format_box_value(val)
            if text:
                entry.insert(0, text)

        self.tolerance_entry.delete(0, tk.END)
        self.tolerance_entry.insert(0, str(int(self.state.avg_price_tolerance * 100)))

    def apply_inputs_to_state_full(self):
        """
        当前值编辑模式：
        输入框就是完整当前值。
        空框代表未知，也就是写回 0。
        """
        # 地图
        selected = self.map_var.get()
        map_id = self.map_value_dict.get(selected)

        if map_id is not None:
            self.state.maptype = int(map_id)
            self.state.map_name = None

            for name, mid in area_dict.items():
                if mid == map_id:
                    self.state.map_name = name
                    break
        else:
            self.state.maptype = None
            self.state.map_name = None

        # 基础字段
        for key, entry in self.manual_entries.items():
            value = self.parse_float_or_zero(entry.get())
            self.state.formatted_info[key] = value

        # 价值均价约束
        for rarity_key, entry in self.price_constraint_entries.items():
            value = self.parse_float_or_zero(entry.get())

            if value <= 0:
                self.state.rarity_avg_price_constraint[rarity_key] = None
            else:
                self.state.rarity_avg_price_constraint[rarity_key] = value

        # 容忍
        tol = self.parse_float_or_zero(self.tolerance_entry.get())
        if tol > 1:
            tol = tol / 100.0

        if tol <= 0:
            tol = 0.15

        if tol > 1:
            tol = 1

        self.state.avg_price_tolerance = tol

    def on_estimate_from_inputs(self):
        try:
            self.apply_inputs_to_state_full()

            self.write("正在按输入框估值...")
            self.root.update_idletasks()

            estimate_from_state(self.state)

            self.write(format_state_result(self.state))

        except Exception as e:
            self.append_error(e)

    def on_find_window(self):
        try:
            self.hwnd = find_bidking_hwnd()
            if self.hwnd:
                self.write(f"已找到 BidKing 窗口。\nhwnd = {self.hwnd}")
            else:
                self.write("没有找到 BidKing 窗口。请确认游戏已启动，窗口标题为 BidKing。")
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

            self.write("正在截图 OCR，请稍等...")
            self.root.update_idletasks()

            scan_ocr_into_state(self.hwnd, self.state)

            # OCR 后自动填到输入框，方便你直接改错
            self.fill_inputs_from_state()

            self.write(
                "OCR 已完成，并已填入底部输入框。\n\n"
                "请检查数字，中文 OCR 不靠谱的话不要信。\n"
                "改完直接按 F6 或回车估值。"
            )

        except Exception as e:
            self.append_error(e)

    def on_reset(self):
        self.state.reset()
        self.clear_all_input_boxes()

        self.tolerance_entry.delete(0, tk.END)
        self.tolerance_entry.insert(0, "15")

        self.write(
            "已重置本局。\n\n"
            "可以重新点击【截图OCR并填入】。"
        )

    def on_show_ocr(self):
        self.write(format_raw_ocr_text(self.state))

    def on_retop(self):
        self.root.attributes("-topmost", False)
        self.root.attributes("-topmost", True)
        self.root.lift()
        self.root.focus_force()

    def on_toggle_compact(self):
        if self.compact_var.get():
            self.root.attributes("-alpha", 0.76)
            self.root.geometry("720x780+20+40")
        else:
            self.root.attributes("-alpha", 0.94)
            self.root.geometry("800x930+20+30")
