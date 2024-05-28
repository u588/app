import streamlit as st
import numpy as np



st.header('欢迎使用！')
use = st.text_input('用户名：', key=0)
passwd = st.text_input('密码：',type='password', key=1)

if use=='root'and passwd=='11111111' :
    st.page_link('./pages/3.py')
else:
    st.write('用户名或密码错误，请重新输入！')


# with st.sidebar:
#     sbo=st.selectbox('文旅', ('a','b','c'))

# # 使用列进行布局
# col1, col2, col3 = st.columns(3)
# with col1:
#     st.header("Column 1")
#     st.write("这是第一列的内容")
# with col2:
#     st.header("Column 2")
#     st.write("这是第二列的内容")
# with col3:
#     st.header("Column 3")
#     st.write("这是第三列的内容")
 
# # 使用展开器创建隐藏内容
# with st.expander("点击展开更多信息"):
#     st.header('ll')
#     st.write("这里是一些可以展开的详细信息。")



# tab1,tab2,tab3 = st.tabs(['a','b','c'])

# with tab1:
#     # st.header('a')
#     st.subheader('subA')
#     with st.container():
#         st.bar_chart(np.random.randn(50, 3))

# st.write("这是容器外的内容")
# with tab2:
#     st.header('b')
#     st.write('B')
# with tab3:
#     st.header('c')
#     st.write('C')
