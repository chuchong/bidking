import ctypes
import win32gui, win32ui, win32con
import mss
import mss.tools
from PIL import Image
import pytesseract
import time
import math
from paddleocr import PaddleOCR

_PADDLE_OCR = None
def get_paddle_ocr():
    global _PADDLE_OCR
    if _PADDLE_OCR is None:
        _PADDLE_OCR = PaddleOCR(
            use_angle_cls=True,
            lang="ch",
            show_log=False
        )
    return _PADDLE_OCR

def paddle_image_to_string(img):
    """
    使用 PaddleOCR 把图片识别成字符串。
    img 可以是 PIL Image，也可以是 numpy/cv2 图片。
    """
    import numpy as np
    import cv2
    from PIL import Image
    if isinstance(img, Image.Image):
        img = np.array(img.convert("RGB"))
        img = cv2.cvtColor(img, cv2.COLOR_RGB2BGR)
    ocr = get_paddle_ocr()
    result = ocr.ocr(img, cls=True)
    lines = []
    if not result:
        return ""
    for page in result:
        if not page:
            continue
        for line in page:
            try:
                text = line[1][0]
                score = line[1][1]
                if score >= 0.40:
                    lines.append(text)
            except Exception:
                continue
    return "\n".join(lines)

def normalize_ocr_text(text):
    """
    OCR 纠错：把容易被识别错的字修回业务词。
    """
    if text is None:
        return ""
    text = str(text)
    replacements = {
        # 橙 常见误识别
        "橘": "橙",
        "澄": "橙",
        "登": "橙",
        "噔": "橙",
        "蹬": "橙",
        "镫": "橙",
        "瞪": "橙",
        "檬": "橙",
        # 标点统一
        "：": ":",
        "，": ",",
        "。": ".",
        "％": "%",
    }
    for wrong, right in replacements.items():
        text = text.replace(wrong, right)
    return text

pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

ctypes.windll.user32.SetProcessDPIAware()

def check_ingame(img):
    cropped = img.crop((650, 160,  1540, 980))
    # cropped 是你前面用 crop() 得到的图像对象
    # text = pytesseract.image_to_string(cropped, lang='chi_sim')  # 中文用 chi_sim
    text = paddle_image_to_string(cropped)
    text = normalize_ocr_text(text)
    text = text.replace(" ", "").replace("　", "")
    return text,cropped


def get_loot_page(img):
    cropped = img.crop((1730, 200, 2530, 1240))
  
    return cropped

def capture_window(hwnd):
    if not hwnd:
        raise Exception("找不到窗口")

    #left, top, right, bottom = win32gui.GetWindowRect(hwnd)
    left, top, right, bottom = 0,0,2560,1440
    width = right - left
    height = bottom - top

    hwndDC = win32gui.GetWindowDC(hwnd)
    mfcDC  = win32ui.CreateDCFromHandle(hwndDC)
    saveDC = mfcDC.CreateCompatibleDC()
    saveBitMap = win32ui.CreateBitmap()
    saveBitMap.CreateCompatibleBitmap(mfcDC, width, height)
    saveDC.SelectObject(saveBitMap)

    # 用 ctypes 调用 PrintWindow
    PW_RENDERFULLCONTENT = 2
    res = ctypes.windll.user32.PrintWindow(hwnd, saveDC.GetSafeHdc(), PW_RENDERFULLCONTENT)

    bmpinfo = saveBitMap.GetInfo()
    bmpstr  = saveBitMap.GetBitmapBits(True)
    img = Image.frombuffer(
        "RGB",
        (bmpinfo["bmWidth"], bmpinfo["bmHeight"]),
        bmpstr, "raw", "BGRX", 0, 1
    )

    win32gui.DeleteObject(saveBitMap.GetHandle())
    saveDC.DeleteDC()
    mfcDC.DeleteDC()
    win32gui.ReleaseDC(hwnd, hwndDC)

    if res == 1:
        return img
    else:
        raise Exception("PrintWindow 调用失败")


def expand_fixed_comb(fixed_comb, valid_mask):
    """
    fixed_comb: tuple of (slots, amounts)，长度等于 valid_mask 中 True 的个数
    valid_mask: list of bool，长度为目标扩展长度
    返回：扩展后的 list
    """
    # 把 fixed_comb 转成迭代器，方便顺序取值
    it = iter(fixed_comb)
    result = []
    for flag in valid_mask:
        if flag:
            result.append(next(it))
        else:
            result.append((0,0))
    return result

def init_formatted_info():
    formatted_info = {}
    for rarity in ['total','red','gold','purple','blue','green','white','green&white']:
        for infotype in ['slots','amounts','avgslot']:
            formatted_info[rarity+'_'+infotype] = 0
    return formatted_info

def fill_collection_data(data):
    """
    自动补全藏品数据：已知任意2个 → 推导出第3个
    并自动校验：总数量 = 各颜色数量之和，总格子 = 各颜色格子之和
    """
    colors = ['red', 'gold', 'purple', 'blue', 'green', 'white', 'green&white']

    # ===================== 1. 单个品质自动推导：slots / amounts / avgslot =====================
    for c in colors:
        s = data[f'{c}_slots']
        a = data[f'{c}_amounts']
        avg = data[f'{c}_avgslot']

        if s == -1 or a == -1 or avg == -1:
            data[f'{c}_slots'] = -1
            data[f'{c}_amounts'] = -1
            data[f'{c}_avgslot'] = -1
        # 已知 slots + amounts → 求 avgslot
        if s != 0 and a != 0 and avg == 0:
            data[f'{c}_avgslot'] = round(s / a, 2)

        # 已知 amounts + avgslot → 求 slots
        elif a != 0 and avg != 0 and s == 0:
            data[f'{c}_slots'] = round(avg * a,0)

        # 已知 slots + avgslot → 求 amounts
        elif s != 0 and avg != 0 and a == 0:
            data[f'{c}_amounts'] = round(s / avg,0)

    return data

import numpy as np

def calculate_standard_deviation(solution, rarity_expected_amount):
    # 1. 提取 solution 里每个元组的第二个数字
    sol_values = [item[1] for item in solution]
  
    # 2. 提取字典的 values（顺序保持你给的原始顺序）
    expected_values = list(rarity_expected_amount.values())
  
    # 3. 一一对应计算标准差（总体标准差）
    std_individual = []
    for s, e in zip(sol_values, expected_values):
        # 单个数值与期望值的标准差
        std = np.sqrt((s - e) ** 2)
        std_individual.append(round(std, 4))
  
    # 4. 整体两组数据的标准差
    std_total = round(np.std(np.array(sol_values) - np.array(expected_values)), 4)
  
    return std_total


import re

# 你之前的数字提取函数（带上）
def extract_number(text):
    match = re.search(r'[约为](\d+\.?\d*)', text)
    return float(match.group(1)) if match else -10


# 配置规则：(关键词列表, 存入的key)
rules = [
    (["总", "数量", "件"], 'total_amounts'),
    (["每件藏品", "平均", "格"], 'total_avgslot'),
    (["有藏品", "总占用", "格"], 'total_slots'),
    (["所有藏品", "总", "格"], 'total_slots'),
    (["红", "品质", "平均", "格"], 'red_avgslot'),
    (["橙", "品质", "平均", "格"], 'gold_avgslot'),
    (["金", "品质", "平均", "格"], 'gold_avgslot'),
    (["紫", "品质", "平均", "格"], 'purple_avgslot'),
    (["蓝", "品质", "平均", "格"], 'blue_avgslot'),
    (["沥英色", "品质", "平均", "格"], 'blue_avgslot'),
    (["绿", "品质", "平均", "格"], 'green_avgslot'),
    (["白", "品质", "平均", "格"], 'white_avgslot'),
    (["白", "绿", "平均",  "格"], 'green&white_avgslot'),
    (["红", "品质", "共有", "件"], 'red_amounts'),
    (["橙", "品质", "共有", "件"], 'gold_amounts'),
    (["金", "品质", "共有", "件"], 'gold_amounts'),
    (["紫", "品质", "共有", "件"], 'purple_amounts'),
    (["蓝", "品质", "共有", "件"], 'blue_amounts'),
    (["蓝", "品质", "总数量"], 'blue_amounts'),
    (["紫", "品质", "总数量"], 'purple_amounts'),
    (["沥英色", "品质", "共有", "件"], 'blue_amounts'),
    (["沥英色", "品质", "总数量"], 'blue_amounts'),
    (["绿", "品质", "共有", "件"], 'green_amounts'),
    (["白", "品质", "共有", "件"], 'white_amounts'),
    (["白", "绿", "品质", "件"], 'green&white_amounts'),
    (["红", "品质", "总占位", "格"], 'red_slots'),
    (["橙", "品质", "总占位", "格"], 'gold_slots'),
    (["金", "品质", "总占位", "格"], 'gold_slots'),
    (["紫", "品质", "总占位", "格"], 'purple_slots'),
    (["蓝", "品质", "总占位", "格"], 'blue_slots'),
    (["沥英色", "品质", "总占位", "格"], 'blue_slots'),
    (["绿", "品质", "总占位", "格"], 'green_slots'),
    (["白", "品质", "总占位", "格"], 'white_slots'),
    (["红", "品质", "总占用", "格"], 'red_slots'),
    (["橙", "品质", "总占用", "格"], 'gold_slots'),
    (["金", "品质", "总占用", "格"], 'gold_slots'),
    (["紫", "品质", "总占用", "格"], 'purple_slots'),
    (["蓝", "品质", "总占用", "格"], 'blue_slots'),
    (["沥英色", "品质", "总占用", "格"], 'blue_slots'),
    (["绿", "品质", "总占用", "格"], 'green_slots'),
    (["白", "品质", "总占用", "格"], 'white_slots'),
    (["白", "绿", "总占位",  "格"], 'green&white_slots'),
  
]


from itertools import product

def solver(final, size_range_dict):
    def get_all_combinations(all_combinations,total_amounts):
        temp = []
        for x in all_combinations:
            if sum(item[1] for item in x) <= total_amounts:
                temp.append(x)
        return temp

    colors = ["red", "gold", "purple", "blue", "green&white"]
    possible_solution = {}

    for color in colors:
        #print(color)
        #print(possible_solution)
        if (final[f"{color}_avgslot"]!=0) and (final[f"{color}_slots"]!=0) and (final[f"{color}_amounts"]!=0):
            if final[f"{color}_avgslot"] == -1:
                possible_solution[color] = [(0, 0)]
            else:
                possible_solution[color] = [(final[f"{color}_slots"], final[f"{color}_amounts"])]
            continue
        avgslot = final[f"{color}_avgslot"]
        if avgslot == -1:
            possible_solution[color] = [(0, 0)]
        elif avgslot == 0:
            if final[f"{color}_amounts"] != 0:
                possible_solution[color] = [(final[f"{color}_amounts"],final[f"{color}_amounts"])]
            else:
                possible_solution[color] = None   # 后续再展开成所有可能组合
        else:
            possible_solution[color] = possible_combination[avgslot]
    #print(possible_solution)
    #print(possible_solution["gold"])
    # ----------------------
    # 1. 筛选出非None的值
    # ----------------------
    valid_values = [v for v in possible_solution.values() if v is not None]
    valid_mask = [True if v is not None else False for v in possible_solution.values()]
    #print("有效数据列表（gold, purple, blue）：")
    #print(f"长度：{len(valid_values[0])}, {len(valid_values[1])}, {len(valid_values[2])}\n")

    # ----------------------
    # 2. 计算所有笛卡尔积组合（所有取值可能性）
    # ----------------------
    all_combinations = list(product(*valid_values))
    #for cob in all_combinations:
        #print(cob,sum(item[1] for item in cob))
    all_combinations = get_all_combinations(all_combinations,final["total_amounts"])
    #print(all_combinations)

    # ----------------------
    # 3. 输出结果
    # ----------------------
    '''
    print("=== 所有数值组合结果 ===")
    for i, comb in enumerate(all_combinations, 1):
        print(f"第{i}组：{comb}")

    print(f"\n✅ fixed 总组合数量：{len(all_combinations)} 个")
    '''

    all_combinations = [x for x in all_combinations]

    #size_range = [ -1, 1,  2,  3,  4,  6,  9,  8, 12,  5, 16, 15, 20, 10, 18]
    final_possible_ans = []
    for fixed_comb in all_combinations:
        cached = {}
        #if fixed_comb[0] != (21,3):
            #continue
        if (final["total_amounts"] - sum(item[1] for item in fixed_comb)) < 0:
            #print("111")
            continue
        if (final["total_amounts"] - sum(item[1] for item in fixed_comb)) >= 0:
            expanded = expand_fixed_comb(fixed_comb, valid_mask)
            #expanded.append((final['green&white_slots'],final['green&white_amounts']))
            final_possible_ans.append(expanded)
            #print("222")
        '''
        else:
            red_amounts = (final["total_amounts"] - sum(item[1] for item in fixed_comb) - final['green&white_amounts'])
            expanded = expand_fixed_comb(fixed_comb, valid_mask)
            expanded[0] = (-1,red_amounts)
            #expanded.append((final['green&white_slots'],final['green&white_amounts']))
            final_possible_ans.append(expanded)
            #print(expanded)
            #print("333")
        '''
    return_list = []
    #print(final_possible_ans)
    # if  (final['total_slots'] != 0) and (final['blue_avgslot']!=0):
    #     final_possible_ans = [
    #         [(final['total_slots'] - sum(t[0] for t in s[1:]), final["total_amounts"] - sum(t[1] for t in s[1:]))] + s[1:]
    #         for s in final_possible_ans if s[0] == (0,0)
    #     ]
    # else:
    #     final_possible_ans = [
    #         [(s[0][0], final["total_amounts"] - sum(t[1] for t in s[1:]))] + s[1:]
    #         for s in final_possible_ans if s[0] == (0,0)
    #     ]
    temp_ans = []
    for s in final_possible_ans:
        if s[0] != (0, 0):
            temp_ans.append(s)
            continue

        red_amounts = final["total_amounts"] - sum(t[1] for t in s[1:])

        if red_amounts <= 0:
            continue

        if (final['total_slots'] != 0) and (final['blue_avgslot'] != 0):
            # 知道总格数，能反推红色实际格数
            red_slots_real = final['total_slots'] - sum(t[0] for t in s[1:])
            if red_slots_real <= 0:
                continue
            # 用实际反推的格数，不展开 1/2/3 格
            temp_ans.append([(red_slots_real, red_amounts)] + s[1:])
        else:
            # 不知道总格数，按平均 1/2/3 格各生成一个候选
            for avg in [1, 2, 3]:
                temp_ans.append([(red_amounts * avg, red_amounts)] + s[1:])

    final_possible_ans = temp_ans

    #print(final_possible_ans)
    tempans = []
    for possans in final_possible_ans:
        addflag = True
        for possans_unit in possans:
            if possans_unit[0]!=0 and (possans_unit[0] < possans_unit[1]):
                addflag = False
                break
        if addflag:
            tempans.append(possans)
    final_possible_ans = tempans
    #print(final_possible_ans)
    for psbans in final_possible_ans:
        needcontinue = False
        #print(psbans)
        count = 6
        for check in psbans:
            if count <=2:
                size_range = size_range_dict['1&2']
            else:
                size_range = size_range_dict[str(count)]
            if (check[1] == 1) and (not(check[0] in size_range)):
                #print("cont")
                needcontinue = True
                break
            count -= 1
        #print(psbans)
        if needcontinue:
            continue
        if psbans[0][1]<=15:
            return_list.append(psbans)
    return return_list

import pandas as pd
import ast
import pickle
# 如果是制表符分隔
drop_df = pd.read_csv(r"D:\bidking\Drop.txt", sep="\t", header=None,
                  names=["id", "name", "abandon1", "abandon2", "relation"])[['id','name','relation']]
                                                                          
drop_df['relation'] = drop_df['relation'].apply(ast.literal_eval)
item_name_list = ["id", "name", "abandon1", "abandon2", "abandon3", "abandon4", "abandon5", "shape"]
for i in range(30):
    item_name_list.append("abandon"+str(i+6))
df_items =  pd.read_csv(r"D:\bidking\Item.txt", sep="\t", header=None,
                  names=item_name_list)[['id','name','shape','abandon7']].rename(columns={"id": "item_id","abandon7": "price"})
map_info = pd.read_csv(r"D:\bidking\bidking_map_priors.csv")       
with open(r"D:\bidking\map_static_dict.pkl", "rb") as f:
    map_static_dict = pickle.load(f)
def relation_to_dict(rel_list):
    # 先累加每个 key 的第五个元素
    if len(rel_list[0]) == 0:
        return {}
    sums = {}
    for sub in rel_list:
        key = sub[1]
        val = sub[4]
        sums[key] = sums.get(key, 0) + val

    total = sum(sums.values())
    # 再转成比值
    return {k: v / total for k, v in sums.items()}


# 假设 df 是你的 DataFrame，relation 列存的是 list of list
drop_df["relation_dict"] = drop_df["relation"].apply(relation_to_dict)
general_dict = {}
print(drop_df["relation_dict"].iloc[0])
for index,row in drop_df.iterrows():
    general_dict[row['id']] = row['relation_dict']
node_list = list(general_dict.keys())


def expand_node(node_id, general_dict, node_list, base_prob=1.0):
    """
    node_id: 当前节点编号
    general_dict: 外层 dict，key 是节点，value 是子节点的 dict
    node_list: 非叶子节点的集合或列表
    base_prob: 当前路径累计的概率
    返回: dict {leaf_id: prob}
    """
    result = {}

    # 如果这个节点没有子字典，说明它是叶子
    if node_id not in general_dict:
        result[node_id] = base_prob
        return result

    # 遍历子节点
    for child_id, prob in general_dict[node_id].items():
        new_prob = base_prob * prob
        if child_id in node_list:
            # 递归展开
            child_result = expand_node(child_id, general_dict, node_list, new_prob)
            # 合并结果
            for k, v in child_result.items():
                result[k] = result.get(k, 0) + v
        else:
            # 已经是叶子
            result[child_id] = result.get(child_id, 0) + new_prob

    return result

def df_wrapper(node_id, general_dict, node_list):
    result_dict = expand_node(node_id, general_dict, node_list)
    return pd.DataFrame(list(result_dict.items()), columns=["item_id", "prob"])

def get_merged_table(mapindex,general_dict,node_list,df_items):
    df_probs = df_wrapper(mapindex,general_dict, node_list)
    merged = pd.merge(df_probs, df_items, on="item_id", how="left")
    merged["rarity"] = merged["item_id"].astype(str).str[-4]
    return merged.fillna(0)


import joblib
from joblib import Parallel, delayed
import os

def monte_carlo_joblib(df, x, n_iter=1_000_000, n_jobs=-1):
    n_proc = os.cpu_count() if n_jobs == -1 else n_jobs
    chunk = n_iter // n_proc
    seeds = np.arange(n_proc) * 12345
  
    results = Parallel(n_jobs=n_jobs)(
        delayed(_worker)(df, x, chunk, int(seeds[i])) for i in range(n_proc)
    )
  
    slots_all = np.concatenate([r[0] for r in results])
    price_all = np.concatenate([r[1] for r in results])
  
    return slots_all, price_all

def _worker(df, x, n_iter, seed):
    rng = np.random.default_rng(seed)
    probs = df["editprob"].to_numpy()
    probs = probs / probs.sum()
    sizes = df["size"].to_numpy()
    prices = df["price"].to_numpy()
  
    slots_results = np.zeros(n_iter, dtype=np.int64)
    price_results = np.zeros(n_iter, dtype=np.float64)
  
    for i in range(n_iter):
        idx = rng.choice(len(df), size=x, replace=True, p=probs)
        slots_results[i] = sizes[idx].sum()
        price_results[i] = prices[idx].sum()
  
    return slots_results, price_results

def finalize_monte_dict(monte_dict):
    for key, values in monte_dict.items():
        arr = np.array(values)
        mean_val = arr.mean()
        std_val = arr.std()
        max_val = arr.max()
        min_val = arr.min()
        monte_dict[key] = (mean_val, std_val, max_val, min_val)
    return monte_dict

def get_static_result(rarity_df):
    # 使用示例
    monte_dict = {}
    for items in range(1,64):
        slots, prices = monte_carlo_joblib(rarity_df, x=items, n_iter=1_000_00, n_jobs=-1)
        for slot,price in zip(slots, prices):
            if (slot,items) not in monte_dict.keys():
                monte_dict[(slot,items)] = [price]
            else:
                templist = monte_dict[(slot,items)]
                templist.append(price)
                monte_dict[(slot,items)] = templist
    return finalize_monte_dict(monte_dict)


def price_solver(infolist,map_type,map_static_dict):
    rarity = ['6','5','4','3','1&2']
    #infolist = [(-1, 2.0), (14, 2), (17, 9), (60.0, 17.0), (11.0, 6.0)]
    infolist = [tuple(int(v) for v in pair) for pair in infolist]
    #map_type = 2401
    total_mean,total_var,total_min,total_max = 0,0,0,0
    for rare,info in zip(rarity,infolist):
        if (info[0] == 0) and (info[1] != 0):
            info = (info[1],info[1])
        if info == (0,0):
            continue
        if info[0] == -1:
            result = get_merged_table(map_type,general_dict,node_list,df_items)
            result["size"] = result["shape"].astype(str).str[0].astype(int) * result["shape"].astype(str).str[-1].astype(int)
            result['unitprice'] = round(result['price']/result['size'],2)
            editfactor = (1/sum(result[result['rarity']==rare]['prob']))
            #print(result[result['rarity']==rare]['prob'] * result[result['rarity']==rare]['price'] * editfactor)
            result['editprob'] = result['prob']*editfactor
            #print(info)
            slots, prices = monte_carlo_joblib(result[result['rarity']==rare], x=info[1], n_iter=1_000_00, n_jobs=-1)
            prices = np.array([x for x in prices if x <=1000000 ])
            total_mean += prices.mean()
            #print(prices.mean(),prices.std())
            continue
        if info not in map_static_dict[map_type][rare].keys():
            continue
        total_mean += map_static_dict[map_type][rare][info][0]
        total_var += map_static_dict[map_type][rare][info][1]
        total_max += map_static_dict[map_type][rare][info][2]
        total_min += map_static_dict[map_type][rare][info][3]
    return total_mean,total_var,total_min,total_max

possible_combination = {}
for possible_slots in range(1,230):
    for possible_amounts in range(1,70):
        #print(possible_combination)
        #possible_avg = int((possible_slots / possible_amounts) * 100) / 100
        possible_avg = math.floor((possible_slots / possible_amounts) * 100 + 0.00001) / 100
        if possible_avg <1 or possible_avg>20:
            continue
        if possible_avg not in possible_combination.keys():
            possible_combination[possible_avg] = [(possible_slots,possible_amounts)]
        else:
            temp = possible_combination[possible_avg]
            temp.append((possible_slots,possible_amounts))
            possible_combination[possible_avg] = temp
          
# 示例：捕获 BidKing.exe 窗口（假设标题是 "BidKing"）
#hwnd = win32gui.FindWindow(None, "BidKing")


#img.show()

import win32gui

def find_real_bidking_window():
    results = []
    def callback(hwnd, extra):
        if win32gui.IsWindowVisible(hwnd):
            title = win32gui.GetWindowText(hwnd).lower()
            cls = win32gui.GetClassName(hwnd)
            # 排除系统控件
            if "bidking" in title and "Shell.TabProxyWindow" not in cls:
                rect = win32gui.GetWindowRect(hwnd)
                results.append((hwnd, win32gui.GetWindowText(hwnd), cls, rect))
        return True

    win32gui.EnumWindows(callback, None)
    return results

info_list = []
maptype = None
formatted_info = init_formatted_info()

area_dict = {"未知残骸":2501, "远洋客轮舱房":2502, "军用舰艇保险库":2503, "冷链货船隔离舱":2504, "殖民商船宝库":2505, "探险家座舰资料库":2506, "皇家御用货舱":2507, "生物实验室样本库":2508, "私掠船军火舱":2509, "现代货轮娱乐库":2510, "未知别墅":2401, "设计师居所":2402, "科学家居所":2403, "养生学家居所":2404, "望族居所":2405, "学者居所":2406, "私人金库":2407, "奢华养老院":2408, "末日庇护所":2409,"未日庇护所":2409, "极客改造屋":2410}

