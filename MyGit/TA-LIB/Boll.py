import pandas as pd 
import numpy as np 
import talib as ta 
import matplotlib.pyplot as plt 
from matplotlib import rc 
rc('mathtext', default='regular') 
import seaborn as sns
sns.set_style('white') 
from matplotlib import dates 
import matplotlib as mpl 
# %matplotlib inline 
myfont =mpl.font_manager.FontProperties(fname=r"c:\windows\fonts\simsun.ttc",size=14) 
from sqlalchemy import create_engine

home = '10.145.254.55:5432'
job = '10.3.18.55:5432'
ip = job

eng = create_engine('postgresql+psycopg2://sa:11111111@' + ip + '/tdxStocks')

plt.rcParams["figure.figsize"] = (14,7) 
stock = '603843'


dw = pd.read_sql(stock, eng).tail(500)
dw.dropna(inplace=True)
dw.datetime = dw.datetime.str.replace('15:00', '')
dw.set_index('datetime', inplace=True)
dw.index = pd.DatetimeIndex(dw.index)

dw['upper'], dw['middle'], dw['lower'] = ta.BBANDS(dw.close.values, timeperiod=55, 
                        # number of non-biased standard deviations from the mean 
                        nbdevup=2, nbdevdn=2, 
                        # Moving average type: simple moving average here 
                        matype=0)


fig = plt.figure(figsize=(14,7)) 
fig.set_tight_layout(True) 
ax1 = fig.add_subplot(111) 
# ax1.bar(dw.index, dw.vol, align='center', width=1.0) 
ax1.plot(dw.close, '-', color='g')
 
ax2 =ax1
ax2.plot(dw.upper, '-', color='r') 
ax2.plot(dw.lower, '-', color='r') 
ax2.plot(dw.middle, '-.', color='b') 

ax1.set_ylabel(u"股票价格(绿色)",fontproperties=myfont, fontsize=16) 
ax2.set_ylabel(u"布林带",fontproperties=myfont, fontsize=16) 
ax1.set_title(u"绿色是股票价格，红色（右轴）布林带",fontproperties=myfont, fontsize=16) 
# plt.xticks(bar_data.index.values, bar_data.barNo.values) 
ax1.set_xlabel(u"布林带",fontproperties=myfont,fontsize=16) 

ax1.grid()
# plt.xlim('2018-01-01', '2019-01-01') 
plt.show()

