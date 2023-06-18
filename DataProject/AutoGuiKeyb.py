399011
import pyautogui
import time
import pandas as pd
import re

ind = pd.read_excel('g:/gitee/1.xlsx',dtype={'IndexCode':object})
indexs = ind['IndexCode'].to_list()
time.sleep(5)
for i in indexs:
    try:
        a = re.findall('\d', i)
        pyautogui.press(a)
        pyautogui.press('enter')
        time.sleep(3)
        print(i + 'ok !')
    except:
        pass


