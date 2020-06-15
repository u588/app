from pyecharts import options as opts
from pyecharts.charts import  Radar, Grid, Timeline, Page
from sqlalchemy import create_engine
import pandas as pd

eng = create_engine('postgresql+psycopg2://sa:11111111@10.145.254.56:5432/smDaily')
mkData = pd.read_sql('Market',eng)
dd = mkData.drop(0)
d1s = dd[['date','sIndex','chg','pct_chg','vol','pct_vol','yChg','pct_yChg']]
allDate = d1s.drop_duplicates('date').date.tolist()

def grid():
    page = Page(js_host='/',page_title='',layout=Page.DraggablePageLayout, interval=1)
    inNames = d1s.sIndex.drop_duplicates().tolist()
    for j,inName in enumerate(inNames):
        dd = d1s.groupby('sIndex').get_group(inName).reset_index(drop=True)
        tl = Timeline(opts.InitOpts(width="650px", height="500px"))
        for i,date in enumerate(allDate):
            c_schema = [
                {"name": "日涨跌", "max": 100,  "min": -100},
                {"name": "日涨跌幅(%)", "max": 10, "min": -10},
                {"name": "成交额较昨日增减(亿元)", "max": 500, "min":-500},
                {"name": "成交额较昨日增减(%)", "max": 50,"min": -50},
                {"name": "今年以来涨跌", "max": 1000,"min": -500},
                {"name": "今年以来涨跌幅(%)", "max": 20,"min": -20},
            ]
            c = Radar()
            c.add_schema(schema=c_schema, shape="circle")
            c.add(dd.loc[i][1].strip(), [dd.loc[i].tolist()[2:]], is_selected=True,
                    areastyle_opts=opts.AreaStyleOpts(opacity=0.1),
                        linestyle_opts=opts.LineStyleOpts(width=2), )
            c.set_series_opts(label_opts=opts.LabelOpts(is_show=True))
            c.set_global_opts(title_opts=opts.TitleOpts(title=""))        
            tl.add(c,"{}日期".format(date))
        tl.chart_id="tl_chart_id"+str(j)
        page.add(tl)
      
    return page
