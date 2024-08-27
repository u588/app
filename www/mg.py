import pandas as pd
from sqlalchemy import create_engine
import streamlit as st

eng = create_engine('postgresql+psycopg2://sa:11111111@10.3.18.56/tdxFS')
engB = create_engine('postgresql+psycopg2://sa:11111111@10.3.18.56/StockBas')
StockIC = pd.read_sql("StockIC", engB)

StockCode = '688349'
day = 20231231

l4name = StockIC[StockIC['StockCode']==StockCode]['L4Name'].tolist()[0]
StockName = StockIC[StockIC['StockCode']==StockCode]['StockName'].tolist()[0]


def GetFin(StockCode, day):
    finRAW = pd.read_sql(StockCode, eng)
    finRAW['report_date']=finRAW['report_date'].astype(object)
    finRAW = pd.concat([finRAW,finRAW['report_date'].rename('Index')],axis=1)
    trsfin = finRAW.set_index('Index').T
    trsfin = trsfin.reset_index().rename(columns={'index':'Code'})
    FSCode = pd.read_sql('FSCode',eng)
    sfin = pd.merge(FSCode,trsfin,on='Code',how='inner')
    ll = ['Index','L1Code','L1Name','L2Code','L2Name','L3Code','L3Name','Code','cnName']
    fin = pd.concat([sfin[ll],sfin[day].rename('vol')],axis=1)
    items = fin.cnName.to_list()
    sumite = [item for item in items if any(substr in item for substr in "万")]
    for ite in sumite:
        fin.loc[fin.cnName==ite,"vol"] = fin[fin.cnName==ite]["vol"]*10000
    return fin

finF = pd.read_sql('gpcw'+str(day), eng)
mfin = pd.merge(finF,StockIC, left_on='code',right_on='StockCode', how='inner')
mfinsel = mfin[mfin['L4Name']==l4name]
desel = mfin[mfin['L4Name']==l4name].describe().T
fin = GetFin(StockCode,day)

tasel = mfinsel[['StockCode','StockName','L1Name','L2Name','L3Name','L4Name']]

anafin = fin.query('L1Code=="FZNL" and L3Code!="EMP"')

data = pd.merge(anafin, desel.reset_index(drop=False),left_on='Code',right_on='index',how='inner')

lens = (max(data['mean'])-min(data['mean']))/2

import plotly.graph_objects as go

categories = data.cnName.tolist()

fig = go.Figure()

fig.add_trace(go.Scatterpolar(
      r=data['mean'].tolist(),
      theta=categories,
      fill='toself',
      name='mean'
))
fig.add_trace(go.Scatterpolar(
      r=data.vol.tolist(),
      theta=categories,
      fill='toself',
      name=StockCode
))

fig.update_layout(
  polar=dict(
    radialaxis=dict(
      visible=True,
      range=[round((min(anafin.vol)-(3*lens)),2), max(anafin.vol)+lens]
    )),
  showlegend=False
)

fig1 = go.Figure(data=[go.Table(
        header=dict(values=list(tasel.columns)),
        cells=dict(values=[tasel.StockCode,tasel.StockName,tasel.L1Name,tasel.L2Name,tasel.L3Name,tasel.L4Name]))
                        ])

tab1, tab2 = st.tabs([StockCode+' : 共'+str(len(tasel))+"支", StockName+' : '+data['L1Name'].head(1).tolist()[0]])
with tab1:
    st.plotly_chart(fig1, theme=None)
with tab2:
    st.plotly_chart(fig, theme=None)

