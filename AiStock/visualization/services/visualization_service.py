#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
VisualizationService：可视化主服务
"""
from typing import Dict, List, Any, Optional
from pathlib import Path
import logging
import yaml
from datetime import datetime

from ..core.factory import RendererFactory
from ..components import (create_price_interval_chart, create_factor_decomposition_chart,
                          create_portfolio_comparison_chart)
from ..utils.data_transform import sanitize_for_json

logger = logging.getLogger(__name__)

class VisualizationService:
    def __init__(self, config_path: Optional[str] = None):
        self.config = self._load_config(config_path) if config_path else {}
        self.renderer = RendererFactory.create(self.config.get('renderer', {}))
        self.output_dir = Path(self.config.get('output', {}).get('dir', 'output/visualization'))
        self.output_dir.mkdir(parents=True, exist_ok=True)
        logger.info(f"✅ VisualizationService 初始化完成 | 输出: {self.output_dir}")
    
    def _load_config(self, path: str) -> Dict:
        try:
            with open(path, 'r', encoding='utf-8') as f:
                return yaml.safe_load(f)
        except Exception as e:
            logger.warning(f"⚠️ 加载配置失败 {path}: {e}，使用默认配置")
            return {}
    
    def visualize_single_result(self, result: Dict[str, Any], chart_types: Optional[List[str]] = None,
                                output_format: str = 'html') -> Dict[str, str]:
        chart_types = chart_types or ['price_interval', 'factor_decomposition']
        outputs = {}
        code = result.get('code', 'unknown')
        safe_result = sanitize_for_json(result)
        
        for chart_type in chart_types:
            try:
                cfg = self.config.get('components', {}).get(chart_type, {})
                if chart_type == 'price_interval':
                    fig = create_price_interval_chart(safe_result, cfg)
                    filename = f"{code}_price_interval"
                elif chart_type == 'factor_decomposition':
                    fig = create_factor_decomposition_chart(safe_result, cfg)
                    filename = f"{code}_factor_decomposition"
                else:
                    continue
                
                if self.config.get('output', {}).get('timestamp_suffix', True):
                    filename += f"_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
                filename += f".{output_format}"
                
                output_path = self.output_dir / filename
                self.renderer.export(fig, str(output_path), format=output_format)
                outputs[chart_type] = str(output_path)
                logger.info(f"✅ 生成图表: {filename}")
            except Exception as e:
                logger.error(f"❌ 生成 {chart_type} 图表失败 {code}: {e}")
        return outputs
    
    def visualize_batch_results(self, results: List[Dict[str, Any]], chart_type: str = 'portfolio_comparison',
                                output_format: str = 'html') -> Optional[str]:
        if not results:
            logger.warning("⚠️ 批量结果为空")
            return None
        
        try:
            cfg = self.config.get('components', {}).get(chart_type, {})
            if chart_type == 'portfolio_comparison':
                fig = create_portfolio_comparison_chart(results, cfg)
                filename = f"portfolio_comparison_{len(results)}_stocks"
            else:
                raise ValueError(f"不支持的批量图表类型: {chart_type}")
            
            if self.config.get('output', {}).get('timestamp_suffix', True):
                filename += f"_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            filename += f".{output_format}"
            
            output_path = self.output_dir / filename
            self.renderer.export(fig, str(output_path), format=output_format)
            logger.info(f"✅ 生成批量图表: {filename}")
            return str(output_path)
        except Exception as e:
            logger.error(f"❌ 生成批量图表失败: {e}")
            return None