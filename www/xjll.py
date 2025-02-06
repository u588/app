import pandas as pd
from sqlalchemy import create_engine
import streamlit as st

eng = create_engine('postgresql+psycopg://sa:11111111@10.3.18.56/tdxFS')

FSCode = pd.read_sql('FSCode',eng)
stockCode = '000001'
day = 20240331

finRAW = pd.read_sql(stockCode, eng,)
finRAW['report_date']=finRAW['report_date'].astype(object)

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

node = fin.query('L1Code=="XJLL" and L3Code!="EMP"')
node = node[~(node["vol"]==0)].reset_index(drop=True).reset_index()

link = pd.DataFrame()

mid = pd.DataFrame()
mid['S'] = node.query('L2Code=="TZHD" and L3Code=="LR"')['index']
mid['V'] = node.query('L2Code=="TZHD" and L3Code=="LR"')['vol']
mid['T'] = node.query('L2Code=="TZHD" and L3Code=="LRHJ"').values[0][0]
link = pd.concat([link, mid])

mid = pd.DataFrame()
mid['S'] = node.query('L2Code=="TZHD" and L3Code=="LC"')['index']
mid['V'] = node.query('L2Code=="TZHD" and L3Code=="LC"')['vol']
mid['T'] = node.query('L2Code=="TZHD" and L3Code=="LCHJ"').values[0][0]
link = pd.concat([link, mid])

mid = pd.DataFrame()
mid['S'] = node.query('L2Code=="TZHD" and (L3Code=="LRHJ" or L3Code=="LCHJ")')['index']
mid['V'] = node.query('L2Code=="TZHD" and (L3Code=="LRHJ" or L3Code=="LCHJ")')['vol']
mid['T'] = node.query('L2Code=="TZHD" and L3Code=="JE"').values[0][0]
link = pd.concat([link, mid])

mid = pd.DataFrame()
mid['S'] = node.query('L2Code=="JYHD" and L3Code=="LR"')['index']
mid['V'] = node.query('L2Code=="JYHD" and L3Code=="LR"')['vol']
mid['T'] = node.query('L2Code=="JYHD" and L3Code=="LRHJ"').values[0][0]
link = pd.concat([link, mid])

mid = pd.DataFrame()
mid['S'] = node.query('L2Code=="JYHD" and L3Code=="LC"')['index']
mid['V'] = node.query('L2Code=="JYHD" and L3Code=="LC"')['vol']
mid['T'] = node.query('L2Code=="JYHD" and L3Code=="LCHJ"').values[0][0]
link = pd.concat([link, mid])

mid = pd.DataFrame()
mid['S'] = node.query('L2Code=="JYHD" and (L3Code=="LRHJ" or L3Code=="LCHJ")')['index']
mid['V'] = node.query('L2Code=="JYHD" and (L3Code=="LRHJ" or L3Code=="LCHJ")')['vol']
mid['T'] = node.query('L2Code=="JYHD" and L3Code=="JE"').values[0][0]
link = pd.concat([link, mid])

mid = pd.DataFrame()
mid['S'] = node.query('L2Code=="CZHD" and L3Code=="LR"')['index']
mid['V'] = node.query('L2Code=="CZHD" and L3Code=="LR"')['vol']
mid['T'] = node.query('L2Code=="CZHD" and L3Code=="LRHJ"').values[0][0]
link = pd.concat([link, mid])

mid = pd.DataFrame()
mid['S'] = node.query('L2Code=="CZHD" and L3Code=="LC"')['index']
mid['V'] = node.query('L2Code=="CZHD" and L3Code=="LC"')['vol']
mid['T'] = node.query('L2Code=="CZHD" and L3Code=="LCHJ"').values[0][0]
link = pd.concat([link, mid])

mid = pd.DataFrame()
mid['S'] = node.query('L2Code=="CZHD" and (L3Code=="LRHJ" or L3Code=="LCHJ")')['index']
mid['V'] = node.query('L2Code=="CZHD" and (L3Code=="LRHJ" or L3Code=="LCHJ")')['vol']
mid['T'] = node.query('L2Code=="CZHD" and L3Code=="JE"').values[0][0]
link = pd.concat([link, mid])
try:
    mid = pd.DataFrame()
    mid['S'] = node.query('L2Code=="BCXM" and L3Code=="LR"')['index']
    mid['V'] = node.query('L2Code=="BCXM" and L3Code=="LR"')['vol']
    mid['T'] = node.query('L2Code=="BCXM" and L3Code=="JEJJ"').values[0][0]
    link = pd.concat([link, mid])
except:
    pass

try:
    mid = pd.DataFrame()
    mid['S'] = node.query('L2Code=="BCXM" and L3Code=="LC"')['index']
    mid['V'] = node.query('L2Code=="BCXM" and L3Code=="LC"')['vol']
    mid['T'] = node.query('L2Code=="BCXM" and L3Code=="JEJJ"').values[0][0]
    link = pd.concat([link, mid])
except:
    pass

try:
    mid = pd.DataFrame()
    mid['S'] = node.query('L2Code=="BCXMDJW" and L3Code=="LR"')['index']
    mid['V'] = node.query('L2Code=="BCXMDJW" and L3Code=="LR"')['vol']
    mid['T'] = node.query('L2Code=="BCXMDJW" and L3Code=="ZJEJJ"').values[0][0]
    link = pd.concat([link, mid])
except:
    pass 

mid = pd.DataFrame()
mid['S'] = node.query('L3Code=="JE"')['index']
mid['V'] = node.query('L3Code=="JE"')['vol']
mid['T'] = node.query('L2Code=="DJW" and L3Code=="ZJE"').values[0][0]
link = pd.concat([link, mid])

import plotly.graph_objects as go

fig1 = go.Figure(data=[go.Sankey(

    node = dict(
      pad = 15,
      thickness = 15,
      line = dict(color = "black", width = 0.5),
      label =  node['cnName'].tolist(),
      # color =  data['data'][0]['node']['color']
    ),
    # Add links
    link = dict(
      source =  link['S'].tolist(),
      target =  link['T'].tolist(),
      value =  abs(link['V']).tolist(),
      # label =  data['data'][0]['link']['label'],
      # color =  data['data'][0]['link']['color']
))])

fig1.update_layout(title_text="Sankey分析<br>"+"Code: "+str(day),
                  font_size=10)

waterfin = node.query('L3Code=="LRHJ" or L3Code=="LCHJ" or L3Code=="JE" ')
waterfin = pd.concat([waterfin,node.query('L2Code=="HLBD" ')])
lis = waterfin.query('L3Code=="LCHJ"').index.tolist()
for i in lis:
    waterfin.loc[i,'vol'] = -waterfin.loc[i,'vol']

x = waterfin.cnName.tolist()
x.append("净流量")
y = waterfin["vol"].tolist()
y.append(0)

fig = go.Figure(go.Waterfall(
    orientation = "v",
    name = 'waterfall',
    x = x,
    measure = ["absolute", "relative", "total", "absolute", "relative", "total", "absolute", "relative", "total","absolute","absolute"],
    y = y, 
    base = 0,
    decreasing = {"marker":{"color":"Maroon", "line":{"color":"red", "width":2}}},
    increasing = {"marker":{"color":"Teal"}},
    totals = {"marker":{"color":"deep sky blue", "line":{"color":"blue", "width":3}}}
))

fig.update_layout(title = "Profit and loss statement", waterfallgap = 0.3)

tab1, tab2 = st.tabs([stockCode+' : '+str(day)+" : Streamlit theme (default)", stockCode+" : Plotly native theme"])
with tab1:
    st.plotly_chart(fig, theme=None)
with tab2:
    st.plotly_chart(fig1, theme=None)