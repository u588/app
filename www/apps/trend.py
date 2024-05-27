import streamlit as st
from streamlit_echarts import st_pyecharts
from chart import makSum


def app():
    with st.form('form'):
        with st.sidebar:
            submitted2 = st.form_submit_button('确认')
        if submitted2:
            tab1, tab2, tab3, tab4, tab5= st.tabs(['周期: 3','周期: 5',
                                                   '周期: 21','周期: 55',
                                                   '21日分时',])
            with tab1:
                st.bokeh_chart(makSum.pp('3D'),use_container_width=True)
            with tab2:
               st.bokeh_chart(makSum.pp('5D'),use_container_width=True)
            with tab3:
                st.bokeh_chart(makSum.pp('21D'),use_container_width=True)
            with tab4:
                st.bokeh_chart(makSum.pp('55D'),use_container_width=True)
            with tab5:
                st_pyecharts(makSum.testti(),height='500px',width="100%")


