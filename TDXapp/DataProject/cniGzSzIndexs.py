import pandas as pd
import requests

# szlist = [['100','规模'],['101','行业'],['102','风格'],['103','主题'],['104','策略'],['105','综合'],['108','定制指数']]

url = "http://www.cnindex.com.cn/index/indexList"
params = {
    "channelCode": "-1",
    "rows": "2000",
    "pageNum": "1",
}

r = requests.get(url, params=params)
data_json = r.json()

rawDF = pd.DataFrame(data_json["data"]["rows"])[['indexcode','indextype','indexname','samplesize','sampleshowdate']]
rawDF['IndexSTL']='STL'

rawDF.loc[rawDF['indextype'].str.contains('00'),'IndexSTL'] = '规模'
rawDF.loc[rawDF['indextype'].str.contains('01'),'IndexSTL'] = '行业'
rawDF.loc[rawDF['indextype'].str.contains('02'),'IndexSTL'] = '风格'
rawDF.loc[rawDF['indextype'].str.contains('03'),'IndexSTL'] = '主题'
rawDF.loc[rawDF['indextype'].str.contains('04'),'IndexSTL'] = '策略'
rawDF.loc[rawDF['indextype'].str.contains('05'),'IndexSTL'] = '综合'
rawDF.loc[rawDF['indextype'].str.contains('08'),'IndexSTL'] = '定制指数'

df = rawDF[~(rawDF['IndexSTL']=='STL')].rename(columns={'indexcode':'IndexCode','indexname':'IndexName','samplesize':'Num','sampleshowdate':'DP'})
df['MarketName'] = 'SZ'
df.loc[df['indextype'].str.startswith('2'), 'MarketName'] = 'GZ'
df['From'] = 'CNI'
df.drop('indextype',axis=1).set_index('IndexCode').to_excel('G:/Gitee/App/TDXapp/tdxAppData/cniGzSzIndexs.xlsx')
print('OK !')