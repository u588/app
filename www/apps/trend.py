import streamlit as st
from streamlit_echarts import st_pyecharts
from chart import makSum
import plotly.express as px
import pandas as pd
from sqlalchemy import create_engine

eng = create_engine('postgresql+psycopg2://sa:11111111@10.3.18.56:5432/smDaily')
engTDX = create_engine('postgresql+psycopg2://sa:11111111@10.3.18.56:5432/tdxIndex')
tdxData = pd.read_sql('tdxIndexsData', engTDX)

def app():

    tdxData = pd.read_sql('tdxIndexsData', engTDX)
    fig = px.scatter_ternary(tdxData,a='3D',b='5D',c='21D',hover_name='IndexName')
    fig1 = px.scatter_3d(tdxData,x='3D',y='5D',z='21D',color='55D',hover_name='IndexName')
    # with st.form('form'):
    tab1,tab2 =st.tabs(['1','2'])
    with tab1:
        st.plotly_chart(fig)
    with tab2:
        st.plotly_chart(fig1)
        # st_pyecharts(makSum.testti(),height='500px',width="100%")






        # with st.sidebar:
        #     submitted2 = st.form_submit_button('确认')
        # if submitted2:
        #     tab1, tab2, tab3, tab4, tab5= st.tabs(['周期: 3','周期: 5',
        #                                            '周期: 21','周期: 55',
        #                                            '21日分时',])
        #     with tab1:
        #         st.bokeh_chart(makSum.pp('3D'),use_container_width=True)
        #     with tab2:
        #        st.bokeh_chart(makSum.pp('5D'),use_container_width=True)
        #     with tab3:
        #         st.bokeh_chart(makSum.pp('21D'),use_container_width=True)
        #     with tab4:
        #         st.bokeh_chart(makSum.pp('55D'),use_container_width=True)
        #     with tab5:
        #         st_pyecharts(makSum.testti(),height='500px',width="100%")


