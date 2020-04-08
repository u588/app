import pandas as pd
import talib as tb
from sqlalchemy import create_engine

# IndexsList= ['sh000001', 'sh000300',  'sh000016',
#  'sh000905', 'sz399314', 'sz399315', 'sz399316', 'sz399106',
#   'sz399007', 'sz399008']

eng = create_engine('postgresql+psycopg2://sa:11111111@10.3.18.56:5432/tdxIndexs')

data = pd.read_excel('F:/IndexsData/tdxIndexLists.xls', dtype={'code':object})
IndexsList = data.code.tolist()

def getDescriIndex(IndexCode, IndexName):
	data = pd.read_sql(IndexCode, eng)[['datetime', 'open', 'high', 'low', 'close', 'vol']]
	data['pre_close']=data.close.shift(1)
	ADOSC = tb.ADOSC(data.high, data.low, data.close, data.vol, fastperiod=5, slowperiod=21)
	data['ADOSC'] = ((ADOSC-ADOSC.mean())/ADOSC.std()).round(2)
	data['pc_chg']=((data.close-data.pre_close)/data.pre_close)*100
	data['open_chg']=((data.open-data.pre_close)/data.pre_close)*100
	data['day_chg']=((data.close-data.open)/data.open)*100

	data['sum3']=tb.SUM(data.pc_chg, timeperiod=3)
	data['sum5']=tb.SUM(data.pc_chg, timeperiod=5)
	data['sum8']=tb.SUM(data.pc_chg, timeperiod=8)
	data['sum13']=tb.SUM(data.pc_chg, timeperiod=13)
	data['sum21']=tb.SUM(data.pc_chg, timeperiod=21)
	data['sum34']=tb.SUM(data.pc_chg, timeperiod=34)
	data['sum55']=tb.SUM(data.pc_chg, timeperiod=55)
	data['sum89']=tb.SUM(data.pc_chg, timeperiod=89)
	data['sum144']=tb.SUM(data.pc_chg, timeperiod=144)
	data['sum233']=tb.SUM(data.pc_chg, timeperiod=233)
	
	DescrIndex = data.describe().drop(['vol','open','close','high','low','pre_close'], 
				axis=1).round(2).T.drop('count',axis=1)

	DescrIndex['code'] = IndexCode
	DescrIndex['name'] = IndexName
	return (DescrIndex, data)

# IndexCode='399621'
df = pd.DataFrame(columns=['A'])
for i , IndexCode in enumerate(IndexsList):
	IndexName=data.loc[data['code']==IndexCode].name.tolist()[0]
	(DescriSet, DataSet)=getDescriIndex(IndexCode, IndexName)
	DataSet.to_csv('f:/IndexsData/'+IndexCode+'.csv')
	DescriSet.to_csv('f:/IndexsData/'+ IndexName+'Descr.csv')
	df = df.append(DescriSet)
	print(IndexCode,'appended!')

df.drop('A',axis=1, inplace=True)
df.to_csv('f:/IndexsData/Descr.csv', encoding='utf8')