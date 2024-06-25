from pygwalker.api.streamlit import init_streamlit_comm, StreamlitRenderer
import pandas as pd
from sqlalchemy import create_engine
import streamlit as st
eng = create_engine('postgresql+psycopg2://sa:11111111@10.3.18.56/tdxStocks')
# Initialize pygwalker communication
init_streamlit_comm()


# You should cache your pygwalker renderer, if you don't want your memory to explode
@st.cache_resource
def get_pyg_renderer() -> "StreamlitRenderer":
    df = pd.read_sql('000001', eng).tail(20)
    # When you need to publish your application, you need set `debug=False`,prevent other users to write your config file.
    return StreamlitRenderer(df, spec="./billion_config.json", debug=True)

renderer = get_pyg_renderer()

# Display explore ui, Developers can use this to prepare the charts you need to display.
renderer.explorer()

# Display pure chart, index is the order of charts in explore mode, starting from 0.
# renderer.chart(0)