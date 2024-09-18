import pages as pgs

import streamlit as st
from streamlit_option_menu import option_menu  
st.set_page_config(page_title='test', page_icon=' ', layout='wide')


import streamlit as st
with st.form('1'):
    with st.sidebar.expander("企业集成平台"):
        # Display widgets in an expandable section
        page = option_menu(
            menu_title='企业集成平台',
            options=['首页', '业务应用', '财务应用', '报表应用', '系统管理'],
            default_index=0,
            # menu_icon='windows',
            icons=['house', 'people', 'piggy-bank', 'clipboard-data', 'gear'],
            key='1'
        )

with st.form('2'):
    with st.sidebar.expander("企业集成平台"):
        # Display widgets in an expandable section
        page = option_menu(
            menu_title='企业集成平台',
            options=['首页', '业务应用', '财务应用', '报表应用', '系统管理'],
            default_index=0,
            # menu_icon='windows',
            icons=['house', 'people', 'piggy-bank', 'clipboard-data', 'gear'],
            key='2'
        )


functions = {
    '首页': pgs.home,
    '业务应用': pgs.business_app,
    '财务应用': pgs.financial_app,
    # '报表应用': pgs.report_app,
    '系统管理': pgs.system_management
}

go_to = functions.get(page)

if go_to:
    go_to()