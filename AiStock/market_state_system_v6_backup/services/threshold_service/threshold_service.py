# services/threshold_service/threshold_service.py
"""
V6.0 阈值动态化服务（独立微服务）
职责：
✅ 集中管理所有阈值的动态计算逻辑
✅ 提供统一API：get_threshold(name, context)
✅ 支持多策略：静态/波动率自适应/宏观状态调整
✅ 完整缓存与降级策略
✅ 与业务服务完全解耦（仅通过参数传递市场状态）
修复点：
✅ 所有数值强制Python原生类型（防Plotly序列化错误）
✅ 完整异常处理与降级
✅ 详细日志与监控
"""
import pandas as pd
import numpy as np
from typing import Dict, Any, Optional
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class ThresholdService:
    """V6.0 阈值动态化服务（独立微服务）"""
    
    def __init__(self, config_service, data_service=None):
        """
        初始化阈值服务
        
        参数:
            config_service: ConfigService实例（获取阈值配置）
            data_service: DataLoadingService实例（可选，用于动态计算）
        """
        self.config = config_service.config  # 直接使用字典配置
        self.data_service = data_service
        self.logger = logger
        
        # 缓存：阈值名称 → (计算结果, 过期时间)
        self._threshold_cache = {}
        self._cache_ttl = self.config.get('cache', {}).get('threshold_ttl', 300)  # 默认5分钟
        
        # 阈值策略注册表
        self._strategy_registry = {
            'static': self._static_strategy,
            'volatility_adaptive': self._volatility_adaptive_strategy,
            'macro_state_adjustment': self._macro_state_adjustment_strategy,
            'market_regime': self._market_regime_strategy
        }
        
        self.logger.info("✅ ThresholdService初始化成功 | 策略: %s", list(self._strategy_registry.keys()))
    
    # ==================== 核心API：统一阈值获取 ====================
    
    def get_threshold(
        self,
        threshold_name: str,
        context: Optional[Dict] = None,
        strategy: str = 'auto'
    ) -> float:
        """
        获取动态阈值（统一入口）
        
        参数:
            threshold_name: 阈值名称（如 'pcr_warning_high', 'liquidity_warning_shrink'）
            context: 市场上下文（含volatility/current_price等）
            strategy: 策略类型（'auto'/'static'/'volatility_adaptive'/...）
        
        返回:
            动态计算的阈值（Python原生float）
        
        示例:
            # 获取PCR看跌预警阈值（自动选择策略）
            pcr_high = threshold_service.get_threshold('pcr_warning_high', context)
            
            # 强制使用静态阈值（回测场景）
            pcr_high = threshold_service.get_threshold('pcr_warning_high', strategy='static')
        """
        context = context or {}
        
        # 1. 尝试从缓存获取（带TTL检查）
        cache_key = self._generate_cache_key(threshold_name, context, strategy)
        cached = self._get_from_cache(cache_key)
        if cached is not None:
            return cached
        
        # 2. 选择策略
        if strategy == 'auto':
            strategy = self._select_strategy(threshold_name, context)
        
        # 3. 执行策略
        try:
            threshold_value = self._execute_strategy(threshold_name, strategy, context)
            
            # 4. 缓存结果（强制Python float）
            threshold_value = float(threshold_value)  # ⭐ 关键修复
            self._set_to_cache(cache_key, threshold_value)
            
            self.logger.debug(
                f"✅ 阈值计算 | {threshold_name} | 策略={strategy} | 值={threshold_value:.3f}"
            )
            return threshold_value
            
        except Exception as e:
            self.logger.warning(
                f"⚠️ 阈值计算失败 {threshold_name}({strategy}): {str(e)[:50]}，回退静态值"
            )
            # 降级：回退静态阈值
            return self._fallback_to_static(threshold_name)
    
    # ==================== 策略实现 ====================
    
    def _static_strategy(self, threshold_name: str, context: Dict) -> float:
        """静态阈值策略（从配置读取）"""
        # 从配置中查找阈值（支持嵌套路径）
        value = self._safe_get_config_value(
            ['risk_thresholds', threshold_name.replace('_', '.')],
            default=0.5
        )
        return float(value)
    
    def _volatility_adaptive_strategy(self, threshold_name: str, context: Dict) -> float:
        """波动率自适应策略"""
        # 获取基础阈值
        base_value = self._static_strategy(threshold_name, context)
        
        # 获取当前波动率（从context或计算）
        current_vol = context.get('volatility', 20.0)
        vol_percentile = context.get('vol_percentile', 50.0)
        
        # 波动率调整逻辑
        if vol_percentile > 70:  # 高波动市场
            adjustment = self.config.get('adaptive_config', {}).get(
                'volatility_adjustment', {}
            ).get('high_vol_multiplier', 1.1)
        elif vol_percentile < 30:  # 低波动市场
            adjustment = self.config.get('adaptive_config', {}).get(
                'volatility_adjustment', {}
            ).get('low_vol_multiplier', 0.9)
        else:
            adjustment = 1.0
        
        return float(base_value * adjustment)
    
    def _market_regime_strategy(self, threshold_name: str, context: Dict) -> float:
        """市场状态调整策略"""
        base_value = self._static_strategy(threshold_name, context)
        market_state = context.get('market_state', '均衡持有区')
        
        # 市场状态映射
        regime_map = {
            '战略进攻区': 0.9,
            '积极配置区': 0.95,
            '防御进攻区': 1.0,
            '左侧布局区': 1.0,
            '均衡持有区': 1.0,
            '防御观望区': 1.05,
            '左侧防御区': 1.1,
            '谨慎持有区': 1.15,
            '战略防御区': 1.2
        }
        
        adjustment = regime_map.get(market_state, 1.0)
        return float(base_value * adjustment)
    
    # ==================== 辅助方法 ====================
    
    def _generate_cache_key(self, threshold_name: str, context: Dict, strategy: str) -> str:
        """生成缓存键（包含日期维度防跨日污染）"""
        today = datetime.now().strftime('%Y%m%d')
        vol_key = f"vol_{context.get('volatility', 0):.1f}"
        state_key = f"state_{context.get('market_state', 'unknown')}"
        return f"threshold_{threshold_name}_{strategy}_{vol_key}_{state_key}_{today}"
    
    def _get_from_cache(self, key: str) -> Optional[float]:
        """从缓存获取（带TTL检查）"""
        if key in self._threshold_cache:
            value, timestamp = self._threshold_cache[key]
            if (datetime.now() - timestamp).total_seconds() < self._cache_ttl:
                return value
            del self._threshold_cache[key]
        return None
    
    def _set_to_cache(self, key: str, value: float):
        """设置缓存"""
        self._threshold_cache[key] = (value, datetime.now())
    
    def _safe_get_config_value(self, keys: list, default: Any = None) -> Any:
        """安全获取嵌套配置值"""
        value = self.config
        for key in keys:
            if isinstance(value, dict) and key in value:
                value = value[key]
            else:
                return default
        return value if value is not None else default
    
    def _select_strategy(self, threshold_name: str, context: Dict) -> str:
        """自动选择策略"""
        # 根据阈值类型选择策略
        if 'pcr' in threshold_name:
            return 'market_regime'
        elif 'liquidity' in threshold_name or 'volatility' in threshold_name:
            return 'volatility_adaptive'
        else:
            return 'static'
    
    def _execute_strategy(self, threshold_name: str, strategy: str, context: Dict) -> float:
        """执行指定策略"""
        if strategy in self._strategy_registry:
            return self._strategy_registry[strategy](threshold_name, context)
        else:
            self.logger.warning(f"⚠️ 未知策略 {strategy}，回退静态策略")
            return self._static_strategy(threshold_name, context)
    
    def _fallback_to_static(self, threshold_name: str) -> float:
        """降级到静态阈值"""
        return self._static_strategy(threshold_name, {})
    
    # ==================== 高级功能 ====================
    
    def get_threshold_range(self, threshold_name: str, context: Dict) -> Dict[str, float]:
        """
        获取阈值范围（用于可视化）
        返回: {'min': float, 'base': float, 'max': float}
        """
        base = self.get_threshold(threshold_name, context, strategy='static')
        min_val = base * 0.8
        max_val = base * 1.2
        return {'min': float(min_val), 'base': float(base), 'max': float(max_val)}
    
    def invalidate_cache(self, prefix: Optional[str] = None):
        """清空缓存（指定前缀或全部）"""
        if prefix:
            keys_to_remove = [k for k in self._threshold_cache if k.startswith(prefix)]
            for key in keys_to_remove:
                del self._threshold_cache[key]
            self.logger.info(f"✅ 清空缓存 {len(keys_to_remove)} 项 | 前缀={prefix}")
        else:
            count = len(self._threshold_cache)
            self._threshold_cache.clear()
            self.logger.info(f"✅ 清空全部缓存 {count} 项")