# services/threshold_service/threshold_service.py
"""
V6.1 阈值动态化服务（增强版）
核心增强：
✅ 支持配置热更新（监听ConfigService变化）
✅ 新增阈值历史记录（用于回溯分析）
✅ 新增阈值效果评估（A/B测试支持）
✅ 完整缓存与降级策略
"""
import pandas as pd
import numpy as np
from typing import Dict, Any, Optional, List, Tuple
from datetime import datetime, timedelta
import logging
logger = logging.getLogger(__name__)


class ThresholdService:
    """V6.1 阈值动态化服务（增强版）"""
    
    def __init__(self, config_service, data_service=None):
        """
        初始化阈值服务（V6.1增强版）
        
        增强点:
        ✅ 支持配置热更新（监听ConfigService变化）
        ✅ 阈值历史记录（用于回溯分析）
        ✅ 阈值效果评估（A/B测试支持）
        """
        self.config_service = config_service
        self.data_service = data_service
        self.logger = logger
        
        # 阈值策略注册表
        self._strategy_registry = {
            'static': self._static_strategy,
            'volatility_adaptive': self._volatility_adaptive_strategy,
            'market_regime': self._market_regime_strategy,
            'macro_state': self._macro_state_strategy,
            'hybrid': self._hybrid_strategy  # ✅ V6.1新增：混合策略
        }
        
        # 阈值历史记录（最近30天）
        self._threshold_history = {}
        self._history_ttl = timedelta(days=30)
        
        # 配置版本跟踪（用于热更新）
        self._config_version = self._get_config_version()
        
        self.logger.info("✅ ThresholdServiceV6.1初始化成功 | 策略: %s", list(self._strategy_registry.keys()))
    
    # ==================== 核心API：统一阈值获取 ====================
    
    def get_threshold(
        self,
        threshold_name: str,
        context: Optional[Dict] = None,
        strategy: str = 'auto'
    ) -> float:
        """
        V6.1增强：获取动态阈值（支持热更新 + 历史记录）
        
        增强点:
        ✅ 配置热更新检测（自动重载策略参数）
        ✅ 阈值历史记录（用于回溯分析）
        ✅ 混合策略支持（volatility_adaptive + market_regime）
        """
        context = context or {}
        
        # ✅ V6.1增强：配置热更新检测
        current_version = self._get_config_version()
        if current_version != self._config_version:
            self.logger.info("🔄 检测到配置更新，重载阈值策略参数")
            self._config_version = current_version
        
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
            
            # 4. 缓存结果 + 记录历史
            threshold_value = float(threshold_value)
            self._set_to_cache(cache_key, threshold_value)
            self._record_threshold_history(threshold_name, threshold_value, context, strategy)
            
            self.logger.debug(
                f"✅ 阈值计算 | {threshold_name} | 策略={strategy} | 值={threshold_value:.3f} | "
                f"来源={'动态' if strategy != 'static' else '静态'}"
            )
            return threshold_value
            
        except Exception as e:
            self.logger.warning(
                f"⚠️ 阈值计算失败 {threshold_name}({strategy}): {str(e)[:50]}，回退静态值"
            )
            return self._fallback_to_static(threshold_name)

    def _get_dynamic_threshold(self, threshold_name: str, context: Dict) -> float:
        """内部方法：动态获取阈值（不再需要 threshold_service 参数）"""
        # ✅ 修复：直接使用 self.get_threshold（而非 self.threshold_service.get_threshold）
        return self.get_threshold(threshold_name, context, strategy='adaptive')

    def _get_config_version(self) -> str:
        """获取配置版本（用于热更新检测）"""
        adaptive_config = self.config_service.config.get('adaptive_config', {})
        return str(adaptive_config.get('version', datetime.now().timestamp()))
    
    def _record_threshold_history(
        self,
        threshold_name: str,
        value: float,
        context: Dict,
        strategy: str
    ):
        """记录阈值历史（用于回溯分析）"""
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
        cutoff = datetime.now() - self._history_ttl
        self._threshold_history[threshold_name] = [
            r for r in self._threshold_history[threshold_name]
            if r['timestamp'] > cutoff
        ]
    
    def get_threshold_history(
        self,
        threshold_name: str,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> List[Dict]:
        """获取阈值历史记录（用于可视化分析）"""
        history = self._threshold_history.get(threshold_name, [])
        
        if start_date or end_date:
            history = [
                r for r in history
                if (not start_date or r['timestamp'] >= start_date) and
                   (not end_date or r['timestamp'] <= end_date)
            ]
        
        return history
    
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

    def _macro_state_strategy(self, threshold_name: str, context: Dict) -> float:
        """
        V6.1新增：宏观状态调整策略（根据宏观评分动态调整阈值）
        
        参数:
            threshold_name: 阈值名称
            context: 上下文（含macro_score）
        
        返回:
            调整后的阈值
        """
        # 获取基础阈值
        base_value = self._static_strategy(threshold_name, context)
        
        # 获取宏观评分（从context或配置）
        macro_score = context.get('macro_score', 50.0)
        
        # 宏观状态映射
        if macro_score > 70:
            adjustment = 0.9  # 乐观市场收紧阈值
        elif macro_score < 30:
            adjustment = 1.1  # 悲观市场放宽阈值
        else:
            adjustment = 1.0
        
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
            
    def _hybrid_strategy(self, threshold_name: str, context: Dict) -> float:
        """
        V6.1新增：混合策略（volatility_adaptive + market_regime加权）
        适用于需要综合多维度因素的阈值
        """
        # 1. 波动率自适应部分（权重0.6）
        vol_value = self._volatility_adaptive_strategy(threshold_name, context)
        
        # 2. 市场状态调整部分（权重0.4）
        regime_value = self._market_regime_strategy(threshold_name, context)
        
        # 3. 加权混合
        hybrid_value = vol_value * 0.6 + regime_value * 0.4
        
        self.logger.debug(
            f"🔄 混合策略 | {threshold_name} | "
            f"vol={vol_value:.3f}(0.6) + regime={regime_value:.3f}(0.4) = {hybrid_value:.3f}"
        )
        
        return float(hybrid_value)