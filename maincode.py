import ctypes
import win32gui
import mss
import mss.tools
from PIL import Image
import pytesseract
import time
pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

ctypes.windll.user32.SetProcessDPIAware()

def check_ingame(img):
    cropped = img.crop((1732, 133, 2328, 189))
    # cropped 是你前面用 crop() 得到的图像对象
    text = pytesseract.image_to_string(cropped, lang='chi_sim')  # 中文用 chi_sim
    text = text.replace(" ", "").replace("　", "")
    return text


def get_loot_page(img):
    cropped = img.crop((1730, 200, 2530, 1240))
    
    return cropped

def capture_window(hwnd):
    # 找到窗口句柄
    
    if not hwnd:
        raise Exception("找不到窗口")

    # 获取窗口坐标
    left, top, right, bottom = 0,0,2560,1440
    width = right - left
    height = bottom - top
    #print(left, top, right, bottom)

    # 用 mss 截取屏幕区域
    with mss.mss() as sct:
        monitor = {"left": left, "top": top, "width": width, "height": height}
        sct_img = sct.grab(monitor)

        # 转换成 PIL 图像
        img = Image.frombytes("RGB", sct_img.size, sct_img.bgra, "raw", "BGRX")

    return img

# 示例：捕获 BidKing.exe 窗口（假设标题是 "BidKing"）
hwnd = win32gui.FindWindow(None, "BidKing")


#img.show()
