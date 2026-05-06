#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
宏观经济图表渲染引擎
=====================
统一管理所有宏观图表的创建和渲染。
将原始 MacroVisualizer 中的 9 种图表拆分为可独立调用的方法，
通过 ThemeConfig 统一样式，通过 plot_helpers 复用通用逻辑。
"""

from typing import Dict, List, Optional, Tuple

import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from visualization.config.theme_config import ThemeConfig, get_default_theme
from visualization.utils.plot_helpers import (
    create_subplots, add_reference_line, add_bar_trace, add_line_trace,
    compute_yoy_series
)


class MacroChartEngine:
    """宏观经济图表渲染引擎

    提供宏观经济分析所需的各类图表创建方法。
    每种图表方法返回独立的 Plotly Figure 对象，
    可由 ReportService 组合为完整报告。

    Usage:
        engine = MacroChartEngine(data=analyzer.data, analysis=analyzer.analysis)
        fig = engine.chart_economic_growth()
        fig.show()
    """

    # 维度中文名映射
    CATEGORY_LABELS = {
        'economic_growth': '经济增长',
        'prosperity': '景气度',
        'monetary': '货币金融',
        'trade_fx': '贸易外汇',
        'energy_industry': '能源工业',
        'capital_market': '资本市场',
        'international': '国际环境',
    }

    def __init__(self, data: Dict[str, pd.DataFrame],
                 analysis: Dict[str, Dict],
                 theme: Optional[ThemeConfig] = None):
        """初始化图表引擎

        Args:
            data: 指标键名到 DataFrame 的映射
            analysis: 各维度分析结果
            theme: 主题配置
        """
        self.data = data
        self.analysis = analysis
        self.theme = theme or get_default_theme()

    def chart_economic_growth(self) -> go.Figure:
        """图表1: 经济增长全景"""
        fig = create_subplots(
            rows=2, cols=2,
            titles=['GDP增速趋势', '工业增加值增速', '社会消费品零售总额', '城镇固定资产投资'],
        )

        # GDP增速
        df_gdp = self._get_gdp_growth_series()
        if len(df_gdp) > 0:
            add_bar_trace(fig, df_gdp['date'], df_gdp['value'], 'GDP增速',
                         self.theme.get_color('secondary'), row=1, col=1)
            add_reference_line(fig, y=5, text='5%目标', row=1, col=1,
                              color=self.theme.get_color('accent'))

        # 工业增加值
        if 'VAI' in self.data:
            df = self.data['VAI']
            add_line_trace(fig, df['date'], df['value'], '工业增加值增速',
                          self.theme.get_color('accent'), row=1, col=2,
                          mode='lines+markers')
            add_reference_line(fig, y=0, row=1, col=2, color='gray')

        # 社消零售
        if 'MSR' in self.data:
            df = self.data['MSR']
            add_bar_trace(fig, df['date'], df['value'], '社消零售(万亿)',
                         self.theme.get_color('success'), row=2, col=1)

        # 固定资产投资
        if 'UFA' in self.data:
            df = self.data['UFA']
            add_bar_trace(fig, df['date'], df['value'], '城镇固投(万亿)',
                         self.theme.get_color('warning'), row=2, col=2)

        self.theme.apply_to(fig, '经济增长全景', height=800)
        fig.update_yaxes(title_text='%', row=1, col=1)
        fig.update_yaxes(title_text='%', row=1, col=2)
        fig.update_yaxes(title_text='万亿元', row=2, col=1)
        fig.update_yaxes(title_text='万亿元', row=2, col=2)
        return fig

    def chart_pmi_prosperity(self) -> go.Figure:
        """图表2: PMI与景气度"""
        fig = create_subplots(
            rows=2, cols=2,
            titles=['制造业PMI与荣枯线', 'PMI分项指标', '消费者信心指数', '经济景气指数'],
        )

        # PMI
        if 'PMI' in self.data:
            df = self.data['PMI']
            colors = self.theme.get_indicator_colors(df['value'].tolist(), threshold=50)
            add_bar_trace(fig, df['date'], df['value'], '制造业PMI', colors,
                         row=1, col=1, opacity=0.85)
            add_reference_line(fig, y=50, text='荣枯线', row=1, col=1, color='black')

        # PMI分项
        for i, (key, name) in enumerate([('PMI_ORDER', '新订单'), ('PMI_EMP', '从业人员'), ('PMI_INV', '库存')]):
            if key in self.data:
                df = self.data[key]
                add_line_trace(fig, df['date'], df['value'], name,
                              self.theme.get_palette_color(i), row=1, col=2)
        add_reference_line(fig, y=50, row=1, col=2, color='gray')

        # 消费者信心
        for key, name in [('CCI', '信心指数'), ('CEI', '预期指数'), ('CSI', '满意指数')]:
            if key in self.data:
                df = self.data[key]
                add_line_trace(fig, df['date'], df['value'], name,
                              self.theme.get_color('secondary'), row=2, col=1)
        add_reference_line(fig, y=100, row=2, col=1, color='gray')

        # 经济景气
        for key, name in [('ESCI', '一致指数'), ('ESLI', '先行指数'), ('ESHI', '滞后指数')]:
            if key in self.data:
                df = self.data[key]
                add_line_trace(fig, df['date'], df['value'], name,
                              self.theme.get_color('secondary'), row=2, col=2)
        add_reference_line(fig, y=100, row=2, col=2, color='gray')

        self.theme.apply_to(fig, '景气度与PMI分析', height=800)
        return fig

    def chart_monetary(self) -> go.Figure:
        """图表3: 货币与金融"""
        fig = create_subplots(
            rows=3, cols=2,
            titles=['M0/M1/M2货币供应量', 'M2与M1增速对比',
                    'Shibor利率期限结构', '十年期国债收益率',
                    '社融规模与存款', '财政收入与支出'],
        )

        # M0/M1/M2
        for key, name, color in [('M0', 'M0', '#3498db'), ('M1', 'M1', '#e74c3c'), ('M2', 'M2', '#27ae60')]:
            if key in self.data:
                df = self.data[key]
                add_line_trace(fig, df['date'], df['value'], name, color,
                              row=1, col=1,
                              fill='tonexty' if key == 'M0' else None)

        # M2-M1增速
        for key, name, color in [('M2', 'M2增速', '#27ae60'), ('M1', 'M1增速', '#e74c3c')]:
            if key in self.data and len(self.data[key]) >= 13:
                df = self.data[key]
                dates, yoy_vals = compute_yoy_series(df['date'].tolist(), df['value'].tolist())
                add_line_trace(fig, dates, yoy_vals, name, color, row=1, col=2)

        # Shibor期限结构
        shibor_keys = [
            ('SHIBOR_ON', '隔夜', '#e74c3c'), ('SHIBOR_1W', '1周', '#f39c12'),
            ('SHIBOR_1M', '1月', '#3498db'), ('SHIBOR_3M', '3月', '#8e44ad'),
            ('SHIBOR_6M', '6月', '#1abc9c'),
        ]
        for key, name, color in shibor_keys:
            if key in self.data:
                df = self.data[key]
                add_line_trace(fig, df['date'], df['value'], f'Shibor {name}',
                              color, row=2, col=1, width=1.5)

        # 十年期国债
        if 'CNTY' in self.data:
            df = self.data['CNTY']
            add_line_trace(fig, df['date'], df['value'], '中国10Y国债',
                          self.theme.get_color('accent'), row=2, col=2,
                          width=2.5, fill='tozeroy')
        if 'US_TY' in self.data:
            df = self.data['US_TY']
            add_line_trace(fig, df['date'], df['value'], '美国10Y国债',
                          self.theme.get_color('secondary'), row=2, col=2,
                          width=2, dash='dash')

        # 社融与存款
        for key, name, color in [('TRY', '社融规模(万亿)', '#8e44ad'), ('TRL', '存款总计(万亿)', '#1abc9c')]:
            if key in self.data:
                df = self.data[key]
                add_line_trace(fig, df['date'], df['value'], name, color, row=3, col=1)

        # 财政收支
        for key, name, color in [('MR', '财政收入(万亿)', '#27ae60'), ('ML', '财政支出(万亿)', '#e74c3c')]:
            if key in self.data:
                df = self.data[key]
                add_bar_trace(fig, df['date'], df['value'], name, color,
                             row=3, col=2, opacity=0.7)

        self.theme.apply_to(fig, '货币金融全景', height=1200)
        fig.update_yaxes(title_text='万亿元', row=1, col=1)
        fig.update_yaxes(title_text='%', row=1, col=2)
        fig.update_yaxes(title_text='%', row=2, col=1)
        fig.update_yaxes(title_text='%', row=2, col=2)
        fig.update_yaxes(title_text='万亿元', row=3, col=1)
        fig.update_yaxes(title_text='万亿元', row=3, col=2)
        return fig

    def chart_trade_fx(self) -> go.Figure:
        """图表4: 贸易与外汇"""
        fig = create_subplots(
            rows=2, cols=2,
            titles=['进出口总额', '美元兑人民币汇率', '外汇储备与黄金储备', 'BDI波罗的海指数'],
            specs=[[{}, {}], [{"secondary_y": True}, {}]],
        )

        if 'TIE' in self.data:
            df = self.data['TIE']
            add_bar_trace(fig, df['date'], df['value'], '进出口(万亿$)',
                         self.theme.get_color('secondary'), row=1, col=1)
        if 'MII' in self.data:
            df = self.data['MII']
            add_bar_trace(fig, df['date'], df['value'], '进口(万亿$)',
                         self.theme.get_color('accent'), row=1, col=1, opacity=0.6)

        if 'RMBUS' in self.data:
            df = self.data['RMBUS']
            add_line_trace(fig, df['date'], df['value'], 'USD/CNY',
                          self.theme.get_color('accent'), row=1, col=2)

        if 'FER' in self.data:
            df = self.data['FER']
            add_line_trace(fig, df['date'], df['value'], '外汇储备(万亿$)',
                          self.theme.get_color('secondary'), row=2, col=1)
        if 'GOLD' in self.data:
            df = self.data['GOLD']
            add_line_trace(fig, df['date'], df['value'], '黄金储备(万盎司)',
                          self.theme.get_color('warning'), row=2, col=1,
                          secondary_y=True)

        if 'BDI' in self.data:
            df = self.data['BDI']
            add_line_trace(fig, df['date'], df['value'], 'BDI指数',
                          self.theme.get_color('info'), row=2, col=2, fill='tozeroy')

        self.theme.apply_to(fig, '贸易与外汇分析', height=800)
        return fig

    def chart_energy_industry(self) -> go.Figure:
        """图表5: 能源与工业"""
        fig = create_subplots(
            rows=2, cols=2,
            titles=['全国发电量', '全社会用电量', '工业品价格指数', 'GDP与工业增加值趋势'],
        )

        if 'TEC' in self.data:
            df = self.data['TEC']
            add_bar_trace(fig, df['date'], df['value'], '发电量(亿度)',
                         self.theme.get_color('warning'), row=1, col=1)

        if 'TEG' in self.data:
            df = self.data['TEG']
            add_bar_trace(fig, df['date'], df['value'], '用电量(亿度)',
                         self.theme.get_color('info'), row=1, col=2)
        if 'IEC' in self.data:
            df = self.data['IEC']
            add_line_trace(fig, df['date'], df['value'], '工业用电(亿度)',
                          self.theme.get_color('accent'), row=1, col=2)

        if 'EPI' in self.data:
            df = self.data['EPI']
            add_line_trace(fig, df['date'], df['value'], '工业品价格指数',
                          self.theme.get_color('primary'), row=2, col=1,
                          width=2.5, fill='tozeroy')

        df_gdp = self._get_gdp_growth_series()
        if len(df_gdp) > 0:
            add_line_trace(fig, df_gdp['date'], df_gdp['value'], 'GDP增速(%)',
                          self.theme.get_color('secondary'), row=2, col=2,
                          mode='lines+markers', marker_size=6, width=2.5)
        if 'VAI' in self.data:
            df = self.data['VAI']
            add_line_trace(fig, df['date'], df['value'], '工业增加值增速(%)',
                          self.theme.get_color('accent'), row=2, col=2,
                          width=2, dash='dash')

        self.theme.apply_to(fig, '能源工业与实体经济', height=800)
        return fig

    def chart_capital_market(self) -> go.Figure:
        """图表6: 资本市场"""
        fig = create_subplots(
            rows=2, cols=2,
            titles=['沪深融资余额', 'ETF基金规模', '北上/南下资金', '融资vs融券'],
        )

        if 'RZ' in self.data:
            df = self.data['RZ']
            add_line_trace(fig, df['date'], df['value'], '融资余额(亿)',
                          self.theme.get_color('accent'), row=1, col=1,
                          width=2.5, fill='tozeroy')

        if 'TETF' in self.data:
            df = self.data['TETF']
            add_bar_trace(fig, df['date'], df['value'], 'ETF规模(亿)',
                         self.theme.get_color('info'), row=1, col=2)

        if 'TON' in self.data:
            df = self.data['TON']
            add_line_trace(fig, df['date'], df['value'], '北上资金(亿)',
                          self.theme.get_color('success'), row=2, col=1)
        if 'TOS' in self.data:
            df = self.data['TOS']
            add_line_trace(fig, df['date'], df['value'], '南下资金(亿)',
                          self.theme.get_color('warning'), row=2, col=1)

        if 'RZ' in self.data and 'RQ' in self.data:
            df_rz = self.data['RZ']
            df_rq = self.data['RQ']
            add_line_trace(fig, df_rz['date'], df_rz['value'], '融资(亿)',
                          self.theme.get_color('accent'), row=2, col=2)
            add_line_trace(fig, df_rq['date'], df_rq['value'], '融券(亿)',
                          self.theme.get_color('secondary'), row=2, col=2)

        self.theme.apply_to(fig, '资本市场监控', height=800)
        return fig

    def chart_international(self) -> go.Figure:
        """图表7: 国际对比"""
        fig = create_subplots(
            rows=2, cols=2,
            titles=['中美制造业PMI对比', '美国CPI同比变化', '美国就业市场', '中美利差走势'],
            specs=[[{}, {}], [{"secondary_y": True}, {}]],
        )

        if 'PMI' in self.data:
            df = self.data['PMI']
            add_line_trace(fig, df['date'], df['value'], '中国PMI',
                          self.theme.get_color('accent'), row=1, col=1, mode='lines+markers')
        if 'US_PMI' in self.data:
            df = self.data['US_PMI']
            add_line_trace(fig, df['date'], df['value'], '美国PMI',
                          self.theme.get_color('secondary'), row=1, col=1, mode='lines+markers')
        add_reference_line(fig, y=50, row=1, col=1, color='gray')

        # 美国CPI同比
        if 'US_CPI' in self.data and len(self.data['US_CPI']) >= 13:
            df = self.data['US_CPI']
            dates, yoy_vals = compute_yoy_series(df['date'].tolist(), df['value'].tolist())
            add_line_trace(fig, dates, yoy_vals, '美国CPI同比%',
                          self.theme.get_color('secondary'), row=1, col=2)
        if 'US_CPIX' in self.data and len(self.data['US_CPIX']) >= 13:
            df = self.data['US_CPIX']
            dates, yoy_vals = compute_yoy_series(df['date'].tolist(), df['value'].tolist())
            add_line_trace(fig, dates, yoy_vals, '美国核心CPI同比%',
                          self.theme.get_color('secondary'), row=1, col=2, dash='dash')

        # 美国就业
        if 'US_UE' in self.data:
            df = self.data['US_UE']
            add_line_trace(fig, df['date'], df['value'], '美国失业率(%)',
                          self.theme.get_color('accent'), row=2, col=1, mode='lines+markers')
        if 'US_NONAG' in self.data:
            df = self.data['US_NONAG']
            add_bar_trace(fig, df['date'], df['value'], '非农就业(万人)',
                         self.theme.get_color('success'), row=2, col=1, opacity=0.6)

        # 中美利差
        if 'CNTY' in self.data and 'US_TY' in self.data:
            cn = self.data['CNTY']
            us = self.data['US_TY']
            merged = pd.merge(
                cn[['date', 'value']].rename(columns={'value': 'cn'}),
                us[['date', 'value']].rename(columns={'value': 'us'}),
                on='date', how='inner'
            )
            merged['spread'] = merged['cn'] - merged['us']
            colors = [self.theme.get_color('success') if v >= 0 else self.theme.get_color('accent')
                      for v in merged['spread']]
            add_bar_trace(fig, merged['date'], merged['spread'], '中美利差',
                         colors, row=2, col=2, opacity=0.8)
            add_reference_line(fig, y=0, row=2, col=2, color='black')

        self.theme.apply_to(fig, '国际经济对比', height=800)
        return fig

    def chart_radar(self, outlook: Dict) -> go.Figure:
        """图表8: 综合评分雷达图"""
        scores = outlook.get('category_scores', {})

        labels = []
        values = []
        for key, label in self.CATEGORY_LABELS.items():
            if key in scores:
                labels.append(label)
                values.append(scores[key])

        fig = go.Figure()
        fig.add_trace(go.Scatterpolar(
            r=values + [values[0]] if values else [],
            theta=labels + [labels[0]] if labels else [],
            fill='toself',
            fillcolor='rgba(41, 128, 185, 0.3)',
            line=dict(color=self.theme.get_color('secondary'), width=2),
            name='当前评分',
        ))

        fig.add_trace(go.Scatterpolar(
            r=[50] * len(labels) + [50],
            theta=labels + [labels[0]] if labels else [],
            line=dict(color='gray', width=1, dash='dash'),
            name='基准线(50)',
        ))

        fig.update_layout(
            polar=dict(radialaxis=dict(visible=True, range=[0, 100], dtick=20)),
            title=dict(
                text=f'宏观经济综合评分: {outlook.get("total_score", 0):.0f}分 — {outlook.get("status", "")}',
                font=dict(size=18, color=self.theme.get_color('text')), x=0.5,
            ),
            template='plotly_white',
            height=600,
            font=dict(family=self.theme.font_family),
        )
        return fig

    def chart_dashboard(self, outlook: Dict) -> go.Figure:
        """图表9: 综合仪表盘"""
        fig = make_subplots(
            rows=3, cols=2,
            specs=[
                [{'type': 'xy'}, {'type': 'xy'}],
                [{'type': 'xy'}, {'type': 'xy'}],
                [{'type': 'xy', 'colspan': 2}, None],
            ],
            vertical_spacing=0.08,
            horizontal_spacing=0.1,
            subplot_titles=[
                '制造业PMI趋势', 'M2货币供应量',
                '中美利差走势', '进出口与汇率',
                '宏观经济综合评分',
            ],
        )

        # PMI趋势
        if 'PMI' in self.data:
            df = self.data['PMI'].tail(24)
            colors = self.theme.get_indicator_colors(df['value'].tolist(), threshold=50)
            add_bar_trace(fig, df['date'], df['value'], 'PMI', colors,
                         row=1, col=1, opacity=0.85, showlegend=False)
            add_reference_line(fig, y=50, row=1, col=1, color='black')

        # M2趋势
        if 'M2' in self.data:
            df = self.data['M2'].tail(24)
            add_line_trace(fig, df['date'], df['value'], 'M2(万亿)',
                          self.theme.get_color('secondary'), row=1, col=2,
                          mode='lines+markers', showlegend=False)

        # 中美利差
        if 'CNTY' in self.data and 'US_TY' in self.data:
            cn = self.data['CNTY'].tail(60)
            us = self.data['US_TY'].tail(60)
            add_line_trace(fig, cn['date'], cn['value'], '中国10Y',
                          self.theme.get_color('accent'), row=2, col=1)
            add_line_trace(fig, us['date'], us['value'], '美国10Y',
                          self.theme.get_color('secondary'), row=2, col=1, dash='dash')

        # 进出口
        if 'TIE' in self.data:
            df = self.data['TIE'].tail(24)
            add_bar_trace(fig, df['date'], df['value'], '进出口(万亿$)',
                         self.theme.get_color('info'), row=2, col=2,
                         opacity=0.7, showlegend=False)

        # 综合评分条形图
        scores = outlook.get('category_scores', {})
        cat_labels = []
        cat_values = []
        cat_colors = []
        for key, label in self.CATEGORY_LABELS.items():
            if key in scores:
                cat_labels.append(label)
                cat_values.append(scores[key])
                cat_colors.append(self.theme.get_score_color(scores[key]))

        fig.add_trace(go.Bar(
            x=cat_labels, y=cat_values,
            marker_color=cat_colors,
            marker_line_width=0, opacity=0.85,
            text=cat_values,
            textposition='outside',
            texttemplate='%{text:.0f}',
            showlegend=False,
        ), row=3, col=1)

        self.theme.apply_to(fig,
            f'中国宏观经济仪表盘 | 综合评分: {outlook.get("total_score", 0):.0f} | '
            f'状态: {outlook.get("status", "")}',
            height=1000)
        return fig

    def _get_gdp_growth_series(self) -> pd.DataFrame:
        """获取GDP增速百分比序列"""
        if 'VGDP' in self.data:
            df = self.data['VGDP'].copy()
            # VGDP 已在 DataLoaderService 中做了 index_minus_100 转换
            return df
        return pd.DataFrame()

    def generate_all(self, outlook: Dict) -> List[Tuple[str, go.Figure, str]]:
        """生成所有图表

        Args:
            outlook: 综合展望字典

        Returns:
            (key, figure, name) 元组列表
        """
        charts = [
            ('dashboard', self.chart_dashboard, '宏观仪表盘', outlook),
            ('economic_growth', self.chart_economic_growth, '经济增长', None),
            ('pmi_prosperity', self.chart_pmi_prosperity, '景气度', None),
            ('monetary', self.chart_monetary, '货币金融', None),
            ('trade_fx', self.chart_trade_fx, '贸易外汇', None),
            ('energy_industry', self.chart_energy_industry, '能源工业', None),
            ('capital_market', self.chart_capital_market, '资本市场', None),
            ('international', self.chart_international, '国际对比', None),
            ('radar', self.chart_radar, '综合评分', outlook),
        ]

        figures = []
        for key, func, name, arg in charts:
            try:
                if arg is not None:
                    fig = func(arg)
                else:
                    fig = func()
                figures.append((key, fig, name))
            except Exception as e:
                print(f"  [FAIL] {name}: {e}")

        return figures
