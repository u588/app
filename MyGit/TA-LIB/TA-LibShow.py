import tkinter as tk
from tkinter import ttk
import matplotlib.pyplot as plt
import pandas as pd
import numpy as np
import talib as ta
from talib import MA_Type

from sqlalchemy import create_engine
home = '10.145.254.55:5432'
job = '10.3.18.56:5432'
ip = job

eng = create_engine('postgresql+psycopg2://sa:11111111@' + ip + '/tdxStocks')

stock = '002149'

dw = pd.read_sql(stock, eng).tail(200)
dw.dropna(inplace=True)
dw.datetime = dw.datetime.str.replace('15:00', '')
dw.set_index('datetime', inplace=True)
dw.index = pd.DatetimeIndex(dw.index)

plt.style.use({'figure.figsize':(12, 6)})


# 重叠指标
def overlap_process(event):
    print(event.widget.get())
    overlap = event.widget.get()
    
    dw['upperband'] , dw['middleband'] , dw['lowerband']  = ta.BBANDS(dw.close.values, timeperiod=21, nbdevup=2, nbdevdn=2, matype=0)
    fig, axes = plt.subplots(2, 1, sharex=True)
    ax1, ax2 = axes[0], axes[1]
    axes[0].plot(dw.close, 'rd-', markersize=1)
    axes[0].plot(dw.upperband, 'g-')
    axes[0].plot(dw.middleband, 'b-.')
    axes[0].plot(dw.lowerband, 'g-')
    axes[0].set_title(overlap, fontproperties="SimHei")
    
    if overlap == '布林线':
        pass
    elif overlap == '双指数移动平均线':
        dw['real1'] = ta.DEMA(dw.close.values, timeperiod=21)
        dw['real2'] = ta.DEMA(dw.close.values, timeperiod=5)
        axes[1].plot(dw.real1, 'r-')
        axes[1].plot(dw.real2, 'g-')
    elif overlap == '指数移动平均线 ':
        dw['real'] = ta.EMA(dw.close.values, timeperiod=30)
        axes[1].plot(dw.real, 'r-')
    elif overlap == '希尔伯特变换——瞬时趋势线':
        dw['real'] = ta.HT_TRENDLINE(dw.close.values)
        axes[1].plot(dw.real, 'r-')
    elif overlap == '考夫曼自适应移动平均线':
        dw['real'] = ta.KAMA(dw.close.values, timeperiod=30)
        axes[1].plot(dw.real, 'r-')
    elif overlap == '移动平均线':
        dw['real'] = ta.MA(dw.close.values, timeperiod=30, matype=0)
        axes[1].plot(dw.real, 'r-')
    elif overlap == 'MESA自适应移动平均':
        dw['mama'], dw['fama'] = ta.MAMA(dw.close.values, fastlimit=0.01, slowlimit=0.05)
        # 梅萨自适应移动平均线(MESA Adaptive Moving Average)
        # 参数
        #     input[double] 一维数组 收盘价
        #     optInFastLimit[double] 可选,从0.01到0.09 最高价
        #     optInSlowLimit[double] 可选,从0.01到0.09
        axes[1].plot(dw.mama, 'r-')
        axes[1].plot(dw.fama, 'g-')
    elif overlap == '变周期移动平均线':
        periods = dw.month
        dw['real'] = ta.MAVP(dw.close.values, periods , minperiod=2, maxperiod=30, matype=0)
        axes[1].plot(dw.real, 'r-')
    elif overlap == '简单移动平均线':
        dw['real'] = ta.SMA(dw.close.values, timeperiod=30)
        axes[1].plot(dw.real, 'r-')
    elif overlap == '三指数移动平均线(T3)':
        dw['real'] = ta.T3(dw.close.values, timeperiod=5, vfactor=0)
        axes[1].plot(dw.real, 'r-')
    elif overlap == '三指数移动平均线':
        dw['real'] = ta.TEMA(dw.close.values, timeperiod=30)
        axes[1].plot(dw.real, 'r-')
    elif overlap == '三角形加权法 ':
        dw['real'] = ta.TRIMA(dw.close.values, timeperiod=30)
        axes[1].plot(dw.real, 'r-')
    elif overlap == '加权移动平均数':
        dw['real'] = ta.WMA(dw.close.values, timeperiod=30)
        axes[1].plot(dw.real, 'r-')

    ax1.grid(ls='--')
    ax2.grid(ls='--')
    plt.subplots_adjust(left=0.05 ,bottom=0.05,right=0.97, top=0.93, wspace=0.2, hspace=0.2)
    plt.show()
 

# 动量指标
def momentum_process(event):
    print(event.widget.get())
    momentum = event.widget.get()
    
    dw['upperband'] , dw['middleband'] , dw['lowerband']  = ta.BBANDS(dw.close.values, timeperiod=5, nbdevup=2, nbdevdn=2, matype=0)
    fig, axes = plt.subplots(2, 1, sharex=True)
    ax1, ax2 = axes[0], axes[1]
    axes[0].plot(dw.close, 'rd-', markersize=3)
    axes[0].plot(dw.upperband, 'y-')
    axes[0].plot(dw.middleband, 'b-')
    axes[0].plot(dw.lowerband, 'y-')
    axes[0].set_title(momentum, fontproperties="SimHei")
    
    if momentum == '绝对价格振荡器':
        dw['real'] = ta.APO(dw.close.values, fastperiod=12, slowperiod=26, matype=0)
        axes[1].plot(dw.real, 'r-')
    elif momentum == '钱德动量摆动指标':
        dw['real'] = ta.CMO(dw.close.values, timeperiod=14)
        axes[1].plot(dw.real, 'r-')
    elif momentum == '移动平均收敛/散度':
        dw['macd'], dw['macdsignal'], dw['macdhist'] = ta.MACD(dw.close.values, fastperiod=12, slowperiod=26, signalperiod=9)
        axes[1].plot(dw.macd, 'r-')
        axes[1].plot(dw.macdsignal, 'g-')
        axes[1].plot(dw.macdhist, 'b-')
    elif momentum == '带可控MA类型的MACD':
        dw['macd'], dw['macdsignal'], dw['macdhist'] = ta.MACDEXT(dw.close.values, fastperiod=12, fastmatype=0, slowperiod=26, slowmatype=0, signalperiod=9, signalmatype=0)
        axes[1].plot(dw.macd, 'r-')
        axes[1].plot(dw.macdsignal, 'g-')
        axes[1].plot(dw.macdhist, 'b-')
    elif momentum == '移动平均收敛/散度 固定 12/26':
        dw['macd'], dw['macdsignal'], dw['macdhist'] = ta.MACDFIX(dw.close.values, signalperiod=9)
        axes[1].plot(dw.macd, 'r-')
        axes[1].plot(dw.macdsignal, 'g-')
        axes[1].plot(dw.macdhist, 'b-')
    elif momentum == '动量':
        dw['real'] = ta.MOM(dw.close.values, timeperiod=10)
        axes[1].plot(dw.real, 'r-')
    elif momentum == '比例价格振荡器':
        dw['real'] = ta.PPO(dw.close.values, fastperiod=12, slowperiod=26, matype=0)
        axes[1].plot(dw.real, 'r-')
    elif momentum == '变化率':
        dw['real'] = ta.ROC(dw.close.values, timeperiod=10)
        axes[1].plot(dw.real, 'r-')
    elif momentum == '变化率百分比':
        dw['real'] = ta.ROCP(dw.close.values, timeperiod=10)
        axes[1].plot(dw.real, 'r-')
    elif momentum == '变化率的比率':
        dw['real'] = ta.ROCR(dw.close.values, timeperiod=10)
        axes[1].plot(dw.real, 'r-')
    elif momentum == '变化率的比率100倍':
        dw['real'] = ta.ROCR100(dw.close.values, timeperiod=10)
        axes[1].plot(dw.real, 'r-')
    elif momentum == '相对强弱指数':
        dw['real'] = ta.RSI(dw.close.values, timeperiod=14)
        axes[1].plot(dw.real, 'r-')
    elif momentum == '随机相对强弱指标':
        dw['fastk'], dw['fastd'] = ta.STOCHRSI(dw.close.values, timeperiod=14, fastk_period=5, fastd_period=3, fastd_matype=0)
        axes[1].plot(dw.fastk, 'r-')
        axes[1].plot(dw.fastd, 'r-')
    elif momentum == '三重光滑EMA的日变化率':
        dw['real'] = ta.TRIX(dw.close.values, timeperiod=30)
        axes[1].plot(dw.real, 'r-')

    ax1.grid(ls='--')
    ax2.grid(ls='--')
    plt.subplots_adjust(left=0.05 ,bottom=0.05,right=0.97, top=0.93, wspace=0.2, hspace=0.2)
    plt.show()
    

# 周期指标
def cycle_process(event):
    print(event.widget.get())
    cycle = event.widget.get()
    
    dw['upperband'] , dw['middleband'] , dw['lowerband']  = ta.BBANDS(dw.close.values, timeperiod=5, nbdevup=2, nbdevdn=2, matype=0)
    fig, axes = plt.subplots(2, 1, sharex=True)
    ax1, ax2 = axes[0], axes[1]
    axes[0].plot(dw.close, 'rd-', markersize=3)
    axes[0].plot(dw.upperband, 'y-')
    axes[0].plot(dw.middleband, 'b-')
    axes[0].plot(dw.lowerband, 'y-')
    axes[0].set_title(cycle, fontproperties="SimHei")
    
    if cycle == '希尔伯特变换——主要的循环周期':
        dw['real'] = ta.HT_DCPERIOD(dw.close.values)
        axes[1].plot(dw.real, 'r-')
    elif cycle == '希尔伯特变换——主要的周期阶段':
        dw['real'] = ta.HT_DCPHASE(dw.close.values)
        axes[1].plot(dw.real, 'r-')
    elif cycle == '希尔伯特变换——相量组件':
        dw['inphase'], dw['quadrature'] = ta.HT_PHASOR(dw.close.values)
        axes[1].plot(dw.inphase, 'r-')
        axes[1].plot(dw.quadrature, 'g-')
    elif cycle == '希尔伯特变换——正弦曲线':
        dw['sine'], dw['leadsine'] = ta.HT_SINE(dw.close.values)
        axes[1].plot(dw.sine, 'r-')
        axes[1].plot(dw.leadsine, 'g-')
    elif cycle == '希尔伯特变换——趋势和周期模式':
        dw['integer'] = ta.HT_TRENDMODE(dw.close.values)
        axes[1].plot(dw.integer, 'r-')
        
    ax1.grid(ls='--')
    ax2.grid(ls='--')
    plt.subplots_adjust(left=0.05 ,bottom=0.05,right=0.97, top=0.93, wspace=0.2, hspace=0.2)
    plt.show()
    
    
# 统计功能
def statistic_process(event):
    print(event.widget.get())
    statistic = event.widget.get()
    
    dw['upperband'] , dw['middleband'] , dw['lowerband']  = ta.BBANDS(dw.close.values, timeperiod=5, nbdevup=2, nbdevdn=2, matype=0)
    fig, axes = plt.subplots(2, 1, sharex=True)
    ax1, ax2 = axes[0], axes[1]
    axes[0].plot(dw.close, 'rd-', markersize=3)
    axes[0].plot(dw.upperband, 'y-')
    axes[0].plot(dw.middleband, 'b-')
    axes[0].plot(dw.lowerband, 'y-')
    axes[0].set_title(statistic, fontproperties="SimHei")
    
    if statistic == '线性回归':
        dw['real'] = ta.LINEARREG(dw.close.values, timeperiod=14)
        axes[1].plot(dw.real, 'r-')
    elif statistic == '贝塔系数；投资风险与股市风险系数':
        dw['real'] = ta.BETA(dw.high.values, dw.low.values, timeperiod=5)
        axes[1].plot(dw.real, 'r-')
    elif statistic == '皮尔逊相关系数':
        dw['real'] = ta.CORREL(dw.high.values, dw.low.values, timeperiod=30)
        axes[1].plot(dw.real, 'r-')
    elif statistic == '线性回归角度':
        dw['real'] = ta.LINEARREG_ANGLE(dw.close.values, timeperiod=14)
        axes[1].plot(dw.real, 'r-')
    elif statistic == '线性回归截距':
        dw['real'] = ta.LINEARREG_INTERCEPT(dw.close.values, timeperiod=14)
        axes[1].plot(dw.real, 'r-')
    elif statistic == '线性回归斜率':
        dw['real'] = ta.LINEARREG_SLOPE(dw.close.values, timeperiod=14)
        axes[1].plot(dw.real, 'r-')
    elif statistic == '标准差':
        dw['real'] = ta.STDDEV(dw.close.values, timeperiod=5, nbdev=1)
        axes[1].plot(dw.real, 'r-')
    elif statistic == '时间序列预测':
        dw['real'] = ta.TSF(dw.close.values, timeperiod=14)
        axes[1].plot(dw.real, 'r-')
    elif statistic == '方差':
        dw['real'] = ta.VAR(dw.close.values, timeperiod=5, nbdev=1)
        axes[1].plot(dw.real, 'r-')

    ax1.grid(ls='--')
    ax2.grid(ls='--')
    plt.subplots_adjust(left=0.05 ,bottom=0.05,right=0.97, top=0.93, wspace=0.2, hspace=0.2)
    plt.show()

    
# 数学变换
def math_transform_process(event):
    print(event.widget.get())
    math_transform = event.widget.get()
    
    dw['upperband'] , dw['middleband'] , dw['lowerband']  = ta.BBANDS(dw.close.values, timeperiod=5, nbdevup=2, nbdevdn=2, matype=0)
    fig, axes = plt.subplots(2, 1, sharex=True)
    ax1, ax2 = axes[0], axes[1]
    axes[0].plot(dw.close, 'rd-', markersize=3)
    axes[0].plot(dw.upperband, 'y-')
    axes[0].plot(dw.middleband, 'b-')
    axes[0].plot(dw.lowerband, 'y-')
    axes[0].set_title(math_transform, fontproperties="SimHei")

    if math_transform == '反余弦':
        dw['real'] = ta.ACOS(dw.close.values)
        axes[1].plot(dw.real, 'r-')
    elif math_transform == '反正弦':
        dw['real'] = ta.ASIN(dw.close.values)
        axes[1].plot(dw.real, 'r-')
    elif math_transform == '反正切':
        dw['real'] = ta.ATAN(dw.close.values)
        axes[1].plot(dw.real, 'r-')
    elif math_transform == '向上取整':
        dw['real'] = ta.CEIL(dw.close.values)
        axes[1].plot(dw.real, 'r-')
    elif math_transform == '余弦':
        dw['real'] = ta.COS(dw.close.values)
        axes[1].plot(dw.real, 'r-')
    elif math_transform == '双曲余弦':
        dw['real'] = ta.COSH(dw.close.values)
        axes[1].plot(dw.real, 'r-')
    elif math_transform == '指数':
        dw['real'] = ta.EXP(dw.close.values)
        axes[1].plot(dw.real, 'r-')
    elif math_transform == '向下取整':
        dw['real'] = ta.FLOOR(dw.close.values)
        axes[1].plot(dw.real, 'r-')
    elif math_transform == '自然对数':
        dw['real'] = ta.LN(dw.close.values)
        axes[1].plot(dw.real, 'r-')
    elif math_transform == '常用对数':
        dw['real'] = ta.LOG10(dw.close.values)
        axes[1].plot(dw.real, 'r-')
    elif math_transform == '正弦':
        dw['real'] = ta.SIN(dw.close.values)
        axes[1].plot(dw.real, 'r-')
    elif math_transform == '双曲正弦':
        dw['real'] = ta.SINH(dw.close.values)
        axes[1].plot(dw.real, 'r-')
    elif math_transform == '平方根':
        dw['real'] = ta.SQRT(dw.close.values)
        axes[1].plot(dw.real, 'r-')
    elif math_transform == '正切':
        dw['real'] = ta.TAN(dw.close.values)
        axes[1].plot(dw.real, 'r-')
    elif math_transform == '双曲正切':
        dw['real'] = ta.TANH(dw.close.values)
        axes[1].plot(dw.real, 'r-')
        
    ax1.grid(ls='--')
    ax2.grid(ls='--')
    plt.subplots_adjust(left=0.05 ,bottom=0.05,right=0.97, top=0.93, wspace=0.2, hspace=0.2)
    plt.show()

    
# 数学操作
def math_operator_process(event):
    print(event.widget.get())
    math_operator = event.widget.get()
    
    dw['upperband'] , dw['middleband'] , dw['lowerband']  = ta.BBANDS(dw.close.values, timeperiod=5, nbdevup=2, nbdevdn=2, matype=0)
    fig, axes = plt.subplots(2, 1, sharex=True)
    ax1, ax2 = axes[0], axes[1]
    axes[0].plot(dw.close, 'rd-', markersize=3)
    axes[0].plot(dw.upperband, 'y-')
    axes[0].plot(dw['middleband'] , 'b-')
    axes[0].plot(dw.lowerband, 'y-')
    axes[0].set_title(math_operator, fontproperties="SimHei")
    
    if math_operator == '指定的期间的最大值':
        dw['real'] = ta.MAX(dw.close.values, timeperiod=30)
        axes[1].plot(dw.real, 'r-')
    elif math_operator == '指定的期间的最大值的索引':
        dw['integer'] = ta.MAXINDEX(dw.close.values, timeperiod=30)
        axes[1].plot(dw.integer, 'r-')
    elif math_operator == '指定的期间的最小值':
        dw['real'] = ta.MIN(dw.close.values, timeperiod=30)
        axes[1].plot(dw.real, 'r-')
    elif math_operator == '指定的期间的最小值的索引':
        dw['integer'] = ta.MININDEX(dw.close.values, timeperiod=30)
        axes[1].plot(dw.integer, 'r-')
    elif math_operator == '指定的期间的最小和最大值':
        dw['min'], dw['max'] = ta.MINMAX(dw.close.values, timeperiod=30)
        axes[1].plot(dw.min, 'r-')
        axes[1].plot(dw.max, 'r-')
    elif math_operator == '指定的期间的最小和最大值的索引':
        dw['minidx'], dw['maxidx'] = ta.MINMAXINDEX(dw.close.values, timeperiod=30)
        axes[1].plot(dw.minidx, 'r-')
        axes[1].plot(dw.maxidx, 'r-')
    elif math_operator == '合计':
        dw['real'] = ta.SUM(dw.close.values, timeperiod=30)
        axes[1].plot(dw.real, 'r-')

    ax1.grid(ls='--')
    ax2.grid(ls='--')
    plt.subplots_adjust(left=0.05 ,bottom=0.05,right=0.97, top=0.93, wspace=0.2, hspace=0.2)
    plt.show()


# 量价指标
def volume_process(event):
    print(event.widget.get())
    Volume_Indicator = event.widget.get()
    
    dw['upperband'] , dw['middleband'] , dw['lowerband']  = ta.BBANDS(dw.close.values, timeperiod=5, nbdevup=2, nbdevdn=2, matype=0)
    fig, axes = plt.subplots(2, 1, sharex=True)
    ax1, ax2 = axes[0], axes[1]
    axes[0].plot(dw.close, 'rd-', markersize=3)
    axes[0].plot(dw.upperband, 'y-')
    axes[0].plot(dw['middleband'] , 'b-')
    axes[0].plot(dw.lowerband, 'y-')
    axes[0].set_title(Volume_Indicator, fontproperties="SimHei")
    
    if Volume_Indicator == '量价指标':
        dw['real'] = ta.AD(dw.high.values, dw.low.values, dw.close.values, dw.vol.values)
        axes[1].plot(dw.real, 'r-')
    elif Volume_Indicator == '震荡指标':
        dw['real'] = ta.ADOSC(dw.high.values, dw.low.values, dw.close.values, dw.vol.values, fastperiod=3, slowperiod=10)
        axes[1].plot(dw.real, 'r-')
    elif Volume_Indicator == '能量潮':
        dw['real'] = ta.OBV(dw.close.values, dw.vol.values)
        axes[1].plot(dw.real, 'r-')

    ax1.grid(ls='--')
    ax2.grid(ls='--')
    plt.subplots_adjust(left=0.05 ,bottom=0.05,right=0.97, top=0.93, wspace=0.2, hspace=0.2)
    plt.show()


# 波动率指标
def Volatility_process(event):
    print(event.widget.get())
    Volatility_Indicator = event.widget.get()
    
    dw['upperband'] , dw['middleband'] , dw['lowerband']  = ta.BBANDS(dw.close.values, timeperiod=5, nbdevup=2, nbdevdn=2, matype=0)
    fig, axes = plt.subplots(2, 1, sharex=True)
    ax1, ax2 = axes[0], axes[1]
    axes[0].plot(dw.close, 'rd-', markersize=3)
    axes[0].plot(dw.upperband, 'y-')
    axes[0].plot(dw['middleband'] , 'b-')
    axes[0].plot(dw.lowerband, 'y-')
    axes[0].set_title(Volatility_Indicator, fontproperties="SimHei")
        
    if Volatility_Indicator == '真实波动幅度均值':
        dw['real'] = ta.ATR(dw.high.values, dw.low.values, dw.close.values, timeperiod=14)
        axes[1].plot(dw.real, 'r-')
    elif Volatility_Indicator == '归一化波动幅度均值':
        dw['real'] = ta.NATR(dw.high.values, dw.low.values, dw.close.values, timeperiod=14)
        axes[1].plot(dw.real, 'r-')
    elif Volatility_Indicator == '真正范围':
        dw['real'] = ta.TRANGE(dw.high.values, dw.low.values, dw.close.values)
        axes[1].plot(dw.real, 'r-')

    ax1.grid(ls='--')
    ax2.grid(ls='--')
    plt.subplots_adjust(left=0.05 ,bottom=0.05,right=0.97, top=0.93, wspace=0.2, hspace=0.2)
    plt.show()    



root = tk.Tk()

# 第一行：重叠指标
rowframe1 = tk.Frame(root)
rowframe1.pack(side=tk.TOP, ipadx=3, ipady=3)
tk.Label(rowframe1, text="重叠指标").pack(side=tk.LEFT)
overlap_indicator = tk.StringVar() # 重叠指标

combobox1 = ttk.Combobox(rowframe1, textvariable=overlap_indicator)
combobox1['values'] = ['布林线','双指数移动平均线','指数移动平均线 ','希尔伯特变换——瞬时趋势线',
                       '考夫曼自适应移动平均线','移动平均线','MESA自适应移动平均','变周期移动平均线',
                       '简单移动平均线','三指数移动平均线(T3)','三指数移动平均线','三角形加权法 ','加权移动平均数']
combobox1.current(0)
combobox1.pack(side=tk.LEFT)
combobox1.bind('<<ComboboxSelected>>', overlap_process)


# 第二行：动量指标
rowframe2 = tk.Frame(root)
rowframe2.pack(side=tk.TOP, ipadx=3, ipady=3)
tk.Label(rowframe2, text="动量指标").pack(side=tk.LEFT)
momentum_indicator = tk.StringVar() # 动量指标

combobox2 = ttk.Combobox(rowframe2, textvariable=momentum_indicator)
combobox2['values'] = ['绝对价格振荡器','钱德动量摆动指标','移动平均收敛/散度','带可控MA类型的MACD',
                       '移动平均收敛/散度 固定 12/26','动量','比例价格振荡器','变化率','变化率百分比',
                       '变化率的比率','变化率的比率100倍','相对强弱指数','随机相对强弱指标','三重光滑EMA的日变化率']
combobox2.current(0)
combobox2.pack(side=tk.LEFT)
combobox2.bind('<<ComboboxSelected>>', momentum_process)


# 第三行：周期指标
rowframe3 = tk.Frame(root)
rowframe3.pack(side=tk.TOP, ipadx=3, ipady=3)
tk.Label(rowframe3, text="周期指标").pack(side=tk.LEFT)
cycle_indicator = tk.StringVar() # 周期指标

combobox3 = ttk.Combobox(rowframe3, textvariable=cycle_indicator)
combobox3['values'] = ['希尔伯特变换——主要的循环周期','希尔伯特变换——主要的周期阶段','希尔伯特变换——相量组件',
                       '希尔伯特变换——正弦曲线','希尔伯特变换——趋势和周期模式']
combobox3.current(0)
combobox3.pack(side=tk.LEFT)
combobox3.bind('<<ComboboxSelected>>', cycle_process)


# 第四行：统计功能
rowframe4 = tk.Frame(root)
rowframe4.pack(side=tk.TOP, ipadx=3, ipady=3)
tk.Label(rowframe4, text="统计功能").pack(side=tk.LEFT)
statistic_indicator = tk.StringVar() # 统计功能

combobox4 = ttk.Combobox(rowframe4, textvariable=statistic_indicator)
combobox4['values'] = ['贝塔系数；投资风险与股市风险系数','皮尔逊相关系数','线性回归','线性回归角度',
                       '线性回归截距','线性回归斜率','标准差','时间序列预测','方差']
combobox4.current(0)
combobox4.pack(side=tk.LEFT)
combobox4.bind('<<ComboboxSelected>>', statistic_process)


# 第五行：数学变换
rowframe5 = tk.Frame(root)
rowframe5.pack(side=tk.TOP, ipadx=3, ipady=3)
tk.Label(rowframe5, text="数学变换").pack(side=tk.LEFT)
math_transform = tk.StringVar() # 数学变换

combobox5 = ttk.Combobox(rowframe5, textvariable=math_transform)
combobox5['values'] = ['反余弦','反正弦','反正切','向上取整','余弦','双曲余弦','指数','向下取整',
                       '自然对数','常用对数','正弦','双曲正弦','平方根','正切','双曲正切']
combobox5.current(0)
combobox5.pack(side=tk.LEFT)
combobox5.bind('<<ComboboxSelected>>', math_transform_process)


# 第六行：数学操作
rowframe6 = tk.Frame(root)
rowframe6.pack(side=tk.TOP, ipadx=3, ipady=3)
tk.Label(rowframe6, text="数学操作").pack(side=tk.LEFT)
math_operator = tk.StringVar() # 数学操作

combobox6 = ttk.Combobox(rowframe6, textvariable=math_operator)
combobox6['values'] = ['指定期间的最大值','指定期间的最大值的索引','指定期间的最小值','指定期间的最小值的索引',
                       '指定期间的最小和最大值','指定期间的最小和最大值的索引','合计']
combobox6.current(0)
combobox6.pack(side=tk.LEFT)
combobox6.bind('<<ComboboxSelected>>', math_operator_process)


# 第七行：成交量指标
rowframe7 = tk.Frame(root)
rowframe7.pack(side=tk.TOP, ipadx=3, ipady=3)
tk.Label(rowframe7, text="成交量指标").pack(side=tk.LEFT)
Volume_Indicators = tk.StringVar() # 成交量指标

combobox7 = ttk.Combobox(rowframe7, textvariable=Volume_Indicators)
combobox7['values'] = ['量价指标', '震荡指标', '能量潮']
combobox7.current(0)
combobox7.pack(side=tk.LEFT)
combobox7.bind('<<ComboboxSelected>>', volume_process)


# 第八行：波动率指标
rowframe8 = tk.Frame(root)
rowframe8.pack(side=tk.TOP, ipadx=3, ipady=3)
tk.Label(rowframe8, text="波动率指标").pack(side=tk.LEFT)
Volatility_Indicators = tk.StringVar() # 波动率指标

combobox8 = ttk.Combobox(rowframe8, textvariable=Volatility_Indicators)
combobox8['values'] = ['真实波动幅度均值', '归一化波动幅度均值', '真正范围']
combobox8.current(0)
combobox8.pack(side=tk.LEFT)
combobox8.bind('<<ComboboxSelected>>', Volatility_process)

root.mainloop() 