# 财务应用
import streamlit as st
data_title = ['账务处理', '发票管理', '固定资产', '工资管理', '往来管理', '报表与分析', '出纳管理']

def financial_app():
    tab01, tab02, tab03, tab04, tab05, tab06, tab07 = st.tabs(data_title)
    with tab01:
        st.image(r'static\1714909940005.png')
    with tab02:
        st.image(r'static\1714909962855.png')
    with tab03:
        st.image(r'static\1714909982198.png')
    with tab04:
        st.image(r'static\1714909997943.png')
    with tab05:
        st.image(r'static\1714910012407.png')
    with tab06:
        st.image(r'static\1714910025974.png')
    with tab07:
        st.image(r'static\1714910042374.png')