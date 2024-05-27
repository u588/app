import streamlit as st
from streamlit_option_menu import option_menu
from apps import home, heatmap, upload


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
        st.title('登录')
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
            # st.balloons()

if __name__ == "__main__":
    
    if st.session_state.logged_in:
        apps = [
            {"func": home.app, "title": "周期分析", "icon": "house"},
            {"func": heatmap.app, "title": "推  荐", "icon": "map"},
            {"func": upload.app, "title": "趋  势", "icon": "cloud-upload"},
        ]

        titles = [app["title"] for app in apps]
        titles_lower = [title.lower() for title in titles]
        icons = [app["icon"] for app in apps]

        # params = st.experimental_get_query_params()
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

            # st.sidebar.title("About")
            # st.sidebar.info(
            #     """
            #     This web [app](https://share.streamlit.io/giswqs/streamlit-template) is maintained by [Qiusheng Wu](https://wetlands.io). You can follow me on social media:
            #         [GitHub](https://github.com/giswqs) | [Twitter](https://twitter.com/giswqs) | [YouTube](https://www.youtube.com/c/QiushengWu) | [LinkedIn](https://www.linkedin.com/in/qiushengwu).
                
            #     Source code: <https://github.com/giswqs/streamlit-template>

            #     More menu icons: <https://icons.getbootstrap.com>
            # """
            # )

        for app in apps:
            if app["title"] == selected:
                app["func"]()
                break
    else:
        login_page()