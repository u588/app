from mootdx.quotes import Quotes
import streamlit as st
import re

n=0
code = '301577'
client = Quotes.factory(market='std')
a = client.F10C(symbol=code)
txt = client.F10(code, a[n].get('name'))

txt = txt.replace('│',' ')                
txt = re.sub('([\u2500-\u25f7])','',txt) #删除制表符            

with st.sidebar:
    st.title(a[n].get('name'))
st.subheader(a[n].get('name'))
st.text(txt)