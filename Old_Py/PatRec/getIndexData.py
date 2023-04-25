import pandas as pd
import talib as tb
import tushare as ts

IndexsList= ['sh000001', 'sh000300',  'sh000016',
 'sh000905', 'sz399314', 'sz399315', 'sz399316', 'sz399106',
  'sz399007', 'sz399008']
# IndexsList = pd.read_excel('/home/ts/app/www/html/IndexsList.xls')
# Index = IndexsList.loc[IndexsList['code']==Id]
def getData(Code):
	
	data = ts.get_k_data(Code[2:], index='True')

	data['pre_close']=data.close.shift(1)
	ADOSC = tb.ADOSC(data.high, data.low, data.close, data.volume, fastperiod=5, slowperiod=21)
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
	

	return data

for i, IndexCode in enumerate(IndexsList):
	try:
		
		data = getData(IndexCode)
		data.to_csv('f:/IndexsData/'+IndexCode[2:]+'.csv')
		print(IndexCode, '写入磁盘')
		sleep(2)
	except:
	    pass
