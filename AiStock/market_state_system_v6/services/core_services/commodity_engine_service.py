"""
V6.1 商品分析服务（完全独立微服务）
核心特性：
✅ 阈值动态化集成（ThresholdService）
✅ 配置统一提取（config_utils.extract_and_validate_config）
✅ 商品期货信号计算（成本型/收益型）
✅ 期货期限结构分析（Contango/Backwardation）
✅ 产业景气度评估（基于期限结构）
✅ 完整降级策略（阈值服务失效时回退静态阈值）
✅ 所有数值强制Python原生float（防Plotly序列化错误）
修复点：
✅ 从config安全获取商品配置（commodity_strategy_map/commodity_thresholds）
✅ 动态阈值获取（优先ThresholdService，回退静态配置）
✅ 商品信号计算完整实现（20日价格变化+阈值判定）
✅ 期限结构分析完整实现（近月/远月价差）
✅ 详细日志与异常处理
✅ 完整数据验证与降级
"""
import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime
import logging
import warnings

warnings.filterwarnings('ignore')
logger = logging.getLogger(__name__)

# ✅ V6.1核心：导入配置工具（统一配置提取）
from utils.config_utils import extract_and_validate_config, safe_config_get


class CommodityEngineService:
    """V6.1 商品分析服务（阈值动态化 + 配置统一化）"""
    
    def __init__(self, data_service, config_service, threshold_service=None):
        """
        初始化商品分析服务
        
        参数:
            data_service: DataLoadingService实例（用于加载期货数据）
            config_service: ConfigService实例（提供配置字典）
            threshold_service: ThresholdService实例（可选，None=使用静态阈值）
        
        修复点:
        ✅ 使用extract_and_validate_config统一配置提取
        ✅ 安全获取嵌套配置（safe_config_get）
        ✅ 详细日志记录配置状态
        ✅ 完整异常处理
        """
        self.data_service = data_service
        self.logger = logger
        
        # ✅ V6.1核心：统一配置提取（1行替代20+行验证逻辑）
        self.config, is_valid, missing_keys = extract_and_validate_config(
            config_service=config_service,
            required_keys=[
                'commodity_strategy_map',
                'commodity_thresholds',
                'futures_markets'
            ],
            logger=self.logger,
            service_name='CommodityEngineService'
        )
        
        # ✅ 保存ThresholdService引用（可选）
        self.threshold_service = threshold_service
        
        # 验证配置完整性
        if is_valid:
            self.logger.info("✅ CommodityEngineService初始化成功（配置完整）")
            self.logger.debug(
                f"   • 商品映射: {len(self.config.get('commodity_strategy_map', {}))}个 | "
                f"商品阈值: 已加载 | 期货市场: {len(self.config.get('futures_markets', {}))}个"
            )
        else:
            self.logger.warning(f"⚠️ CommodityEngineService初始化完成（缺失{len(missing_keys)}项配置）")
    
    # ==================== 核心方法：商品期货信号计算 ====================
    
    def calculate_commodity_signals(self) -> Dict[str, Dict]:
        """
        V6.1核心：商品期货信号计算
        
        返回:
            {
                'CUL8': {
                    'name': '沪铜',
                    'price_chg_20d': float,      # 20日价格变化(%)
                    'signal': str,                # 信号描述
                    'score': float,               # 调整分数（-0.15到+0.12）
                    'directions': List[str],      # 影响的战略方向
                    'weight': float,              # 商品权重
                    'impact_type': str,           # 影响类型（cost/benefit）
                    'threshold_up': float,        # 上阈值
                    'threshold_down': float       # 下阈值
                },
                ...
            }
        
        修复点:
        ✅ 动态阈值获取（优先ThresholdService，回退静态配置）
        ✅ 所有数值强制Python原生float
        ✅ 完整降级策略（任一商品失败不影响整体）
        ✅ 详细日志记录每步计算
        """
        commodity_signals = {}
        
        # 获取商品配置
        commodity_map = safe_config_get(
            self.config,
            ['commodity_strategy_map'],
            default={},
            logger=self.logger
        )
        
        for code, config in commodity_map.items():
            try:
                # 1. 获取市场代码
                market_code = config.get('market_code', 30)
                
                # 2. 加载商品期货数据
                df = self.data_service.load_derivative_data(code, market_code, days=60)
                
                if len(df) < 20:
                    self.logger.debug(f"⚠️ {code}({config.get('name', code)}) 数据不足（需≥20日）")
                    continue
                
                # 3. 计算20日价格变化
                price_chg_20d = ((df['close'].iloc[-1] / df['close'].iloc[-20]) - 1) * 100
                
                # 4. ✅ V6.1核心：动态获取阈值（优先ThresholdService）
                threshold_up = self._get_dynamic_threshold(
                    code, 'threshold_up', config.get('threshold_up', 10.0)
                )
                threshold_down = self._get_dynamic_threshold(
                    code, 'threshold_down', config.get('threshold_down', -10.0)
                )
                
                # 5. 生成信号和调整分数
                signal, score = self._generate_signal(
                    price_chg=price_chg_20d,
                    impact_type=config.get('impact_type', 'cost'),
                    threshold_up=threshold_up,
                    threshold_down=threshold_down,
                    code=code
                )
                
                # 6. 构建信号字典（强制Python原生类型）
                commodity_signals[code] = {
                    'name': config.get('name', code),
                    'price_chg_20d': float(price_chg_20d),
                    'signal': signal,
                    'score': float(score),
                    'directions': config.get('directions', []),
                    'weight': float(config.get('weight', 0.05)),
                    'impact_type': config.get('impact_type', 'cost'),
                    'threshold_up': float(threshold_up),
                    'threshold_down': float(threshold_down),
                    'market_code': int(market_code)
                }
                
                self.logger.debug(
                    f"✅ {code}({config.get('name', code)}) | "
                    f"20日变化={price_chg_20d:+.1f}% | 信号={signal} | 调整={score:+.2f} | "
                    f"阈值来源={'动态' if self.threshold_service else '静态'}"
                )
            
            except Exception as e:
                self.logger.warning(
                    f"⚠️ {code}({config.get('name', code)}) 信号计算失败: {str(e)[:30]}"
                )
                continue
        
        self.logger.info(f"✅ 计算商品期货信号：{len(commodity_signals)}个商品")
        return commodity_signals
    
    # ==================== 核心方法：期货期限结构分析 ====================
    
    def calculate_futures_term_structure(self) -> Dict[str, Dict]:
        """
        V6.1核心：期货期限结构分析（Contango/Backwardation）
        
        返回:
            {
                'copper': {
                    'spread': float,              # 价差(%)
                    'structure': 'backwardation'/'contango',
                    'signal': str,                # 信号描述
                    'near_price': float,          # 近月价格
                    'far_price': float,           # 远月价格
                    'near_code': str,             # 近月合约代码
                    'far_code': str               # 远月合约代码
                },
                ...
            }
        
        修复点:
        ✅ 完整商品合约配置（从config获取）
        ✅ 所有数值强制Python原生float
        ✅ 完整异常处理与降级
        ✅ 详细日志记录
        """
        term_structure = {}
        
        # 获取商品合约配置
        commodity_contracts = safe_config_get(
            self.config,
            ['commodity_contracts'],
            default={
                'copper': ('CU2603', 'CU2606', 30),
                'aluminum': ('AL2603', 'AL2606', 30),
                'lithium': ('LC2603', 'LC2606', 66),
                'silicon': ('SI2603', 'SI2606', 66),
                'crude': ('SC2603', 'SC2606', 30),
                'rebar': ('RB2603', 'RB2606', 30),
                'gold': ('AU2603', 'AU2606', 30),
                'soybean': ('M2603', 'M2605', 29)
            },
            logger=self.logger
        )
        
        for key, (near_code, far_code, market_code) in commodity_contracts.items():
            try:
                # 1. 加载近月合约数据
                near_df = self.data_service.load_derivative_data(near_code, market_code, days=20)
                
                # 2. 加载远月合约数据
                far_df = self.data_service.load_derivative_data(far_code, market_code, days=20)
                
                # 3. 计算价差
                if len(near_df) > 0 and len(far_df) > 0 and far_df['close'].iloc[-1] > 0:
                    near_price = near_df['close'].iloc[-1]
                    far_price = far_df['close'].iloc[-1]
                    spread = ((near_price - far_price) / far_price) * 100
                    
                    # 4. 判定期限结构
                    structure = 'backwardation' if spread > 0 else 'contango'
                    signal = '供应紧张/景气' if spread > 0 else '供应充足/疲软'
                    
                    # 5. 构建结果（强制Python原生类型）
                    term_structure[key] = {
                        'spread': round(float(spread), 2),
                        'structure': structure,
                        'signal': signal,
                        'near_price': float(near_price),
                        'far_price': float(far_price),
                        'near_code': near_code,
                        'far_code': far_code
                    }
                    
                    self.logger.debug(
                        f"✅ {key}: 价差{spread:+.1f}% ({structure}) | "
                        f"近月={near_price:.1f} | 远月={far_price:.1f}"
                    )
                else:
                    self.logger.debug(f"⚠️ {key} 期限结构数据不足或无效")
            
            except Exception as e:
                self.logger.warning(f"⚠️ {key} 期限结构计算失败: {str(e)[:30]}")
                continue
        
        self.logger.info(f"✅ 计算期货期限结构：{len(term_structure)}个品种")
        return term_structure
    
    # ==================== 核心方法：产业景气度评估 ====================
    
    def calculate_industry_sentiment(self, term_structure: Dict) -> Dict[str, float]:
        """
        V6.1核心：基于期限结构计算产业景气度评分
        
        参数:
            term_structure: 期限结构数据（来自calculate_futures_term_structure）
        
        返回:
            {'高端制造': 65.0, '新能源': 72.0, ...}  # 评分0-100
        """
        # 商品到战略方向的映射
        commodity_to_direction = {
            'copper': ['高端制造', '供应链'],
            'aluminum': ['高端制造', '新能源'],
            'lithium': ['新能源', '信息技术'],
            'silicon': ['信息技术', '新能源'],
            'crude': ['公用事业', '供应链', '传统升级'],
            'rebar': ['传统升级', '供应链'],
            'gold': ['公用事业'],
            'soybean': ['现代农业', '生物健康']
        }
        
        # 初始化方向评分（默认50分）
        direction_sentiment = {
            '高端制造': 50.0,
            '信息技术': 50.0,
            '新能源': 50.0,
            '生物健康': 50.0,
            '供应链': 50.0,
            '现代农业': 50.0,
            '公用事业': 50.0,
            '传统升级': 50.0,
            '文化消费': 50.0
        }
        
        # 根据期限结构更新评分
        for commodity, data in term_structure.items():
            if commodity not in commodity_to_direction:
                continue
            
            # Backwardation(近月>远月) = 供应紧张 = 景气度高
            # Contango(近月<远月) = 供应充足 = 景气度低
            if data['structure'] == 'backwardation':
                sentiment_score = min(100, 50 + abs(data['spread']) * 3)
            else:  # contango
                sentiment_score = max(0, 50 - abs(data['spread']) * 3)
            
            # 更新关联方向的评分（加权平均）
            for direction in commodity_to_direction[commodity]:
                if direction in direction_sentiment:
                    # 70%保留原评分 + 30%新评分
                    direction_sentiment[direction] = (
                        direction_sentiment[direction] * 0.7 +
                        sentiment_score * 0.3
                    )
        
        # ✅ 强制转换为Python原生float（关键修复：防Plotly序列化错误）
        return {k: float(v) for k, v in direction_sentiment.items()}
    
    # ==================== 辅助方法：动态阈值获取 ====================
    
    def _get_dynamic_threshold(
        self,
        commodity_code: str,
        threshold_type: str,
        default_value: float
    ) -> float:
        """
        V6.1核心：动态获取商品阈值
        
        逻辑:
        1. 优先从ThresholdService获取动态阈值
        2. 降级：从配置获取静态阈值
        3. 根据波动率/市场状态动态调整
        
        返回:
            阈值（float）
        """
        # ✅ V6.1核心：动态获取阈值（优先ThresholdService）
        if self.threshold_service:
            try:
                threshold_name = f"commodity_{commodity_code}_{threshold_type}"
                threshold_value = self.threshold_service.get_threshold(
                    threshold_name,
                    context={'commodity': commodity_code},
                    strategy='volatility_adaptive'
                )
                
                self.logger.debug(
                    f"🔄 动态阈值 | {commodity_code}.{threshold_type} = {threshold_value:.1f} | "
                    f"策略=volatility_adaptive"
                )
                return float(threshold_value)
                
            except Exception as e:
                self.logger.warning(
                    f"⚠️ 动态阈值获取失败，回退静态配置: {str(e)[:30]}"
                )
        
        # 降级：使用静态配置阈值
        commodity_thresholds = safe_config_get(
            self.config,
            ['commodity_thresholds'],
            default={},
            logger=self.logger
        )
        
        # 从商品配置获取阈值
        commodity_map = safe_config_get(
            self.config,
            ['commodity_strategy_map'],
            default={},
            logger=self.logger
        )
        
        if commodity_code in commodity_map:
            config = commodity_map[commodity_code]
            if threshold_type == 'threshold_up':
                return float(config.get('threshold_up', default_value))
            elif threshold_type == 'threshold_down':
                return float(config.get('threshold_down', default_value))
        
        return float(default_value)
    
    # ==================== 辅助方法：信号生成 ====================
    
    def _generate_signal(
        self,
        price_chg: float,
        impact_type: str,
        threshold_up: float,
        threshold_down: float,
        code: str
    ) -> Tuple[str, float]:
        """
        生成商品信号和调整分数
        
        逻辑:
        1. 根据impact_type（cost/benefit）确定信号方向
        2. 根据price_chg与阈值比较生成信号
        3. 计算调整分数（-0.15到+0.12）
        
        返回:
            (信号描述, 调整分数)
        """
        if impact_type == 'cost':
            # 成本型商品：价格上涨对相关方向不利
            if price_chg > threshold_up:
                return '成本大幅上升', -0.15
            elif price_chg > threshold_up / 2:
                return '成本上升', -0.08
            elif price_chg < threshold_down:
                return '成本大幅下降', 0.12
            elif price_chg < threshold_down / 2:
                return '成本下降', 0.06
            else:
                return '成本稳定', 0.0
        else:  # benefit
            # 收益型商品：价格上涨对相关方向有利
            if price_chg > 8:
                return '避险情绪高涨', 0.10
            else:
                return '正常', 0.0
    
    # ==================== 高级功能：商品趋势数据 ====================
    
    def generate_commodity_trend_data(
        self,
        commodity_signals: Dict,
        days: int = 90
    ) -> Dict[str, Any]:
        """
        生成商品趋势图表数据（用于可视化）
        
        返回:
            {
                'dates': List[str],
                'commodity_prices': Dict[str, List[float]],
                'commodity_signals': Dict[str, List[str]],
                'industry_sentiment': Dict[str, List[float]]
            }
        """
        # 模拟历史数据（实际应从数据库获取）
        dates = pd.date_range(end=datetime.now(), periods=days).strftime('%Y-%m-%d').tolist()
        
        # 模拟商品价格（随机波动）
        commodity_prices = {}
        for code, signal in commodity_signals.items():
            base_price = np.random.uniform(50, 100)
            prices = [float(base_price + np.random.randn() * 5) for _ in range(days)]
            commodity_prices[code] = prices
        
        # 模拟商品信号（根据价格变化）
        commodity_signals_history = {}
        for code, prices in commodity_prices.items():
            signals = []
            for i in range(days):
                if i < 20:
                    signals.append('稳定')
                else:
                    price_chg = ((prices[i] / prices[i-20]) - 1) * 100
                    if price_chg > 10:
                        signals.append('上升')
                    elif price_chg < -10:
                        signals.append('下降')
                    else:
                        signals.append('稳定')
            commodity_signals_history[code] = signals
        
        # 模拟产业景气度（随机波动）
        industry_sentiment = {
            '高端制造': [float(50 + np.random.randn() * 10) for _ in range(days)],
            '新能源': [float(50 + np.random.randn() * 10) for _ in range(days)],
            '信息技术': [float(50 + np.random.randn() * 10) for _ in range(days)],
            '生物健康': [float(50 + np.random.randn() * 10) for _ in range(days)],
            '供应链': [float(50 + np.random.randn() * 10) for _ in range(days)],
            '现代农业': [float(50 + np.random.randn() * 10) for _ in range(days)],
            '公用事业': [float(50 + np.random.randn() * 10) for _ in range(days)],
            '传统升级': [float(50 + np.random.randn() * 10) for _ in range(days)],
            '文化消费': [float(50 + np.random.randn() * 10) for _ in range(days)]
        }
        
        return {
            'dates': dates,
            'commodity_prices': commodity_prices,
            'commodity_signals': commodity_signals_history,
            'industry_sentiment': industry_sentiment,
            'timestamp': datetime.now().isoformat()
        }


# ==================== 使用示例 ====================
def example_commodity_engine_service():
    """CommodityEngineService使用示例"""
    
    print("=" * 80)
    print("🧪 CommodityEngineService 使用示例（V6.1阈值动态化）")
    print("=" * 80)
    
    # 1. 初始化服务（简化版）
    print("\n1️⃣ 初始化CommodityEngineService...")
    
    class MockConfigService:
        def __init__(self):
            self.config = {
                'commodity_strategy_map': {
                    'CUL8': {
                        'name': '沪铜',
                        'market_code': 30,
                        'directions': ['高端制造', '供应链'],
                        'impact_type': 'cost',
                        'weight': 0.10,
                        'threshold_up': 10.0,
                        'threshold_down': -10.0
                    },
                    'LCL8': {
                        'name': '碳酸锂',
                        'market_code': 66,
                        'directions': ['新能源', '信息技术'],
                        'impact_type': 'cost',
                        'weight': 0.12,
                        'threshold_up': 20.0,
                        'threshold_down': -20.0
                    },
                    'SIL8': {
                        'name': '工业硅',
                        'market_code': 66,
                        'directions': ['信息技术', '新能源'],
                        'impact_type': 'cost',
                        'weight': 0.10,
                        'threshold_up': 15.0,
                        'threshold_down': -15.0
                    }
                },
                'commodity_thresholds': {
                    'enabled': True,
                    'volatility_adaptive': {
                        'enabled': True,
                        'base_threshold': 10.0,
                        'benchmark_vol': 25.0
                    }
                },
                'commodity_contracts': {
                    'copper': ('CU2603', 'CU2606', 30),
                    'aluminum': ('AL2603', 'AL2606', 30),
                    'lithium': ('LC2603', 'LC2606', 66),
                    'silicon': ('SI2603', 'SI2606', 66)
                },
                'futures_markets': {
                    'shfe': {'market_code': 30, 'enabled': True},
                    'dce': {'market_code': 29, 'enabled': True},
                    'czce': {'market_code': 32, 'enabled': True},
                    'gfex': {'market_code': 66, 'enabled': True}
                }
            }
    
    class MockDataService:
        def load_derivative_data(self, code, market_code, days):
            dates = pd.date_range(end=datetime.now(), periods=days)
            # 模拟期货价格（近月略高于远月=Backwardation）
            base_price = np.random.uniform(50, 100)
            if 'near' in code.lower() or '2603' in code:
                prices = np.random.randn(days).cumsum() + base_price + 1
            else:
                prices = np.random.randn(days).cumsum() + base_price
            return pd.DataFrame({
                'datetime': dates,
                'close': prices
            })
    
    config_service = MockConfigService()
    data_service = MockDataService()
    
    # 模拟ThresholdService（可选）
    class MockThresholdService:
        def get_threshold(self, name, context, strategy):
            # 模拟动态阈值
            if 'CUL8' in name:
                return 12.0 if 'up' in name else -12.0
            elif 'LCL8' in name:
                return 22.0 if 'up' in name else -22.0
            return 10.0
    
    threshold_service = MockThresholdService()
    
    commodity_service = CommodityEngineService(data_service, config_service, threshold_service)
    print("✅ 服务初始化成功")
    
    # 2. 计算商品期货信号
    print("\n2️⃣ 计算商品期货信号...")
    commodity_signals = commodity_service.calculate_commodity_signals()
    
    print(f"   ✅ 检测到 {len(commodity_signals)} 个商品信号")
    for code, signal in list(commodity_signals.items())[:3]:
        print(f"   • {signal['name']}({code}): {signal['signal']} (调整: {signal['score']:+.2f})")
    
    # 3. 计算期货期限结构
    print("\n3️⃣ 计算期货期限结构...")
    term_structure = commodity_service.calculate_futures_term_structure()
    
    print(f"   ✅ 检测到 {len(term_structure)} 个期限结构")
    for key, data in list(term_structure.items())[:3]:
        print(f"   • {key}: {data['spread']:+.1f}% ({data['structure']}) | {data['signal']}")
    
    # 4. 计算产业景气度
    print("\n4️⃣ 计算产业景气度...")
    industry_sentiment = commodity_service.calculate_industry_sentiment(term_structure)
    
    print(f"   ✅ 评估 {len(industry_sentiment)} 个产业景气度")
    top3 = sorted(industry_sentiment.items(), key=lambda x: x[1], reverse=True)[:3]
    for direction, score in top3:
        status = '🟢 景气' if score > 65 else ('🟡 稳健' if score > 50 else '🔴 疲软')
        print(f"   • {direction:8s}: {score:5.1f}分 {status}")
    
    # 5. 验证数据类型
    print("\n5️⃣ 验证数据类型（防Plotly序列化错误）:")
    sample_score = commodity_signals['CUL8']['score'] if 'CUL8' in commodity_signals else 0.0
    is_python_float = isinstance(sample_score, float) and not isinstance(sample_score, np.floating)
    print(f"   ✅ 调整分数类型: {type(sample_score).__name__} | Python float: {is_python_float}")
    
    # 6. 商品趋势数据（模拟）
    print("\n6️⃣ 商品趋势数据（模拟）:")
    trend_data = commodity_service.generate_commodity_trend_data(commodity_signals, days=30)
    print(f"   ✅ 数据点: {len(trend_data['dates'])}天")
    print(f"   ✅ 商品数量: {len(trend_data['commodity_prices'])}个")
    
    print("\n" + "=" * 80)
    print("✅ CommodityEngineService 示例运行完成")
    print("=" * 80)


if __name__ == "__main__":
    example_commodity_engine_service()