from pyecharts import options as opts
from pyecharts.charts import Bar, Grid, Line, Pie, Tab, Timeline ,Radar
from pyecharts.faker import Faker
import mytable
from sqlalchemy import create_engine
import pandas as pd

from pyecharts.charts import WordCloud


eng = create_engine('postgresql+psycopg2://sa:11111111@10.145.254.56:5432/smDaily')
engCs = create_engine('postgresql+psycopg2://sa:11111111@10.145.254.56:5432/csIndex')

hs300Data = pd.read_sql('hs300', eng)
zz500Data = pd.read_sql('zz500', eng)
sz50Data = pd.read_sql('sz50', eng)
strongData = pd.read_sql_table('Strong',eng)
weakData = pd.read_sql_table('weak',eng)
wcData = pd.concat([strongData, weakData], ignore_index=True).sort_values(by=['date']).reset_index(drop=True)
mkData = pd.read_sql('Market',eng)
csData = pd.read_sql('csYield', engCs)
csIndexsData = pd.read_sql('csIndexsData', engCs)

def raDarIndex(dd):
    tl = Timeline()
    dd = dd.drop(0)
    d1s = dd[['date','sIndex','chg','pct_chg','vol','pct_vol','yChg','pct_yChg']]

    date = dd.drop_duplicates(subset=('date'), keep='first').date.to_list()

    for i in date:
        d1 = d1s.groupby('date').get_group(i).reset_index(drop=True)


        c_schema = [
            {"name": "日涨跌", "max": 100,  "min": -100},
            {"name": "日涨跌幅(%)", "max": 10, "min": -10},
            {"name": "成交额较昨日增减(亿元)", "max": 500, "min":-500},
            {"name": "成交额较昨日增减(%)", "max": 20,"min": -20},
            {"name": "今年以来涨跌", "max": 1000,"min": -500},
            {"name": "今年以来涨跌幅(%)", "max": 20,"min": -20},
        ]
        c = Radar()
        c.add_schema(schema=c_schema, shape="circle",center=['25%', '40%'], radius=100)
        # c.add_schema(schema=c_schema, shape="circle",center=['50%', '40%'], radius=100)
        for j in range(0,10):
            c.add(d1.loc[j][1].strip(), [d1.loc[j].tolist()[2:]], is_selected=False,
                    areastyle_opts=opts.AreaStyleOpts(opacity=0.1),
                     linestyle_opts=opts.LineStyleOpts(width=2), )
            c.set_series_opts(label_opts=opts.LabelOpts(is_show=True))
            c.set_global_opts(title_opts=opts.TitleOpts(title=""))        
        tl.add(c,"{}日期".format(i))    
    return tl


def raDar(dd):
    tl = Timeline()
    dd = dd.drop(0)
    d1s = dd[['date','sIndex','pe_lyr','pr_ttm','pb','pct_dv']]
    d2s = dd[['date','sIndex','pe_lyr_ly','pr_ttm_ly','pb_ly']]
    date = dd.drop_duplicates(subset=('date'), keep='first').date.to_list()

    for i in date:
        d1 = d1s.groupby('date').get_group(i).reset_index(drop=True)
        d2 = d2s.groupby('date').get_group(i).reset_index(drop=True)

        c_schema = [
            {"name": "静态市盈率", "max": 30, "min": 5},
            {"name": "滚动市盈率", "max": 30, "min": 5},
            {"name": "市净率", "max": 5, "min": 0},
            {"name": "股息率", "max": 8},
        ]

        c = (
            Radar()
            .add_schema(schema=c_schema, shape="circle")
            .add(d2.loc[0][1].strip()+'去年底', [d2.loc[0].tolist()[2:]],is_selected=True,color="#b3e4a1",
                    areastyle_opts=opts.AreaStyleOpts(opacity=0.3),
                     linestyle_opts=opts.LineStyleOpts(width=2),)
            .add(d1.loc[0][1].strip(), [d1.loc[0].tolist()[2:]], is_selected=True,
                  linestyle_opts=opts.LineStyleOpts(width=2),)
            .add(d2.loc[1][1].strip()+'去年底', [d2.loc[1].tolist()[2:]], is_selected=False, color="#b3e4a1")
            .add(d1.loc[1][1].strip(), [d1.loc[1].tolist()[2:]], is_selected=False)
            .add(d2.loc[2][1].strip()+'去年底', [d2.loc[2].tolist()[2:]], is_selected=False, color="#b3e4a1")
            .add(d1.loc[2][1].strip(), [d1.loc[2].tolist()[2:]], is_selected=False)
            .add(d2.loc[3][1].strip()+'去年底', [d2.loc[3].tolist()[2:]], is_selected=False, color="#b3e4a1")
            .add(d1.loc[3][1].strip(), [d1.loc[3].tolist()[2:]], is_selected=False)
            .add(d2.loc[4][1].strip()+'去年底', [d2.loc[4].tolist()[2:]], is_selected=False, color="#b3e4a1")
            .add(d1.loc[4][1].strip(), [d1.loc[4].tolist()[2:]], is_selected=False)
            .add(d2.loc[5][1].strip()+'去年底', [d2.loc[5].tolist()[2:]], is_selected=False, color="#b3e4a1")
            .add(d1.loc[5][1].strip(), [d1.loc[5].tolist()[2:]], is_selected=False)
            .add(d2.loc[6][1].strip()+'去年底', [d2.loc[6].tolist()[2:]], is_selected=False, color="#b3e4a1")
            .add(d1.loc[6][1].strip(), [d1.loc[6].tolist()[2:]], is_selected=False)
            .add(d2.loc[7][1].strip()+'去年底', [d2.loc[7].tolist()[2:]], is_selected=False, color="#b3e4a1")
            .add(d1.loc[7][1].strip(), [d1.loc[7].tolist()[2:]], is_selected=False)
            .add(d2.loc[8][1].strip()+'去年底', [d2.loc[8].tolist()[2:]], is_selected=False, color="#b3e4a1")
            .add(d1.loc[8][1].strip(), [d1.loc[8].tolist()[2:]], is_selected=False)
            .add(d2.loc[9][1].strip()+'去年底', [d2.loc[9].tolist()[2:]], is_selected=False, color="#b3e4a1")
            .add(d1.loc[9][1].strip(), [d1.loc[9].tolist()[2:]], is_selected=False)
            .add(d2.loc[10][1].strip()+'去年底', [d2.loc[10].tolist()[2:]], is_selected=False, color="#b3e4a1")
            .add(d1.loc[10][1].strip(), [d1.loc[10].tolist()[2:]], is_selected=False)
            .set_series_opts(label_opts=opts.LabelOpts(is_show=True))
            .set_global_opts(title_opts=opts.TitleOpts(title=""))
            # .render("radar_air_quality.html")
        )
        tl.add(c,"{}日期".format(i))    
    return tl


def wordCloud(d):
    data= d.groupby(['code','exchange']).sum().round(2).reset_index()
    data['name'] = data.code + data.exchange
    c = (
            WordCloud()
            .add(series_name="热点分析", data_pair=[list(z) for z in zip(data.name,data.pct_chg)], word_size_range=[6, 66])
            .set_global_opts(
                title_opts=opts.TitleOpts(
                    title="热点分析", title_textstyle_opts=opts.TextStyleOpts(font_size=23)
                ),
                tooltip_opts=opts.TooltipOpts(is_show=True),
            )
            # .render("basic_wordcloud.html")
        )
    return c


def csWordCloud(d,yie):
    # data = d.sort_values(by=yie).head(25).append(d.sort_values(by=yie).tail(25))[['Index_code','Index_name', yie]].reset_index()
    data = pd.concat([d.sort_values(by=yie).head(25) , d.sort_values(by=yie).tail(25)[['Index_code','Index_name', yie]].reset_index()])
    data['name'] = data.Index_name + '-' + data.Index_code
    c = (
            WordCloud()
            .add(series_name="热点分析", data_pair=[list(z) for z in zip(data.Index_name,data[yie])], word_size_range=[8, 70])
            .set_global_opts(
                title_opts=opts.TitleOpts(
                    title="热点分析", title_textstyle_opts=opts.TextStyleOpts(font_size=23)
                ),
                tooltip_opts=opts.TooltipOpts(is_show=True),
            )
            # .render("basic_wordcloud.html")
        )
    return c

def timeLine_wordCloud(d):
    tl = Timeline()
    date = d.drop_duplicates(subset=('date'), keep='first').date.to_list()
    
    
    for i in date:  
        data= d.groupby('date').get_group(i).groupby(['code','exchange']).sum().reset_index()
        data['name'] = data.code + data.exchange
        # data['date'] = i
        # data = data[['date','name','pct_chg']]
        c = (
                WordCloud()
                .add(series_name="热点分析", data_pair=[list(z) for z in zip(data.name,data.pct_chg)], word_size_range=[6, 66])
                .set_global_opts(
                    title_opts=opts.TitleOpts(
                        title="热点分析 "+i, title_textstyle_opts=opts.TextStyleOpts(font_size=23)
                    ),
                    tooltip_opts=opts.TooltipOpts(is_show=True),
                )
                # .render("basic_wordcloud.html")
        )
        tl.add(c,"{}日期".format(i))
    return tl

def bar_datazoom_slider(dd) -> Bar:
    tl = Timeline()
    name_list = dd.loc[0][9:13].tolist()
    dd = dd.drop(0)
    d1s = dd[['date','sIndex','pe_lyr','pr_ttm','pb','pct_dv']]
    d2s = dd[['date','sIndex','pe_lyr_ly','pr_ttm_ly','pb_ly']]
    date = dd.drop_duplicates(subset=('date'), keep='first').date.to_list()

    for i in date:
        d1 = d1s.groupby('date').get_group(i).reset_index(drop=True)
        d2 = d2s.groupby('date').get_group(i).reset_index(drop=True)

        c = (
            Bar()
            .add_xaxis(name_list)
            .set_global_opts(title_opts=opts.TitleOpts(title=""),)
        )

        for j in range(0,8):
            c.add_yaxis(d2.loc[j][1].strip()+'去年底', d2.loc[j].tolist()[2:],stack=str(j))
            c.add_yaxis(d1.loc[j][1].strip(), d1.loc[j].tolist()[2:],stack=str(j))            
        tl.add(c,"{}日期".format(i))
    return tl


def line_markpoint(dd) -> Line:

    dd = dd.drop(0)
    d1s = dd[['date','sIndex','pe_lyr','pr_ttm','pb','pct_dv']]
    # d2s = dd[['date','sIndex','pe_lyr_ly','pr_ttm_ly','pb_ly']]
    d1g = d1s.groupby('sIndex')
    inName = d1g.head(1).sIndex.tolist()
    date = dd.drop_duplicates(subset=('date'), keep='first').date.to_list()
    c = (
        Line()
        .add_xaxis(date)
        .set_global_opts(title_opts=opts.TitleOpts(title=""))
    )
    for i in range(0,10):
        c.add_yaxis(inName[i], d1g.get_group(inName[i]).pe_lyr.tolist(),is_smooth=True, label_opts=opts.LabelOpts(is_show=False),)
    return c


def pie_rosetype(d) -> Pie:
    tl = Timeline()
    date = d.drop_duplicates(subset=('date'), keep='first').date.to_list()

    for i in date:
        dd = d.groupby('date').get_group(i)
        c = (
            Pie()
            .add(
                "收盘",
                [list(z) for z in zip(dd.code,dd.close)],
                radius=["15%", "50%"],
                center=["15%", "55%"],
                rosetype="radius",
                label_opts=opts.LabelOpts(is_show=False),
            )
            .add(
                "日涨跌幅(%)",
                [list(z) for z in zip(dd.code,dd.pct_chg)],
                radius=["15%", "50%"],
                center=["45%", "55%"],
                rosetype="radius",
            )
            .add(
                "贡献点数",
                [list(z) for z in zip(dd.code,dd.contrib)],
                radius=["15%", "50%"],
                center=["75%", "55%"],
                rosetype="radius",
                label_opts=opts.LabelOpts(is_show=False),
            )
            .set_global_opts(title_opts=opts.TitleOpts(title=""))
        )
        tl.add(c,"{}日期".format(i))
    return tl


def grid_mutil_yaxis() -> Grid:
    x_data = ["{}月".format(i) for i in range(1, 13)]
    bar = (
        Bar()
        .add_xaxis(x_data)
        .add_yaxis(
            "蒸发量",
            [2.0, 4.9, 7.0, 23.2, 25.6, 76.7, 135.6, 162.2, 32.6, 20.0, 6.4, 3.3],
            yaxis_index=0,
            color="#d14a61",
        )
        .add_yaxis(
            "降水量",
            [2.6, 5.9, 9.0, 26.4, 28.7, 70.7, 175.6, 182.2, 48.7, 18.8, 6.0, 2.3],
            yaxis_index=1,
            color="#5793f3",
        )
        .extend_axis(
            yaxis=opts.AxisOpts(
                name="蒸发量",
                type_="value",
                min_=0,
                max_=250,
                position="right",
                axisline_opts=opts.AxisLineOpts(
                    linestyle_opts=opts.LineStyleOpts(color="#d14a61")
                ),
                axislabel_opts=opts.LabelOpts(formatter="{value} ml"),
            )
        )
        .extend_axis(
            yaxis=opts.AxisOpts(
                type_="value",
                name="温度",
                min_=0,
                max_=25,
                position="left",
                axisline_opts=opts.AxisLineOpts(
                    linestyle_opts=opts.LineStyleOpts(color="#675bba")
                ),
                axislabel_opts=opts.LabelOpts(formatter="{value} °C"),
                splitline_opts=opts.SplitLineOpts(
                    is_show=True, linestyle_opts=opts.LineStyleOpts(opacity=1)
                ),
            )
        )
        .set_global_opts(
            yaxis_opts=opts.AxisOpts(
                name="降水量",
                min_=0,
                max_=250,
                position="right",
                offset=80,
                axisline_opts=opts.AxisLineOpts(
                    linestyle_opts=opts.LineStyleOpts(color="#5793f3")
                ),
                axislabel_opts=opts.LabelOpts(formatter="{value} ml"),
            ),
            title_opts=opts.TitleOpts(title="Grid-多 Y 轴示例"),
            tooltip_opts=opts.TooltipOpts(trigger="axis", axis_pointer_type="cross"),
        )
    )

    line = (
        Line()
        .add_xaxis(x_data)
        .add_yaxis(
            "平均温度",
            [2.0, 2.2, 3.3, 4.5, 6.3, 10.2, 20.3, 23.4, 23.0, 16.5, 12.0, 6.2],
            yaxis_index=2,
            color="#675bba",
            label_opts=opts.LabelOpts(is_show=False),
        )
    )

    bar.overlap(line)
    return Grid().add(
        bar, opts.GridOpts(pos_left="5%", pos_right="20%"), is_control_axis_index=True
    )

def timeline_pie():
    attr = Faker.choose()
    tl = Timeline()
    for i in range(2015, 2020):
        pie = (
            Pie()
            .add(
                "商家A",
                [list(z) for z in zip(attr, Faker.values())],
                rosetype="radius",
                radius=["30%", "55%"],
            )
            # .set_global_opts(title_opts=opts.TitleOpts("某商店{}年营业额".format(i)))
        )
        tl.add(pie, "{}年".format(i))
    # tl.render("timeline_pie.html")
    return tl

def tab():

    tab = Tab(js_host='/',page_title='板块分析')
    # tab.add(mytable.table(), 'mytable')
    # tab.add(bar_datazoom_slider(mkData), "指数估值")
    # tab.add(line_markpoint(mkData), "静态市盈率")
    # tab.add(pie_rosetype(hs300Data), "沪深300贡献TOP10")
    # tab.add(pie_rosetype(zz500Data), "中正500贡献TOP10")
    # tab.add(pie_rosetype(sz50Data), "上证50贡献TOP10")
    # tab.add(grid_mutil_yaxis(), "grid-example")
    # tab.add(timeline_pie(), "grid-example")
    tab.add(csWordCloud(csIndexsData,'3D'),'3日市场强弱板块')
    tab.add(csWordCloud(csIndexsData,'5D'),'5日市场强弱板块')
    tab.add(csWordCloud(csIndexsData,'21D'),'21日市场强弱板块')
    tab.add(csWordCloud(csIndexsData,'55D'),'55日市场强弱板块')    
    # tab.add(timeLine_wordCloud(wcData.tail(60)),'3日内分时市场强弱板块')
    # tab.add(timeLine_wordCloud(wcData.tail(100)),'5日内分时市场强弱板块')
    tab.add(timeLine_wordCloud(wcData.tail(420)),'21日内分时市场强弱板块')
    # tab.add(timeLine_wordCloud(wcData.tail(1000)),'55日内分时市场强弱板块')

    tab.add(csWordCloud(csData, 'Yie1M'),'cs1月市场强弱板块')
    tab.add(csWordCloud(csData, 'Yie3M'),'cs3月市场强弱板块')
    tab.add(csWordCloud(csData, 'YieToNow'),'cs至今市场强弱板块')
    tab.add(csWordCloud(csData, 'Yie1Y'),'cs1年市场强弱板块')
    tab.add(csWordCloud(csData, 'Yie3Y'),'cs3年市场强弱板块')
    tab.add(csWordCloud(csData, 'Yie5Y'),'cs5年市场强弱板块')
    # tab.add(csWordCloud(csData, '2016'),'2016年市场强弱板块')
    # tab.add(csWordCloud(csData, '2017'),'2017年市场强弱板块')
    # tab.add(csWordCloud(csData, '2018'),'2018年市场强弱板块')
    # tab.add(csWordCloud(csData, '2019'),'2019年市场强弱板块')

    # tab.add(raDar(mkData),"RaDar指数估值")
    # tab.add(raDarIndex(mkData),"RaDar指数")
    
    return tab

