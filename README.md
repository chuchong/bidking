石油佬计算器

解压rar得到一个我计算的蒙特卡洛的dict，格式如下:

{
   地图id:
       {
           稀有度: {
                (所占格子总和，物品总数量) : 价格的(均值，标准差，最小值，最大值)
           }
       }
}

所有代码均在ipynb 用到了ocr但偶尔会不准确   换个比如easyocr应该会更好
欢迎二次开发但需要引用
期待你的star~  感谢！


---
vibe coding by gpt

更新：用tk 写了悬浮UI方便手写输入
换成了PaddleOCR更准确：
```
python -m pip install paddlepaddle==2.6.2
python -m pip install paddleocr==2.7.3
```

均值估价现在有些问题
感谢原作者开源


使用：
```
python run_gui_tk.py
```
