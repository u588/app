import pandas as pd
from sqlalchemy import create_engine
import streamlit as st

eng = create_engine('postgresql+psycopg2://sa:11111111@10.3.18.56/tdxFS')
engB = create_engine('postgresql+psycopg2://sa:11111111@10.3.18.56/StockBas')
StockIC = pd.read_sql("StockIC", engB)

StockCode = '600256'
day = 20240331

l4name = StockIC[StockIC['StockCode']==StockCode]['L4Name'].tolist()[0]



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
desel = mfin[mfin['L4Name']==l4name].describe().T
fin = GetFin(StockCode,day)

anafin = fin.query('L1Code=="CZNL" and L3Code!="EMP"')

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
      name='20240331'
))

fig.update_layout(
  polar=dict(
    radialaxis=dict(
      visible=True,
      range=[round((min(anafin.vol)-(3*lens)),2), max(anafin.vol)+lens]
    )),
  showlegend=False
)

tab1, tab2 = st.tabs([StockCode+' : '+str(day)+" : Streamlit theme (default)", StockCode+" : Plotly native theme"])
with tab1:
    st.plotly_chart(fig, theme=None)
with tab2:
    st.plotly_chart(fig, theme=None)

