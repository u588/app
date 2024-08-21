import pandas as pd
from sqlalchemy import create_engine
import streamlit as st

eng = create_engine('postgresql+psycopg2://sa:11111111@10.3.18.56/tdxFS')

FSCode = pd.read_sql('FSCode',eng)
stockCode = '000017'
day = 20240331

finRAW = pd.read_sql(stockCode, eng)
finRAW = pd.concat([finRAW,finRAW['report_date'].rename('Index')],axis=1)
trsfin = finRAW.set_index('Index').T
trsfin = trsfin.reset_index().rename(columns={'index':'Code'})

sfin = pd.merge(FSCode,trsfin,on='Code',how='inner')

ll = ['Index','L1Code','L1Name','L2Code','L2Name','L3Code','L3Name','Code','cnName']
fin = pd.concat([sfin[ll],sfin[day].rename('vol')],axis=1)
items = fin.cnName.to_list()
sumite = [item for item in items if any(substr in item for substr in "万")]

for ite in sumite:
    fin.loc[fin.cnName==ite,"vol"] = fin[fin.cnName==ite]["vol"]*10000
zcfz = fin.query('L1Code=="ZCFZ" and L3Code!="EMP" and L3Code!="HJ"')

zcfz = zcfz[~(zcfz["vol"]==0)].reset_index(drop=True)
# zcfz.loc[:,"vol"]=abs(zcfz["vol"])
for i,ite in enumerate(zcfz.vol.to_list()):
    if ite < 0:
        zcfz.loc[i,'cnName'] ='负：'+ zcfz.loc[i,'cnName']
        zcfz.loc[i,'vol'] = abs(ite) 
    else:
        pass



import plotly.express as px

fig = px.sunburst(zcfz, path=['L2Name','L3Name','cnName'], values="vol")
fig.update_layout(title=stockCode)

tab1, tab2 = st.tabs([stockCode+' : '+str(day)+" : Streamlit theme (default)", stockCode+" : Plotly native theme"])
with tab1:
    st.plotly_chart(fig, theme="streamlit")
with tab2:
    st.plotly_chart(fig, theme=None)