import requests
import numpy as np
import pandas as pd


header = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:76.0) Gecko/20100101 Firefox/76.0',}
header1 = {"User-Agent": "Mozilla/5.0 (Linux; Android 7.0; SM-G892A Build/NRD90M; wv) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/67.0.3396.87 Mobile Safari/537.36",}

def getFina(stockID):
    
    url = 'http://basic.10jqka.com.cn/api/stock/export.php?export=main&type=report&code='+stockID
    r = requests.get(url, headers=header)
    a = pd.read_excel(r.content, skiprows=1).T.sort_index().replace('--', np.nan).reset_index()
    t = a.tail(1)
    h = a.head(-1)
    data = pd.concat([t,h], ignore_index=True)
    data.columns = data.iloc[0]

    return data