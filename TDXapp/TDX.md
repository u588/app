## TDX
* https://rainx.gitbooks.io/pytdx/content/pytdx_exhq.html

### 标准行情

``` python
from pytdx.hq import TdxHq_API
api = TdxHq_API()

api.connect('180.153.18.170', 7709)

```
#### 股票行情

#### 股票数量

* 0 - 深圳， 1 - 上海
* api.get_security_count(0)

#### 股票列表
* (市场代码, 起始位置)
* api.get_security_list(1, 0)

#### 股票实时行情
* api.get_security_quotes([(0, '000001'), (1, '600300')])

#### 股票k线
* category
``` txt
K线种类
0 5分钟K线 1 15分钟K线 2 30分钟K线 3 1小时K线 4 日K线
5 周K线
6 月K线
7 1分钟
8 1分钟K线 9 日K线
10 季K线
11 年K线
```
* market -> 市场代码 0:深圳，1:上海
* stockcode -> 证券代码;
* start -> 指定的范围开始位置;
* count -> 用户要请求的 K 线数目，最大值为 800
* api.get_security_bars(9,0, '000001', 4, 3)

#### 指数k线
* category
``` text
K线种类
0 5分钟K线 1 15分钟K线 2 30分钟K线 3 1小时K线 4 日K线
5 周K线
6 月K线
7 1分钟
8 1分钟K线 9 日K线
10 季K线
11 年K线
```
* market -> 市场代码 0:深圳，1:上海
* stockcode -> 证券代码;
* start -> 指定的范围开始位置;
* count -> 用户要请求的 K 线数目，最大值为 800
* api.get_index_bars(9,1, '000001', 1, 2)

### 扩展行情
```python
from pytdx.exhq import TdxExHq_API
eapi = TdxExHq_API()

eapi.connect('47.112.95.207', 7720)
```

#### 市场代码
* 中证market-62 国证market-102
* eapi.get_markets()

#### 查询数量
* api.get_instrument_count()

#### 查询代码列表
* (起始位置,获取数量)
* eapi.get_instrument_info(0, 100)

#### 五档行情
* （市场ID，证券代码）
* api.get_instrument_quote(47, "IF1709")

#### 查询k线
* （K线周期， 市场ID， 证券代码，起始位置， 数量）
* api.get_instrument_bars(9, 102, "10000843", 0, 100)


