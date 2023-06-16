import pyautogui
n = 1

import pyautogui
import time
n=1
time.sleep(2)
while n < 3000:
    pyautogui.scroll(-1)
    time.sleep(3)
    n = n + 1
    print(str(n))