# 业务应用
import streamlit as st

data_title = [
    '工程建设标准查询', '建设工程项目信息', '建设工程基本信息', 
    '建设工程人员信息', '建设工程企业信息', '住房保障服务', 
    '住房公积金服务', '工程建设服务', '物业管理服务', 
    '燃气监管服务', '更多服务>>>'
    ]

def tit_button():
    for ind, tit in enumerate(data_title):
        if st.session_state[f"tit_{ind}"]:
            st.session_state['index'] = ind
            st.session_state['info'] = tit

def business_app():
    if 'info' not in st.session_state:
        st.session_state.index = 0
        st.session_state.info = data_title[0]
    tp = lambda x: 'primary' if st.session_state.index == x else 'secondary'
    col01, col02 = st.columns([1, 9])
    with col01:
        with st.container(height=660, border=False):
            for ind, tit in enumerate(data_title):
                st.button(label=tit, key=f'tit_{ind}', use_container_width=True, on_click=tit_button, type=tp(ind))
    with col02:
        with st.container(border=True, height=660):
            st.write(st.session_state.info)