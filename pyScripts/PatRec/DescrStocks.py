import pandas as pd
import talib as tb
import data_fq  as fq
from sqlalchemy import create_engine

# StocksList= ['sh000001', 'sh000300',  'sh000016',
#  'sh000905', 'sz399314', 'sz399315', 'sz399316', 'sz399106',
#   'sz399007', 'sz399008']
# StocksList =['603686']
engS = create_engine('postgresql+psycopg2://sa:11111111@10.3.18.56:5432/tdxStocks')
engX = create_engine('postgresql+psycopg2://sa:11111111@10.3.18.56:5432/tdxXdXr')

data = pd.read_csv('f:/stocksdata/stockslist.csv', index_col=0,dtype={'code':object})
StocksList = data.code.tolist()

def getDescrStock(StockCode, StockName):
	Data = pd.read_sql(StockCode, engS)
	XdXr = pd.read_sql(StockCode, engX)
	data = fq.qfq(Data, XdXr)[['open', 'high', 'low', 'close', 'vol']].tail(-10).reset_index()
	data['pre_close']=data.close.shift(1)

	data['pc_chg']=((data.close-data.pre_close)/data.pre_close)*100
	data['open_chg']=((data.open-data.pre_close)/data.pre_close)*100
	data['day_chg']=((data.close-data.open)/data.open)*100
	data.loc[abs(data.pc_chg)>11, 'pc_chg']=0.0
	data.loc[abs(data.open_chg)>11, 'open_chg']=0.0
	
	ADOSC = tb.ADOSC(data.high, data.low, data.close, data.vol, fastperiod=5, slowperiod=21)
	data['ADOSC'] = ((ADOSC-ADOSC.mean())/ADOSC.std()).round(2)
	

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
	
	DescrStock = data.describe().drop(['vol','open','close','high','low','pre_close'], 
				axis=1).round(2).T.drop('count',axis=1)

	DescrStock['code'] = StockCode
	DescrStock['name'] = StockName
	return (DescrStock, data)

# StockCode='399621'
df = pd.DataFrame(columns=['A'])
for i , StockCode in enumerate(StocksList):
	StockName=data.loc[data['code']==StockCode].name.tolist()[0].replace('*', '')
	(DescriSet, DataSet)=getDescrStock(StockCode, StockName)
	DataSet.to_csv('f:/StocksData/'+StockCode+'.csv')
	DescriSet.to_csv('f:/StocksData/' +StockCode+StockName+'Descr.csv')
	df = df.append(DescriSet)
	print(StockCode,'appended!')
	# if i>5:
	# 	break

df.drop('A',axis=1, inplace=True)
df.to_csv('f:/StocksData/Descr.csv', encoding='utf8')