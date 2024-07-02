from mootdx.quotes import Quotes
import streamlit as st
import re

client = Quotes.factory(market='std')
a = client.F10C(symbol='000001')
txt = client.F10('000001', a[11].get('name'))
txt = txt.replace('│',' ')        
# txt = txt.replace('([^\u4e00-\u9fa5\u0030-\u0039\n\u0020-\u007e\u00A4-\u00BF])','')            
# txt = re.sub('([^\u4e00-\u9fa5\u0030-\u0039\n\u0020-\u007e\u00A4-\u00BF])','',txt)            
with st.sidebar:
    st.text(a[0].get('name'))
st.text(txt)