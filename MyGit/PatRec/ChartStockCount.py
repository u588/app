import pandas as pd
import datetime
import os
from pyecharts import Bar

path = "f:/FindStocks/" #文件夹目录
files= os.listdir(path) #得到文件夹下的所有文件名称
today = datetime.date.today().strftime('%Y%m%d')

df = pd.DataFrame(columns=['code'])
for file in files: #遍历文件夹
    Data = pd.read_csv(path + file, header=None, names=['code'], dtype={'code':str})
    df = df.append(Data, ignore_index=True)


df['Count'] = 1

D = df.groupby('code').count()

bar = Bar('StocksCount', height=600, width=1300, page_title= today+'StocksCount')
bar.add('Count', D.index.tolist(), D.Count.tolist(), mark_point=['max'],
        is_label_show=True, is_datazoom_show=True)

bar.render('F:/WWWStocks/'+today + 'StocksCount.html')
print('Chart OK !')