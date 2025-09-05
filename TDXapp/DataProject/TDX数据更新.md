# TDX 数据更新

## 每年 6、12月 第三个星期日 更新股指数据

## 以下程序在PC上完成

### 1、中证列表导出->编辑后存（csIndex.xlsx）

* <https://www.csindex.com.cn/#/indices/family/list> -->导出列表(中证、上证、深证、中基协。综合指数-人民币)

|IndexCode|IndexName|MarketName|Num|IndexSTL|From|
|-----|-------|-------|-------|------|----------|
|指数代码|指数简称|指数系列|样本数量|指数类别|CS|

G:/Gitee/App/TDXapp/tdxAppData/csIndex.xlsx

### 2、tdx软件，板块列表导出后->运行(tdxIndexsBLK.xlsx tdxIndexsConsBLK.xlsx)

* 通达信软件 -->选项(眉头) -->数据导出-->板块导出(逗号分隔)

```bash  

python G:\Gitee\App\TDXapp\DataProject\tdxBLKIndex_StcokCode.py

```

### 3、tdxApi，生成中证、国证指数列表(tdxApiZzGzIndexs.xlsx)

```bash

python G:\Gitee\App\TDXapp\DataProject\tdxApiZzGzIndex.py

```

### 4、tdx软件，生成上证、深证指数列表(tdxShSzIndexs.xlsx)

```bash

python G:\Gitee\App\TDXapp\DataProject\tdxShSzIndex.py

```

### 5、获取akshare, 股指DP(akIndexDP.xlsx)

```bash

python G:\Gitee\App\TDXapp\DataProject\akIndexsDP.py

```
### 6、国证网获取深证、国证指数数据

* <https://www.cnindex.com.cn/>

```bash

python G:\Gitee\App\TDXapp\DataProject\cniGzSzIndexs.py

```

### 6、生成指数列表(tdxIndexs.xlsx)

```bash

python G:\Gitee\App\TDXapp\DataProject\IndexMerg.py

```

### 7、编辑（tdxIndexs.xlsx），生成（dropIndexs.xlsx empIndexs.xlsx）

* 编辑生成的此两表不用大动
* 需要去除的指数添加入（dropIndexs.xlsx）
* 需要不参加后期指数成分股获得的加入（empIndexs.xlsx）

### 8、优化指数列表(optIndexs.xlsx)

```bash

python G:\Gitee\App\TDXapp\DataProject\optlndex.py

```

## 以下程序在Linux完成

### 7、获取akshare成分股列表(akIndexCons),存入数据库

* 执行程序，由于网站保护需多次执行
* 初始化

```bash

python /home/ts/app/TDXapp/DataProject/akGetIndexCons.py

```

* 多次执行，获取全部数据

```bash

python /home/ts/app/TDXapp/DataProject/akGetIndexConsB.py

```

### 8、生成最终股指列表（FinaIndexs.xlsx） 更新数据库（optIndexs）

* 由于历史原因服务器中为（FinaIndexs.xlsx），数据库中为（optIndexs）

```bash

python /home/ts/app/TDXapp/DataProject/Finalndex.py

```

### 9、生成最终股指成分股，更新数据库（IndexCons）

```bash
python /home/ts/app/TDXapp/DataProject/ConsMerg.py

```


## === 每年 4、8月 第三个星期日 更新个股财务数据

### 10、tdx个股题材相关度 {Top}

```bash

python G:\Gitee\App\TDXapp\tdxGetTop.py
python /home/ts/app/TDXapp/tdxGetTop.py
```

### 11、tdx个股主营占比及前五大合作商占比 {mBiz,BizP}

* 年报集中披露时间: 3月下旬至4月中旬（占全年披露量的70%以上）(4.30最终披露截止日)
* 半年报集中披露时间: 7月下旬至8月中下旬（尤其最后一周为高峰期）(8.31最终披露截止日)

```bash

python G:\Gitee\App\TDXapp\tdxGetBiz.py

python /home/ts/app/TDXapp/tdxGetBiz.py

```

### 12、tdx个股3年业绩预测 {Fcast}


```bash

python G:\Gitee\App\TDXapp\tdxGetFcast.py

python /home/ts/app/TDXapp/tdxGetFcast.py
```

## ======== tdx 服务器

### tdx 服务器

* std:
  * '180.153.18.170', 7709
  * '110.41.147.114', 7709

* ext:
  * '182.175.240.157', 7727 2024.9.30废弃
  * '47.112.95.207', 7720

/new_tdx/connect.cfg

### mootdx包

* <https://github.com/mootdx/mootdx?tab=readme-ov-file>
* <https://www.mootdx.com/zh-cn/latest/quick/>

pip show mootdx  
注销 ==> quotes.py  518行 logger.warning

* 初始化

mootdx bestip  
/home/ts/.mootdx/config.json  
ext  client.bars(9,62,'H50055', 0, 100) 扩展行情查询

```python F10资料

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

```

## 代码

### 1、深圳

```txt
    股票:   主板 00  创业板 30  
    指数:   39
```

### 2、上海

```txt

    股票:  主板 60  科创板 68
    指数:  00 88

```

## ===========================

## tdx 历史专业财务数据 1231 0930 0630 0331

### 1、获取历史专业财务数据列表

/home/ts/app/TDXapp/MtdxGetFS.py

```python

import pandas as pd
from pytdx.hq import TdxHq_API
from pytdx.crawler.history_financial_crawler import HistoryFinancialListCrawler

api = TdxHq_API()

# api.connect('119.147.212.81', 7709) 2024.9.30废弃

api.connect('180.153.18.170', 7709)

crawler = HistoryFinancialListCrawler()
list_data = crawler.fetch_and_parse()
print(pd.DataFrame(data=list_data))

```

2024.5.12  --> gpcw20240331.zip 4786722  
2024.6.21  --> gpcw20240331.zip 4788337  
并入---> /home/ts/app/TDXapp/MtdxGetFS.py

### 2、手动更新数据库数据

更改以下程序中 ls = ["gpcwxxxxxxx.zip"]

```bash

python G:\Gitee\App\TDXapp\MtdxGetFS.py

```
