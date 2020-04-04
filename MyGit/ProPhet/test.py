import pandas as pd
from fbprophet import Prophet
import matplotlib.pyplot as plt

df = pd.read_csv('f:/indexone.csv')[['datetime', '000001']].tail(365)
df = pd.read_csv('f:/stocksone.csv')[['datetime', '600409']].tail(500)
df.columns = ['ds', 'y']
m = Prophet()
m.fit(df)
future = m.make_future_dataframe(periods=100)
m = Prophet(changepoint_prior_scale=0.15, ).fit(df)
future = m.make_future_dataframe(periods=500, freq='5min')
future2 = future.copy()
future2.ds= pd.to_datetime(future2.ds)

future2 = future2[(future2['ds'].dt.hour>9) | (future2['ds'].dt.hour<15)]

future = future[future['ds'].dt.weekday<5]

fcst = m.predict(future)
fig1 = m.plot_components(fcst)
fig = m.plot(fcst)

plt.show()

