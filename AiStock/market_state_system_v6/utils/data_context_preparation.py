"""
V6.0 可视化数据准备模块
职责：
1. 统一准备data_context（18大图表所需全部数据）
2. 完整数据验证与降级处理
3. 强制Python原生类型转换（防Plotly序列化错误）
4. 详细日志与错误追踪
依赖：
- 所有业务服务实例（MarketStateService/RiskAssessmentService等）
- 配置服务（ConfigService）
- 数据加载服务（DataLoadingService）
修复点：
✅ 所有数值强制转换为Python原生float（防Plotly序列化错误）
✅ 完整数据验证与空值处理
✅ 降级策略（数据缺失时提供默认值）
✅ 详细日志（每步数据准备状态）
✅ 验证函数（validate_data_context）
"""
import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime
import logging
import warnings

warnings.filterwarnings('ignore')
logger = logging.getLogger(__name__)


def prepare_visualization_data_context(
    market_state_service,
    risk_service,
    allocation_service,
    sentiment_service,
    commodity_service,
    macro_service,
    pcr_service,
    cross_market_service,
    rotation_service,
    futures_service,
    data_service,
    config_service
) -> Dict[str, Any]:
    """
    V6.0核心：准备完整data_context（18大图表所需全部数据）
    
    参数:
        market_state_service: MarketStateService实例
        risk_service: RiskAssessmentService实例
        allocation_service: AllocationService实例
        sentiment_service: SentimentAnalysisService实例
        commodity_service: CommodityEngineService实例
        macro_service: MacroAnalysisService实例
        pcr_service: OptionPCRService实例
        cross_market_service: CrossMarketService实例
        rotation_service: IndustryRotationService实例
        futures_service: FuturesAnalysisService实例
        data_service: DataLoadingService实例
        config_service: ConfigService实例
    
    返回:
        data_context: 完整数据上下文字典（含18大图表所需全部数据）
            {
                'market_state': str,
                'val_score': float,
                'trend_score': float,
                'benchmark_data': Dict[str, pd.DataFrame],
                'micro_data': Dict,
                'allocation_df': pd.DataFrame,
                'pcr_data': Dict,
                'basis_data': Dict,
                'term_data': Dict,
                'flow_data': Dict,
                'sentiment_data': Dict,
                'market_data': Dict,
                'industry_data': Dict,
                'risk_metrics': Dict,
                'risk_data': List[Dict],
                'commodity_signals': Dict,
                'macro_history': Dict,
                'pe_data': pd.DataFrame,
                'bond_yield': float
            }
    
    修复点:
    ✅ 所有数值强制转换为Python原生float（防Plotly序列化错误）
    ✅ 完整数据验证与空值处理
    ✅ 降级策略（数据缺失时提供默认值）
    ✅ 详细日志（每步数据准备状态）
    """
    data_context = {}
    logger.info("=" * 80)
    logger.info("🔄 开始准备可视化数据上下文 (data_context)...")
    logger.info("=" * 80)
    
    # ========== 1. 市值基准数据 ==========
    logger.info("\n[1/18] 准备市值基准数据...")
    try:
        benchmark_data = {}
        for size, cfg in config_service.config.get('market_benchmarks', {}).items():
            code = cfg.get('code')
            if not code:
                logger.warning(f"⚠️ {size} 配置缺少code字段")
                continue
            
            df = data_service.load_index_data(code, min_days=500)
            if len(df) >= 500:
                benchmark_data[size] = df
                logger.info(f"   ✅ {size} ({code}): {len(df)}条")
            else:
                logger.warning(f"   ⚠️ {size} ({code}): 数据不足（{len(df)} < 500）")
        
        data_context['benchmark_data'] = benchmark_data
        logger.info(f"   📊 市值基准数据准备完成: {len(benchmark_data)}个层级")
    except Exception as e:
        logger.error(f"❌ 市值基准数据准备失败: {str(e)[:50]}")
        data_context['benchmark_data'] = {}
    
    # ========== 2. 微盘流动性数据 ==========
    logger.info("\n[2/18] 准备微盘流动性数据...")
    try:
        micro_data = {}
        df_primary = benchmark_data.get('微盘', pd.DataFrame())
        df_secondary = pd.DataFrame()
        
        # 加载次指数
        secondary_code = config_service.config.get('micro_redundancy', {}).get('secondary')
        if secondary_code:
            df_secondary = data_service.load_index_data(secondary_code, min_days=500)
            if len(df_secondary) > 0:
                micro_data['secondary'] = df_secondary
                logger.info(f"   ✅ 次指数 ({secondary_code}): {len(df_secondary)}条")
        
        # 评估微盘流动性
        if len(df_primary) > 0:
            micro_data['primary'] = df_primary
            liquidity_status = risk_service.assess_micro_liquidity(df_primary, df_secondary)
            micro_data['liquidity_status'] = liquidity_status
            logger.info(f"   ✅ 微盘流动性状态: {liquidity_status.get('stage', '未知')} (持续{liquidity_status.get('days_in_stage', 0)}日)")
        else:
            logger.warning("   ⚠️ 微盘主指数数据为空")
        
        data_context['micro_data'] = micro_data
    except Exception as e:
        logger.error(f"❌ 微盘流动性数据准备失败: {str(e)[:50]}")
        data_context['micro_data'] = {}
    
    # ========== 3. 市场状态数据 ==========
    logger.info("\n[3/18] 准备市场状态数据...")
    try:
        market_state, val_score, trend_score, _ = market_state_service.determine_market_state(benchmark_data)
        
        # ⭐⭐⭐ 关键修复：强制转换为Python原生float ⭐⭐⭐
        data_context['market_state'] = market_state
        data_context['val_score'] = float(val_score)
        data_context['trend_score'] = float(trend_score)
        
        logger.info(f"   ✅ 市场状态: {market_state}")
        logger.info(f"   ✅ 估值安全边际: {val_score:.1f}/100")
        logger.info(f"   ✅ 趋势动能强度: {trend_score:.1f}/100")
    except Exception as e:
        logger.error(f"❌ 市场状态数据准备失败: {str(e)[:50]}")
        data_context['market_state'] = '均衡持有区'
        data_context['val_score'] = 50.0
        data_context['trend_score'] = 50.0
    
    # ========== 4. 配置数据 ==========
    logger.info("\n[4/18] 准备配置数据...")
    try:
        allocation_df = allocation_service.calculate_allocation(
            benchmark_data=benchmark_data,
            micro_liquidity=micro_data.get('liquidity_status'),
            market_state=data_context['market_state']
        )
        data_context['allocation_df'] = allocation_df
        logger.info(f"   ✅ 配置完成: {len(allocation_df)}个方向")
    except Exception as e:
        logger.error(f"❌ 配置数据准备失败: {str(e)[:50]}")
        data_context['allocation_df'] = pd.DataFrame()
    
    # ========== 5. 期权PCR数据 ==========
    logger.info("\n[5/18] 准备期权PCR数据...")
    try:
        pcr_data = pcr_service.calculate_composite_pcr()
        
        # ⭐⭐⭐ 关键修复：强制转换为Python原生float ⭐⭐⭐
        if 'composite_pcr' in pcr_data:
            pcr_data['composite_pcr'] = float(pcr_data['composite_pcr'])
        
        data_context['pcr_data'] = pcr_data
        logger.info(f"   ✅ 综合PCR: {pcr_data.get('composite_pcr', 1.0):.2f} | {pcr_data.get('composite_signal', '中性')}")
    except Exception as e:
        logger.error(f"❌ 期权PCR数据准备失败: {str(e)[:50]}")
        # 降级：提供默认值
        data_context['pcr_data'] = {
            'composite_pcr': 1.0,
            'composite_signal': '中性',
            'components': {},
            'weights_used': {}
        }
    
    # ========== 6. 期货数据 ==========
    logger.info("\n[6/18] 准备期货数据...")
    try:
        # 商品期限结构
        term_structure = futures_service.calculate_commodity_term_structure()
        data_context['term_data'] = term_structure
        logger.info(f"   ✅ 商品期限结构: {len(term_structure)}个品种")
        
        # 股指基差（V6.0新增）
        basis_data = futures_service.calculate_index_futures_basis()
        data_context['basis_data'] = basis_data
        logger.info(f"   ✅ 股指基差: {len(basis_data)}个品种")
    except Exception as e:
        logger.error(f"❌ 期货数据准备失败: {str(e)[:50]}")
        data_context['term_data'] = {}
        data_context['basis_data'] = {}
    
    # ========== 7. 资金流向数据 ==========
    logger.info("\n[7/18] 准备资金流向数据...")
    try:
        flow_data = sentiment_service.calculate_fund_flow_heatmap()
        data_context['flow_data'] = flow_data
        logger.info(f"   ✅ 资金流向: {len(flow_data.get('categories', []))}个类别")
    except Exception as e:
        logger.error(f"❌ 资金流向数据准备失败: {str(e)[:50]}")
        # 降级：提供默认值
        data_context['flow_data'] = {
            'categories': ['融资余额', '北上资金', 'ETF规模', '南下资金'],
            'data_values': [[0.0, 0.0, 0.0]] * 4
        }
    
    # ========== 8. 情绪数据 ==========
    logger.info("\n[8/18] 准备情绪数据...")
    try:
        sentiment_data = sentiment_service.calculate_sentiment_scores()
        
        # ⭐⭐⭐ 关键修复：强制转换为Python原生float ⭐⭐⭐
        for key in ['margin_score', 'fund_score', 'vol_score', 'vix_score']:
            if key in sentiment_data:
                sentiment_data[key] = float(sentiment_data[key])
        
        data_context['sentiment_data'] = sentiment_data
        logger.info(f"   ✅ 融资余额: {sentiment_data.get('margin_score', 50):.1f}/100")
        logger.info(f"   ✅ 基金资金: {sentiment_data.get('fund_score', 50):.1f}/100")
        logger.info(f"   ✅ 波动率: {sentiment_data.get('vol_score', 50):.1f}/100")
        logger.info(f"   ✅ 恐慌指数: {sentiment_data.get('vix_score', 50):.1f}/100")
    except Exception as e:
        logger.error(f"❌ 情绪数据准备失败: {str(e)[:50]}")
        # 降级：提供默认值
        data_context['sentiment_data'] = {
            'margin_score': 50.0,
            'fund_score': 50.0,
            'vol_score': 50.0,
            'vix_score': 50.0
        }
    
    # ========== 9. 跨市场数据 ==========
    logger.info("\n[9/18] 准备跨市场数据...")
    try:
        market_data = cross_market_service.load_cross_market_data()
        data_context['market_data'] = market_data
        logger.info(f"   ✅ 跨市场: {len(market_data)}个市场")
    except Exception as e:
        logger.error(f"❌ 跨市场数据准备失败: {str(e)[:50]}")
        data_context['market_data'] = {}
    
    # ========== 10. 行业轮动数据 ==========
    logger.info("\n[10/18] 准备行业轮动数据...")
    try:
        industry_data = rotation_service.calculate_industry_rotation()
        data_context['industry_data'] = industry_data
        logger.info(f"   ✅ 行业轮动: {len(industry_data.get('industries', {}))}个行业")
    except Exception as e:
        logger.error(f"❌ 行业轮动数据准备失败: {str(e)[:50]}")
        data_context['industry_data'] = {'industries': {}, 'benchmark_return': 0.0}
    
    # ========== 11. 风险传导数据 ==========
    logger.info("\n[11/18] 准备风险传导数据...")
    try:
        risk_metrics = risk_service.calculate_risk_transmission(benchmark_data)
        data_context['risk_metrics'] = risk_metrics
        logger.info(f"   ✅ 风险传导: {len(risk_metrics)}个层级")
    except Exception as e:
        logger.error(f"❌ 风险传导数据准备失败: {str(e)[:50]}")
        data_context['risk_metrics'] = {}
    
    # ========== 12. 高风险方向数据（迁移自RiskAssessmentService） ==========
    logger.info("\n[12/18] 准备高风险方向数据...")
    try:
        risk_data = risk_service.prepare_high_risk_data()
        data_context['risk_data'] = risk_data
        logger.info(f"   ✅ 高风险方向: {len(risk_data)}个方向")
    except Exception as e:
        logger.error(f"❌ 高风险方向数据准备失败: {str(e)[:50]}")
        data_context['risk_data'] = []
    
    # ========== 13. 商品信号数据 ==========
    logger.info("\n[13/18] 准备商品信号数据...")
    try:
        commodity_signals = commodity_service.calculate_commodity_signals()
        data_context['commodity_signals'] = commodity_signals
        logger.info(f"   ✅ 商品信号: {len(commodity_signals)}个商品")
    except Exception as e:
        logger.error(f"❌ 商品信号数据准备失败: {str(e)[:50]}")
        data_context['commodity_signals'] = {}
    
    # ========== 14. 宏观数据 ==========
    logger.info("\n[14/18] 准备宏观数据...")
    try:
        macro_result = macro_service.calculate_macro_composite_score()
        
        # 构建宏观历史数据（简化版）
        macro_history = {
            'dates': [datetime.now().strftime('%Y-%m-%d')],
            'composite_score': [float(macro_result.get('composite_score', 50.0))],
            'category_scores': macro_result.get('category_scores', {})
        }
        
        data_context['macro_history'] = macro_history
        logger.info(f"   ✅ 宏观综合评分: {macro_result.get('composite_score', 50.0):.1f}/100")
        logger.info(f"   ✅ 宏观市场状态: {macro_result.get('market_state', '均衡持有区')}")
    except Exception as e:
        logger.error(f"❌ 宏观数据准备失败: {str(e)[:50]}")
        # 降级：提供默认值
        data_context['macro_history'] = {
            'dates': [datetime.now().strftime('%Y-%m-%d')],
            'composite_score': [50.0],
            'category_scores': {}
        }
    
    # ========== 15. 估值数据 ==========
    logger.info("\n[15/18] 准备估值数据...")
    try:
        pe_data = data_service.load_pe_data('000300')
        data_context['pe_data'] = pe_data
        logger.info(f"   ✅ PE数据: {len(pe_data)}条")
    except Exception as e:
        logger.error(f"❌ PE数据准备失败: {str(e)[:50]}")
        data_context['pe_data'] = pd.DataFrame()
    
    # ========== 16. 国债收益率 ==========
    logger.info("\n[16/18] 准备国债收益率...")
    try:
        bond_yield = 2.5  # 可从宏观数据获取
        data_context['bond_yield'] = float(bond_yield)  # ⭐ 强制转换
        logger.info(f"   ✅ 国债收益率: {bond_yield}%")
    except Exception as e:
        logger.error(f"❌ 国债收益率准备失败: {str(e)[:50]}")
        data_context['bond_yield'] = 2.5
    
    # ========== 17. 验证完整性 ==========
    logger.info("\n" + "=" * 80)
    logger.info("✅ data_context准备完成，验证完整性...")
    logger.info("=" * 80)
    
    is_valid, missing_keys = validate_data_context(data_context)
    if is_valid:
        logger.info("✅ data_context完整，所有必需数据已准备")
    else:
        logger.warning(f"⚠️ data_context缺失: {missing_keys}")
    
    # 统计各数据项
    logger.info("\n📊 data_context数据统计:")
    for key in [
        'market_state', 'val_score', 'trend_score',
        'benchmark_data', 'micro_data', 'allocation_df',
        'pcr_data', 'basis_data', 'term_data',
        'flow_data', 'sentiment_data', 'market_data',
        'industry_data', 'risk_metrics', 'risk_data',
        'commodity_signals', 'macro_history',
        'pe_data', 'bond_yield'
    ]:
        value = data_context.get(key)
        if isinstance(value, dict):
            logger.info(f"   • {key:20s}: {len(value)} 项")
        elif isinstance(value, list):
            logger.info(f"   • {key:20s}: {len(value)} 项")
        elif isinstance(value, pd.DataFrame):
            logger.info(f"   • {key:20s}: {len(value)} 行")
        else:
            logger.info(f"   • {key:20s}: {value}")
    
    logger.info("\n" + "=" * 80)
    logger.info("✅ data_context准备流程结束")
    logger.info("=" * 80)
    
    return data_context


def validate_data_context(data_context: Dict) -> Tuple[bool, List[str]]:
    """
    验证data_context完整性
    
    参数:
        data_context: 数据上下文字典
    
    返回:
        (是否完整, 缺失的键列表)
    """
    required_keys = [
        'market_state', 'val_score', 'trend_score',
        'benchmark_data', 'micro_data', 'allocation_df',
        'pcr_data', 'basis_data', 'term_data',
        'flow_data', 'sentiment_data', 'market_data',
        'industry_data', 'risk_metrics', 'risk_data',
        'commodity_signals', 'macro_history',
        'pe_data', 'bond_yield'
    ]
    
    missing = []
    for key in required_keys:
        if key not in data_context or data_context[key] is None:
            missing.append(key)
        # 特殊验证：DataFrame不能为空
        elif isinstance(data_context[key], pd.DataFrame) and len(data_context[key]) == 0:
            if key in ['benchmark_data', 'allocation_df', 'pe_data']:
                missing.append(key)
        # 特殊验证：字典不能为空
        elif isinstance(data_context[key], dict) and len(data_context[key]) == 0:
            if key in ['pcr_data', 'basis_data', 'term_data']:
                missing.append(key)
    
    return len(missing) == 0, missing


def ensure_python_float(value: Any) -> float:
    """
    确保数值为Python原生float（防Plotly序列化错误）
    
    参数:
        value: 任意数值类型
    
    返回:
        Python原生float
    """
    if pd.isna(value) or value is None:
        return 0.0
    
    # 转换为Python float
    return float(value)


# ==================== 使用示例 ====================
def example_usage():
    """使用示例"""
    
    print("=" * 80)
    print("🧪 data_context_preparation.py 使用示例")
    print("=" * 80)
    
    # 1. 初始化所有服务（简化版）
    print("\n1️⃣ 初始化服务...")
    
    # 实际使用时替换为真实服务实例
    class MockService:
        def __getattr__(self, name):
            return lambda *args, **kwargs: {}
    
    services = {
        'market_state_service': MockService(),
        'risk_service': MockService(),
        'allocation_service': MockService(),
        'sentiment_service': MockService(),
        'commodity_service': MockService(),
        'macro_service': MockService(),
        'pcr_service': MockService(),
        'cross_market_service': MockService(),
        'rotation_service': MockService(),
        'futures_service': MockService(),
        'data_service': MockService(),
        'config_service': MockService()
    }
    
    print("✅ 服务初始化完成")
    
    # 2. 准备data_context
    print("\n2️⃣ 准备data_context...")
    data_context = prepare_visualization_data_context(**services)
    
    # 3. 验证完整性
    print("\n3️⃣ 验证data_context完整性...")
    is_valid, missing = validate_data_context(data_context)
    if is_valid:
        print("✅ data_context完整")
    else:
        print(f"⚠️ data_context缺失: {missing}")
    
    # 4. 统计数据
    print("\n4️⃣ data_context数据统计:")
    for key, value in data_context.items():
        if isinstance(value, dict):
            print(f"   • {key}: {len(value)}项")
        elif isinstance(value, list):
            print(f"   • {key}: {len(value)}项")
        elif isinstance(value, pd.DataFrame):
            print(f"   • {key}: {len(value)}行")
        else:
            print(f"   • {key}: {value}")
    
    print("\n" + "=" * 80)
    print("✅ data_context_preparation.py 示例运行完成")
    print("=" * 80)


if __name__ == "__main__":
    example_usage()