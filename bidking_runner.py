# bidking_runner.py

import traceback
import numpy as np

from bidking_lib import (
    capture_window,
    check_ingame,
    find_real_bidking_window,
    area_dict,
    rules,
    extract_number,
    fill_collection_data,
    possible_combination,
    get_merged_table,
    general_dict,
    node_list,
    df_items,
    solver,
    price_solver,
    map_static_dict,
    calculate_standard_deviation,
)


RARITY_LABELS = ["红", "金", "紫", "蓝", "绿白"]
RARITY_KEYS = ["6", "5", "4", "3", "1&2"]


def find_bidking_hwnd():
    windows = find_real_bidking_window()
    for w in windows:
        if w[1] == "BidKing":
            return w[0]
    return None


def scan_ocr_into_state(hwnd, state):
    """
    截图 OCR，并把识别结果写入 state。
    """
    if not hwnd:
        raise RuntimeError("没有找到 BidKing 窗口")

    current_window = capture_window(hwnd)
    info, cropped = check_ingame(current_window)

    state.raw_ocr_text = info

    result_list = info.split("\n")
    result_list = [item.replace(",", "").strip() for item in result_list]

    for s in result_list:
        if not s:
            continue

        # 识别地图
        for k, v in area_dict.items():
            if k in s:
                state.map_name = k
                state.maptype = v
                break

        if any(key in s for key in ["哈迈", "竞拍信息"]):
            continue

        if len(s) <= 1:
            continue

        if s not in state.info_list:
            state.info_list.append(s)

    # 解析数值
    for rawinfo in state.info_list:
        num = extract_number(rawinfo)
        if num == -10:
            continue

        for keys, key in rules:
            if all(k in rawinfo for k in keys):
                if num == 0:
                    state.formatted_info[key] = -1
                else:
                    state.formatted_info[key] = num

    if not state.maptype:
        raise RuntimeError("地图名识别失败，请手动补充地图 ID 或重新截图。")

    return state


def build_rarity_expected_amount(maptype, total_amount):
    """
    根据地图掉落概率和总件数，计算各品质期望件数。
    """
    tempused = get_merged_table(maptype, general_dict, node_list, df_items)

    rarity_expected_amount = {}

    for rarity in range(6, 2, -1):
        rarity_expected_amount[str(rarity)] = round(
            sum(tempused[tempused["rarity"] == str(rarity)]["prob"]) * total_amount,
            2
        )

    rarity_expected_amount["1&2"] = round(
        sum(tempused[tempused["rarity"] == "1"]["prob"]) * total_amount
        + sum(tempused[tempused["rarity"] == "2"]["prob"]) * total_amount,
        2
    )

    return rarity_expected_amount


def build_size_list_dict(maptype):
    """
    生成当前地图各品质可能出现的单件尺寸。
    """
    tempused = get_merged_table(maptype, general_dict, node_list, df_items).copy()

    tempused["shape"] = tempused["shape"].astype(int)
    tempused["size"] = (
        tempused["shape"].astype(str).str[0].astype(int)
        * tempused["shape"].astype(str).str[-1].astype(int)
    )

    size_list_dict = {}

    for rarity in range(3, 7):
        size_list = tempused[tempused["rarity"] == str(rarity)]["size"].unique()
        size_list = list(size_list)
        size_list.append(-1)
        size_list_dict[str(rarity)] = size_list

    size_list = tempused[
        (tempused["rarity"] == "1") | (tempused["rarity"] == "2")
    ]["size"].unique()

    size_list = list(size_list)
    size_list.append(-1)
    size_list_dict["1&2"] = size_list

    return size_list_dict


def get_rarity_value_from_solution(maptype, rarity_key, pair):
    """
    根据某个品质的 solution pair 获取该品质总估值。

    pair = (slots, amount)

    注意：
    map_static_dict[maptype][rarity_key][pair] 返回通常是一个 tuple/list，
    第 0 位是估值。
    """
    try:
        if pair == (0, 0):
            return 0

        if rarity_key not in map_static_dict[maptype]:
            return None

        if pair not in map_static_dict[maptype][rarity_key]:
            return None

        return map_static_dict[maptype][rarity_key][pair][0]
    except Exception:
        return None


def solution_pass_avg_price_constraints(state, solution):
    """
    用用户输入的品质均价约束过滤 solution。

    输入例子：
    用户填 金色均价 = 500000
    则该 solution 的金色总估值 / 金色件数 必须在：
    500000 * (1 - tolerance)
    到
    500000 * (1 + tolerance)
    之间。

    solution 顺序：
    [红, 金, 紫, 蓝, 绿白]
    对应 rarity：
    ["6", "5", "4", "3", "1&2"]
    """
    constraints = getattr(state, "rarity_avg_price_constraint", {})
    tolerance = getattr(state, "avg_price_tolerance", 0.15)

    for rarity_key, pair in zip(RARITY_KEYS, solution):
        target_avg = constraints.get(rarity_key)

        if target_avg in [None, "", 0]:
            continue

        try:
            target_avg = float(target_avg)
        except Exception:
            continue

        slots, amount = pair

        try:
            amount = float(amount)
        except Exception:
            return False

        # 用户填了均价，但是这个方案这个品质为 0 件，则不通过
        if amount <= 0:
            return False

        total_value = get_rarity_value_from_solution(
            state.maptype,
            rarity_key,
            pair
        )

        if total_value is None:
            return False

        real_avg = float(total_value) / amount

        low = target_avg * (1 - tolerance)
        high = target_avg * (1 + tolerance)

        if not (low <= real_avg <= high):
            return False

    return True


def estimate_from_state(state):
    """
    根据 state.formatted_info 和 state.maptype 重新估值。
    """
    formatted_info = state.formatted_info

    if not state.maptype:
        raise RuntimeError("缺少地图 ID，无法估值。")

    if not formatted_info.get("total_amounts"):
        raise RuntimeError("缺少总件数 total_amounts，无法估值。")

    total_amount = int(formatted_info["total_amounts"])

    rarity_expected_amount = build_rarity_expected_amount(
        state.maptype,
        total_amount
    )
    state.rarity_expected_amount = rarity_expected_amount

    size_list_dict = build_size_list_dict(state.maptype)
    state.size_list_dict = size_list_dict

    final = fill_collection_data(formatted_info.copy())

    # 如果识别到总平均格，尝试反推总格数
    if final.get("total_avgslot", 0) != 0:
        avg = final["total_avgslot"]
        if avg in possible_combination:
            for choice in possible_combination[avg]:
                if choice[1] == final["total_amounts"]:
                    final["total_slots"] = choice[0]

    state.final = final

    sortlist = []

    for solutions in solver(final, size_list_dict):

        # 新增：品质均价约束
        if not solution_pass_avg_price_constraints(state, solutions):
            continue

        price_predict = price_solver(
            solutions,
            state.maptype,
            map_static_dict
        )

        # 紫色估值
        try:
            purple_value = map_static_dict[state.maptype]["4"][solutions[2]][0]
        except KeyError:
            continue

        # 金色估值
        if solutions[1] == (0, 0):
            gold_value = 0
        else:
            if solutions[1] not in map_static_dict[state.maptype]["5"].keys():
                continue
            gold_value = map_static_dict[state.maptype]["5"][solutions[1]][0]

        deviation = calculate_standard_deviation(
            solutions,
            rarity_expected_amount
        )

        # 新增：各品质估值
        rarity_values = {}
        for rarity_key, pair in zip(RARITY_KEYS, solutions):
            rarity_values[rarity_key] = get_rarity_value_from_solution(
                state.maptype,
                rarity_key,
                pair
            )

        sortlist.append((
            solutions,
            price_predict[0],
            price_predict[1],
            deviation,
            purple_value,
            gold_value,
            rarity_values,
        ))

    sortlist.sort(key=lambda x: x[3])

    state.sortlist = sortlist
    return sortlist


def format_number(x):
    try:
        return f"{float(x):,.0f}"
    except Exception:
        return str(x)


def format_field_value(v):
    if v in [0, None, ""]:
        return "未知"
    if v == -1:
        return "0"
    try:
        if float(v).is_integer():
            return str(int(v))
        return str(v)
    except Exception:
        return str(v)


def format_constraints_info(state):
    constraints = getattr(state, "rarity_avg_price_constraint", {})
    tolerance = getattr(state, "avg_price_tolerance", 0.15)

    names = {
        "6": "红",
        "5": "金",
        "4": "紫",
        "3": "蓝",
        "1&2": "绿白",
    }

    used = []
    for k in RARITY_KEYS:
        v = constraints.get(k)
        if v not in [None, "", 0]:
            used.append(f"{names[k]}均价≈{format_number(v)}")

    if not used:
        return ""

    return (
        "品质均价约束\n"
        + "-" * 22 + "\n"
        + "；".join(used)
        + f"\n容忍范围：±{tolerance * 100:.0f}%\n"
    )


def format_recognized_info(state):
    """
    格式化 OCR/手动识别到的信息。
    """
    info = state.formatted_info

    lines = []
    lines.append("已识别信息")
    lines.append("-" * 22)

    if state.map_name:
        lines.append(f"地图：{state.map_name} ({state.maptype})")
    elif state.maptype:
        lines.append(f"地图ID：{state.maptype}")
    else:
        lines.append("地图：未知")

    lines.append(f"总件数：{format_field_value(info.get('total_amounts'))}")
    lines.append(f"总格数：{format_field_value(info.get('total_slots'))}")
    lines.append(f"总平均格：{format_field_value(info.get('total_avgslot'))}")
    lines.append("")

    color_map = [
        ("red", "红"),
        ("gold", "金"),
        ("purple", "紫"),
        ("blue", "蓝"),
        ("green&white", "绿白"),
    ]

    for key, label in color_map:
        amounts = format_field_value(info.get(f"{key}_amounts"))
        slots = format_field_value(info.get(f"{key}_slots"))
        avg = format_field_value(info.get(f"{key}_avgslot"))
        lines.append(f"{label}：{amounts} 件 / {slots} 格 / 平均 {avg}")

    return "\n".join(lines)


def format_state_result(state, max_solutions=8):
    """
    把估值结果格式化成 GUI 文本。
    """
    lines = []

    lines.append("竞拍之王估值结果")
    lines.append("=" * 26)
    lines.append("")

    lines.append(format_recognized_info(state))
    lines.append("")

    constraints_text = format_constraints_info(state)
    if constraints_text:
        lines.append(constraints_text)
        lines.append("")

    if state.rarity_expected_amount:
        exp = state.rarity_expected_amount
        lines.append("理论品质件数")
        lines.append("-" * 22)
        lines.append(
            f"红 {exp.get('6', 0)} | "
            f"金 {exp.get('5', 0)} | "
            f"紫 {exp.get('4', 0)} | "
            f"蓝 {exp.get('3', 0)} | "
            f"绿白 {exp.get('1&2', 0)}"
        )
        lines.append("")

    if not state.sortlist:
        lines.append("没有找到可用估值方案。")
        lines.append("")
        lines.append("可能原因：")
        lines.append("1. OCR 信息不完整")
        lines.append("2. 地图识别错误")
        lines.append("3. 平均格数识别错误")
        lines.append("4. 手动补充信息不一致")
        lines.append("5. 品质均价约束过严")
        return "\n".join(lines)

    for i, tupleunit in enumerate(state.sortlist[:max_solutions], 1):
        solution = tupleunit[0]
        total_value = tupleunit[1]
        deviation = tupleunit[3]
        purple_value = tupleunit[4]
        gold_value = tupleunit[5]

        if len(tupleunit) >= 7:
            rarity_values = tupleunit[6]
        else:
            rarity_values = {}

        lines.append(f"方案 {i}")
        lines.append("-" * 22)

        for label, rarity_key, pair in zip(RARITY_LABELS, RARITY_KEYS, solution):
            slots, amount = pair

            try:
                slots_f = float(slots)
                amount_f = float(amount)
            except Exception:
                lines.append(f"{label}：{pair}")
                continue

            rv = rarity_values.get(rarity_key)

            if amount_f == 0:
                lines.append(f"{label}：0 件")
            elif slots_f == 0:
                if rv is not None:
                    lines.append(
                        f"{label}：{amount_f:.0f} 件，占格未知，"
                        f"估值 {format_number(rv)}，均价 {format_number(rv / amount_f)}"
                    )
                else:
                    lines.append(f"{label}：{amount_f:.0f} 件，占格未知")
            else:
                avg_slot = slots_f / amount_f if amount_f else 0

                if rv is not None:
                    avg_price = rv / amount_f
                    lines.append(
                        f"{label}：{amount_f:.0f} 件，"
                        f"{slots_f:.0f} 格，"
                        f"平均 {avg_slot:.2f} 格，"
                        f"估值 {format_number(rv)}，"
                        f"均价 {format_number(avg_price)}"
                    )
                else:
                    lines.append(
                        f"{label}：{amount_f:.0f} 件，"
                        f"{slots_f:.0f} 格，"
                        f"平均 {avg_slot:.2f}"
                    )

        total_slots = sum(float(x[0]) for x in solution)

        lines.append("")
        lines.append(f"总估值：{format_number(total_value)}")
        lines.append(f"金色估值：{format_number(gold_value)}")
        lines.append(f"紫色估值：{format_number(purple_value)}")
        lines.append(f"方案总格数：{total_slots:.0f}")
        lines.append(f"分布偏离度：{deviation:.4f}")
        lines.append("")

    return "\n".join(lines)


def format_raw_ocr_text(state):
    lines = []
    lines.append("OCR 原始文本")
    lines.append("=" * 26)
    lines.append(state.raw_ocr_text or "暂无 OCR 文本")
    return "\n".join(lines)


def safe_traceback(e):
    return str(e) + "\n" + traceback.format_exc()
