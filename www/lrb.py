import pandas as pd
from sqlalchemy import create_engine
import streamlit as st

eng = create_engine('postgresql+psycopg2://sa:11111111@10.3.18.56/tdxFS')

stockCode = '600256'
day = 20240331
finRAW = pd.read_sql(stockCode, eng)
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

node = fin.query('L1Code=="LRB" and L3Code!="EMP"')
node = node[~(node["vol"]==0)].reset_index(drop=True).reset_index()

link = pd.DataFrame()

mid = pd.DataFrame()
mid['S'] = node.query('L2Code=="CBFY" and (L3Code=="CB" or L3Code=="CW")')['index']
mid['V'] = node.query('L2Code=="CBFY" and (L3Code=="CB" or L3Code=="CW")')['vol']
mid['T'] = node.query('L2Code=="CBFY" and L3Code=="HJ"').values[0][0]
link = pd.concat([link, mid])

mid = pd.DataFrame()
mid['S'] = node.query('L2Code=="CBFY" and L3Code=="TZSY"')['index']
mid['V'] = node.query('L2Code=="CBFY" and L3Code=="TZSY"')['vol']
mid['T'] = node.query('L2Code=="CBFY" and L3Code=="TZ"').values[0][0]
link = pd.concat([link, mid])

mid = pd.DataFrame()
mid['S'] = node.query('L2Code=="LR" and (L3Code=="SDS" or L3Code =="LRZE") ')['index']
mid['V'] = node.query('L2Code=="LR" and (L3Code=="SDS"or L3Code =="LRZE")')['vol']
mid['T'] = node.query('L2Code=="LR" and L3Code=="JLR"').values[0][0]
link = pd.concat([link, mid])

mid = pd.DataFrame()
mid['S'] = node.query('L2Code=="LR" and (L3Code=="YYLR" or L3Code=="YYLRHJ")')['index']
mid['V'] = node.query('L2Code=="LR" and (L3Code=="YYLR" or L3Code=="YYLRHJ")')['vol']
mid['T'] = node.query('L2Code=="LR" and L3Code=="LRZE"').values[0][0]
link = pd.concat([link, mid])

mid = pd.DataFrame()
mid['T'] = node.query('L2Code=="LR" and L3Code=="JLRS" ')['index']
mid['V'] = node.query('L2Code=="LR" and L3Code=="JLRS" ')['vol']
mid['S'] = node.query('L2Code=="LR" and L3Code=="JLR"').values[0][0]
link = pd.concat([link, mid])

mid = pd.DataFrame()
mid['S'] = node.query('L2Code=="LR" and (L3Code=="JLR" or L3Code=="HJ")')['index']
mid['V'] = node.query('L2Code=="LR" and (L3Code=="JLR" or L3Code=="HJ")')['vol']
mid['T'] = node.query('L3Code=="ZHSYZE"').values[0][0]
link = pd.concat([link, mid])

mid = pd.DataFrame()
mid['S'] = node.query('L2Code=="YYSR" and L3Code=="SR"')['index']
mid['V'] = node.query('L2Code=="YYSR" and L3Code=="SR"')['vol']
mid['T'] = node.query('L2Code=="YYSR" and L3Code=="HJ"').values[0][0]
link = pd.concat([link, mid])

mid = pd.DataFrame()
mid['T'] = node.query('L2Code=="ZHSY" and L3Code=="GS"')['index']
mid['V'] = node.query('L2Code=="ZHSY" and L3Code=="GS"')['vol']
mid['S'] = node.query('L2Code=="ZHSY" and L3Code=="ZHSYZE"').values[0][0]
link = pd.concat([link, mid])

mid = pd.DataFrame()
mid['S'] = node.query('L2Code=="LRY" and L3Code=="HJY"')['index']
mid['V'] = node.query('L2Code=="LRY" and L3Code=="HJY"')['vol']
mid['T'] = node.query('L2Code=="LRY" and L3Code=="HJYJ"').values[0][0]
link = pd.concat([link, mid])

mid = pd.DataFrame()
mid['T'] = node.query('L2Code=="LRY" and L3Code=="HJYS"')['index']
mid['V'] = node.query('L2Code=="LRY" and L3Code=="HJYS"')['vol']
mid['S'] = node.query('L2Code=="LRY" and L3Code=="HJYJ"').values[0][0]
link = pd.concat([link, mid])

mid = pd.DataFrame()
mid['S'] = node.query('L2Code=="CBFY" and L3Code=="HJ"')['index']
mid['V'] = node.query('L2Code=="CBFY" and L3Code=="HJ"')['vol']
mid['T'] = node.query('L3Code=="YYLRHJ"').values[0][0]
link = pd.concat([link, mid])

mid = pd.DataFrame()
mid['S'] = node.query('L2Code=="YYSR" and L3Code=="HJ"')['index']
mid['V'] = node.query('L2Code=="YYSR" and L3Code=="HJ"')['vol']
mid['T'] = node.query('L3Code=="YYLRHJ"').values[0][0]
link = pd.concat([link, mid])

mid = pd.DataFrame()
mid['S'] = node.query('L2Code=="CBFY" and (L3Code=="SY" or L3Code=="TZ")')['index']
mid['V'] = node.query('L2Code=="CBFY" and (L3Code=="SY" or L3Code=="TZ")')['vol']
mid['T'] = node.query('L2Code=="LR" and L3Code=="YYLRHJ"').values[0][0]
link = pd.concat([link, mid])

# try:
mid = pd.DataFrame()
mid['S'] = node.query('L2Code=="CBFY" and L3Code=="CWFY"')['index']
mid['V'] = node.query('L2Code=="CBFY" and L3Code=="CWFY" ')['vol']
mid['T'] = node.query('L2Code=="CBFY" and L3Code=="CW"').values[0][0]
link = pd.concat([link, mid])
# except:
#     pass

li =['col502','col519','col86','col92','col95','col206','col270']
x = []
y = []

for i, ite in enumerate(li):
    x.append(node[node.Code==ite].cnName.values[0])
    y.append(node[node.Code==ite].vol.values[0])

xx = pd.DataFrame(x).rename(columns={0:'cnName'})
yy = pd.DataFrame(y).rename(columns={0:'vol'})
xxx = pd.concat([xx,yy],axis=1)


import plotly.express as px

fig = px.bar(xxx, x='cnName', y='vol')





import plotly.graph_objects as go
# override gray link colors with 'source' colors
# change 'magenta' to its 'rgba' value to add opacity


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

fig.update_layout(title_text="Sankey分析<br>"+"Code: "+str(day),
                  font_size=10)

fig.update_layout(title = "Profit and loss statement", waterfallgap = 0.3)
fig.update_layout(dragmode='pan')
tab1, tab2 = st.tabs([stockCode+' : '+str(day)+" : Streamlit theme (default)", stockCode+" : Plotly native theme"])
with tab1:
    st.plotly_chart(fig, theme=None,config={'scrollZoom':True})
with tab2:
    st.plotly_chart(fig1, theme=None)
