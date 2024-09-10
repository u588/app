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

# zzcfz = fin.query('L1Code=="ZCFZ" and (L3Code=="HJ" or L3Code=="SSGD")')
# zzcfz = zzcfz[~(zzcfz["vol"]==0)].reset_index(drop=True)

# for i,ite in enumerate(zzcfz.vol.to_list()):
#     if ite < 0:
#         zzcfz.loc[i,'cnName'] ='负：'+ zzcfz.loc[i,'cnName']
#         zzcfz.loc[i,'vol'] = abs(ite) 
#     else:
#         pass


import plotly.graph_objects as go
from plotly.subplots import make_subplots

# colors = plotly.colors.qualitative.Light24
# colors = plotly.colors.sequential.Plotly3

df = zcfz

levels = ['cnName', 'L3Name', 'L2Name'] # levels used for the hierarchical chart
# color_columns = ['vol']
value_column = 'vol'

def build_hierarchical_dataframe(df, levels, value_column):
    """
    Build a hierarchy of levels for Sunburst or Treemap charts.

    Levels are given starting from the bottom to the top of the hierarchy,
    ie the last level corresponds to the root.
    """
    df_list = []
    for i, level in enumerate(levels):
        # df_tree = pd.DataFrame(columns=['id', 'parent', 'value', 'color'])
        df_tree = pd.DataFrame(columns=['id', 'parent', 'value'])
        dfg = df.groupby(levels[i:]).sum()
        dfg = dfg.reset_index()
        df_tree['id'] = dfg[level].copy()
        if i < len(levels) - 1:
            df_tree['parent'] = dfg[levels[i+1]].copy()
        else:
            df_tree['parent'] = 'total'
        df_tree['value'] = dfg[value_column]
        # df_tree['color'] = dfg[color_columns[0]] / dfg[color_columns[1]]
        df_list.append(df_tree)
    # total = pd.Series(dict(id='total', parent='',
    #                           value=df[value_column].sum(),
    #                           color=df[color_columns[0]].sum() / df[color_columns[1]].sum()), name=0)
    # df_list.append(total)
    df_all_trees = pd.concat(df_list, ignore_index=True)
    return df_all_trees


df_all_trees = build_hierarchical_dataframe(df, levels, value_column)
# df_all_trees = build_hierarchical_dataframe(df, levels, value_column, color_columns)
# average_score = df['sales'].sum() / df['calls'].sum()

fig = make_subplots(1, 2, specs=[[{"type": "domain"}, {"type": "domain"}]],)

fig.add_trace(go.Sunburst(
    labels=df_all_trees['id'],
    parents=df_all_trees['parent'],
    values=df_all_trees['value'],
    # branchvalues='total',
    branchvalues='remainder',
    textinfo='label +percent root',
    # marker_colors=colors,
    # marker=dict(
    #     colors=df_all_trees['color'],
    #     colorscale='RdBu',
    #     cmid=average_score),
    # hovertemplate='<b>%{label} </b> <br> Sales: %{value}<br> Success rate: %{color:.2f}',

    ), 1, 2)

fig.add_trace(go.Sunburst(
    labels=df_all_trees['id'],
    parents=df_all_trees['parent'],
    values=df_all_trees['value'],
    textinfo='percent parent +label',
    # branchvalues='remainder',
    branchvalues='total',
    name='2',
    
    # marker_colors=colors,
    # marker=dict(
    #     colors=df_all_trees['color'],
    #     colorscale='RdBu',
    #     cmid=average_score),
    # hovertemplate='<b>%{label} </b> <br> Sales: %{value}<br> Success rate: %{color:.2f}',
    maxdepth=3
    ), 1, 1)
traces=fig.data
fig.update_layout(margin=dict(t=0, b=0, r=0, l=0))
st.plotly_chart(fig)