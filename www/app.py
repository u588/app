import streamlit as st
from streamlit_option_menu import option_menu
from apps import cycAna, recom, trend,qInfo


st.set_page_config(
    page_title="分析",
    layout="wide"
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
            {"func": cycAna.app, "title": "周期分析", "icon": "house"},
            {"func": recom.app, "title": "推  荐", "icon": "map"},
            {"func": trend.app, "title": "趋  势", "icon": "cloud-upload"},
            {"func": qInfo.app, "title": "查  询", "icon": "cloud-upload"},
        ]

        titles = [app["title"] for app in apps]
        titles_lower = [title.lower() for title in titles]
        icons = [app["icon"] for app in apps]

        params = st.session_state

        if "page" in params:
            default_index = int(titles_lower.index(params["page"][0].lower()))
        else:
            default_index = 0

        with st.sidebar:
            selected = option_menu(
                "分析",
                options=titles,
                icons=icons,
                menu_icon="cast",
                default_index=default_index,
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