from __future__ import print_function, absolute_import
from gm.api import *


# 可以直接提取数据，掘金终端需要打开，接口取数是通过网络请求的方式，效率一般，行情数据可通过subscribe订阅方式
# 设置token， 查看已有token ID,在用户-秘钥管理里获取
set_token('987f30801b7ce443345b749a78bc03e292d985ec')

# 查询历史行情, 采用定点复权的方式， adjust指定前复权，adjust_end_time指定复权时间点
d1 = get_instrumentinfos(symbols=None, exchanges="SHSE", sec_types=1, names=None, fields=None, df=True)
d1['listed_date'] = d1['listed_date'].dt.tz_localize(None)
d1['delisted_date'] = d1['delisted_date'].dt.tz_localize(None)
d1.to_excel('j:/myqut/d1.xlsx')

d3 = get_instrumentinfos(symbols=None, exchanges="SHSE", sec_types=3, names=None, fields=None, df=True)
d3['listed_date'] = d3['listed_date'].dt.tz_localize(None)
d3['delisted_date'] = d3['delisted_date'].dt.tz_localize(None)
d3.to_excel('j:/myqut/d3.xlsx')

dd1 = get_instrumentinfos(symbols=None, exchanges="SZSE", sec_types=1, names=None, fields=None, df=True)
dd1['listed_date'] = dd1['listed_date'].dt.tz_localize(None)
dd1['delisted_date'] = dd1['delisted_date'].dt.tz_localize(None)
dd1.to_excel('j:/myqut/dd1.xlsx')

dd3 = get_instrumentinfos(symbols=None, exchanges="SZSE", sec_types=3, names=None, fields=None, df=True)
dd3['listed_date'] = dd3['listed_date'].dt.tz_localize(None)
dd3['delisted_date'] = dd3['delisted_date'].dt.tz_localize(None)
dd3.to_excel('j:/myqut/dd3.xlsx')

g = get_instrumentinfos(symbols=None, exchanges="", sec_types=1, names=None, fields=None, df=True)
g['listed_date'] = g['listed_date'].dt.tz_localize(None)
g['delisted_date'] = g['delisted_date'].dt.tz_localize(None)
g.to_excel('j:/myqut/g.xlsx')

z = get_instrumentinfos(symbols=None, exchanges="", sec_types=3, names=None, fields=None, df=True)
z['listed_date'] = z['listed_date'].dt.tz_localize(None)
z['delisted_date'] = z['delisted_date'].dt.tz_localize(None)
z.to_excel('j:/myqut/z.xlsx')







"查询指数最新成份股"
get_constituents(index='SHSE.000001', fields='symbol, weight', df=True)

" 查询基本面数据"
get_fundamentals(table, symbols, start_date, end_date, fields=None, filter=None, order_by=None, limit=1000, df=False)

data = history(symbol='SHSE.600000', frequency='1d', start_time='2020-01-01 09:00:00', end_time='2020-12-31 16:00:00',
               fields='open,high,low,close', adjust=ADJUST_PREV, adjust_end_time='2020-12-31', df=True)
print(data)