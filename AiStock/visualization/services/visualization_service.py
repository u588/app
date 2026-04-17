#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
VisualizationService：可视化主服务
职责：
  - 协调数据获取、图表渲染、文件导出
  - 支持单标的/批量/仪表盘多种场景
  - 配置驱动 + 异常隔离 + 日志记录
"""

from typing import Dict, List, Any, Optional
from pathlib import Path
import logging
import yaml

from .core.factory import RendererFactory
from .components.price_chart import create_price_interval_chart
from .components.factor_chart import create_factor_decomposition_chart
from .components.portfolio_chart import create_portfolio_comparison_chart

logger = logging.getLogger(__name__)


class VisualizationService:
    """可视化主服务"""
    
    def __init__(self, config_path: Optional[str] = None):
        """
        初始化可视化服务
        
        参数:
            config_path: 图表配置文件路径（可选）
        """
        self.config = self._load_config(config_path) if config_path else {}
        self.renderer = RendererFactory.create(self.config.get('renderer', {}))
        self.output_dir = Path(self.config.get('output', {}).get('dir', 'output/visualization'))
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        logger.info(f"✅ VisualizationService 初始化完成 | 输出: {self.output_dir}")
    
    def _load_config(self, config_path: str) -> Dict:
        """加载 YAML 配置"""
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                return yaml.safe_load(f)
        except Exception as e:
            logger.warning(f"⚠️ 加载配置失败 {config_path}: {e}，使用默认配置")
            return {}
    
    def visualize_single_result(
        self,
        result: Dict[str, Any],
        chart_types: Optional[List[str]] = None,
        output_format: str = 'html'
    ) -> Dict[str, str]:
        """
        可视化单标的计算结果
        
        参数:
            result: DynamicPriceEngine 计算结果
            chart_types: 要生成的图表类型列表
            output_format: 输出格式（html/png/pdf）
        
        返回:
            {chart_name: output_path}
        """
        chart_types = chart_types or ['price_interval', 'factor_decomposition']
        outputs = {}
        code = result.get('code', 'unknown')
        
        for chart_type in chart_types:
            try:
                # 1. 生成图表
                if chart_type == 'price_interval':
                    chart_config = self.config.get('price_chart', {})
                    fig = create_price_interval_chart(result, chart_config)
                    filename = f"{code}_price_interval.{output_format}"
                
                elif chart_type == 'factor_decomposition':
                    chart_config = self.config.get('factor_chart', {})
                    fig = create_factor_decomposition_chart(result, chart_config)
                    filename = f"{code}_factor_decomposition.{output_format}"
                
                else:
                    logger.warning(f"⚠️ 未知图表类型: {chart_type}")
                    continue
                
                # 2. 导出文件
                output_path = self.output_dir / filename
                self.renderer.export(fig, str(output_path), format=output_format)
                outputs[chart_type] = str(output_path)
                
                logger.info(f"✅ 生成图表: {filename}")
                
            except Exception as e:
                logger.error(f"❌ 生成 {chart_type} 图表失败 {code}: {e}")
                continue
        
        return outputs
    
    def visualize_batch_results(
        self,
        results: List[Dict[str, Any]],
        chart_type: str = 'portfolio_comparison',
        output_format: str = 'html'
    ) -> Optional[str]:
        """
        可视化批量计算结果（组合对比）
        
        参数:
            results: 批量计算结果列表
            chart_type: 图表类型
            output_format: 输出格式
        
        返回:
            输出文件路径
        """
        if not results:
            logger.warning("⚠️ 批量结果为空，跳过可视化")
            return None
        
        try:
            # 生成图表
            if chart_type == 'portfolio_comparison':
                chart_config = self.config.get('portfolio_chart', {})
                fig = create_portfolio_comparison_chart(results, chart_config)
                filename = f"portfolio_comparison_{len(results)}_stocks.{output_format}"
            else:
                raise ValueError(f"不支持的批量图表类型: {chart_type}")
            
            # 导出
            output_path = self.output_dir / filename
            self.renderer.export(fig, str(output_path), format=output_format)
            
            logger.info(f"✅ 生成批量图表: {filename}")
            return str(output_path)
            
        except Exception as e:
            logger.error(f"❌ 生成批量图表失败: {e}")
            return None
    
    def generate_dashboard(
        self,
        results: List[Dict[str, Any]],
        template: str = 'default'
    ) -> Optional[str]:
        """
        生成综合仪表盘（多图表组合）
        
        参数:
            results: 计算结果列表
            template: 仪表盘模板名称
        
        返回:
            HTML 文件路径
        """
        logger.info(f"🎨 生成仪表盘 (模板:{template}) | 标的数:{len(results)}")
        
        # 简化版：返回批量对比图
        # 完整版：可使用 Plotly subplots 或 Dash 实现多图表联动
        return self.visualize_batch_results(
            results, 
            chart_type='portfolio_comparison',
            output_format='html'
        )