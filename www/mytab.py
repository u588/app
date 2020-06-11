from pyecharts import options as opts
from pyecharts.charts import Bar, Grid, Line, Pie, Tab, Timeline
from pyecharts.faker import Faker
import mytable
from sqlalchemy import create_engine
import pandas as pd

from pyecharts.charts import WordCloud


eng = create_engine('postgresql+psycopg2://sa:11111111@10.145.254.56:5432/smDaily')

hs300Data = pd.read_sql('hs300', eng)
zz500Data = pd.read_sql('zz500', eng)
sz50Data = pd.read_sql('sz50', eng)
strongData = pd.read_sql_table('Strong',eng)
weakData = pd.read_sql_table('weak',eng)
wcData = pd.concat([strongData, weakData], ignore_index=True)
mkData = pd.read_sql('Market',eng)




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
                        title="热点分析", title_textstyle_opts=opts.TextStyleOpts(font_size=23)
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
        d1 = d1s.groupby('date').get_group(i)
        d2 = d2s.groupby('date').get_group(i)

        c = (
            Bar()
            .add_xaxis(name_list)
            for ii in d1.sIndex.tolist():
                .add_yaxis(ii.strip()+'去年底', d2.loc[1].tolist()[2:],stack='1')
                .add_yaxis(ii.strip(), d1.loc[1].tolist()[2:],stack='1')

            .set_global_opts(
                title_opts=opts.TitleOpts(title=""),
                # datazoom_opts=[opts.DataZoomOpts()],
            )
        )
        tl.add(c,"{}日期".format(i))
    return tl


def line_markpoint() -> Line:
    c = (
        Line()
        .add_xaxis(Faker.choose())
        .add_yaxis(
            "商家A",
            Faker.values(),
            markpoint_opts=opts.MarkPointOpts(data=[opts.MarkPointItem(type_="min")]),
        )
        .add_yaxis(
            "商家B",
            Faker.values(),
            markpoint_opts=opts.MarkPointOpts(data=[opts.MarkPointItem(type_="max")]),
        )
        .set_global_opts(title_opts=opts.TitleOpts(title="Line-MarkPoint"))
    )
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

    tab = Tab(js_host='/',page_title='TAB')
    tab.add(mytable.table(), 'mytable')
    tab.add(bar_datazoom_slider(mkData), "指数估值")
    tab.add(line_markpoint(), "line-example")
    tab.add(pie_rosetype(hs300Data), "沪深300贡献TOP10")
    tab.add(pie_rosetype(zz500Data), "中正500贡献TOP10")
    tab.add(pie_rosetype(sz50Data), "上证50贡献TOP10")
    tab.add(grid_mutil_yaxis(), "grid-example")
    tab.add(timeline_pie(), "grid-example")
    tab.add(wordCloud(wcData),'市场强弱板块')
    tab.add(timeLine_wordCloud(wcData),'分时市场强弱板块')
    
    return tab

