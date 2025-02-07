import pandas as pd
from sqlalchemy import create_engine
import streamlit as st

eng = create_engine('postgresql+psycopg://sa:11111111@10.3.18.56:5432/tdxIndex')
# date = 3D 5D 21D
@st.cache_data
def csIndexData(date):
    d = pd.read_sql('tdxIndexsData', eng)
    # data = d.sort_values(by=date).head(10).append(d.sort_values(by=date).tail(10))[['Index_code','Index_name', date]].reset_index(drop=True)
    data = pd.concat([d.sort_values(by=date).head(10), d.sort_values(by=date).tail(10)[['IndexCode','IndexName', date]].reset_index(drop=True)])

    dd = data[['IndexName','IndexCode', date]].sort_values(date, ascending=0).reset_index(drop=True)
    return dd