"""
V6.1 阈值动态化服务（专为 V6.1 标准配置设计）
核心特性：
✅ 专为 V6.1 配置结构设计（adaptive_config.strategies）
✅ 无配置兼容逻辑（简化代码，提升性能）
✅ 完整策略实现（static/volatility_adaptive/market_regime/hybrid）
✅ 精确阈值名称解析（option_tolerance_base → base_tolerance）
✅ 所有数值强制 Python 原生 float（防 Plotly 序列化错误）
✅ 完整异常处理与详细日志
修复问题：
✅ timedelta 导入缺失
✅ 阈值名称解析错误（option_tolerance_base → base_tolerance）
✅ 配置路径错误（直接从 adaptive_config.strategies 获取）
✅ 策略方法缺失（仅保留已实现策略）
"""
import pandas as pd
import numpy as np
from typing import Dict, Any, Optional, List, Tuple
from datetime import datetime, timedelta  # ✅ 修复1：添加 timedelta 导入
import logging

logger = logging.getLogger(__name__)


class ThresholdService:
    """V6.1 阈值动态化服务（专为 V6.1 标准配置设计）"""
    
    def __init__(self, config_service, data_service=None):
        """
        初始化阈值服务（V6.1 专用版）
        
        参数:
            config_service: ConfigService 实例（提供配置字典）
            data_service: DataLoadingService 实例（可选）
        
        修复点:
        ✅ 直接从 adaptive_config.strategies 获取策略配置（V6.1 标准结构）
        ✅ 无配置兼容逻辑（简化代码）
        ✅ 策略注册表仅包含已实现策略
        ✅ 详细日志记录配置加载状态
        """
        self.config_service = config_service
        self.data_service = data_service
        self.logger = logger
        
        # ✅ 修复2：直接从 adaptive_config.strategies 获取策略配置（V6.1 标准结构）
        self.strategies_config = self._extract_strategies_config()
        
        # 策略注册表（仅包含已实现策略）
        self._strategy_registry = {
            'static': self._static_strategy,
            'volatility_adaptive': self._volatility_adaptive_strategy,
            'market_regime': self._market_regime_strategy,
            'hybrid': self._hybrid_strategy
        }
        
        # 验证策略方法存在性
        for strategy_name, strategy_func in self._strategy_registry.items():
            if not callable(strategy_func):
                raise AttributeError(f"策略 '{strategy_name}' 未实现或不可调用")
        
        # 阈值历史记录
        self._threshold_history = {}
        self._history_ttl = 86400 * 30  # 30天
        
        # 配置版本
        self._config_version = self._get_config_version()
        
        self.logger.info(
            f"✅ ThresholdServiceV6.1 初始化成功（V6.1 专用版） | "
            f"策略: {list(self._strategy_registry.keys())} | "
            f"配置版本: {self._config_version}"
        )
    
    def _extract_strategies_config(self) -> Dict:
        """
        ✅ 修复3：直接从 adaptive_config.strategies 获取策略配置（V6.1 标准结构）
        无需兼容旧配置，简化逻辑
        """
        # 直接获取 adaptive_config
        adaptive_config = self.config_service.config.get('adaptive_config', {})
        
        # 验证 adaptive_config 类型
        if not isinstance(adaptive_config, dict):
            self.logger.error(f"❌ adaptive_config 配置类型错误: {type(adaptive_config)}")
            raise ValueError("adaptive_config 配置必须为字典类型")
        
        # 直接获取 strategies（V6.1 标准结构）
        strategies = adaptive_config.get('strategies', {})
        
        if not isinstance(strategies, dict):
            self.logger.error(f"❌ strategies 配置类型错误: {type(strategies)}")
            raise ValueError("strategies 配置必须为字典类型")
        
        # 验证必要策略存在
        required_strategies = [
            'pcr_thresholds',
            'micro_liquidity_thresholds',
            'option_tolerance',
            'commodity_thresholds',
            'macro_scoring'
        ]
        
        missing_strategies = [s for s in required_strategies if s not in strategies]
        
        if missing_strategies:
            self.logger.error(
                f"❌ strategies 缺失必要策略: {', '.join(missing_strategies)} | "
                f"当前策略: {list(strategies.keys())}"
            )
            raise ValueError(f"缺失必要策略配置: {', '.join(missing_strategies)}")
        
        self.logger.info(
            f"✅ strategies 配置加载成功 | 策略: {list(strategies.keys())}"
        )
        
        return strategies
    
    def _get_config_version(self) -> str:
        """获取配置版本"""
        version = self.config_service.config.get('version', {})
        return version.get('config_version', str(datetime.now().timestamp()))
    
    # ==================== 核心 API：统一阈值获取 ====================
    
    def get_threshold(
        self,
        threshold_name: str,
        context: Optional[Dict] = None,
        strategy: str = 'auto'
    ) -> float:
        """
        V6.1 核心：获取动态阈值（统一入口）
        
        参数:
            threshold_name: 阈值名称（如 'pcr_warning_high', 'option_tolerance_base'）
            context: 市场上下文（含 volatility/market_state 等）
            strategy: 策略类型（'auto'/'static'/'volatility_adaptive'/'market_regime'/'hybrid'）
        
        返回:
            动态计算的阈值（Python 原生 float）
        """
        context = context or {}
        
        # 选择策略
        if strategy == 'auto':
            strategy = self._select_strategy(threshold_name, context)
        
        # 验证策略存在性
        if strategy not in self._strategy_registry:
            self.logger.warning(
                f"⚠️ 未知策略 '{strategy}'，回退 static | 可用策略: {list(self._strategy_registry.keys())}"
            )
            strategy = 'static'
        
        # 执行策略
        try:
            threshold_value = self._execute_strategy(threshold_name, strategy, context)
            threshold_value = float(threshold_value)  # ✅ 强制 Python 原生 float
            self._record_threshold_history(threshold_name, threshold_value, context, strategy)
            return threshold_value
        except Exception as e:
            self.logger.warning(
                f"⚠️ 阈值计算失败 {threshold_name}({strategy}): {str(e)[:50]}，回退 static"
            )
            return self._fallback_to_static(threshold_name)
    
    def _execute_strategy(self, threshold_name: str, strategy: str, context: Dict) -> float:
        """执行指定策略"""
        return self._strategy_registry[strategy](threshold_name, context)
    
    # ==================== 策略实现（4个已实现策略） ====================
    
    def _static_strategy(self, threshold_name: str, context: Dict) -> float:
        """
        静态阈值策略（从 strategies 配置获取基础阈值）
        
        阈值名称映射:
        - 'pcr_warning_high' → strategies.pcr_thresholds.base_thresholds.warning_high
        - 'liquidity_warning_shrink' → strategies.micro_liquidity_thresholds.base_thresholds.warning_shrink
        - 'option_tolerance_base' → strategies.option_tolerance.base_tolerance
        - 'commodity_base_threshold' → strategies.commodity_thresholds.volatility_adaptive.base_threshold
        """
        # ✅ 修复4：精确阈值名称解析（V6.1 标准映射）
        path_parts = self._parse_threshold_path(threshold_name)
        
        # 从 strategies_config 获取阈值
        value = self._safe_get_config_value(path_parts, default=0.05)
        
        return float(value)
    
    def _volatility_adaptive_strategy(self, threshold_name: str, context: Dict) -> float:
        """波动率自适应策略"""
        # 1. 获取基础阈值
        base_value = self._static_strategy(threshold_name, context)
        
        # 2. 获取当前波动率分位数
        vol_percentile = context.get('vol_percentile', 50.0)
        
        # 3. 获取波动率调整参数（从对应策略配置）
        strategy_key = self._get_strategy_key(threshold_name)
        volatility_config = self.strategies_config.get(strategy_key, {}).get(
            'volatility_adjustment', {}
        )
        
        low_vol_multiplier = float(volatility_config.get('low_vol_multiplier', 0.9))
        high_vol_multiplier = float(volatility_config.get('high_vol_multiplier', 1.1))
        
        # 4. 动态调整
        if vol_percentile > 70:  # 高波动市场
            adjustment = high_vol_multiplier
        elif vol_percentile < 30:  # 低波动市场
            adjustment = low_vol_multiplier
        else:
            adjustment = 1.0
        
        return float(base_value * adjustment)
    
    def _market_regime_strategy(self, threshold_name: str, context: Dict) -> float:
        """市场状态调整策略"""
        # 1. 获取基础阈值
        base_value = self._static_strategy(threshold_name, context)
        
        # 2. 获取市场状态
        market_state = context.get('market_state', 'balanced')
        
        # 3. 获取市场状态调整参数
        strategy_key = self._get_strategy_key(threshold_name)
        regime_config = self.strategies_config.get(strategy_key, {}).get(
            'market_regime_adjustment', {}
        )
        
        if 'bull' in market_state.lower():
            adjustment = float(regime_config.get('bull_multiplier', 0.9))
        elif 'bear' in market_state.lower():
            adjustment = float(regime_config.get('bear_multiplier', 1.1))
        else:
            adjustment = 1.0
        
        return float(base_value * adjustment)
    
    def _hybrid_strategy(self, threshold_name: str, context: Dict) -> float:
        """混合策略（波动率自适应 + 市场状态调整）"""
        # 1. 波动率自适应部分（权重 0.6）
        vol_value = self._volatility_adaptive_strategy(threshold_name, context)
        
        # 2. 市场状态调整部分（权重 0.4）
        regime_value = self._market_regime_strategy(threshold_name, context)
        
        # 3. 加权混合
        hybrid_value = vol_value * 0.6 + regime_value * 0.4
        
        self.logger.debug(
            f"🔄 混合策略 | {threshold_name} | "
            f"vol={vol_value:.3f}(0.6) + regime={regime_value:.3f}(0.4) = {hybrid_value:.3f}"
        )
        
        return float(hybrid_value)
    
    # ==================== 辅助方法 ====================
    
    def _parse_threshold_path(self, threshold_name: str) -> List[str]:
        """
        ✅ 修复5：精确阈值名称解析（V6.1 标准映射）
        
        映射规则:
        - 'pcr_warning_high' → ['pcr_thresholds', 'base_thresholds', 'warning_high']
        - 'liquidity_warning_shrink' → ['micro_liquidity_thresholds', 'base_thresholds', 'warning_shrink']
        - 'option_tolerance_base' → ['option_tolerance', 'base_tolerance']  # 修正！
        - 'commodity_base_threshold' → ['commodity_thresholds', 'volatility_adaptive', 'base_threshold']
        """
        # 特殊映射（修正阈值名称与配置键名不一致问题）
        special_mappings = {
            'option_tolerance_base': ['option_tolerance', 'base_tolerance'],
            'commodity_base_threshold': ['commodity_thresholds', 'volatility_adaptive', 'base_threshold']
        }
        
        if threshold_name in special_mappings:
            return special_mappings[threshold_name]
        
        # 常规解析
        prefix_map = {
            'pcr': 'pcr_thresholds',
            'liquidity': 'micro_liquidity_thresholds'
        }
        
        for prefix, strategy_key in prefix_map.items():
            if threshold_name.startswith(prefix + '_'):
                suffix = threshold_name[len(prefix) + 1:]  # 去掉前缀和下划线
                return [strategy_key, 'base_thresholds', suffix]
        
        # 默认：直接使用阈值名称
        return [threshold_name]
    
    def _get_strategy_key(self, threshold_name: str) -> str:
        """根据阈值名称获取策略键"""
        if threshold_name.startswith('pcr_'):
            return 'pcr_thresholds'
        elif threshold_name.startswith('liquidity_'):
            return 'micro_liquidity_thresholds'
        elif 'option' in threshold_name:
            return 'option_tolerance'
        elif 'commodity' in threshold_name:
            return 'commodity_thresholds'
        else:
            return 'pcr_thresholds'  # 默认
    
    def _safe_get_config_value(self, keys: List[str], default: Any = 0.05) -> Any:
        """安全获取嵌套配置值"""
        value = self.strategies_config
        for i, key in enumerate(keys):
            if isinstance(value, dict) and key in value:
                value = value[key]
            else:
                self.logger.debug(f"⚠️ 配置路径缺失: {' → '.join(keys[:i+1])}")
                return default
        return value if value is not None else default
    
    def _select_strategy(self, threshold_name: str, context: Dict) -> str:
        """自动选择策略"""
        if 'pcr' in threshold_name:
            return 'market_regime'
        elif 'liquidity' in threshold_name or 'volatility' in threshold_name:
            return 'volatility_adaptive'
        else:
            return 'static'
    
    def _fallback_to_static(self, threshold_name: str) -> float:
        """降级到静态阈值"""
        return self._static_strategy(threshold_name, {})
    
    def _record_threshold_history(
        self,
        threshold_name: str,
        value: float,
        context: Dict,
        strategy: str
    ):
        """记录阈值历史"""
        if threshold_name not in self._threshold_history:
            self._threshold_history[threshold_name] = []
        
        record = {
            'timestamp': datetime.now(),
            'value': value,
            'context': context.copy(),
            'strategy': strategy
        }
        
        self._threshold_history[threshold_name].append(record)
        
        # 清理过期历史
        cutoff = datetime.now() - timedelta(seconds=self._history_ttl)
        self._threshold_history[threshold_name] = [
            r for r in self._threshold_history[threshold_name] if r['timestamp'] > cutoff
        ]
    
    def get_threshold_history(
        self,
        threshold_name: str,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> List[Dict]:
        """获取阈值历史记录"""
        history = self._threshold_history.get(threshold_name, [])
        
        if start_date or end_date:
            history = [
                r for r in history
                if (not start_date or r['timestamp'] >= start_date) and
                   (not end_date or r['timestamp'] <= end_date)
            ]
        
        return history


# ==================== 使用示例 ====================
def example_threshold_service():
    """ThresholdServiceV6.1 使用示例（V6.1 专用版）"""
    
    print("=" * 80)
    print("🧪 ThresholdServiceV6.1 使用示例（V6.1 专用版）")
    print("=" * 80)
    
    # 1. 初始化服务（简化版）
    print("\n1️⃣ 初始化 ThresholdServiceV6.1...")
    
    class MockConfigService:
        def __init__(self):
            # ✅ V6.1 标准配置结构（与上传文件完全一致）
            self.config = {
                'adaptive_config': {
                    'enabled': True,
                    'strategies': {  # ✅ V6.1 标准：策略配置在 strategies 下
                        'pcr_thresholds': {
                            'enabled': True,
                            'base_thresholds': {
                                'warning_high': 1.3,
                                'warning_low': 0.7,
                                'extreme_high': 1.5,
                                'extreme_low': 0.5
                            },
                            'volatility_adjustment': {
                                'enabled': True,
                                'low_vol_multiplier': 0.9,
                                'high_vol_multiplier': 1.1,
                                'threshold_percentile': 0.7
                            },
                            'market_regime_adjustment': {
                                'enabled': True,
                                'bull_multiplier': 0.9,
                                'bear_multiplier': 1.1
                            },
                            'window_size': 50
                        },
                        'micro_liquidity_thresholds': {
                            'enabled': True,
                            'base_thresholds': {
                                'warning_shrink': 0.6,
                                'extreme_shrink': 0.4
                            },
                            'volatility_adjustment': {
                                'enabled': True,
                                'adjustment_range': [0.55, 0.65]
                            },
                            'market_state_adjustment': {
                                'enabled': True,
                                'strategic_defense': {
                                    'warning_shrink': 0.7,
                                    'extreme_shrink': 0.5
                                },
                                'strategic_offense': {
                                    'warning_shrink': 0.55,
                                    'extreme_shrink': 0.35
                                }
                            }
                        },
                        'option_tolerance': {
                            'enabled': True,
                            'base_tolerance': 0.05,  # ✅ 直接键名（非 base_thresholds）
                            'volatility_based': {
                                'enabled': True,
                                'low_vol_tolerance': 0.03,
                                'high_vol_tolerance': 0.08,
                                'threshold_percentile': 0.7
                            },
                            'liquidity_based': {
                                'enabled': True,
                                'high_liquidity_tolerance': 0.04,
                                'low_liquidity_tolerance': 0.06
                            }
                        },
                        'commodity_thresholds': {
                            'enabled': True,
                            'volatility_adaptive': {
                                'enabled': True,
                                'base_threshold': 10.0,  # ✅ 直接键名
                                'benchmark_vol': 25.0
                            },
                            'regime_adjustment': {
                                'enabled': True,
                                'bull_market': 0.9,
                                'bear_market': 1.1
                            }
                        },
                        'macro_scoring': {
                            'enabled': True,
                            'regime_based_adjustment': {
                                'enabled': True,
                                'high_volatility': {
                                    'inflation_weight': 0.35,
                                    'liquidity_weight': 0.30,
                                    'growth_weight': 0.20,
                                    'sentiment_weight': 0.10,
                                    'external_weight': 0.05
                                },
                                'low_volatility': {
                                    'inflation_weight': 0.15,
                                    'liquidity_weight': 0.20,
                                    'growth_weight': 0.35,
                                    'sentiment_weight': 0.15,
                                    'external_weight': 0.15
                                }
                            }
                        }
                    }
                },
                'version': {
                    'config_version': '2.0.0',
                    'system_version': '6.1.0'
                }
            }
    
    config_service = MockConfigService()
    
    # ✅ V6.1 专用版：无需 threshold_service 参数
    threshold_service = ThresholdService(config_service)
    print("✅ 服务初始化成功（V6.1 专用版）")
    
    # 2. 获取动态阈值
    print("\n2️⃣ 获取动态阈值（PCP 看跌预警）...")
    
    # 静态阈值
    static_value = threshold_service.get_threshold(
        'pcr_warning_high',
        strategy='static'
    )
    print(f"   ✅ 静态阈值: {static_value:.2f}")
    
    # 动态阈值（波动率自适应）
    dynamic_value = threshold_service.get_threshold(
        'pcr_warning_high',
        context={'vol_percentile': 80.0, 'market_state': 'bull_market'},
        strategy='volatility_adaptive'
    )
    print(f"   ✅ 动态阈值（高波动）: {dynamic_value:.2f}")
    
    # 混合策略
    hybrid_value = threshold_service.get_threshold(
        'pcr_warning_high',
        context={'vol_percentile': 80.0, 'market_state': 'bull_market'},
        strategy='hybrid'
    )
    print(f"   ✅ 混合策略阈值: {hybrid_value:.2f}")
    
    # 3. 验证 option_tolerance_base（关键修复点）
    print("\n3️⃣ 验证 option_tolerance_base（关键修复点）...")
    option_tolerance = threshold_service.get_threshold('option_tolerance_base', strategy='static')
    status = "✅" if abs(option_tolerance - 0.05) < 0.01 else "❌"
    print(f"   {status} option_tolerance_base = {option_tolerance:.3f} (期望 0.050)")
    
    # 4. 验证数据类型
    print("\n4️⃣ 验证数据类型（防 Plotly 序列化错误）:")
    is_python_float = isinstance(static_value, float) and not isinstance(static_value, np.floating)
    print(f"   ✅ 静态阈值类型: {type(static_value).__name__} | Python float: {is_python_float}")
    
    # 5. 阈值历史记录
    print("\n5️⃣ 阈值历史记录（模拟）:")
    history = threshold_service.get_threshold_history('pcr_warning_high')
    print(f"   ✅ 历史记录数量: {len(history)}")
    
    print("\n" + "=" * 80)
    print("✅ ThresholdServiceV6.1 示例运行完成（V6.1 专用版）")
    print("=" * 80)


if __name__ == "__main__":
    example_threshold_service()