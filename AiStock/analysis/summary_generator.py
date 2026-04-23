#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SummaryGenerator：分析摘要生成器
功能：
  - 生成批量分析摘要（统计指标 + 推荐列表）
  - 支持多格式输出（JSON/HTML/Markdown）
  - 支持自定义模板 + 国际化
"""

import logging
import json
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Any, Union
import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


class SummaryGenerator:
    """分析摘要生成器"""
    
    # 默认模板
    DEFAULT_TEMPLATES = {
        'json': 'summary_template.json',
        'html': 'summary_template.html',
        'markdown': 'summary_template.md'
    }
    
    def __init__(self, config: Optional[Dict] = None, template_dir: Optional[Union[str, Path]] = None):
        """
        初始化摘要生成器
        
        参数:
            config: 生成器配置
            template_dir: 模板目录路径
        """
        self.config = config or {}
        self.template_dir = Path(template_dir) if template_dir else None
        self.templates = self._load_templates()
        
        logger.info(f"✅ SummaryGenerator 初始化 | 模板数: {len(self.templates)}")
    
    def _load_templates(self) -> Dict[str, str]:
        """加载模板文件"""
        templates = {}
        if not self.template_dir or not self.template_dir.exists():
            return self._default_templates()
        
        for fmt, filename in self.DEFAULT_TEMPLATES.items():
            path = self.template_dir / filename
            if path.exists():
                try:
                    with open(path, 'r', encoding='utf-8') as f:
                        templates[fmt] = f.read()
                except Exception as e:
                    logger.warning(f"⚠️ 加载模板 {filename} 失败: {e}")
        
        return templates or self._default_templates()
    
    def _default_templates(self) -> Dict[str, str]:
        """默认模板（内联）"""
        return {
            'json': '''
{
  "timestamp": "{{timestamp}}",
  "version": "{{version}}",
  "summary": {
    "total_analyzed": {{total}},
    "recommended_count": {{recommended}},
    "by_sector": {{by_sector}},
    "by_recommendation": {{by_recommendation}},
    "metrics": {{metrics}}
  },
  "top_picks": {{top_picks}}
}
            ''',
            'html': '''
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>AiStock 分析摘要 - {{version}}</title>
    <style>
        body { font-family: sans-serif; margin: 20px; }
        .header { background: #1f77b4; color: white; padding: 15px; border-radius: 5px; }
        .metrics { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 10px; margin: 20px 0; }
        .metric { background: #f8f9fa; padding: 10px; border-radius: 3px; text-align: center; }
        .metric-value { font-size: 24px; font-weight: bold; color: #1f77b4; }
        table { width: 100%; border-collapse: collapse; margin: 20px 0; }
        th, td { padding: 8px; text-align: left; border-bottom: 1px solid #ddd; }
        th { background: #f2f2f2; }
        .recommend-strong { color: #2ca02c; font-weight: bold; }
        .recommend-normal { color: #1f77b4; }
        .recommend-wait { color: #ff7f0e; }
        .recommend-caution { color: #d62728; }
    </style>
</head>
<body>
    <div class="header">
        <h1>📊 AiStock 动态价格分析摘要</h1>
        <p>版本: {{version}} | 生成时间: {{timestamp}}</p>
    </div>
    
    <div class="metrics">
        <div class="metric">
            <div class="metric-value">{{total}}</div>
            <div>分析标的</div>
        </div>
        <div class="metric">
            <div class="metric-value">{{recommended}}</div>
            <div>推荐标的</div>
        </div>
        <div class="metric">
            <div class="metric-value">{{avg_pl}}x</div>
            <div>平均盈亏比</div>
        </div>
        <div class="metric">
            <div class="metric-value">{{high_conf}}</div>
            <div>高置信度</div>
        </div>
    </div>
    
    <h2>🏆 推荐标的</h2>
    <table>
        <thead>
            <tr>
                <th>代码</th><th>名称</th><th>板块</th>
                <th>入场价</th><th>目标价</th><th>盈亏比</th><th>建议</th>
            </tr>
        </thead>
        <tbody>
            {{#top_picks}}
            <tr>
                <td>{{code}}</td><td>{{name}}</td><td>{{sector}}</td>
                <td>¥{{entry}}</td><td>¥{{target}}</td>
                <td>{{pl_ratio}}x</td>
                <td class="recommend-{{recommend_class}}">{{recommendation}}</td>
            </tr>
            {{/top_picks}}
        </tbody>
    </table>
</body>
</html>
            ''',
            'markdown': '''
# 📊 AiStock 动态价格分析摘要

**版本**: {{version}}  
**生成时间**: {{timestamp}}

## 📈 核心指标

| 指标 | 数值 |
|------|------|
| 分析标的 | {{total}} 只 |
| 推荐标的 | {{recommended}} 只 |
| 平均盈亏比 | {{avg_pl}}x |
| 高置信度标的 | {{high_conf}} 只 |

## 🏆 推荐标的

| 代码 | 名称 | 板块 | 入场价 | 目标价 | 盈亏比 | 建议 |
|------|------|------|--------|--------|--------|------|
{{#top_picks}}
| {{code}} | {{name}} | {{sector}} | ¥{{entry}} | ¥{{target}} | {{pl_ratio}}x | {{recommendation}} |
{{/top_picks}}

## 📊 板块分布

{{by_sector_table}}

> 生成于 {{timestamp}} | AiStock V6.2
            '''
        }
    
    def generate(
        self,
        batch_results: List[Dict],
        recommended: List[Dict],
        output_format: str = 'json',
        output_path: Optional[Union[str, Path]] = None,
        template_name: Optional[str] = None
    ) -> Optional[Union[Dict, str]]:
        """
        生成分析摘要
        
        参数:
            batch_results: 批量计算结果
            recommended: 推荐标的列表
            output_format: 输出格式 (json/html/markdown)
            output_path: 输出文件路径（可选）
            template_name: 模板名称（可选）
        
        返回:
            Dict/str: 生成的摘要内容，或写入文件时返回路径
        """
        try:
            # 1. 计算摘要数据
            summary_data = self._compute_summary(batch_results, recommended)
            
            # 2. 渲染模板
            template = self.templates.get(template_name or output_format, self.templates[output_format])
            rendered = self._render_template(template, summary_data)
            
            # 3. 输出
            if output_format == 'json':
                result = json.loads(rendered)
            else:
                result = rendered
            
            if output_path:
                output_path = Path(output_path)
                output_path.parent.mkdir(parents=True, exist_ok=True)
                with open(output_path, 'w', encoding='utf-8') as f:
                    if output_format == 'json':
                        json.dump(result, f, ensure_ascii=False, indent=2)
                    else:
                        f.write(result)
                logger.info(f"✅ 摘要已保存: {output_path}")
                return str(output_path)
            
            return result
            
        except Exception as e:
            logger.error(f"❌ 生成摘要失败: {e}", exc_info=True)
            return None
    
    def _compute_summary(self, batch_results: List[Dict], recommended: List[Dict]) -> Dict:
        """计算摘要数据"""
        if not batch_results:
            return self._empty_summary()
        
        # 基础统计
        total = len(batch_results)
        rec_count = len(recommended)
        
        # 板块分布
        by_sector = {}
        for r in batch_results:
            sector = r.get('sector', '未知')
            by_sector[sector] = by_sector.get(sector, 0) + 1
        
        # 建议分布
        by_recommendation = {}
        for r in batch_results:
            rec = r.get('recommendation', '未知')
            by_recommendation[rec] = by_recommendation.get(rec, 0) + 1
        
        # 指标统计
        pl_ratios = [r['scores']['pl_ratio'] for r in batch_results if 'scores' in r and 'pl_ratio' in r['scores']]
        conf_factors = [r.get('technical_quality', {}).get('factor', 1.0) for r in batch_results if 'technical_quality' in r]
        fin_scores = [r['scores']['fundamental'] for r in batch_results if 'scores' in r and 'fundamental' in r['scores']]
        
        metrics = {
            'avg_pl_ratio': round(float(np.mean(pl_ratios)), 2) if pl_ratios else 0.0,
            'median_pl_ratio': round(float(np.median(pl_ratios)), 2) if pl_ratios else 0.0,
            'avg_confidence': round(float(np.mean(conf_factors)), 3) if conf_factors else 1.0,
            'avg_fundamental': round(float(np.mean(fin_scores)), 1) if fin_scores else 50.0,
            'high_confidence_count': sum(1 for c in conf_factors if c >= 1.01),
            'strong_recommend_count': by_recommendation.get('强烈推荐', 0)
        }
        
        # 推荐标的详情（取前 10）
        top_picks = []
        for r in recommended[:10]:
            rec_class = {
                '强烈推荐': 'strong',
                '推荐': 'normal',
                '观望': 'wait',
                '谨慎': 'caution'
            }.get(r['recommendation'], 'normal')
            
            top_picks.append({
                'code': r['code'],
                'name': r['name'],
                'sector': r['sector'],
                'entry': r['prices']['entry'],
                'target': r['prices']['target'],
                'pl_ratio': f"{r['scores']['pl_ratio']:.1f}",
                'recommendation': r['recommendation'],
                'recommend_class': rec_class,
                'confidence': r.get('technical_quality', {}).get('factor', 1.0)
            })
        
        # 板块分布表格（Markdown 用）
        by_sector_table = "| 板块 | 数量 |\n|------|------|\n"
        for sector, count in sorted(by_sector.items(), key=lambda x: -x[1]):
            by_sector_table += f"| {sector} | {count} |\n"
        
        return {
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'version': self.config.get('version', 'unknown'),
            'total': total,
            'recommended': rec_count,
            'by_sector': by_sector,
            'by_recommendation': by_recommendation,
            'metrics': metrics,
            'top_picks': top_picks,
            'by_sector_table': by_sector_table,
            'avg_pl': metrics['avg_pl_ratio'],
            'high_conf': metrics['high_confidence_count']
        }
    
    def _empty_summary(self) -> Dict:
        """空数据摘要"""
        return {
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'version': self.config.get('version', 'unknown'),
            'total': 0,
            'recommended': 0,
            'by_sector': {},
            'by_recommendation': {},
            'metrics': {
                'avg_pl_ratio': 0.0,
                'median_pl_ratio': 0.0,
                'avg_confidence': 1.0,
                'avg_fundamental': 50.0,
                'high_confidence_count': 0,
                'strong_recommend_count': 0
            },
            'top_picks': [],
            'by_sector_table': "| 板块 | 数量 |\n|------|------|\n",
            'avg_pl': 0.0,
            'high_conf': 0
        }
    
    def _render_template(self, template: str,  Dict) -> str:
        """简单模板渲染（支持 {{key}} 和 {{#list}}...{{/list}}）"""
        result = template
        
        # 替换简单变量
        for key, value in data.items():
            if isinstance(value, (str, int, float)):
                result = result.replace(f'{{{{{key}}}}}', str(value))
        
        # 处理列表循环（简化版）
        if 'top_picks' in data and isinstance(data['top_picks'], list):
            # 提取循环块
            import re
            pattern = r'\{\{#top_picks\}\}(.*?)\{\{/top_picks\}\}'
            match = re.search(pattern, result, re.DOTALL)
            if match:
                block = match.group(1)
                rows = []
                for item in data['top_picks']:
                    row = block
                    for k, v in item.items():
                        row = row.replace(f'{{{{{k}}}}}', str(v))
                    rows.append(row)
                result = re.sub(pattern, ''.join(rows), result, flags=re.DOTALL)
        
        return result.strip()
    
    def export_to_html(self,  Dict, output_path: Union[str, Path]) -> str:
        """导出为 HTML 报告"""
        return self.generate(
            batch_results=[],  # 已计算在 data 中
            recommended=[],
            output_format='html',
            output_path=output_path
        )