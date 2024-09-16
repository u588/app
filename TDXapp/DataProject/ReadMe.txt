======== tdx 服务器 ========
std: '180.153.18.170', 7709
     '110.41.147.114', 7709

ext: '182.175.240.157', 7727
     '47.112.95.207', 7720

/new_tdx/connect.cfg

======== mootdx包 =========
https://github.com/mootdx/mootdx?tab=readme-ov-file
https://www.mootdx.com/zh-cn/latest/quick/
pip show mootdx
注销 ==> quotes.py  518行 logger.warning

======== 初始化 ============
mootdx bestip


ext  client.bars(9,62,'H50055', 0, 100) 扩展行情查询 

F10资料 
from mootdx.quotes import Quotes
client = Quotes.factory(market='std')
a = client.F10C(symbol='000001')
file = open('g:/1.txt', 'w')
n= 0
while n < 16:
    file.write(client.F10('600996',a[n].get('name')))
    n = n+1

client.F10(symbol='000001', name='最新提示')


dict.get(list(dict.key())[x])


=========== 代码 ============
1、深圳
    股票    主板00 创业板30
    指数    39    
    2、上海
    股票    主板60 科创板68    
    指数    00 88 



1、StockCode来源
通达信软件 J:\new_tdx\T0002\hq_cache\
infoharbor*


2、csIndexs及成分股 来源
https://www.csindex.com.cn/#/indices/family/list -->导出列表

3、tdxBolckIndexs及成分股 来源
通达信软件 -->选项 -->数据导出-->板块导出

4、tdxIndex 来源
中证指数  -->其他-->中证指数--> 导出数据
通达信软件 J:\new_tdx\T0002\hq_cache\
shm.tnf  szm.tnf 


======================= 每年 6.20  12.20 日 更新 =====================
1、中证列表(2)导出 编辑后存==> G:/Gitee/App/TDXapp/tdxAppData/csIndex.xlsx
2、tdx板块列表(3)导出后 运行==>       python  G:\Gitee\App\TDXapp\DataProject\tdxBLKIndex_StcokCode.py
3、tdx中证指数列表(4)导出 编辑后存==> G:/Gitee/App/TDXapp/tdxAppData/tdxZZindexs.xlsx
4、tdx上证、深证指数列表生成 运行==>   python G:\Gitee\App\TDXapp\DataProject\tdxSHSZIndex.py

5、生成指数列表 运行==>               python G:\Gitee\App\TDXapp\DataProject\IndexMerg.py
6、生成最终指数列表  更新数据库 ==>    python G:\Gitee\App\TDXapp\DataProject\Finalndex.py
7、获取cs成分股列表 ==>               python G:\Gitee\App\TDXapp\pgTDXCons.py
8、生成股票成分股 更新数据库==>        python G:\Gitee\App\TDXapp\MergeCsTdxCons.py

9、最终指数列表，由于在指数获取时服务器返回数据为空，需优化列表。 
        ==>  python G:\Gitee\App\TDXapp\optIndex.py

============================ tdx 历史专业财务数据 1231 0930 0630 0331  =====================

1、获取历史专业财务数据列表

import pandas as pd
from pytdx.hq import TdxHq_API
from pytdx.crawler.history_financial_crawler import HistoryFinancialListCrawler

api = TdxHq_API()
api.connect('119.147.212.81', 7709)

crawler = HistoryFinancialListCrawler()
list_data = crawler.fetch_and_parse()
print(pd.DataFrame(data=list_data))

2024.5.12  --> gpcw20240331.zip 4786722
2024.6.21  --> gpcw20240331.zip 4788337
并入======== /home/ts/app/TDXapp/MtdxGetFS.py 


2、手动更新数据库数据 
    更改以下程序中 ls = ["gpcwxxxxxxx.zip"]
python G:\Gitee\App\TDXapp\MtdxGetFS.py



