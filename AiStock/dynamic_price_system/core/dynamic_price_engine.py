#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
V6.2 DynamicPriceEngine：三维动态价格计算引擎
功能：
  - 整合技术面/基本面/宏观面计算器
  - 应用 40/35/25 三维权重融合逻辑
  - 参数校验 + 数据充分性检查 + 降级策略
  - 批量计算 + 原生类型转换（防序列化报错）
  - 结构化日志 + 生产级异常处理
"""

import logging
import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime
from copy import deepcopy

from base_services.config_service import ConfigService
from base_services.cache_service import CacheService
from dynamic_price_system.core.technical_calculator import TechnicalCalculator
from dynamic_price_system.core.fundamental_calculator import FundamentalCalculator
from dynamic_price_system.core.macro_calculator import MacroCalculator
from dynamic_price_system.core.price_validator import PriceValidator

logger = logging.getLogger(__name__)


class DynamicPriceEngine:
    """三维动态价格计算引擎"""
    
    # 默认三维权重配置
    DEFAULT_WEIGHTS = {
        'technical': 0.40,
        'fundamental': 0.35,
        'macro': 0.25
    }
    
    # 数据充分性阈值
    MIN_TRADING_DAYS = 60
    MIN_FUNDAMENTAL_SCORE = 50
    
    def __init__(
        self,
        config_service: Optional[Any] = None,
        weights: Optional[Dict[str, float]] = None,
        cache_service: Optional[CacheService] = None,
        logger_instance: Optional[logging.Logger] = None
    ):
        """
        初始化计算引擎
        
        参数:
            config_service: 配置服务实例（用于读取全局参数）
            weights: 三维权重字典（默认 40/35/25）
            logger_instance: 自定义日志器
        """
        self.config = config_service
        self.cache = cache_service
        self.weights = self._validate_weights(self.config.get('weights', {}) or self.DEFAULT_WEIGHTS)
        # self.weights = self._validate_weights(weights or self.DEFAULT_WEIGHTS)
        self.logger = logger_instance or logger
        
        # 缓存计算器实例（避免重复初始化开销）
        self._calc_cache = {}
        
        self.logger.info(
            f"✅ DynamicPriceEngine 初始化成功 | "
            f"权重={self.weights} | 最小交易日={self.MIN_TRADING_DAYS}"
        )
    
    def _validate_weights(self, weights: Dict[str, float]) -> Dict[str, float]:
        """校验并归一化权重"""
        valid_keys = {'technical', 'fundamental', 'macro'}
        if not all(k in valid_keys for k in weights):
            raise ValueError(f"权重键必须包含: {valid_keys}")
        
        total = sum(weights.values())
        if abs(total - 1.0) > 1e-6:
            self.logger.warning(f"⚠️ 权重总和 {total} != 1.0，自动归一化")
            weights = {k: v/total for k, v in weights.items()}
            
        return weights
    
    def _convert_to_native(self, obj: Any) -> Any:
        """递归转换 numpy/pandas 类型为 Python 原生类型（防 JSON 序列化报错）"""
        if isinstance(obj, dict):
            return {k: self._convert_to_native(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [self._convert_to_native(v) for v in obj]
        elif isinstance(obj, (np.integer,)):
            return int(obj)
        elif isinstance(obj, (np.floating,)):
            return float(obj)
        elif isinstance(obj, np.ndarray):
            return obj.tolist()
        elif isinstance(obj, pd.Timestamp):
            return obj.isoformat()
        elif pd.isna(obj):
            return None
        return obj
    
    def _check_data_sufficiency(
        self, 
        stock_data: pd.DataFrame, 
        financial_data: Dict,
        params: Dict
    ) -> Tuple[bool, str]:
        """检查数据充分性"""
        min_days = params.get('min_trading_days', self.MIN_TRADING_DAYS)
        
        if stock_data is None or stock_data.empty:
            return False, "股票日线数据为空"
        if len(stock_data) < min_days:
            return False, f"交易日不足: {len(stock_data)}/{min_days}"
        
        required_cols = {'open', 'high', 'low', 'close', 'volume'}
        missing_cols = required_cols - set(stock_data.columns)
        if missing_cols:
            return False, f"缺失必要列: {missing_cols}"
            
        return True, "数据充分"
    
    def calculate_single(
        self,
        code: str,
        name: str,
        sector: str,
        stock_data: pd.DataFrame,
        financial_data: Dict,
        macro_data: Dict,
        stock_params: Optional[Dict] = None
    ) -> Optional[Dict[str, Any]]:
        """
        计算单只标的动态价格
        
        参数:
            code: 股票代码
            name: 股票名称
            sector: 所属板块
            stock_data: OHLCV DataFrame
            financial_data: 财务指标字典
            macro_data: 宏观指标字典
            stock_params: 标的个性化参数（来自 stocks_config.yaml）
        
        返回:
            结构化计算结果字典，失败返回 None
        """
        params = stock_params or {}
        
        # 1. 数据充分性检查
        is_sufficient, msg = self._check_data_sufficiency(stock_data, financial_data, params)
        if not is_sufficient:
            self.logger.warning(f"⚠️ {code} 数据检查失败: {msg}")
            return None
            
        try:
            # 2. 技术面计算（基准价格生成）
            tech_calc = TechnicalCalculator(stock_data, params=params)
            tech_signals = tech_calc.get_all_signals()
            
            if tech_signals.get('status') != 'valid':
                self.logger.warning(f"⚠️ {code} 技术面信号无效: {tech_signals.get('status')}")
                return None
                
            base_entry = tech_signals['entry_price']
            base_stop = tech_signals['stop_loss']
            base_target = tech_signals['target_price']
            
            # 3. 基本面计算（评分与调整因子）
            fin_calc = FundamentalCalculator(financial_data, params=params)
            fin_score = fin_calc.get_score()
            fin_factor = fin_calc.get_adjustment_factor(fin_score)
            
            min_score = params.get('min_fundamental_score', self.MIN_FUNDAMENTAL_SCORE)
            if fin_score < min_score:
                self.logger.info(f"📉 {code} 基本面评分 {fin_score} < 阈值 {min_score}，启用降权")
            
            # 4. 宏观面计算（联动调整因子）
            macro_calc = MacroCalculator(
                macro_data, 
                sector=sector, 
                params=params,
                config_macros=getattr(self.config, 'config', {}).get('macro_indicators', {}) if self.config else {}
            )
            macro_factor = macro_calc.get_adjustment_factor()
            
            # 5. 三维权重融合（复合调整因子）
            # 逻辑：技术面定基准，基本面/宏观面提供偏离中性的调整幅度，按权重加权
            w_fin = self.weights['fundamental']
            w_macro = self.weights['macro']
            
            # 将因子转换为相对于 1.0 的偏离度，加权后再转回因子
            fin_dev = fin_factor - 1.0
            macro_dev = macro_factor - 1.0
            composite_dev = (fin_dev * w_fin + macro_dev * w_macro) / (w_fin + w_macro)
            composite_factor = 1.0 + composite_dev
            
            # 6. 应用复合因子调整目标价与入场价（止损价保持技术面刚性）
            final_entry = round(base_entry * composite_factor, 2)
            final_target = round(base_target * composite_factor, 2)
            final_stop = base_stop  # 止损不随宏观/基本面浮动，保持纪律
            
            # 7. 盈亏比计算
            risk = final_entry - final_stop
            reward = final_target - final_entry
            pl_ratio = round(reward / risk, 2) if risk > 0 else 0.0
            
            # 8. 投资建议生成
            recommendation = self._make_recommendation(
                pl_ratio=pl_ratio,
                fin_score=fin_score,
                macro_factor=macro_factor,
                trend=tech_signals.get('trend', 'unknown')
            )
            
            # 9. 组装结果（确保原生类型）
            result = {
                'code': code,
                'name': name,
                'sector': sector,
                'calc_time': datetime.now().isoformat(),
                'prices': {
                    'current': round(float(stock_data['close'].iloc[-1]), 2),
                    'entry': final_entry,
                    'stop_loss': final_stop,
                    'target': final_target
                },
                'factors': {
                    'technical': 1.0,
                    'fundamental': round(fin_factor, 3),
                    'macro': round(macro_factor, 3),
                    'composite': round(composite_factor, 3)
                },
                'scores': {
                    'fundamental': fin_score,
                    'pl_ratio': pl_ratio
                },
                'signals': {
                    'trend': tech_signals.get('trend'),
                    'rsi_zone': tech_signals.get('rsi_zone')
                },
                'recommendation': recommendation,
                'params_used': {
                    'stop_loss_atr_mult': params.get('stop_loss_atr_mult', 3.0),
                    'entry_ma_period': params.get('entry_ma_period', 20),
                    'macro_sensitivity': params.get('macro_sensitivity', 1.0)
                }
            }
            
            return self._convert_to_native(result)
            
        except Exception as e:
            self.logger.error(f"❌ {code} 动态价格计算失败: {e}", exc_info=True)
            return None
    
    def calculate_batch(
        self,
        stock_list: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        批量计算动态价格
        
        参数:
            stock_list: 字典列表，每项需包含 code, sector, stock_data, financial_data, macro_data, params
        
        返回:
            成功计算的结果列表
        """
        results = []
        self.logger.info(f"🚀 开始批量计算: {len(stock_list)} 只标的")
        
        for i, stock in enumerate(stock_list):
            try:
                res = self.calculate_single(
                    code=stock['code'],
                    name=stock.get('name', '未知'),
                    sector=stock.get('sector', '未知'),
                    stock_data=stock['stock_data'],
                    financial_data=stock.get('financial_data', {}),
                    macro_data=stock.get('macro_data', {}),
                    stock_params=stock.get('params', {})
                )
                if res:
                    results.append(res)
                    
                # 进度日志（每 10 只或最后一只）
                if (i + 1) % 10 == 0 or i == len(stock_list) - 1:
                    self.logger.info(f"📊 批量进度: {i+1}/{len(stock_list)} | 成功: {len(results)}")
                    
            except Exception as e:
                self.logger.error(f"❌ 批量计算中 {stock.get('code', 'unknown')} 异常: {e}")
                continue
                
        self.logger.info(f"✅ 批量计算完成 | 成功: {len(results)}/{len(stock_list)}")
        return results
    
    def _make_recommendation(
        self, 
        pl_ratio: float, 
        fin_score: float, 
        macro_factor: float,
        trend: str
    ) -> str:
        """生成投资建议（规则引擎）"""
        if pl_ratio < 1.5 or fin_score < 40:
            return "谨慎"
        if pl_ratio < 2.0 or fin_score < 55:
            return "观望"
        if pl_ratio >= 2.5 and fin_score >= 65 and macro_factor >= 1.02 and trend == 'bullish':
            return "强烈推荐"
        if pl_ratio >= 2.0 and fin_score >= 60:
            return "推荐"
        return "观望"
    
    def update_weights(self, new_weights: Dict[str, float]):
        """运行时动态更新权重"""
        self.weights = self._validate_weights(new_weights)
        self.logger.info(f"🔄 权重已更新: {self.weights}")