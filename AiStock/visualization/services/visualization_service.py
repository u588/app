#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
VisualizationService：可视化主服务（增强版）
功能：
  - 单标的六宫格深度分析
  - 批量对比 + 置信度筛选
  - 多格式导出 + 智能缓存
  - 错误隔离 + 性能统计
"""

import logging
import hashlib
import json
from pathlib import Path
from typing import Dict, List, Optional, Any, Union
from datetime import datetime
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go  # ✅ 新增导入

from ..components.price_chart import create_price_interval_chart
from ..components.factor_breakdown import create_factor_breakdown
from ..components.confidence_gauge import create_confidence_gauge
from ..components.diagnostics_tree import create_diagnostics_tree
from ..components.indicator_scatter import create_indicator_scatter
from ..components.historical_trend import create_historical_trend
from ..components.portfolio_chart import create_portfolio_comparison_chart
from ..components.risk_chart import create_risk_matrix_chart
from ..core.plotly_renderer import PlotlyRenderer
from ..utils.data_transform import sanitize_for_json

logger = logging.getLogger(__name__)


class VisualizationService:
    """可视化主服务（增强版）"""
    
    def __init__(self, config_path: Optional[str] = None):
        """初始化服务"""
        self.config = self._load_config(config_path) if config_path else {}
        self.renderer = PlotlyRenderer(self.config.get('renderer', {}))
        self.output_dir = Path(self.config.get('output', {}).get('dir', 'output/visualization'))
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # 缓存管理
        self._cache = {}  # {cache_key: output_path}
        self._cache_ttl = self.config.get('cache', {}).get('ttl_seconds', 3600)
        
        logger.info(f"✅ VisualizationService 初始化完成 | 输出: {self.output_dir}")
    
    def _load_config(self, path: str) -> Dict:
        """加载 YAML 配置"""
        try:
            import yaml
            with open(path, 'r', encoding='utf-8') as f:
                return yaml.safe_load(f)
        except Exception as e:
            logger.warning(f"⚠️ 加载配置失败 {path}: {e}，使用默认配置")
            return {}
    
    def _generate_cache_key(self, data: Dict, chart_types: List[str], config: Dict) -> str:
        """生成缓存键（基于数据哈希 + 配置）"""
        # 提取关键数据（避免大对象）
        key_data = {
            'code': data.get('code'),
            'entry': data.get('prices', {}).get('entry'),
            'stop': data.get('prices', {}).get('stop_loss'),
            'target': data.get('prices', {}).get('target'),
            'pl_ratio': data.get('scores', {}).get('pl_ratio'),
            'confidence': data.get('technical_quality', {}).get('factor'),
            'chart_types': sorted(chart_types),
            'config_hash': hashlib.md5(json.dumps(config, sort_keys=True, default=str).encode()).hexdigest()[:8]
        }
        return hashlib.md5(json.dumps(key_data, sort_keys=True, default=str).encode()).hexdigest()
    
    def _is_cache_valid(self, cache_key: str, output_path: str) -> bool:
        """检查缓存是否有效（文件存在 + 未过期）"""
        if cache_key not in self._cache:
            return False
        if not Path(output_path).exists():
            return False
        # 检查修改时间
        mtime = Path(output_path).stat().st_mtime
        if datetime.now().timestamp() - mtime > self._cache_ttl:
            return False
        return True

    def _create_summary_card_chart(self, result: Dict) -> go.Figure:
        """生成单标的汇总卡片"""
        prices = result.get('prices', {})
        scores = result.get('scores', {})
        recommendation = result.get('recommendation', '未知')
        
        # 确定颜色
        rec_colors = {
            '强烈推荐': '#2ca02c', '推荐': '#1f77b4', 
            '观望': '#ff7f0e', '谨慎': '#d62728'
        }
        rec_color = rec_colors.get(recommendation, '#7f7f7f')
        
        fig = go.Figure()
        
        # 1. 入场价（主指标）
        fig.add_trace(go.Indicator(
            mode='number+delta',
            value=prices.get('entry', 0),
            number={'font': {'size': 24}, 'prefix': '¥'},
            title={'text': '建议入场价'},
            delta={
                'reference': prices.get('current', 0), 
                'valueformat': '.2f',
                'relative': False
            },
            domain={'x': [0.25, 0.75], 'y': [0.6, 1]}
        ))
        
        # 2. 目标价
        fig.add_trace(go.Indicator(
            mode='number',
            value=prices.get('target', 0),
            number={'font': {'size': 16}, 'prefix': '¥'},
            title={'text': '目标价'},
            domain={'x': [0.0, 0.5], 'y': [0.25, 0.55]}
        ))
        
        # 3. 止损价
        fig.add_trace(go.Indicator(
            mode='number',
            value=prices.get('stop_loss', 0),
            number={'font': {'size': 16}, 'prefix': '¥'},
            title={'text': '止损价'},
            domain={'x': [0.5, 1.0], 'y': [0.25, 0.55]}
        ))

        # 4. 盈亏比与建议
        fig.add_annotation(
            x=0.5, y=0.05,
            text=f"盈亏比: {scores.get('pl_ratio', 0):.2f}x | 建议: {recommendation}",
            showarrow=False,
            font=dict(size=14, color=rec_color),
            bgcolor='rgba(255,255,255,0.9)',
            bordercolor=rec_color,
            borderwidth=1,
            xref='paper', yref='paper'
        )
        
        # 布局
        fig.update_layout(
            height=250,
            margin=dict(l=10, r=10, t=30, b=10),
            showlegend=False,
            template='plotly_white'
        )
        
        return fig
    
    def visualize_single_result(
        self,
        result: Dict[str, Any],
        chart_types: Optional[List[str]] = None,
        output_format: str = 'html',
        enable_cache: bool = True
    ) -> Dict[str, str]:
        """
        可视化单标的计算结果（六宫格深度分析）
        
        参数:
            result: DynamicPriceEngine 计算结果
            chart_types: 要生成的图表类型列表
                - 'price_interval': 价格区间图
                - 'factor_breakdown': 因子分解图
                - 'confidence_gauge': 置信度仪表盘
                - 'diagnostics_tree': 诊断树状图
                - 'indicator_scatter': 指标关联散点图
                - 'historical_trend': 历史趋势图（需历史数据）
            output_format: 输出格式 (html/png/pdf/json)
            enable_cache: 是否启用缓存
        
        返回:
            Dict[chart_type -> output_path]
        """
        if not result or 'prices' not in result:
            logger.warning("⚠️ 无效结果，跳过可视化")
            return {}
        
        chart_types = chart_types or ['price_interval', 'factor_breakdown', 'confidence_gauge']
        code = result.get('code', 'unknown')
        outputs = {}
        
        # sanitization（防序列化报错）
        safe_result = sanitize_for_json(result)
        
        for chart_type in chart_types:
            try:
                # 1. 生成缓存键
                cache_key = self._generate_cache_key(safe_result, [chart_type], self.config)
                output_filename = f"{code}_{chart_type}.{output_format}"
                output_path = self.output_dir / output_filename
                
                # 2. 检查缓存
                if enable_cache and self._is_cache_valid(cache_key, str(output_path)):
                    logger.debug(f"✅ 缓存命中: {output_filename}")
                    outputs[chart_type] = str(output_path)
                    continue
                
                # 3. 生成图表
                fig = self._create_single_chart(chart_type, safe_result)
                if not fig:
                    continue
                
                # 4. 导出
                self.renderer.export(fig, str(output_path), format=output_format)
                
                # 5. 更新缓存
                if enable_cache:
                    self._cache[cache_key] = str(output_path)
                
                outputs[chart_type] = str(output_path)
                logger.debug(f"✅ 生成 {chart_type}: {output_filename}")
                
            except Exception as e:
                logger.warning(f"⚠️ 生成 {chart_type} 图表失败 {code}: {e}")
                continue
        
        return outputs
    
    def _create_single_chart(self, chart_type: str, result: Dict) -> Optional[Any]:
        """创建单个图表（路由到对应组件）"""
        try:
            if chart_type == 'price_interval':
                return create_price_interval_chart(result, self.config.get('price_chart', {}))
            elif chart_type == 'factor_breakdown':
                return create_factor_breakdown(
                    technical=result.get('factors', {}).get('technical', 1.0),
                    fundamental=result.get('factors', {}).get('fundamental', 1.0),
                    macro=result.get('factors', {}).get('macro', 1.0),
                    weights=self.config.get('weights', {'technical': 0.4, 'fundamental': 0.35, 'macro': 0.25}),
                    composite=result.get('factors', {}).get('composite', 1.0)
                )
            elif chart_type == 'confidence_gauge':
                if 'technical_quality' not in result:
                    return None
                return create_confidence_gauge(
                    factor=result['technical_quality']['factor'],
                    score=result['technical_quality']['score'],
                    level=result['technical_quality']['level']
                )
            elif chart_type == 'diagnostics_tree':
                if 'technical_quality' not in result or 'diagnostics' not in result['technical_quality']:
                    return None
                return create_diagnostics_tree(result['technical_quality']['diagnostics'])
            elif chart_type == 'indicator_scatter':
                return create_indicator_scatter(result.get('signals', {}), result.get('prices', {}))
            # ✅ 新增：处理 summary_card 类型
            elif chart_type == 'summary_card':
                return self._create_summary_card_chart(result)
            elif chart_type == 'historical_trend':
                # 需要历史数据，此处简化返回 None
                return None
            else:
                logger.warning(f"⚠️ 未知图表类型: {chart_type}")
                return None
        except Exception as e:
            logger.error(f"❌ 创建 {chart_type} 图表异常: {e}")
            return None
    
    def visualize_batch_results(
        self,
        # results: List[Dict[str, Any]],
        results: Union[List[Dict], pd.DataFrame],
        chart_type: str = 'portfolio_comparison',
        output_format: str = 'html',
        filter_config: Optional[Dict] = None,
        enable_cache: bool = True
    ) -> Optional[str]:
        """
        可视化批量计算结果（组合对比 + 置信度筛选）
        
        参数:
            results: 批量计算结果列表
            chart_type: 图表类型 ('portfolio_comparison'/'risk_matrix'/'confidence_filter')
            output_format: 输出格式
            filter_config: 筛选配置（如 min_confidence, min_pl_ratio）
            enable_cache: 是否启用缓存
        
        返回:
            str: 输出文件路径
        """
        if not results:
            logger.warning("⚠️ 批量结果为空，跳过可视化")
            return None

        if isinstance(results, pd.DataFrame):
            if results.empty:
                logger.warning("⚠️ DataFrame 为空，跳过可视化")
                return None
            results = results.to_dict('records')
            logger.debug("🔄 已将 DataFrame 转换为 List[Dict]")        
        fig = create_portfolio_comparison_chart(results,
            self.config.get('portfolio_chart', {})
        )
        
        # 应用筛选
        filtered_results = self._apply_batch_filter(results, filter_config)
        if not filtered_results:
            logger.warning(f"⚠️ 筛选后无有效结果: {filter_config}")
            return None
        
        # 缓存键
        cache_key = self._generate_cache_key(
            {'count': len(filtered_results), 'sectors': list(set(r['sector'] for r in filtered_results))},
            [chart_type],
            {**self.config, 'filter': filter_config}
        )
        output_filename = f"{chart_type}_{len(filtered_results)}_stocks_{datetime.now().strftime('%Y%m%d')}.{output_format}"
        output_path = self.output_dir / output_filename
        
        # 检查缓存
        if enable_cache and self._is_cache_valid(cache_key, str(output_path)):
            logger.debug(f"✅ 批量缓存命中: {output_filename}")
            return str(output_path)
        
        try:
            # 生成图表
            if chart_type == 'portfolio_comparison':
                fig = create_portfolio_comparison_chart(filtered_results, self.config.get('portfolio_chart', {}))
            elif chart_type == 'risk_matrix':
                fig = create_risk_matrix_chart(filtered_results, self.config.get('risk_chart', {}))
            elif chart_type == 'confidence_filter':
                # 使用 confidence_dashboard 的批量对比
                from ..confidence_dashboard import ConfidenceDashboard
                dashboard = ConfidenceDashboard(self.config.get('dashboard', {}))
                fig = dashboard.create_batch_comparison_dashboard(filtered_results, filter_config)
            else:
                logger.warning(f"⚠️ 未知批量图表类型: {chart_type}")
                return None
            
            if not fig:
                return None
            
            # 导出
            self.renderer.export(fig, str(output_path), format=output_format)
            
            # 更新缓存
            if enable_cache:
                self._cache[cache_key] = str(output_path)
            
            logger.info(f"✅ 生成批量图表: {output_filename}")
            return str(output_path)
            
        except Exception as e:
            logger.error(f"❌ 生成批量图表失败: {e}")
            return None
    
    def _apply_batch_filter(self, results: List[Dict], filter_config: Optional[Dict]) -> List[Dict]:
        """应用批量筛选条件"""
        if not filter_config:
            return results
        
        filtered = results
        if 'min_confidence' in filter_config:
            filtered = [r for r in filtered if r.get('technical_quality', {}).get('factor', 1.0) >= filter_config['min_confidence']]
        if 'min_pl_ratio' in filter_config:
            filtered = [r for r in filtered if r.get('scores', {}).get('pl_ratio', 0) >= filter_config['min_pl_ratio']]
        if 'sectors' in filter_config and filter_config['sectors']:
            filtered = [r for r in filtered if r.get('sector') in filter_config['sectors']]
        if 'recommendations' in filter_config and filter_config['recommendations']:
            filtered = [r for r in filtered if r.get('recommendation') in filter_config['recommendations']]
        
        logger.debug(f"🔍 批量筛选: {len(results)} → {len(filtered)} 只")
        return filtered
    
    def clear_cache(self, pattern: Optional[str] = None):
        """清理缓存"""
        if pattern:
            keys = [k for k in self._cache.keys() if pattern in k]
            for k in keys:
                del self._cache[k]
            logger.info(f"🗑️ 清理缓存: {len(keys)} 条 (pattern: {pattern})")
        else:
            count = len(self._cache)
            self._cache.clear()
            logger.info(f"🗑️ 清理全部缓存: {count} 条")
    
    def get_cache_stats(self) -> Dict:
        """获取缓存统计"""
        return {
            'size': len(self._cache),
            'ttl_seconds': self._cache_ttl,
            'output_dir': str(self.output_dir)
        }