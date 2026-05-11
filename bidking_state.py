# bidking_state.py

from bidking_lib import init_formatted_info


class BidKingState:
    def __init__(self):
        self.reset()

    def reset(self):
        self.info_list = []
        self.maptype = None
        self.map_name = None

        self.formatted_info = init_formatted_info()

        self.final = None
        self.rarity_expected_amount = {}
        self.size_list_dict = {}
        self.sortlist = []

        self.raw_ocr_text = ""
        self.last_error = None

        # 新增：品质价值均价约束
        # key 用 rarity：6红 5金 4紫 3蓝 1&2绿白
        # value 是用户输入的单件均价
        self.rarity_avg_price_constraint = {
            "6": None,
            "5": None,
            "4": None,
            "3": None,
            "1&2": None,
        }

        # 新增：均价容忍比例
        # 0.15 代表允许正负 15%
        self.avg_price_tolerance = 0.15
