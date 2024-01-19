import pyautogui
import time
import pandas as pd
import re

indexs = pd.read_excel('g:/Gitee/App/tdxAppData/tdxAppAutoGui1.xlsx',dtype={'IndexCode':object})

time.sleep(5)
i = 0
while i < indexs.shape[0]:
    try:
        a = re.findall('\d', indexs.loc[i][0])
        pyautogui.press(a)
        pyautogui.press('enter')
        n = indexs.loc[i][1]
        match n:
            case n if n >=1601:
               time.sleep(6)
            case n if 881<= n < 1601:
                time.sleep(4) 
            case n if 401 <= n < 881:
                time.sleep(3) 
            case n if 81 <= n < 401:
                time.sleep(2) 
            case n if n < 81:
                time.sleep(1.2)
        
    except:
        pass
    print(indexs.loc[i][0] + '  ok !') 
    i = i + 1
        