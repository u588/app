from sqlalchemy import create_engine
import pandas as pd
import numpy as np
from pyecharts.components import Table
from pyecharts.charts import Pie
from pyecharts import options as opts
from pyecharts.options import ComponentTitleOpts


# eng = create_engine('postgresql+psycopg2://sa:11111111@10.145.254.56:5432/tdxIndexs')
eng = create_engine('postgresql+psycopg2://sa:11111111@10.145.254.56:5432/csIndex')

def table(Stock):
    IndexConst = pd.read_sql('IndexConst', eng)
    StockInIndex = IndexConst[IndexConst.code==Stock][['index_code', 'code','name']]
    StockInIndex.rename(columns={'name':'stock_name','code':'stock_code'}, inplace=True)
    csIndex = pd.read_sql('IndexList', eng)
    csIndex =csIndex[['index_code', 'index_name']]
    # csIndex.rename(columns={'name':'index_name'}, inplace=True)
    data = pd.merge(StockInIndex, csIndex, on='index_code')  

    table = Table(js_host='/',page_title='DARK'  )
    headers = data.columns.tolist()
    rows = np.array(data).tolist()
    table.add(headers, rows)
    table.set_global_opts(
        title_opts=ComponentTitleOpts(title="Table-基本示例", subtitle='共有 '+str(data.shape[0]))
    )
    return table



def pie(StockID):

    StocksList = pd.read_csv('/home/ts/app/data/StocksList.csv', dtype={'code':object})
    Stock = StocksList.loc[StocksList['code']==StockID].astype(str).reset_index()

    IndexConst = pd.read_sql('csDetail', eng)
    StockInIndex = IndexConst[IndexConst.code==StockID][['Index_code', 'code','name']]
    StockInIndex.rename(columns={'name':'stock_name','code':'stock_code'}, inplace=True)
    csIndex = pd.read_sql('csIndexs', eng)
    csIndex =csIndex[['Index_code', 'Index_name']]
    # csIndex.rename(columns={'name':'index_name'}, inplace=True)
    data = pd.merge(StockInIndex, csIndex, on='Index_code')  

    dd = data[['Index_name', 'Index_code']]
    d = data.stock_name[0]+" : " + data.stock_code[0]
    c = (
        Pie()
        .add(
            "",
            [list(z) for z in zip(dd.Index_name, dd.Index_code)],
            radius=["25%", "70%"],
            center=["50%", "50%"],
            rosetype="area",
        )
        .set_global_opts(
                        title_opts=opts.TitleOpts(
                                    title=(d),pos_left="center",pos_top="20",
                          
                                    subtitle = ('所属行业: '+Stock['industry'][0]+'  地域: '+Stock['area'][0]+'  市盈率: '+Stock['pe'][0]+'  总股本: '+Stock['totals'][0]+'亿元'+
                            '  流通股本: '+Stock['outstanding'][0]+'亿元'+'  市净率:'+Stock['pb'][0]+'  每股收益:'+Stock['esp'][0]+ '  每股净资:'+Stock['bvps'][0]+
                            '  每股分配利润:'+Stock['perundp'][0]+'  收入同比:'+Stock['rev'][0]+'%'+'  利润同比:'+Stock['profit'][0]+'%'+'  毛利率:'+Stock['gpr'][0]+'%'+
                            '  净利润率:'+Stock['npr'][0]+'%'), 
                                    subtitle_textstyle_opts=opts.TextStyleOpts(color='blue',font_style='italic',font_weight='bold'),
                        ),
                        legend_opts=opts.LegendOpts(is_show=False),
        )
        .set_series_opts(label_opts=opts.LabelOpts(formatter="{b}: {c}"))
    )
    return c
