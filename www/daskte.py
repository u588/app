from dask.distributed import Client
from sqlalchemy import create_engine
import pandas as pd
import dask.dataframe as dd
import streamlit as st

client = Client("10.18.0.3:8786")
# 读取大型数据集
eng = create_engine('postgresql+psycopg://sa:11111111@10.3.18.56/tdxStocks')
dff = pd.read_sql('000001', eng)
df = dd.from_pandas(dff)

# 使用Dask进行数据处理，例如分组求和
# result = df.groupby('year').sum().compute()
result = client.submit(df.groupby('year').sum().compute())

# 使用Streamlit创建交互式Web应用
st.title('My Data Science App')
st.write('Here is our first attempt at a data app!')
st.write(result)
