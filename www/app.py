import streamlit as st
from streamlit_option_menu import option_menu
# from apps import cycAna, recom, trend,qInfo,llmAna,bcAna,scAna
from apps import  recom, trend,qInfo,bcAna,scAna,fuzQ

st.set_page_config(
    page_title="分析",
    layout="wide",
    # menu_items={None}
)

USER = 'root'
PASSWD = '11111111'

if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False



def login_page():
    with st.form('login_from'):
        # st.title('登录')
        username = st.text_input('用户名',value='')
        password = st.text_input('密码', value='' ,type='password')
        submit = st.form_submit_button('登录')

    if submit:
        if username == USER and password == PASSWD:
            st.success("登录成功！")
            st.session_state.logged_in = True
            st.rerun()
        else:
            st.error("用户名或密码错误，请重新输入。")


if __name__ == "__main__":
    if st.session_state.logged_in:
        apps = [
            {"func": trend.app, "title": "趋  势", "icon": "graph-up-arrow"},
            {"func": recom.app, "title": "推  荐", "icon": "cup-hot"},
            # {"func": cycAna.app, "title": "周  期", "icon": "clock"},
            {"title": "---", "icon": "graph-up-arrow"},
            {"func": qInfo.app, "title": "个 股 查 询", "icon": "search"},
            {"func": fuzQ.app, "title": "模 糊 查 询", "icon": "robot"},
            {"func": bcAna.app, "title": "长 周 期", "icon": "robot"},
            {"func": scAna.app, "title": "短 周 期", "icon": "robot"},
            {"title": "---", "icon": "graph-up-arrow"},
            {"func": st.cache_data.clear, "title": "缓存清理", "icon": "recycle"},
        ]

        titles = [app["title"] for app in apps]
        # titles_lower = [title.lower() for title in titles]
        icons = [app["icon"] for app in apps]

        params = st.session_state

        if "page" in params:
            default_index = int(titles.index(params["page"][0]))
        else:
            default_index = 0
        # with st.expander('分析'):
        with st.sidebar:
            selected = option_menu(
                "工作室",
                options=titles,
                # orientation='horizontal', 
                icons=icons,
                menu_icon="bank2",
                default_index=default_index,
                key='1'
            )

        for app in apps:
            if app["title"] == selected:
                app["func"]()
                break
  
    else:
        col1 ,col2,col3= st.columns(3)
        with col2:
            st.markdown('<center><h2>  登 录 </h2></center>', unsafe_allow_html=True)
            login_page()

    # st.button("清除缓存", on_click=st.cache_data.clear())