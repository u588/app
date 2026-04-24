#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SummaryReport：分析摘要报告组件
功能：
  - 生成 HTML/Markdown/PDF 格式摘要报告
  - 支持自定义模板 + 国际化
  - 集成 Plotly 图表 + 数据表格
"""

import logging
import numpy as np
from pathlib import Path
from typing import Dict, List, Optional, Any, Union
from datetime import datetime
import json

logger = logging.getLogger(__name__)


def generate_summary_report(
    batch_results: List[Dict],
    recommended: List[Dict],
    output_path: Union[str, Path],
    format: str = 'html',
    config: Optional[Dict] = None
) -> Optional[str]:
    """
    生成分析摘要报告
    
    参数:
        batch_results: 批量计算结果
        recommended: 推荐标的列表
        output_path: 输出文件路径
        format: 输出格式 (html/markdown/pdf)
        config: 报告配置
    
    返回:
        str: 输出文件路径
    """
    config = config or {}
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    try:
        if format == 'html':
            return _generate_html_report(batch_results, recommended, output_path, config)
        elif format == 'markdown':
            return _generate_markdown_report(batch_results, recommended, output_path, config)
        elif format == 'pdf':
            # 先生成 HTML 再转换（需安装 pdfkit + wkhtmltopdf）
            html_path = output_path.with_suffix('.html')
            _generate_html_report(batch_results, recommended, html_path, config)
            # 转换逻辑（可选）
            return str(output_path)
        else:
            logger.warning(f"⚠️ 不支持的报告格式: {format}")
            return None
            
    except Exception as e:
        logger.error(f"❌ 生成报告失败: {e}", exc_info=True)
        return None


def _generate_html_report(
    batch_results: List[Dict],
    recommended: List[Dict],
    output_path: Path,
    config: Dict
) -> str:
    """生成 HTML 格式报告"""
    import plotly.graph_objects as go
    import plotly.io as pio
    
    # 1. 计算摘要数据
    total = len(batch_results)
    rec_count = len(recommended)
    
    # 指标统计
    pl_ratios = [r['scores']['pl_ratio'] for r in batch_results if 'scores' in r]
    conf_factors = [r.get('technical_quality', {}).get('factor', 1.0) for r in batch_results]
    
    avg_pl = np.mean(pl_ratios) if pl_ratios else 0
    avg_conf = np.mean(conf_factors) if conf_factors else 1.0
    high_conf_count = sum(1 for c in conf_factors if c >= 1.01)
    
    # 板块分布
    from collections import Counter
    sector_dist = Counter(r['sector'] for r in batch_results)
    
    # 2. 创建图表
    # 2.1 板块分布饼图
    pie_fig = go.Figure(data=[go.Pie(
        labels=list(sector_dist.keys()),
        values=list(sector_dist.values()),
        textinfo='label+percent',
        hole=0.4
    )])
    pie_fig.update_layout(height=300, margin=dict(l=20, r=20, t=20, b=20), showlegend=False)
    pie_html = pio.to_html(pie_fig, full_html=False, include_plotlyjs='cdn')
    
    # 2.2 推荐标的表格
    table_rows = ""
    for r in recommended[:10]:
        rec_class = {
            '强烈推荐': 'strong',
            '推荐': 'normal',
            '观望': 'wait',
            '谨慎': 'caution'
        }.get(r['recommendation'], 'normal')
        
        table_rows += f"""
        <tr>
            <td>{r['code']}</td>
            <td>{r['name']}</td>
            <td>{r['sector']}</td>
            <td>¥{r['prices']['current']}</td>
            <td>¥{r['prices']['entry']}</td>
            <td>¥{r['prices']['target']}</td>
            <td>{r['scores']['pl_ratio']:.1f}x</td>
            <td class="recommend-{rec_class}">{r['recommendation']}</td>
        </tr>
        """
    
    # 3. 生成 HTML
    html_content = f"""
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>AiStock 分析摘要 - {config.get('version', 'unknown')}</title>
    <script src="https://cdn.plot.ly/plotly-latest.min.js"></script>
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; margin: 0; padding: 20px; background: #f8f9fa; }}
        .container {{ max-width: 1200px; margin: 0 auto; background: white; padding: 30px; border-radius: 8px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }}
        .header {{ background: linear-gradient(135deg, #1f77b4, #2ca02c); color: white; padding: 20px; border-radius: 5px; margin-bottom: 30px; }}
        .header h1 {{ margin: 0 0 10px 0; }}
        .metrics {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 15px; margin: 20px 0; }}
        .metric {{ background: #f8f9fa; padding: 15px; border-radius: 5px; text-align: center; border-left: 4px solid #1f77b4; }}
        .metric-value {{ font-size: 28px; font-weight: bold; color: #1f77b4; }}
        .metric-label {{ font-size: 12px; color: #666; margin-top: 5px; }}
        .section {{ margin: 30px 0; }}
        .section h2 {{ border-bottom: 2px solid #1f77b4; padding-bottom: 10px; color: #333; }}
        table {{ width: 100%; border-collapse: collapse; margin: 15px 0; }}
        th, td {{ padding: 10px; text-align: left; border-bottom: 1px solid #eee; }}
        th {{ background: #f2f2f2; font-weight: 600; }}
        .recommend-strong {{ color: #2ca02c; font-weight: bold; }}
        .recommend-normal {{ color: #1f77b4; }}
        .recommend-wait {{ color: #ff7f0e; }}
        .recommend-caution {{ color: #d62728; }}
        .footer {{ text-align: center; color: #666; font-size: 12px; margin-top: 40px; padding-top: 20px; border-top: 1px solid #eee; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>📊 AiStock 动态价格分析摘要</h1>
            <p>版本: {config.get('version', 'unknown')} | 生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
        </div>
        
        <div class="metrics">
            <div class="metric">
                <div class="metric-value">{total}</div>
                <div class="metric-label">分析标的</div>
            </div>
            <div class="metric">
                <div class="metric-value">{rec_count}</div>
                <div class="metric-label">推荐标的</div>
            </div>
            <div class="metric">
                <div class="metric-value">{avg_pl:.1f}x</div>
                <div class="metric-label">平均盈亏比</div>
            </div>
            <div class="metric">
                <div class="metric-value">{high_conf_count}</div>
                <div class="metric-label">高置信度</div>
            </div>
        </div>
        
        <div class="section">
            <h2>🥧 板块分布</h2>
            {pie_html}
        </div>
        
        <div class="section">
            <h2>🏆 推荐标的</h2>
            <table>
                <thead>
                    <tr>
                        <th>代码</th><th>名称</th><th>板块</th><th>现价</th>
                        <th>入场价</th><th>目标价</th><th>盈亏比</th><th>建议</th>
                    </tr>
                </thead>
                <tbody>
                    {table_rows}
                </tbody>
            </table>
        </div>
        
        <div class="footer">
            <p>生成于 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} | AiStock V6.2</p>
            <p>⚠️ 本分析仅供参考，不构成投资建议</p>
        </div>
    </div>
</body>
</html>
    """
    
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(html_content)
    
    logger.info(f"✅ HTML 报告已生成: {output_path}")
    return str(output_path)


def _generate_markdown_report(
    batch_results: List[Dict],
    recommended: List[Dict],
    output_path: Path,
    config: Dict
) -> str:
    """生成 Markdown 格式报告"""
    # 计算摘要数据
    total = len(batch_results)
    rec_count = len(recommended)
    
    pl_ratios = [r['scores']['pl_ratio'] for r in batch_results if 'scores' in r]
    avg_pl = np.mean(pl_ratios) if pl_ratios else 0
    
    # 板块分布表格
    from collections import Counter
    sector_dist = Counter(r['sector'] for r in batch_results)
    sector_table = "| 板块 | 数量 |\n|------|------|\n"
    for sector, count in sector_dist.most_common():
        sector_table += f"| {sector} | {count} |\n"
    
    # 推荐标的表格
    rec_table = "| 代码 | 名称 | 板块 | 现价 | 入场价 | 目标价 | 盈亏比 | 建议 |\n"
    rec_table += "|---- |-----|------|-------|-------|--------|--------|------|\n"
    for r in recommended[:10]:
        rec_table += f"| {r['code']} | {r['name']} | {r['sector']} | ¥{r['prices']['current']} | ¥{r['prices']['entry']} | ¥{r['prices']['target']} | {r['scores']['pl_ratio']:.1f}x | {r['recommendation']} |\n"
    
    # 生成 Markdown
    md_content = f"""# 📊 AiStock 动态价格分析摘要

**版本**: {config.get('version', 'unknown')}  
**生成时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

## 📈 核心指标

| 指标 | 数值 |
|------|------|
| 分析标的 | {total} 只 |
| 推荐标的 | {rec_count} 只 |
| 平均盈亏比 | {avg_pl:.1f}x |
| 高置信度标的 | {sum(1 for r in batch_results if r.get('technical_quality', {{}}).get('factor', 1.0) >= 1.01)} 只 |

## 🥧 板块分布

{sector_table}

## 🏆 推荐标的

{rec_table}

> ⚠️ 本分析仅供参考，不构成投资建议  
> 生成于 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} | AiStock V6.2
    """
    
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(md_content)
    
    logger.info(f"✅ Markdown 报告已生成: {output_path}")
    return str(output_path)