import pandas as pd
from sqlalchemy import create_engine
import streamlit as st
import plotly

st.set_page_config(
    page_title="分析",
    layout="wide"
)

colors = plotly.colors.qualitative.Light24

eng = create_engine('postgresql+psycopg2://sa:11111111@10.3.18.56/tdxFS')
engB = create_engine('postgresql+psycopg2://sa:11111111@10.3.18.56/StockBas')
StockIC = pd.read_sql("StockIC", engB)

StockCode = '002202'
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

# anafin = fin.query('L1Code=="FZNL" and L3Code!="EMP"') #1
# anafin = fin.query('L1Code=="CZNL" and L3Code!="EMP"')#2
# anafin = fin.query('L1Code=="HLNL" and L3Code!="EMP"')#3
anafin = fin.query('L1Code=="JYNL" and L3Code!="EMP"')#4

data = pd.merge(anafin, desel.reset_index(drop=False),left_on='Code',right_on='index',how='inner')

lens = (max(data['mean'])-min(data['mean']))/2

ll = ['StockCode','StockName']
ta = mfinsel[ll + anafin.Code.tolist()].reset_index(drop=True)
ta = ta.rename(columns=dict(zip(ta.columns,(ll+anafin.cnName.tolist()))))

# ta_sort = ta.drop(index=ta[ta['StockCode']==StockCode].index).sort_values('扣非每股收益同比(%)',ascending=False) #1
# ta_sort = ta.drop(index=ta[ta['StockCode']==StockCode].index).sort_values('速动比率(非金融类指标)',ascending=False) #2
# ta_sort = ta.drop(index=ta[ta['StockCode']==StockCode].index).sort_values('净利润率(非金融类指标)',ascending=False) #3
ta_sort = ta.drop(index=ta[ta['StockCode']==StockCode].index).sort_values('存货周转率(非金融类指标)',ascending=False) #4
fta = pd.concat([ta_sort.head(8),ta_sort.tail(2)]).drop_duplicates(subset='StockCode').reset_index(drop=True)
Tta = pd.concat([fta,ta[ta['StockCode']==StockCode]]).T.reset_index()

import plotly.graph_objects as go
categories = data.cnName.tolist()


fig3 = go.Figure()
fig3.add_trace(go.Barpolar(
    r=list(data['mean']),
    theta=categories,
    name='行业均值',
    marker_color='rgb(0,152,255)',
    # base='stack'
))
fig3.add_trace(go.Barpolar(
    r=list(data['vol']),
    theta=categories,
    name=StockName,
    marker_color='rgb(251,106,78)',
    # base='stack'
))
i = 0
while i<len(fta):
    fig3.add_trace(go.Barpolar(
        r=list(fta.loc[i])[3:],
        theta=categories,
        name=list(fta.loc[i])[1],
        marker_color=colors[i],
        visible='legendonly',
        # opacity=0.5
        # base='overlay'
    ))
    i = i+1

# fig.update_traces(text=list(data['cnName']))
fig3.update_layout(
    # title='Wind Speed Distribution in Laurel, NE',
    activeshape_opacity=0.2,
    font_size=12,
    legend_font_size=12,
    # legend_title='tee',
    # legend_itemclick='toggleothers',


    # legend_visible=False,
    # showlegend=False,
    # legend_activeselection=False,
    

    # polar_radialaxis_ticksuffix='%',
    # polar_angularaxis_rotation=90,

)

fig = go.Figure()

fig.add_trace(go.Scatterpolar(
      r=data['mean'].tolist(),
      theta=categories,
      fill='toself',
      name='行业均值'
))
fig.add_trace(go.Scatterpolar(
      r=data.vol.tolist(),
      theta=categories,
      fill='toself',
      name=StockName
))

i = 0
while i<len(fta):
    fig.add_trace(go.Scatterpolar(
        r=list(fta.loc[i])[2:],
        theta=categories,
        name=list(fta.loc[i])[1],
        marker_color=colors[i],
        visible='legendonly',
        fill='toself'
        # opacity=0.5
        # base='overlay'
    ))
    i = i+1

fig.update_layout(
  polar=dict(
    radialaxis=dict(
      visible=True,
    #   range=[round((min(anafin.vol)-(3*lens)),2), max(anafin.vol)+lens]
    )),
  # showlegend=False
)

fig1 = go.Figure(data=[go.Table(
        header=dict(values=list(tasel.columns),
                    fill_color='lightskyblue',
                    ),
        cells=dict(values=[tasel.StockCode,tasel.StockName,tasel.L1Name,tasel.L2Name,tasel.L3Name,tasel.L4Name],
                   fill_color='lightcyan',
                )
        )
    ])

fig4 = go.Figure(data=[go.Table(
    header=dict(values=list(fta.columns),
                line_color='darkslategray',
                fill_color='lightskyblue',
                align='left'),
    cells=dict(values=list(round(fta,2).values.T),
                line_color='darkslategray',
                fill_color='lightcyan',
                align='left'))
])

fig5 = go.Figure()
i =2 
while i<len(Tta):
    fig5.add_trace(go.Bar(
        name=list(Tta.loc[i])[0],
        x=list(Tta.loc[1])[1:],
        # y=list(ta.loc[i])[2:]+abs(tamin)+8,
        y=list(Tta.loc[i])[1:],
        legendgroup="group"+str(i),
        # visible='legendonly', 
        marker=dict(color=colors[i])
    ))
    
    fig5.add_trace(go.Scatter(
        legendgroup="group"+str(i),
        mode='lines',
        showlegend=False,
        visible='legendonly',
        marker_color='red',
        x=[list(Tta.loc[1])[1],list(Tta.loc[1])[-1]],
        y=[list(data.loc[i-2])[12],list(data.loc[i-2])[12]]
    ))

    i = i+1 
fig5.update_xaxes(zeroline=True, zerolinewidth=2, zerolinecolor='LightPink')
fig5.update_layout(yaxis_tickformat=',d',legend_itemclick='toggleothers',)    


tab1, tab2 = st.tabs([StockCode+' : 共'+str(len(tasel))+"支", StockName+' : '+data['L1Name'].head(1).tolist()[0]])
with tab1:
    st.subheader(' — '.join(list(tasel.head(1).values[0][2:])))
    st.plotly_chart(fig4, theme=None)
with tab2:
    st.plotly_chart(fig, theme=None)
    st.plotly_chart(fig5, theme=None)
# with tab3:
#     st.plotly_chart(fig5, theme=None)


