import pandas as pd
from sqlalchemy import create_engine
import streamlit as st

eng = create_engine('postgresql+psycopg2://sa:11111111@10.3.18.56/tdxFS')

FSCode = pd.read_sql('FSCode',eng)
stockCode = '600409'
day = 20240331

finRAW = pd.read_sql(stockCode, eng)
finRAW['Index']=finRAW['report_date']
trsfin = finRAW.set_index('Index').T
trsfin = trsfin.reset_index().rename(columns={'index':'Code'})

sfin = pd.merge(FSCode,trsfin,on='Code',how='inner')

ll = ['Index','L1Code','L1Name','L2Code','L2Name','L3Code','L3Name','Code','cnName',day]
fin = sfin[ll]
items = fin.cnName.to_list()
sumite = [item for item in items if any(substr in item for substr in "万")]

for ite in sumite:
    fin.loc[fin.cnName==ite,day] = fin[fin.cnName==ite][day]*10000

zcfz = fin.query('L1Code=="ZCFZ" and L3Code!="EMP" and L3Code!="HJ"')

zcfz = zcfz[~(zcfz[day]==0)]

import plotly.express as px

fig = px.sunburst(zcfz, path=['L2Name','L3Name','cnName'], values=day)


tab1, tab2 = st.tabs([stockCode+" : Streamlit theme (default)", stockCode+" : Plotly native theme"])
with tab1:
    st.plotly_chart(fig, theme="streamlit")
with tab2:
    st.plotly_chart(fig, theme=None)