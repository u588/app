#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ConfidenceDashboard：技术面置信度可视化面板
功能：
  - 单标的置信度深度分析
  - 批量标的对比筛选
  - 历史趋势回溯
  - 交互式钻取诊断
"""

import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots
import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Any, Union
from datetime import datetime, timedelta
import logging

from .components.confidence_gauge import create_confidence_gauge
from .components.factor_breakdown import create_factor_breakdown
from .components.diagnostics_tree import create_diagnostics_tree
from .components.historical_trend import create_historical_trend
from .utils.color_scales import CONFIDENCE_COLORSCALE
from .utils.layout_presets import DASHBOARD_LAYOUT

logger = logging.getLogger(__name__)


class ConfidenceDashboard:
    """置信度可视化面板"""
    
    def __init__(self, config: Optional[Dict] = None):
        """
        初始化面板
        
        参数:
            config: 面板配置（可选）
        """
        self.config = config or {}
        self.theme = self.config.get('theme', 'plotly_white')
        self.width = self.config.get('width', 1400)
        self.height = self.config.get('height', 900)
        
    def create_single_stock_dashboard(
        self,
        code: str,
        name: str,
        confidence_result: Any,  # ConfidenceResult
        indicators: Dict,
        stock_data: pd.DataFrame,
        historical_confidence: Optional[pd.DataFrame] = None
    ) -> go.Figure:
        """
        创建单标的置信度分析面板
        
        参数:
            code: 股票代码
            name: 股票名称
            confidence_ ConfidenceResult 对象
            indicators: 技术指标字典
            stock_ OHLCV 数据
            historical_ 历史置信度序列（可选）
        
        返回:
            Plotly Figure 对象
        """
        # 创建 3×2 子图布局
        fig = make_subplots(
            rows=3, cols=2,
            subplot_titles=[
                f"{name}({code}) 置信度总览",
                "因子分解",
                "诊断详情",
                "技术指标关联",
                "历史趋势" if historical_confidence is not None else "数据质量",
                "操作建议"
            ],
            specs=[
                [{'type': 'indicator'}, {'type': 'bar'}],
                [{'type': 'table'}, {'type': 'scatter'}],
                [{'type': 'scatter'}, {'type': 'indicator'}]
            ],
            vertical_spacing=0.08,
            horizontal_spacing=0.08,
            row_heights=[0.35, 0.35, 0.30]
        )
        
        # 1. 置信度仪表盘（左上）
        gauge_fig = create_confidence_gauge(
            factor=confidence_result.factor,
            score=confidence_result.score,
            level=confidence_result.level
        )
        for trace in gauge_fig.data:
            fig.add_trace(trace, row=1, col=1)
        
        # 2. 因子分解图（右上）
        breakdown_fig = create_factor_breakdown(
            technical=confidence_result.factor,
            fundamental=1.0,  # 占位，实际应传入
            macro=1.0,        # 占位，实际应传入
            weights={'technical': 0.40, 'fundamental': 0.35, 'macro': 0.25}
        )
        for trace in breakdown_fig.data:
            fig.add_trace(trace, row=1, col=2)
        
        # 3. 诊断树状图（中左）
        tree_fig = create_diagnostics_tree(confidence_result.diagnostics)
        for trace in tree_fig.data:
            fig.add_trace(trace, row=2, col=1)
        
        # 4. 技术指标关联散点图（中右）
        scatter_fig = self._create_indicator_scatter(indicators, confidence_result)
        for trace in scatter_fig.data:
            fig.add_trace(trace, row=2, col=2)
        
        # 5. 历史趋势/数据质量（左下）
        if historical_confidence is not None:
            trend_fig = create_historical_trend(historical_confidence)
            for trace in trend_fig.data:
                fig.add_trace(trace, row=3, col=1)
        else:
            quality_fig = self._create_data_quality_chart(confidence_result.diagnostics)
            for trace in quality_fig.data:
                fig.add_trace(trace, row=3, col=1)
        
        # 6. 操作建议仪表盘（右下）
        suggestion_fig = self._create_suggestion_gauge(
            confidence_result.level,
            confidence_result.score,
            indicators.get('pl_ratio', 0)
        )
        for trace in suggestion_fig.data:
            fig.add_trace(trace, row=3, col=2)
        
        # 统一布局
        fig.update_layout(
            title=f"🎯 {name}({code}) 技术面置信度分析",
            height=self.height,
            width=self.width,
            template=self.theme,
            hovermode='closest',
            showlegend=False,
            **DASHBOARD_LAYOUT
        )
        
        # 添加交互说明
        fig.add_annotation(
            x=0.5, y=-0.05,
            text="💡 提示：点击图表元素可钻取详情 | 双击图例可隐藏/显示系列",
            showarrow=False,
            bgcolor='rgba(240,240,240,0.8)',
            font=dict(size=10),
            xref='paper', yref='paper'
        )
        
        return fig
    
    def create_batch_comparison_dashboard(
        self,
        results: List[Dict[str, Any]],
        filter_config: Optional[Dict] = None
    ) -> go.Figure:
        """
        创建批量标的置信度对比面板（修复版）
        
        参数:
            results: 批量计算结果列表（含 technical_quality 字段）
            filter_config: 筛选配置（可选）
        
        返回:
            Plotly Figure 对象
        """
        # 数据预处理
        df = pd.DataFrame([{
            'code': r['code'],
            'name': r['name'],
            'sector': r['sector'],
            'confidence_factor': r['technical_quality']['factor'],
            'confidence_score': r['technical_quality']['score'],
            'confidence_level': r['technical_quality']['level'],
            'pl_ratio': r['scores']['pl_ratio'],
            'recommendation': r['recommendation'],
            'data_quality': r['technical_quality']['breakdown']['data_quality'],
            'consistency': r['technical_quality']['breakdown']['consistency'],
            'strength': r['technical_quality']['breakdown']['strength']
        } for r in results if 'technical_quality' in r])
        
        if df.empty:
            logger.warning("⚠️ 无有效置信度数据，返回空面板")
            return go.Figure()
        
        # 应用筛选
        if filter_config:
            if 'min_confidence' in filter_config:
                df = df[df['confidence_factor'] >= filter_config['min_confidence']]
            if 'sectors' in filter_config:
                df = df[df['sector'].isin(filter_config['sectors'])]
            if 'min_pl_ratio' in filter_config:
                df = df[df['pl_ratio'] >= filter_config['min_pl_ratio']]
        
        if df.empty:
            logger.warning("⚠️ 筛选后无数据，返回空面板")
            return go.Figure()
        
        # 创建 2×2 子图
        fig = make_subplots(
            rows=2, cols=2,
            subplot_titles=[
                "置信度分布",
                "置信度×盈亏比",
                "分项得分对比",
                "板块置信度热力图"
            ],
            specs=[
                [{'type': 'histogram'}, {'type': 'scatter'}],
                [{'type': 'bar'}, {'type': 'heatmap'}]
            ],
            vertical_spacing=0.1,
            horizontal_spacing=0.1
        )
        
        # 1. 置信度分布直方图（左上）
        fig.add_trace(go.Histogram(
            x=df['confidence_factor'],
            name='置信度因子',
            marker_color='#1f77b4',
            nbinsx=20,
            hovertemplate='<b>置信度</b><br>%{x:.3f}<br>标的数：%{y}<extra></extra>'
        ), row=1, col=1)
        
        # 2. 置信度×盈亏比散点图（右上）✅ 修复：使用 marker.color
        fig.add_trace(go.Scatter(
            x=df['confidence_factor'],
            y=df['pl_ratio'],
            mode='markers',
            marker=dict(
                size=8,
                color=df['confidence_score'],  # ✅ 正确：在 marker 内设置 color
                colorscale='RdYlGn',
                showscale=True,
                colorbar=dict(title='综合得分'),
                line=dict(width=1, color='white')
            ),
            text=df['name'],
            hovertemplate='<b>%{text}</b><br>置信度：%{x:.3f}<br>盈亏比：%{y:.1f}x<extra></extra>'
        ), row=1, col=2)
        
        # 添加参考线
        fig.add_vline(x=1.0, line_dash='dash', line_color='gray', annotation_text='中性')
        fig.add_hline(y=2.0, line_dash='dash', line_color='blue', annotation_text='盈亏比阈值')
        
        # 3. 分项得分对比条形图（左下）✅ 修复：使用 marker.color + 分类映射
        # 计算各板块×维度的均值
        agg = df.groupby('sector')[['data_quality', 'consistency', 'strength']].mean().reset_index()
        agg_melted = agg.melt(id_vars='sector', var_name='dimension', value_name='score')
        
        # 为每个维度分配固定颜色（避免随机色）
        dimension_colors = {
            'data_quality': '#1f77b4',    # 蓝色
            'consistency': '#ff7f0e',     # 橙色
            'strength': '#2ca02c'         # 绿色
        }
        agg_melted['color'] = agg_melted['dimension'].map(dimension_colors)
        
        # 按板块分组添加条形图（确保颜色正确映射）
        for dimension in agg_melted['dimension'].unique():
            subset = agg_melted[agg_melted['dimension'] == dimension]
            fig.add_trace(go.Bar(
                x=subset['sector'],
                y=subset['score'],
                name=dimension,  # ✅ 使用 name 实现图例
                marker=dict(color=dimension_colors[dimension]),  # ✅ 正确：在 marker 内设置颜色
                hovertemplate='<b>%{x}</b><br>%{name}：%{y:.2f}<extra></extra>'
            ), row=2, col=1)
        
        # 4. 板块置信度热力图（右下）
        # 构建板块×置信度等级的矩阵
        heatmap_data = df.pivot_table(
            index='sector',
            columns='confidence_level',
            values='code',
            aggfunc='count',
            fill_value=0
        )
        
        # 确保列顺序
        level_order = ['low', 'normal', 'high']
        heatmap_data = heatmap_data.reindex(columns=[c for c in level_order if c in heatmap_data.columns], fill_value=0)
        
        fig.add_trace(go.Heatmap(
            z=heatmap_data.values,
            x=heatmap_data.columns,
            y=heatmap_data.index,
            colorscale='Blues',
            showscale=True,
            hovertemplate='<b>%{y}</b><br>%{x}：%{z} 只<extra></extra>',
            zmin=0,
            zmax=heatmap_data.values.max() if heatmap_data.values.size > 0 else 1
        ), row=2, col=2)
        
        # 统一布局 ✅ 修复：使用正确参数名
        fig.update_layout(
            title="📊 批量标的置信度对比分析",
            height=800,
            width=1400,
            template=self.theme or 'plotly_white',
            hovermode='closest',
            bargap=0.1,  # 条形图间隙
            legend=dict(orientation='h', yanchor='bottom', y=-0.15, xanchor='center', x=0.5)
        )
        
        # 添加筛选说明
        if filter_config:
            filter_text = " | ".join([f"{k}={v}" for k, v in filter_config.items()])
            fig.add_annotation(
                x=0.5, y=-0.03,
                text=f"🔍 筛选条件: {filter_text}",
                showarrow=False,
                bgcolor='lightyellow',
                font=dict(size=9),
                xref='paper', yref='paper'
            )
        
        return fig
    
    def _create_indicator_scatter(
        self,
        indicators: Dict,
        confidence_result: Any
    ) -> go.Figure:
        """创建技术指标关联散点图"""
        # 提取关键指标
        data = {
            '指标': ['RSI', 'MACD', 'ATR/Price', 'Volume Ratio', 'ADX'],
            '值': [
                indicators.get('rsi14', 50),
                indicators.get('macd_hist', 0),
                (indicators.get('atr14', 0) / indicators.get('close', 1)) * 100,
                indicators.get('volume', 0) / indicators.get('vol_20d_avg', 1),
                indicators.get('adx', 20)
            ],
            '理想区间': [
                '30-70',
                '>0(多)/<0(空)',
                '1-8%',
                '>1.2(放量)/<0.8(缩量)',
                '>25(强趋势)'
            ],
            '状态': [
                '✅' if 30 <= indicators.get('rsi14', 50) <= 70 else '⚠️',
                '✅' if indicators.get('macd_hist', 0) != 0 else '⚠️',
                '✅' if 1 <= (indicators.get('atr14', 0) / indicators.get('close', 1)) * 100 <= 8 else '⚠️',
                '✅' if indicators.get('volume', 0) / indicators.get('vol_20d_avg', 1) > 1.2 or 
                      indicators.get('volume', 0) / indicators.get('vol_20d_avg', 1) < 0.8 else '⚠️',
                '✅' if indicators.get('adx', 20) >= 25 else '⚠️'
            ]
        }
        
        df = pd.DataFrame(data)
        
        fig = px.scatter(
            df,
            x='值',
            y='指标',
            color='状态',
            color_discrete_map={'✅': 'green', '⚠️': 'orange'},
            size=[15 if s=='✅' else 10 for s in df['状态']],
            hover_data=['理想区间'],
            title='技术指标状态'
        )
        
        fig.update_layout(
            xaxis_title='指标值',
            yaxis_title='',
            showlegend=False,
            height=300
        )
        
        return fig
    
    def _create_data_quality_chart(self, diagnostics: Dict) -> go.Figure:
        """创建数据质量雷达图"""
        dq = diagnostics.get('data_quality', {})
        
        fig = go.Figure(data=go.Scatterpolar(
            r=[
                min(dq.get('days', 0) / 250, 1.0),  # 数据长度
                1.0 - dq.get('missing_ratio', 1.0),  # 完整性
                max(0, 1.0 - dq.get('freshness_days', 999) / 7),  # 新鲜度
                1.0  # 占位
            ],
            theta=['数据长度', '完整性', '新鲜度', ''],
            fill='toself',
            line_color='#1f77b4',
            fillcolor='rgba(31, 119, 180, 0.2)'
        ))
        
        fig.update_layout(
            polar=dict(
                radialaxis=dict(visible=True, range=[0, 1])
            ),
            showlegend=False,
            height=300,
            title='数据质量雷达'
        )
        
        return fig
    
    def _create_suggestion_gauge(
        self,
        confidence_level: str,
        confidence_score: float,
        pl_ratio: float
    ) -> go.Figure:
        """创建操作建议仪表盘"""
        # 综合评分：置信度 60% + 盈亏比 40%
        composite_score = confidence_score * 0.6 + min(pl_ratio / 3.0, 1.0) * 0.4
        
        # 确定建议
        if confidence_level == 'high' and pl_ratio >= 2.0:
            suggestion = "✅ 重点关注"
            color = 'green'
        elif confidence_level == 'low' or pl_ratio < 1.5:
            suggestion = "⚠️ 谨慎对待"
            color = 'orange'
        else:
            suggestion = "🔍 正常跟踪"
            color = 'blue'
        
        fig = go.Figure(go.Indicator(
            mode='gauge+number+delta',
            value=composite_score,
            domain={'x': [0, 1], 'y': [0, 1]},
            title={'text': f"操作建议: {suggestion}"},
            number={'font': {'size': 24}},
            gauge={
                'axis': {'range': [0, 1]},
                'bar': {'color': color},
                'steps': [
                    {'range': [0, 0.4], 'color': 'lightcoral'},
                    {'range': [0.4, 0.7], 'color': 'lightyellow'},
                    {'range': [0.7, 1.0], 'color': 'lightgreen'}
                ],
                'threshold': {
                    'line': {'color': 'red', 'width': 4},
                    'thickness': 0.75,
                    'value': 0.6
                }
            }
        ))
        
        fig.update_layout(height=300)
        return fig
    
    def export_dashboard(
        self,
        fig: go.Figure,
        output_path: str,
        format: str = 'html'
    ) -> str:
        """导出面板"""
        from pathlib import Path
        
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        if format == 'html':
            fig.write_html(
                str(output_path),
                include_plotlyjs='cdn',
                full_html=True,
                config={'displayModeBar': True}
            )
        elif format in ['png', 'pdf', 'svg']:
            fig.write_image(
                str(output_path),
                width=self.width,
                height=self.height,
                scale=2,
                format=format
            )
        else:
            raise ValueError(f"不支持的导出格式: {format}")
        
        logger.info(f"✅ 面板已导出: {output_path}")
        return str(output_path)