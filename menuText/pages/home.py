# 首页导航
import streamlit as st

def home():
    col01, col02_1, col02_2, col03 = st.columns([1,5,1, 1])
    col02_1.text_input(label='sou', max_chars=36, key='search_text', label_visibility='collapsed')
    col02_2.button(label=' 搜索', key='search_button')