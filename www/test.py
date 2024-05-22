from streamlit_echarts import st_pyecharts
import streamlit as st

import d3plt
import mytab
import mytable
import Kpro
import timel
import griRada
import getData
import detailChart
import csIndexPie
import getCsIndex
import getCsStock
import csIndexChart
import BokK
import geoGrid

title = '回测结果分析'
st.set_page_config(page_title=title, page_icon=":bar_chart:", layout="wide")
st.title(title)


c = geoGrid.geoo()
# c = Kpro.Kchart('000001')
# c = d3plt.d3('000001')
# c = BokK.K('000001')
# st.bokeh_chart(c)
st_pyecharts(c)