import requests
import numpy as np
import pandas as pd
from selenium import webdriver
from selenium.webdriver.common.desired_capabilities import DesiredCapabilities
# from selenium.webdriver import ChromeOptions

options = webdriver.ChromeOptions()

options.add_argument("--disable-blink-features")
options.add_argument("--disable-blink-features=AutomationControlled")

web = webdriver.Remote(command_executor='http://10.3.18.55:11111/wd/hub',desired_capabilities=DesiredCapabilities.CHROME, options=options)
#web = webdriver.Remote(command_executor='http://10.3.18.55:11111/wd/hub',desired_capabilities=DesiredCapabilities.EDGE, options=options)

def getFina(stockID):
    web.get('http://data.10jqka.com.cn')
    v = web.get_cookie("v")['value']
    header = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/93.0.4577.63 Safari/537.36 Edg/93.0.961.38", "Cookie":"" , }
#    header = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/93.0.4577.63 Safari/537.36","Cookie": "v=A9EffRKlVNckLLjDWKpKSatd4NZoPkWw77LpxLNmzRi3Wv8Q-45VgH8C-ZBA",}
    header["Cookie"] = "v="+ v
    
    url = 'http://basic.10jqka.com.cn/api/stock/export.php?export=main&type=report&code='+stockID
    r = requests.get(url, headers=header)
    a = pd.read_excel(r.content, skiprows=1).T.sort_index().replace('--', np.nan).reset_index()
    t = a.tail(1)
    h = a.head(-1)
    data = pd.concat([t,h], ignore_index=True)
    data.columns = data.iloc[0]
    return data