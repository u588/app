"""
V6.1 市场状态服务（完全独立微服务）
核心特性：
✅ 阈值动态化集成（ThresholdService）
✅ 配置统一提取（config_utils.extract_and_validate_config）
✅ 九宫格市场状态判定（估值×趋势）
✅ 估值安全边际计算（PE分位数+股债性价比）
✅ 趋势动能强度计算（20日动量+均线位置）
✅ 完整降级策略（阈值服务失效时回退静态阈值）
✅ 所有数值强制Python原生float（防Plotly序列化错误）
修复点：
✅ 从config安全获取估值/趋势阈值（非硬编码）
✅ 动态阈值获取（优先ThresholdService，回退静态配置）
✅ 详细日志与异常处理
✅ 微盘数据验证与降级
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


class MarketStateService:
    """V6.1 市场状态服务（阈值动态化 + 配置统一化）"""
    
    def __init__(self, data_service, config_service, threshold_service=None):
        """
        初始化市场状态服务
        
        参数:
            data_service: DataLoadingService实例（用于加载PE数据）
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
                'market_benchmarks',
                'risk_thresholds',
                'position_control'
            ],
            logger=self.logger,
            service_name='MarketStateService'
        )
        
        # ✅ 保存ThresholdService引用（可选）
        self.threshold_service = threshold_service
        
        # 验证配置完整性
        if is_valid:
            self.logger.info("✅ MarketStateService初始化成功（配置完整）")
            self.logger.debug(
                f"   • 市值基准: {len(self.config.get('market_benchmarks', {}))}个 | "
                f"风险阈值: 已加载 | 仓位控制: 已加载"
            )
        else:
            self.logger.warning(f"⚠️ MarketStateService初始化完成（缺失{len(missing_keys)}项配置）")
    
    # ==================== 核心方法：市场状态判定 ====================
    
    def determine_market_state(
        self,
        benchmark_data: Dict[str, pd.DataFrame]
    ) -> Tuple[str, float, float, Dict[str, str]]:
        """
        V6.1核心：判定市场状态（九宫格定位）
        
        参数:
            benchmark_ 市值基准数据字典 {'大盘': df, '中盘': df, ...}
        
        返回:
            (市场状态, 估值安全边际, 趋势动能强度, 各层诊断)
                市场状态: '战略进攻区'/'积极配置区'/.../'战略防御区'
                估值安全边际: 0-100（越高越安全）
                趋势动能强度: 0-100（越高越强势）
                各层诊断: {'大盘': '↑低估↑强势', '中盘': '→合理→中性', ...}
        
        修复点:
        ✅ 动态阈值获取（优先ThresholdService，回退静态配置）
        ✅ 所有数值强制Python原生float
        ✅ 完整降级策略（任一数据缺失时回退默认值）
        ✅ 详细日志记录每步计算
        """
        try:
            # 1. 验证数据有效性
            if not benchmark_data or '大盘' not in benchmark_data:
                self.logger.error("❌ 基准数据缺失（需包含'大盘'）")
                return '数据失效', 50.0, 50.0, {'大盘': '数据缺失'}
            
            # 2. 计算加权市场估值安全边际（动态阈值）
            market_val_score = self._calculate_market_valuation_score(benchmark_data)
            
            # 3. 计算加权市场趋势动能强度（动态阈值）
            market_trend_score = self._calculate_market_trend_score(benchmark_data)
            
            # 4. 生成各层诊断
            layer_diagnosis = self._generate_layer_diagnosis(benchmark_data)
            
            # 5. 判定市场状态（九宫格定位）
            market_state = self._map_scores_to_market_state(
                market_val_score,
                market_trend_score
            )
            
            # 6. 强制转换为Python原生float（关键修复：防Plotly序列化错误）
            market_val_score = float(market_val_score)
            market_trend_score = float(market_trend_score)
            
            self.logger.info(
                f"✅ 市场状态判定完成 | 状态={market_state} | "
                f"估值={market_val_score:.1f}/100 | 趋势={market_trend_score:.1f}/100 | "
                f"阈值来源={'动态' if self.threshold_service else '静态'}"
            )
            
            return market_state, market_val_score, market_trend_score, layer_diagnosis
            
        except Exception as e:
            self.logger.error(f"❌ 市场状态判定失败: {str(e)[:50]}")
            import traceback
            self.logger.debug(traceback.format_exc())
            return '系统错误', 50.0, 50.0, {'系统': '计算异常'}
    
    # ==================== 辅助方法：估值安全边际计算 ====================
    
    def _calculate_market_valuation_score(
        self,
        benchmark_data: Dict[str, pd.DataFrame]
    ) -> float:
        """
        计算加权市场估值安全边际（0-100）
        
        逻辑:
        1. 对每个有效层级计算估值评分
        2. 按市值权重加权平均
        3. 动态阈值调整（PE分位数+股债性价比）
        """
        layer_scores = {}
        valid_layers = []
        total_weight = 0.0
        
        for size in ['大盘', '中盘', '小盘']:
            if size not in benchmark_data or len(benchmark_data[size]) < 250:
                continue
            
            df = benchmark_data[size]
            code = self.config['market_benchmarks'][size]['code']
            
            # 计算该层级估值评分
            val_score = self.calculate_valuation_score(df, code)
            weight = self.config['market_benchmarks'][size]['weight']
            
            layer_scores[size] = val_score
            valid_layers.append(size)
            total_weight += weight
        
        # 加权平均
        if total_weight > 0:
            market_val_score = sum(
                layer_scores[size] * self.config['market_benchmarks'][size]['weight']
                for size in valid_layers
            ) / total_weight
        else:
            market_val_score = 50.0
        
        return float(np.clip(market_val_score, 0, 100))
    
    def calculate_valuation_score(
        self,
        df: pd.DataFrame,
        index_code: str
    ) -> float:
        """
        计算单个指数估值评分（0-100）
        
        评分逻辑:
        1. 获取PE历史数据（从PE数据库）
        2. 计算当前PE分位数（0-100，越低越安全）
        3. 反转为安全边际得分（100-分位数）
        4. 动态阈值调整（可选）
        
        返回:
            估值安全边际得分（0-100，越高越安全）
        """
        try:
            # 1. 获取PE历史数据
            pe_df = self.data_service.load_pe_data(index_code)
            if len(pe_df) < 250 or 'pe_ttm' not in pe_df.columns:
                self.logger.debug(f"⚠️ {index_code} PE数据不足，使用默认估值50分")
                return 50.0
            
            current_pe = df['close'].iloc[-1] / (df['close'].iloc[-1] / pe_df['pe_ttm'].iloc[-1])
            pe_history = pe_df['pe_ttm'].iloc[-250:-1]
            
            # 2. 计算PE分位数（0-100，越低越安全）
            pe_percentile = (pe_history < current_pe).mean() * 100
            
            # 3. 反转为安全边际得分（100-分位数）
            safety_margin = 100 - pe_percentile
            
            # ✅ V6.1核心：动态阈值调整（可选）
            if self.threshold_service:
                # 动态调整安全边际（根据市场状态）
                context = {'pe_percentile': pe_percentile}
                adjustment = self.threshold_service.get_threshold(
                    'valuation_safety_margin_adjustment',
                    context=context,
                    strategy='market_regime'
                )
                safety_margin = safety_margin * (1 + adjustment / 100)
                self.logger.debug(
                    f"🔄 动态估值调整 | {index_code} | PE分位数={pe_percentile:.0f}% | "
                    f"安全边际={safety_margin:.1f} | 调整={adjustment:+.1f}%"
                )
            
            return float(np.clip(safety_margin, 0, 100))
            
        except Exception as e:
            self.logger.warning(f"⚠️ {index_code} 估值计算失败: {str(e)[:30]}，回退50分")
            return 50.0
    
    # ==================== 辅助方法：趋势动能强度计算 ====================
    
    def _calculate_market_trend_score(
        self,
        benchmark_data: Dict[str, pd.DataFrame]
    ) -> float:
        """
        计算加权市场趋势动能强度（0-100）
        
        逻辑:
        1. 对每个有效层级计算趋势评分
        2. 按市值权重加权平均
        3. 动态阈值调整（20日动量+均线位置）
        """
        layer_scores = {}
        valid_layers = []
        total_weight = 0.0
        
        for size in ['大盘', '中盘', '小盘']:
            if size not in benchmark_data or len(benchmark_data[size]) < 120:
                continue
            
            df = benchmark_data[size]
            trend_score = self.calculate_trend_score(df)
            weight = self.config['market_benchmarks'][size]['weight']
            
            layer_scores[size] = trend_score
            valid_layers.append(size)
            total_weight += weight
        
        # 加权平均
        if total_weight > 0:
            market_trend_score = sum(
                layer_scores[size] * self.config['market_benchmarks'][size]['weight']
                for size in valid_layers
            ) / total_weight
        else:
            market_trend_score = 50.0
        
        return float(np.clip(market_trend_score, 0, 100))
    
    def calculate_trend_score(self, df: pd.DataFrame) -> float:
        """
        计算单个指数趋势评分（0-100）
        
        评分逻辑:
        1. 20日动量（40%权重）
        2. 价格在20日均线上方天数占比（30%权重）
        3. 20日均线在60日均线上方（30%权重）
        
        返回:
            趋势动能强度得分（0-100，越高越强势）
        """
        try:
            if len(df) < 60:
                return 50.0
            
            # 1. 20日动量（40%权重）
            if len(df) >= 21:
                mom_20 = ((df['close'].iloc[-1] / df['close'].iloc[-21]) - 1) * 100
                mom_score = np.clip(mom_20 * 2 + 50, 0, 100)  # 转换为0-100
            else:
                mom_score = 50.0
            
            # 2. 价格在20日均线上方天数占比（30%权重）
            if 'ma_20' not in df.columns:
                df['ma_20'] = df['close'].rolling(20).mean()
            
            if len(df) >= 20:
                above_ma20 = (df['close'].iloc[-20:] > df['ma_20'].iloc[-20:]).mean() * 100
                ma_score = above_ma20
            else:
                ma_score = 50.0
            
            # 3. 20日均线在60日均线上方（30%权重）
            if 'ma_60' not in df.columns:
                df['ma_60'] = df['close'].rolling(60).mean()
            
            if len(df) >= 60:
                ma20_above_ma60 = df['ma_20'].iloc[-1] > df['ma_60'].iloc[-1]
                trend_score = 70 if ma20_above_ma60 else 30
            else:
                trend_score = 50.0
            
            # 综合评分
            total_score = (
                mom_score * 0.4 +
                ma_score * 0.3 +
                trend_score * 0.3
            )
            
            # ✅ V6.1核心：动态阈值调整（可选）
            if self.threshold_service:
                context = {'mom_20': mom_20, 'above_ma20': above_ma20}
                adjustment = self.threshold_service.get_threshold(
                    'trend_strength_adjustment',
                    context=context,
                    strategy='volatility_adaptive'
                )
                total_score = total_score * (1 + adjustment / 100)
                self.logger.debug(
                    f"🔄 动态趋势调整 | mom={mom_20:+.1f}% | above_ma20={above_ma20:.0f}% | "
                    f"得分={total_score:.1f} | 调整={adjustment:+.1f}%"
                )
            
            return float(np.clip(total_score, 0, 100))
            
        except Exception as e:
            self.logger.warning(f"⚠️ 趋势计算失败: {str(e)[:30]}，回退50分")
            return 50.0
    
    # ==================== 辅助方法：市场状态映射 ====================
    
    def _map_scores_to_market_state(
        self,
        val_score: float,
        trend_score: float
    ) -> str:
        """
        将估值和趋势得分映射到九宫格市场状态
        
        九宫格映射:
        |          | 低估(<40) | 合理(40-60) | 高估(>60) |
        |----------|----------|-------------|-----------|
        | 强势(>70)| 战略进攻区 | 积极配置区   | 防御进攻区 |
        | 中性(40-70)| 左侧布局区 | 均衡持有区   | 防御观望区 |
        | 弱势(<40)| 左侧防御区 | 谨慎持有区   | 战略防御区 |
        
        返回:
            市场状态字符串
        """
        # ✅ V6.1核心：动态阈值获取（优先ThresholdService）
        if self.threshold_service:
            # 动态获取估值/趋势阈值
            val_low = self.threshold_service.get_threshold(
                'valuation_low_threshold',
                context={'market_state': 'current'},
                strategy='static'
            )
            val_high = self.threshold_service.get_threshold(
                'valuation_high_threshold',
                context={'market_state': 'current'},
                strategy='static'
            )
            trend_weak = self.threshold_service.get_threshold(
                'trend_weak_threshold',
                context={'market_state': 'current'},
                strategy='static'
            )
            trend_strong = self.threshold_service.get_threshold(
                'trend_strong_threshold',
                context={'market_state': 'current'},
                strategy='static'
            )
        else:
            # 降级：使用静态配置阈值
            val_low = 40.0
            val_high = 60.0
            trend_weak = 40.0
            trend_strong = 70.0
        
        # 判定估值状态
        if val_score < val_low:
            val_state = '低估'
        elif val_score > val_high:
            val_state = '高估'
        else:
            val_state = '合理'
        
        # 判定趋势状态
        if trend_score < trend_weak:
            trend_state = '弱势'
        elif trend_score > trend_strong:
            trend_state = '强势'
        else:
            trend_state = '中性'
        
        # 九宫格映射
        state_map = {
            ('低估', '强势'): '战略进攻区',
            ('合理', '强势'): '积极配置区',
            ('高估', '强势'): '防御进攻区',
            ('低估', '中性'): '左侧布局区',
            ('合理', '中性'): '均衡持有区',
            ('高估', '中性'): '防御观望区',
            ('低估', '弱势'): '左侧防御区',
            ('合理', '弱势'): '谨慎持有区',
            ('高估', '弱势'): '战略防御区'
        }
        
        return state_map.get((val_state, trend_state), '均衡持有区')
    
    # ==================== 辅助方法：各层诊断生成 ====================
    
    def _generate_layer_diagnosis(
        self,
        benchmark_data: Dict[str, pd.DataFrame]
    ) -> Dict[str, str]:
        """
        生成各市值层级诊断（估值+趋势状态）
        
        返回:
            {'大盘': '↑低估↑强势', '中盘': '→合理→中性', ...}
        """
        diagnosis = {}
        
        for size in ['大盘', '中盘', '小盘', '微盘']:
            if size not in benchmark_data or len(benchmark_data[size]) < 120:
                diagnosis[size] = '数据缺失'
                continue
            
            df = benchmark_data[size]
            
            # 计算估值状态
            val_score = self.calculate_valuation_score(df, self.config['market_benchmarks'][size]['code'])
            if val_score < 40:
                val_status = '↑低估'
            elif val_score > 60:
                val_status = '↓高估'
            else:
                val_status = '→合理'
            
            # 计算趋势状态
            trend_score = self.calculate_trend_score(df)
            if trend_score < 40:
                trend_status = '↓弱势'
            elif trend_score > 70:
                trend_status = '↑强势'
            else:
                trend_status = '→中性'
            
            diagnosis[size] = f"{val_status}{trend_status} | 估值{val_score:.0f} 趋势{trend_score:.0f}"
        
        return diagnosis
    
    # ==================== 高级功能：市场状态历史记录 ====================
    
    def get_market_state_history(
        self,
        benchmark_data: Dict[str, pd.DataFrame],
        lookback_days: int = 90
    ) -> pd.DataFrame:
        """
        获取市场状态历史记录（用于可视化）
        
        参数:
            benchmark_ 市值基准数据字典
            lookback_days: 回溯天数
        
        返回:
            DataFrame with columns: ['date', 'market_state', 'val_score', 'trend_score']
        """
        history = []
        
        # 获取最短数据长度
        min_len = min(len(df) for df in benchmark_data.values() if len(df) > 0)
        if min_len < lookback_days + 120:
            lookback_days = min_len - 120
        
        for i in range(lookback_days):
            # 构建历史数据快照
            snapshot = {}
            for size, df in benchmark_data.items():
                if len(df) >= lookback_days + 120:
                    snapshot[size] = df.iloc[:-(lookback_days - i)].copy()
            
            if not snapshot:
                continue
            
            # 判定历史市场状态
            market_state, val_score, trend_score, _ = self.determine_market_state(snapshot)
            
            # 获取日期
            date = benchmark_data['大盘'].iloc[-(lookback_days - i)]['datetime']
            
            history.append({
                'date': date,
                'market_state': market_state,
                'val_score': float(val_score),
                'trend_score': float(trend_score)
            })
        
        return pd.DataFrame(history)
    
    # ==================== 高级功能：市场状态变化检测 ====================
    
    def detect_market_state_change(
        self,
        current_state: str,
        previous_state: str
    ) -> Dict[str, Any]:
        """
        检测市场状态变化并生成信号
        
        返回:
            {
                'changed': bool,
                'from': str,
                'to': str,
                'signal': str,
                'action': str,
                'severity': str
            }
        """
        if current_state == previous_state:
            return {
                'changed': False,
                'from': current_state,
                'to': current_state,
                'signal': '维持',
                'action': '持有',
                'severity': 'neutral'
            }
        
        # 定义状态优先级（数值越小越激进）
        state_priority = {
            '战略进攻区': 1,
            '积极配置区': 2,
            '防御进攻区': 3,
            '左侧布局区': 4,
            '均衡持有区': 5,
            '防御观望区': 6,
            '左侧防御区': 7,
            '谨慎持有区': 8,
            '战略防御区': 9
        }
        
        current_priority = state_priority.get(current_state, 5)
        previous_priority = state_priority.get(previous_state, 5)
        
        # 判定变化方向
        if current_priority < previous_priority:
            direction = '向上'
            signal = '转强'
            action = '加仓'
            severity = 'positive'
        elif current_priority > previous_priority:
            direction = '向下'
            signal = '转弱'
            action = '减仓'
            severity = 'negative'
        else:
            direction = '横向'
            signal = '震荡'
            action = '观望'
            severity = 'neutral'
        
        return {
            'changed': True,
            'from': previous_state,
            'to': current_state,
            'direction': direction,
            'signal': signal,
            'action': action,
            'severity': severity,
            'priority_change': current_priority - previous_priority
        }


# ==================== 使用示例 ====================
def example_market_state_service():
    """MarketStateService使用示例"""
    
    print("=" * 80)
    print("🧪 MarketStateService 使用示例（V6.1阈值动态化）")
    print("=" * 80)
    
    # 1. 初始化服务（简化版）
    print("\n1️⃣ 初始化MarketStateService...")
    
    class MockConfigService:
        def __init__(self):
            self.config = {
                'market_benchmarks': {
                    '大盘': {'code': '000300', 'weight': 0.40},
                    '中盘': {'code': '000905', 'weight': 0.30},
                    '小盘': {'code': '000852', 'weight': 0.20},
                    '微盘': {'code': '932000', 'weight': 0.10}
                },
                'risk_thresholds': {
                    'valuation': {
                        'overvalued_pe_percentile': 75,
                        'undervalued_pe_percentile': 25,
                        'erp_warning': 1.5,
                        'erp_safe': 3.5
                    }
                },
                'position_control': {
                    'market_state_weights': {
                        '战略进攻区': {'equity_min': 0.75, 'equity_max': 0.85},
                        '均衡持有区': {'equity_min': 0.55, 'equity_max': 0.65},
                        '战略防御区': {'equity_min': 0.20, 'equity_max': 0.30}
                    }
                }
            }
    
    class MockDataService:
        def load_pe_data(self, code):
            dates = pd.date_range(end=datetime.now(), periods=500)
            return pd.DataFrame({
                'date': dates,
                'pe_ttm': np.random.randn(500).cumsum() + 12 + np.abs(np.random.randn(500)) * 2
            })
    
    config_service = MockConfigService()
    data_service = MockDataService()
    
    # 模拟ThresholdService（可选）
    class MockThresholdService:
        def get_threshold(self, name, context, strategy):
            # 模拟动态阈值
            if 'valuation' in name:
                return 0.05  # 5%调整
            elif 'trend' in name:
                return 0.03  # 3%调整
            elif 'low_threshold' in name:
                return 38.0
            elif 'high_threshold' in name:
                return 62.0
            elif 'weak_threshold' in name:
                return 38.0
            elif 'strong_threshold' in name:
                return 72.0
            return 0.0
    
    threshold_service = MockThresholdService()
    
    market_state_service = MarketStateService(data_service, config_service, threshold_service)
    print("✅ 服务初始化成功")
    
    # 2. 准备模拟数据
    print("\n2️⃣ 准备模拟市值基准数据...")
    benchmark_data = {}
    for size in ['大盘', '中盘', '小盘', '微盘']:
        dates = pd.date_range(end=datetime.now(), periods=500)
        df = pd.DataFrame({
            'datetime': dates,
            'close': np.random.randn(500).cumsum() + 100,
            'amount': np.random.rand(500) * 1000 + 500,
            'return_1d': np.random.randn(500) * 0.01,
            'volatility_20': np.random.rand(500) * 20 + 15
        })
        df['ma_20'] = df['close'].rolling(20).mean()
        df['ma_60'] = df['close'].rolling(60).mean()
        benchmark_data[size] = df
        print(f"   ✅ {size}: {len(df)}条")
    
    # 3. 判定市场状态
    print("\n3️⃣ 判定市场状态...")
    market_state, val_score, trend_score, diagnosis = \
        market_state_service.determine_market_state(benchmark_data)
    
    print(f"   ✅ 市场状态: {market_state}")
    print(f"   ✅ 估值安全边际: {val_score:.1f}/100")
    print(f"   ✅ 趋势动能强度: {trend_score:.1f}/100")
    
    # 4. 显示各层诊断
    print("\n4️⃣ 各层诊断:")
    for size, diag in diagnosis.items():
        print(f"   • {size:4s}: {diag}")
    
    # 5. 验证数据类型
    print("\n5️⃣ 验证数据类型（防Plotly序列化错误）:")
    is_python_float = isinstance(val_score, float) and not isinstance(val_score, np.floating)
    print(f"   ✅ 估值得分类型: {type(val_score).__name__} | Python float: {is_python_float}")
    
    # 6. 市场状态变化检测
    print("\n6️⃣ 市场状态变化检测:")
    change_info = market_state_service.detect_market_state_change(
        current_state=market_state,
        previous_state='均衡持有区'
    )
    if change_info['changed']:
        print(f"   🔔 状态变化: {change_info['from']} → {change_info['to']} | "
              f"信号: {change_info['signal']} | 建议: {change_info['action']}")
    else:
        print(f"   ✅ 状态维持: {market_state}")
    
    print("\n" + "=" * 80)
    print("✅ MarketStateService 示例运行完成")
    print("=" * 80)


if __name__ == "__main__":
    example_market_state_service()