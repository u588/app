# %% [markdown]
# # 🧪 AiStock 动态价格系统 - 调试 Notebook (优化版)
# > ✅ 修复语法错误 | ✅ 增强可视化 | ✅ 性能诊断 | ✅ 批量对比

# %% [markdown]
# ## 🔧 1. 环境配置与路径注入

# %%
import sys
import os
from pathlib import Path
import warnings
import json
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import time
import traceback

# 禁用警告
warnings.filterwarnings('ignore')

# 注入项目根目录
PROJECT_ROOT = Path.cwd().parent
sys.path.insert(0, str(PROJECT_ROOT))
os.chdir(PROJECT_ROOT)

print(f"✅ 项目根目录: {PROJECT_ROOT}")
print(f"📁 工作目录: {os.getcwd()}")
print(f"🐍 Python 版本: {sys.version.split()[0]}")

# %% [markdown]
# ## 📝 2. 日志配置与智能导入

# %%
import logging
import importlib

# 配置彩色日志（终端支持时）
class ColoredFormatter(logging.Formatter):
    COLORS = {'DEBUG': '\033[36m', 'INFO': '\033[32m', 'WARNING': '\033[33m', 
              'ERROR': '\033[31m', 'CRITICAL': '\033[35m', 'RESET': '\033[0m'}
    
    def format(self, record):
        color = self.COLORS.get(record.levelname, self.COLORS['RESET'])
        record.levelname = f"{color}{record.levelname}{self.COLORS['RESET']}"
        return super().format(record)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    datefmt='%H:%M:%S',
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger("DebugMain")

def safe_import(import_path, fallback=None):
    """安全动态导入，支持模块.类名格式"""
    try:
        parts = import_path.split('.')
        if len(parts) == 1:
            return __import__(parts[0])
        module_path, obj_name = '.'.join(parts[:-1]), parts[-1]
        module = importlib.import_module(module_path)
        return getattr(module, obj_name)
    except Exception as e:
        logger.warning(f"⚠️ 导入 {import_path} 失败: {type(e).__name__}: {e}")
        return fallback

# 核心服务导入
ConfigService = safe_import('base_services.config_service.ConfigService')
CacheService = safe_import('base_services.cache_service.CacheService')
DatabaseReader = safe_import('data_services.database_reader.DatabaseReader')
TDXAdapter = safe_import('data_services.tdx_adapter.TDXAdapter')
AKAdapter = safe_import('data_services.ak_adapter.AKAdapter')
DataLoadingService = safe_import('data_services.data_loading_service.DataLoadingService')
DynamicPriceEngine = safe_import('dynamic_price_system.core.dynamic_price_engine.DynamicPriceEngine')

logger.info("🚀 调试环境初始化完成")

# %% [markdown]
# ## ⚙️ 3. 服务初始化与配置加载

# %%
# 1. 配置服务
try:
    config = ConfigService(system_name='dynamic_price')
    logger.info(f"✅ 配置服务加载: {config.config.get('system.name', 'unknown')}")
except Exception as e:
    logger.error(f"❌ 配置加载失败: {e}")
    raise

# 2. 缓存服务
cache_config = config.config.get('cache', {})
cache = CacheService(
    max_size=cache_config.get('max_size', 2000), 
    ttl=cache_config.get('ttl', 300)
) if CacheService else None
logger.info(f"✅ 缓存服务: max_size={cache_config.get('max_size', 2000)}, ttl={cache_config.get('ttl', 300)}s")

# 3. 数据库服务
try:
    db_config = config.config.get('database', {})
    db_reader = DatabaseReader(
        db_config.get('DATABASE_ENGINES', {}), 
        db_config.get('DB_POOL_CONFIG', {})
    )
    logger.info("✅ 数据库连接池初始化")
except Exception as e:
    logger.warning(f"⚠️ 数据库初始化失败: {e}，部分功能可能受限")
    db_reader = None

# 4. TDX 适配器
tdx_config = config.config.get('tdx', {})
tdx = TDXAdapter(tdx_config) if tdx_config.get('use_tdx') and TDXAdapter else None
if tdx:
    logger.info(f"✅ TDX 适配器: {tdx_config.get('exhq_host')}:{tdx_config.get('exhq_port')}")

# 5. 外部数据适配器 (AKShare)
ak = AKAdapter() if AKAdapter else None
if ak:
    logger.info("✅ AKShare 外部数据适配器就绪")

# %% [markdown]
# ## 📊 4. 数据加载模块调试

# %%
# 初始化数据加载服务
data_loader = DataLoadingService(
    config_service=config,
    cache_service=cache,
    database_reader=db_reader,
    tdx_adapter=tdx,
    ak_adapter=ak,
    enable_cache=True
)
logger.info("✅ DataLoadingService 初始化完成")

# 测试宏观指标智能路由
macro_codes = ['brent_crude', 'comex_gold', 'lme_copper', 'pmi', 'm2_growth', 'usd_cny']
start = time.time()
macro_data = data_loader.load_all_macro_indicators(macro_codes)
macro_time = time.time() - start

print(f"\n📊 宏观指标加载 ({macro_time:.2f}s):")
for k, v in macro_data.items():
    status = "✅" if v is not None else "❌"
    print(f"  {status} {k}: {v if isinstance(v, (int, float)) else 'N/A'}")

# 缓存统计
if cache:
    stats = data_loader.get_cache_stats()
    print(f"\n📈 缓存统计: 命中率={stats['hit_rate']:.1%}, 大小={stats['size']}")

# 股票数据加载测试
test_code = '600803'  # 新奥股份
start = time.time()
test_df = data_loader.load_stock_daily(test_code, min_days=200)
load_time = time.time() - start

if test_df is not None and not test_df.empty:
    print(f"\n✅ 行情数据加载: {test_code} | {len(test_df)}条 | {load_time:.2f}s")
    print(test_df[['datetime', 'open', 'high', 'low', 'close', 'volume']].tail(3).to_string(index=False))
else:
    logger.warning(f"⚠️ 股票 {test_code} 数据加载失败或为空")

# %% [markdown]
# ## 🎯 5. 动态价格引擎 - 单标的深度调试

# %%
# 初始化计算引擎
engine = DynamicPriceEngine(config_service=config) if DynamicPriceEngine else None

# 准备输入参数
stock_cfg = next((s for s in config.get('stocks', []) if s.get('code') == test_code), {})
if not stock_cfg:
    logger.error(f"❌ 未找到标的配置: {test_code}")
else:
    stock_params = stock_cfg.get('params', {})
    
    # 财务数据加载
    try:
        fin_df = data_loader.load_stock_financials(test_code)
        financial_data = fin_df.to_dict(orient='records')[0] if not fin_df.empty else {}
    except Exception as e:
        logger.warning(f"⚠️ 财务数据加载失败: {e}")
        financial_data = {}
    
    # 执行计算（带耗时统计）
    start = time.time()
    result = engine.calculate_single(
        code=test_code,
        name=stock_cfg.get('name', '未知'),
        sector=stock_cfg.get('sector', '未知'),
        stock_data=test_df,
        financial_data=financial_data,
        macro_data=macro_data,
        stock_params=stock_params
    )
    calc_time = time.time() - start
    
    if result:
        print(f"\n✅ 单标的计算成功! ({calc_time:.2f}s)")
        print("\n📋 计算结果摘要:")
        print(f"  • 当前价: ¥{result['prices']['current']:.2f}")
        print(f"  • 入场价: ¥{result['prices']['entry']:.2f} | 止损: ¥{result['prices']['stop_loss']:.2f} | 目标: ¥{result['prices']['target']:.2f}")
        print(f"  • 盈亏比: {result['scores']['pl_ratio']:.2f}x")
        print(f"  • 综合因子: {result['factors']['composite']:.3f} (基本面:{result['factors']['fundamental']:.3f} × 宏观:{result['factors']['macro']:.3f})")
        print(f"  • 建议: {result['recommendation']} | 趋势: {result['signals']['trend']}")
    else:
        logger.warning("❌ 计算返回 None，请检查日志或数据充分性")

# %% [markdown]
# ## 🚀 6. 批量计算与性能诊断

# %%
# 批量计算配置
batch_codes = [s.get('code') for s in config.get('stocks', [])[:5] if s.get('code')]
logger.info(f"🚀 开始批量计算: {len(batch_codes)} 只标的")

batch_inputs = []
for sc in config.get('stocks', []):
    code = sc.get('code')
    if code not in batch_codes:
        continue
    try:
        stock_data = data_loader.load_stock_daily(code, min_days=200)
        fin_df = data_loader.load_stock_financials(code)
        financial_data = fin_df.to_dict(orient='records')[0] if not fin_df.empty else {}
        
        batch_inputs.append({
            'code': code,
            'name': sc.get('name', '未知'),
            'sector': sc.get('sector', '未知'),
            'stock_data': stock_data,
            'financial_data': financial_data,
            'macro_data': macro_data,
            'params': sc.get('params', {})
        })
    except Exception as e:
        logger.warning(f"⚠️ 准备 {code} 输入失败: {e}")

# 执行批量计算
start = time.time()
batch_results = engine.calculate_batch(batch_inputs) if engine else []
batch_time = time.time() - start

print(f"\n✅ 批量计算完成: {len(batch_results)}/{len(batch_inputs)} 成功 | 耗时: {batch_time:.2f}s | 平均: {batch_time/max(1,len(batch_inputs)):.2f}s/只")

# 结果摘要表格
if batch_results:
    summary_data = []
    for r in batch_results:
        summary_data.append({
            '代码': r['code'],
            '名称': r['name'],
            '板块': r['sector'],
            '当前价': r['prices']['current'],
            '入场价': r['prices']['entry'],
            '止损价': r['prices']['stop_loss'],
            '目标价': r['prices']['target'],
            '盈亏比': r['scores']['pl_ratio'],
            '综合因子': r['factors']['composite'],
            '建议': r['recommendation']
        })
    
    df_summary = pd.DataFrame(summary_data)
    print("\n📊 批量结果摘要:")
    print(df_summary.to_string(index=False))

# %% [markdown]
# ## 📈 7. 增强可视化模块（交互式 Plotly）

# %%
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots

# 7.1 单标的价格区间可视化（增强版）
def plot_price_analysis(result):
    """增强版价格区间可视化"""
    if not result or 'prices' not in result:
        return None
    
    p = result['prices']
    f = result['factors']
    
    # 动态计算 Y 轴范围
    all_p = [v for v in p.values() if isinstance(v, (int, float))]
    y_min, y_max = min(all_p), max(all_p)
    padding = (y_max - y_min) * 0.3
    
    fig = make_subplots(
        rows=2, cols=1,
        subplot_titles=[f"价格区间分析 ({result['code']}:{result['name']})", "因子分解"],
        vertical_spacing=0.15,
        row_heights=[0.7, 0.3]
    )
    
    # 第一行：价格区间
    # 当前价
    fig.add_trace(go.Scatter(
        x=['当前价'], y=[p['current']],
        mode='markers',
        marker=dict(size=16, color='blue', symbol='star', line=dict(width=2, color='white')),
        name='当前价',
        hovertemplate='<b>当前价</b><br>¥%{y:.2f}<extra></extra>'
    ), row=1, col=1)
    
    # 入场区间（绿色色带）
    entry_low, entry_high = p['entry'] * 0.98, p['entry'] * 1.02
    fig.add_trace(go.Scatter(
        x=['入场区间', '入场区间'], y=[entry_low, entry_high],
        mode='lines',
        line=dict(color='green', width=4, dash='dash'),
        name='入场区间',
        fill='toself',
        fillcolor='rgba(0,128,0,0.1)',
        hovertemplate='<b>入场区间</b><br>¥' + f'{entry_low:.2f} - {entry_high:.2f}<extra></extra>'
    ), row=1, col=1)
    
    # 止损价
    fig.add_trace(go.Scatter(
        x=['止损价'], y=[p['stop_loss']],
        mode='markers+text',
        marker=dict(size=14, color='red', symbol='x', line=dict(width=2)),
        text=['止损'], textposition='bottom center',
        name='止损价',
        hovertemplate='<b>止损价</b><br>¥%{y:.2f}<extra></extra>'
    ), row=1, col=1)
    
    # 目标价
    fig.add_trace(go.Scatter(
        x=['目标价'], y=[p['target']],
        mode='markers+text',
        marker=dict(size=14, color='darkblue', symbol='diamond', line=dict(width=2)),
        text=[f"目标 ({result['scores']['pl_ratio']:.1f}x)"],
        textposition='top center',
        name='目标价',
        hovertemplate='<b>目标价</b><br>¥%{y:.2f}<br>盈亏比：' + f"{result['scores']['pl_ratio']:.1f}x<extra></extra>"
    ), row=1, col=1)
    
    # 潜在盈利区间（浅绿色背景）
    fig.add_shape(
        type="rect", xref="x", yref="y",
        x0=0.6, x1=1.4, y0=p['entry'], y1=p['target'],
        fillcolor="rgba(0,200,0,0.08)", line_width=0, layer="below"
    )
    
    # 第二行：因子分解（条形图）
    factors = [
        ('技术面', 1.0),
        ('基本面', f['fundamental']),
        ('宏观面', f['macro']),
        ('综合', f['composite'])
    ]
    factor_names, factor_values = zip(*factors)
    
    colors = ['gray', 'orange', 'purple', 'darkblue']
    fig.add_trace(go.Bar(
        x=factor_names, y=factor_values,
        marker_color=colors,
        name='调整因子',
        text=[f"{v:.3f}" for v in factor_values],
        textposition='auto',
        hovertemplate='<b>%{x}</b><br>因子：%{y:.3f}<extra></extra>'
    ), row=2, col=1)
    
    # 更新布局
    fig.update_layout(
        height=600,
        hovermode='closest',
        xaxis=dict(title='价格类型', showgrid=False),
        yaxis=dict(title='价格 (元)', range=[y_min - padding, y_max + padding]),
        yaxis2=dict(title='调整因子', range=[0.85, 1.15]),
        legend=dict(orientation='h', yanchor='bottom', y=-0.1, xanchor='center', x=0.5),
        showlegend=True
    )
    
    # 添加注释
    fig.add_annotation(
        x=0.5, y=1.02,
        text=f"板块:{result['sector']} | 趋势:{result['signals']['trend']} | RSI:{result['signals']['rsi_zone']}",
        showarrow=False, bgcolor='lightgray', font=dict(size=10),
        xref='paper', yref='paper'
    )
    
    return fig

# 7.2 批量结果对比可视化
def plot_batch_comparison(results):
    """批量结果对比图"""
    if not results:
        return None
    
    # 准备数据
    df = pd.DataFrame([{
        '代码': r['code'],
        '名称': r['name'],
        '板块': r['sector'],
        '盈亏比': r['scores']['pl_ratio'],
        '综合因子': r['factors']['composite'],
        '建议': r['recommendation'],
        '入场价': r['prices']['entry'],
        '目标价': r['prices']['target']
    } for r in results])
    
    # 建议颜色映射
    color_map = {'强烈推荐': 'green', '推荐': 'blue', '观望': 'orange', '谨慎': 'red'}
    
    # 盈亏比散点图
    fig = px.scatter(
        df, x='综合因子', y='盈亏比',
        color='建议', color_discrete_map=color_map,
        size='目标价', hover_name='名称',
        title='🎯 批量标的对比（综合因子 × 盈亏比）',
        labels={'综合因子': '综合调整因子', '盈亏比': '盈亏比 (x)'},
        size_max=30, opacity=0.8
    )
    
    # 添加参考线
    fig.add_vline(x=1.0, line_dash='dash', line_color='gray', annotation_text='中性因子')
    fig.add_hline(y=2.0, line_dash='dash', line_color='blue', annotation_text='盈亏比阈值')
    
    fig.update_layout(height=500, hovermode='closest')
    return fig

# 执行可视化
print("\n🎨 生成可视化图表...")

# 单标的详细分析
if result:
    fig1 = plot_price_analysis(result)
    if fig1:
        fig1.show()

# 批量对比
if batch_results:
    fig2 = plot_batch_comparison(batch_results)
    if fig2:
        fig2.show()

# %% [markdown]
# ## 📊 8. 性能诊断与缓存分析

# %%
# 性能诊断面板
if cache:
    stats = data_loader.get_cache_stats()
    
    # 创建性能仪表板
    fig_perf = make_subplots(
        rows=1, cols=3,
        subplot_titles=['缓存命中率', '请求分布', '容量使用'],
        specs=[[{'type': 'indicator'}, {'type': 'pie'}, {'type': 'indicator'}]]
    )
    
    # 命中率仪表
    fig_perf.add_trace(go.Indicator(
        mode='gauge+number+delta',
        value=stats['hit_rate'],
        domain={'x': [0, 0.3], 'y': [0, 1]},
        title={'text': '命中率'},
        delta={'reference': 0.8},
        gauge={'axis': {'range': [0, 1]}, 'bar': {'color': 'darkblue'}}
    ), row=1, col=1)
    
    # 请求分布饼图
    fig_perf.add_trace(go.Pie(
        labels=['命中', '未命中'],
        values=[stats['hits'], stats['misses']],
        marker_colors=['green', 'orange'],
        hole=0.4
    ), row=1, col=2)
    
    # 容量使用
    current, max_size = map(int, stats['size'].split('/'))
    fig_perf.add_trace(go.Indicator(
        mode='gauge+number',
        value=current / max_size,
        domain={'x': [0.7, 1], 'y': [0, 1]},
        title={'text': '容量'},
        gauge={'axis': {'range': [0, 1]}, 'bar': {'color': 'purple'}}
    ), row=1, col=3)
    
    fig_perf.update_layout(
        title='📈 性能诊断面板',
        height=300,
        margin=dict(l=20, r=20, t=50, b=20)
    )
    fig_perf.show()

# %% [markdown]
# ## 🧹 9. 资源清理与总结

# %%
# 清理资源
try:
    if hasattr(data_loader, 'close'):
        data_loader.close()
    if cache and hasattr(cache, 'clear'):
        cache.clear()
    if tdx and hasattr(tdx, 'close'):
        tdx.close()
    logger.info("✅ 资源清理完成")
except Exception as e:
    logger.warning(f"⚠️ 资源清理警告: {e}")

# 最终总结
print("\n" + "="*70)
print("🏁 调试流水线执行完毕")
print("="*70)
print("💡 关键指标回顾:")
if batch_results:
    avg_pl = np.mean([r['scores']['pl_ratio'] for r in batch_results])
    avg_factor = np.mean([r['factors']['composite'] for r in batch_results])
    rec_counts = pd.Series([r['recommendation'] for r in batch_results]).value_counts()
    print(f"  • 平均盈亏比: {avg_pl:.2f}x")
    print(f"  • 平均综合因子: {avg_factor:.3f}")
    print(f"  • 建议分布: {dict(rec_counts)}")
print("🔍 后续建议:")
print("  1. 检查日志中 ⚠️ 警告，确认降级策略是否合理")
print("  2. 验证 macro_data 路由：外部源 → TDX → DB 降级链")
print("  3. 监控缓存命中率：>80% 为优，<50% 需优化加载策略")
print("  4. 生产环境：关闭 DEBUG 日志，启用性能监控")
print("="*70)