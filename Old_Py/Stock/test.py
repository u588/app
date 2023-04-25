import pandas as pd
import matplotlib.pyplot as plt


df = pd.read_csv('f:/qutdata/test.csv',index_col='date')
df.index = pd.DatetimeIndex(df.index)
df1 = df.tail(100)

f, ((ax1, ax2)) = plt.subplots(2, 1, sharex=True)
#plt.figure()
#ax1.plot(df1[['MACD', 'MACDsignal']])
plt.bar(df1.index, df1.MACDhist)


plt.show()