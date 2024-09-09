import pandas as pd
from sqlalchemy import create_engine
import streamlit as st

eng = create_engine('postgresql+psycopg2://sa:11111111@10.3.18.56/tdxFS')

FSCode = pd.read_sql('FSCode',eng)
stockCode = '600409'
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
zcfz = fin.query('L1Code=="ZCFZ" and L3Code!="EMP" and L3Code!="HJ" and L3Code!="ZJ" and L3Code!="XJ"')

zcfz = zcfz[~(zcfz["vol"]==0)].reset_index(drop=True)
# zcfz.loc[:,"vol"]=abs(zcfz["vol"])
for i,ite in enumerate(zcfz.vol.to_list()):
    if ite < 0:
        zcfz.loc[i,'cnName'] ='负：'+ zcfz.loc[i,'cnName']
        zcfz.loc[i,'vol'] = abs(ite) 
    else:
        pass

zzcfz = fin.query('L1Code=="ZCFZ" and (L3Code=="HJ" or L3Code=="SSGD")')
zzcfz = zzcfz[~(zzcfz["vol"]==0)].reset_index(drop=True)

for i,ite in enumerate(zzcfz.vol.to_list()):
    if ite < 0:
        zzcfz.loc[i,'cnName'] ='负：'+ zzcfz.loc[i,'cnName']
        zzcfz.loc[i,'vol'] = abs(ite) 
    else:
        pass


import plotly.express as px
# import plotly.graph_objects as go
# from plotly.subplots import make_subplots
# fig = make_subplots(
#     rows=2, cols=2,
#     subplot_titles=("Plot 1", "Plot 2", "Plot 3", "Plot 4"))

# fig.add_trace(px.sunburst(zcfz, path=['L2Name','L3Name','cnName'], values="vol"),
#               row=1,col=1
#               )
# fig.add_trace(px.sunburst(zzcfz, path=['L2Name','cnName'], values="vol"),
#               row=1,col=2)
# fig.add_trace(go.Sunburst(zcfz, path=['L2Name','L3Name','cnName'], values="vol"),
#               row=1,col=1
#               )
# fig.add_trace(go.Sunburst(zzcfz, path=['L2Name','cnName'], values="vol"),
#               row=1,col=2)

# fig.update_layout(title_text=stockCode)

# st.plotly_chart(fig)

fig = px.sunburst(zcfz, path=['L2Name','L3Name','cnName'], values="vol")
# fig = px.treemap(zcfz, path=['L2Name','L3Name','cnName'], values="vol")
fig.update_layout(title=stockCode)
fig.update_traces(branchvalues = "total",textinfo='label+percent parent+percent root')

fig1 = px.sunburst(zzcfz, path=['L2Name','cnName'], values="vol")
# fig1 = px.treemap(zzcfz, path=['L2Name','cnName'], values="vol")
fig1.update_layout(title=stockCode)
fig1.update_traces(textinfo='percent parent +label')
# fig1.update_traces(textinfo='percent root +label')

# # tab1, tab2 = st.tabs([stockCode+' : '+str(day)+" : Streamlit theme (default)", stockCode+" : Plotly native theme"])
# # with tab1:
# #     st.plotly_chart(fig1, theme="streamlit")
# # with tab2:
# #     st.plotly_chart(fig, theme=None)

row1 = st.columns(2)
row2 = st.columns(2)

row1[0].container().plotly_chart(fig1)
row1[1].container().plotly_chart(fig)
# for col in row1+row2:
#     cont=col.container()
#     cont.plotly_chart(fig1)