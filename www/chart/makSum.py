from pyecharts import options as opts
from pyecharts.charts import  Timeline ,WordCloud
from sqlalchemy import create_engine
import pandas as pd
from sklearn import preprocessing
from math import pi

from bokeh.palettes import Category20c
from bokeh.transform import cumsum,log_cmap
from bokeh.models import ColumnDataSource, RangeTool, WheelZoomTool
from bokeh.plotting import figure


eng = create_engine('postgresql+psycopg://sa:11111111@10.145.254.56:5432/smDaily')
engTDX = create_engine('postgresql+psycopg://sa:11111111@10.145.254.56:5432/tdxIndex')

def pie(d,yie):
    d.sort_values(by=yie, inplace=True)
    data = pd.concat([d.head(10) , d.tail(10)])[['IndexCode','IndexName', yie]].reset_index(drop=True)
    data['name'] = data.IndexName + '-' + data.IndexCode
    data['pp'] = data[yie]
    data['value']= data[yie]+7
    data['angle'] = data['value']/data['value'].sum() * 2*pi
    data['color'] = Category20c[len(data)]

    p = figure(height=350, title="Pie Chart", toolbar_location=None,
            tools="hover", tooltips="@IndexName: @pp", x_range=(-0.5, 1.0))

    p.wedge(x=0, y=1, radius=0.4,
            start_angle=cumsum('angle', include_zero=True), end_angle=cumsum('angle'),
            line_color="white",  fill_color='color', legend_field='IndexName', source=data)

    p.axis.axis_label = None
    p.axis.visible = False
    p.grid.grid_line_color = None
    return p

def d3(d,yie):
    d.sort_values(by=yie, inplace=True)
    data = pd.concat([d.head(20) , d.tail(10)])[['IndexCode','IndexName', yie]].reset_index(drop=True)
    data['name'] = data.IndexName + '：' + data.IndexCode
    data['pct'] = data[yie]

    TOOLS="hover,crosshair,pan,box_zoom,undo,ywheel_zoom,redo,reset,tap,save"

    TOOLTIPS = [
        ("名称", "@name"),
        ("Pct", '@Y')
    ]


    size =  ((preprocessing.minmax_scale(abs(data.pct)))*58).round(2)

    cmap = log_cmap(field_name='Y', palette="RdYlGn8", low=min(abs(data['pct'])), high=max(abs(data['pct'])))
    source = ColumnDataSource(data=dict(X=list(range(len(data))), Y=data['pct'],name = data['name'] ,size=size))
    p = figure(height=500, width=1800, tools=TOOLS, toolbar_location="right",
        #    x_axis_location="above",
            background_fill_color="#efefef",
            tooltips = TOOLTIPS)

    # p.line('date', 'close', source=source)
    p.scatter(x='X' ,y='Y', color=cmap, size='size', alpha=0.5, source=source, line_color='#333333')
    p.yaxis.axis_label = 'pct'
    wheel_zoom = WheelZoomTool()
    wheel_zoom.dimensions = 'width'
    p.add_tools(wheel_zoom)
    p.toolbar.active_scroll = wheel_zoom
    p.toolbar.autohide = True


    return p



def csWordCloud(d,yie):
    d.sort_values(by=yie, inplace=True)
    data = pd.concat([d.head(15) , d.tail(15)[['IndexCode','IndexName', yie]].reset_index()])
    data['name'] = data.IndexName + '-' + data.IndexCode
    c = (
            WordCloud()
            .add(series_name="热点分析", data_pair=[list(z) for z in zip(data.IndexName,data[yie])], word_size_range=[8, 70])
            .set_global_opts(
                # title_opts=opts.TitleOpts(
                #     title="热点分析", title_textstyle_opts=opts.TextStyleOpts(font_size=23)
                # ),
                tooltip_opts=opts.TooltipOpts(is_show=True),
            )
            # .render("basic_wordcloud.html")
        )
    return c

def timeLine_wordCloud(d):
    tl = Timeline()
    date = d.drop_duplicates(subset=('date'), keep='first').date.to_list()
    for i in date:  
        data= d.groupby('date').get_group(i).groupby(['code','exchange']).sum(numeric_only=True).reset_index()
        data['name'] = data.code + data.exchange
        c = (
                WordCloud()
                .add(series_name="热点分析", data_pair=[list(z) for z in zip(data.name,data.pct_chg)], word_size_range=[8, 70])
                .set_global_opts(
                    title_opts=opts.TitleOpts(
                        title="日期： "+i, title_textstyle_opts=opts.TextStyleOpts(font_size=23),
                    ),
                    tooltip_opts=opts.TooltipOpts(is_show=True),
                )
        )
        tl.add(c,"{}日期".format(i))
    return tl


def testtab(yie):
    tdxIndexsData = pd.read_sql('tdxIndexsData', engTDX)
    engTDX.dispose()
    c = csWordCloud(tdxIndexsData,yie)
    return c

def pp(yie):
    tdxIndexsData = pd.read_sql('tdxIndexsData', engTDX)
    engTDX.dispose()
    c = d3(tdxIndexsData,yie)
    return c

def testti():
    strongData = pd.read_sql_table('Strong',eng)
    weakData = pd.read_sql_table('weak',eng)
    eng.dispose()
    wcData = pd.concat([strongData, weakData], ignore_index=True).sort_values(by=['date']).reset_index(drop=True)
    c = timeLine_wordCloud(wcData.tail(420))
    return c