# ===================== 扩展接口 ======================

from pytdx.exhq import TdxExHq_API
import pandas as pd
from sqlalchemy import create_engine


api =  TdxExHq_API()
api = TdxExHq_API(heartbeat=True)


api.connect('182.175.240.157', 7727)

api.get_instrument_count()
api.to_df(api.get_markets())

MacroIndexCN = api.to_df(api.get_instrument_info(72093, 500)).head(104)

zzIndex = api.to_df(api.get_instrument_info(79800, 741)).tail(652)

gzIndexs = api.to_df(api.get_instrument_info(98600, 100)).tail(14)

98766
start = 0
df = api.to_df(api.get_instrument_info(0, 1))
df.drop(index=df.index, inplace=True)
while start < 99000:
    df1 = api.to_df(api.get_instrument_info(start, 500))
    start = start + 500
    df = pd.concat([df,df1])

df[['category','market','code','name']].to_excel('/home/ts/tdxRawMark.xlsx')



api.to_df(api.get_instrument_bars(9, 62, "000809", 0, 100))




# ===================== 标准接口 ======================


from pytdx.hq import TdxHq_API
import pandas as pd
from sqlalchemy import create_engine

api = TdxHq_API()
api = TdxHq_API(heartbeat=True)
api = TdxHq_API(auto_retry=True)

api.connect('119.147.212.81', 7709)


#  1 - 上海（21299）

df = api.to_df(api.get_security_list(1, 517))
df.drop(index=df.index, inplace=True)
start = 517
while start < 30000:
    df1 = api.to_df(api.get_security_list(1, start))
    start = start + 1000
    df = pd.concat([df,df1])


# 0 - 深圳（16462）

df = api.to_df(api.get_security_list(0, 0))
df.drop(index=df.index, inplace=True)
start = 0
while start < 20000:
    df1 = api.to_df(api.get_security_list(0, start))
    start = start + 1000
    df = pd.concat([df,df1])



# 数据处理
df[df.duplicated()]
df[df.drop_duplicates(subset=['',''])]



#====================== Reader ==================

from pytdx.reader import BlockReader

BlockReader().get_df("D:/new_tdx/T0002/hq_cache/block_fg.dat").to_excel('F:/FinaDataRaw/TDXdata/App_hq_cache/fgRaw.xlsx')

pd.read_excel('F:/FinaDataRaw/TDXdata/App_hq_cache/zsRaw.xlsx',dtype={'code':'object'})



# ===================== re =======================
import re
import pandas as pd

f = open('j:/tdxRawData/shm.txt', 'r',encoding='utf-8')

ls = f.readlines()
n = len(ls)
i = 0
f.close
l = []
while i < n :
    
    try:
        # ll = re.findall('[3,0][0-9]{5}.{25}', ls[i]) 
        ll = re.findall('[8,,6,0][0-9]{5}.{25}', ls[i])
        ## 深圳 3，0开头， 上海 0，8，6开头
        i = i+1
        l = l+ll
    except:
        pass

n = len(l)
i=0

lns = []
lcs = []

while i < n:
    try:
        ln = l[i].split()
        # lc = l[i].split()
        i = i+1
        print(i)
        lns = lns + ln
        # lcs = lcs + lc
    except:
        pass         

df = pd.DataFrame(columns=['code','name'])

n = len(lns)
i = 0

while i< n:
    try:
        df.loc[i,'code'] = lns[i]
        df.loc[i, 'name'] = lns[i+1]
        print(i)
        i = i+2
    except:
        pass











#=================================

while i < n:
   
    try:
        ln = re.findall('[0-9]{6}', l[i])
        lc = re.findall('[\u4e00-\u9fa5].{6}|[*ST].{6}|[ST].{6}',l[i])
        i=i+1
        lns = lns + ln
        lcs = lcs + lc 
    except:
        pass








re.findall('[3,0][0-9]{5}.{25}', ls[21])
re.findall('[\u4e00-\u9fa5].{6}',l[280])