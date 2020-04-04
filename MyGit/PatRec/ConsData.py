import pandas as pd
import talib as tb
import data_fq  as fq
from sqlalchemy import create_engine

# StocksList= ['sh000001', 'sh000300',  'sh000016',
#  'sh000905', 'sz399314', 'sz399315', 'sz399316', 'sz399106',
#   'sz399007', 'sz399008']
# StocksList =['002384']
Index = '930706_中证水泥'
engS = create_engine('postgresql+psycopg2://sa:11111111@10.3.18.55:5432/tdxStocks')
engX = create_engine('postgresql+psycopg2://sa:11111111@10.3.18.55:5432/tdxXdXr')

data = pd.read_excel('f:/ConsData/Cons/'+ Index + '.xls', index_col=0,dtype={'index_code':object, 'st_code':object})
StocksList = data.st_code.tolist()
IndexName = data.index_name.tolist()[1]

def getStocks(StockCode,StockName):	
	D = pd.read_sql(StockCode, engS)
	Data = D[D.datetime>'2000-01-01']
	X = pd.read_sql(StockCode, engX)
	XdXr = X[X.year>1999]

	data = fq.qfq(Data, XdXr)[['open', 'high', 'low', 'close', 'vol']].tail(-10).reset_index()
	data['st_code'] = StockCode
	data['st_name'] = StockName
	data['pre_close']=data.close.shift(1)

	data['pc_chg']=(((data.close-data.pre_close)/data.pre_close)*100).round(1)
	data['open_chg']=(((data.open-data.pre_close)/data.pre_close)*100).round(1)
	data['day_chg']=(((data.close-data.open)/data.open)*100).round(1)
	data.loc[abs(data.pc_chg)>11, 'pc_chg']=0.0
	data.loc[abs(data.open_chg)>11, 'open_chg']=0.0
	
	ADOSC = tb.ADOSC(data.high, data.low, data.close, data.vol, fastperiod=5, slowperiod=21)
	data['ADOSC'] = ((ADOSC-ADOSC.mean())/ADOSC.std()).round(2)

	data['ema5'] = tb.EMA(data.close, timeperiod=5).round(2)
	data['ema8'] = tb.EMA(data.close, timeperiod=8).round(2)
	data['ema21'] = tb.EMA(data.close, timeperiod=21).round(2)
	data['kama55'] = tb.KAMA(data.close, timeperiod=55).round(2)

	data['sum3']=tb.SUM(data.pc_chg, timeperiod=3).round(1)
	data['sum5']=tb.SUM(data.pc_chg, timeperiod=5).round(1)
	data['sum8']=tb.SUM(data.pc_chg, timeperiod=8).round(1)
	data['sum13']=tb.SUM(data.pc_chg, timeperiod=13).round(1)
	data['sum21']=tb.SUM(data.pc_chg, timeperiod=21).round(1)
	data['sum34']=tb.SUM(data.pc_chg, timeperiod=34).round(1)
	data['sum55']=tb.SUM(data.pc_chg, timeperiod=55).round(1)
	data['sum89']=tb.SUM(data.pc_chg, timeperiod=89).round(1)
	data['sum144']=tb.SUM(data.pc_chg, timeperiod=144).round(1)
	data['sum233']=tb.SUM(data.pc_chg, timeperiod=233).round(1)
	return (data)

# StockCode='399621'
df = pd.DataFrame(columns=['A'])
for i , StockCode in enumerate(StocksList):
	StockName=data.loc[data['st_code']==StockCode].st_name.tolist()[0]
	DataSet=getStocks(StockCode, StockName)
	df = df.append(DataSet, ignore_index=True, sort=False)
	print(StockCode,'appended!')
	# if i>5:
	# 	break

df.drop('A',axis=1, inplace=True)
df.to_csv('f:/StocksData/Cons/' +IndexName + '.csv', encoding='utf-8')