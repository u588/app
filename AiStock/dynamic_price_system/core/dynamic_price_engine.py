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

from dynamic_price_system.core.technical_confidence import TechnicalConfidence, ConfidenceConfig


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
        
        # 初始化置信度评估器
        conf_config = ConfidenceConfig.from_dict(self.config.get('technical_confidence', {}))
        self.tech_confidence = TechnicalConfidence(conf_config)

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
        # print(stock_data.tail(5))
        required_cols = {'open', 'high', 'low', 'close', 'volume'}
        missing_cols = required_cols - set(stock_data.columns)
        if missing_cols:
            return False, f"缺失必要列: {missing_cols}"
            
        return True, "数据充分"

    def _calculate_technical_confidence(
        self, 
        indicators: Dict, 
        stock_data: pd.DataFrame
    ) -> float:
        """
        计算技术面置信度因子 (0.98~1.02)
        
        返回:
            float: 技术面调整因子，1.0=中性，>1.0=增强信心，<1.0=谨慎
        """
        score = 0.0
        
        # 1. 数据质量 (40%)
        if len(stock_data) >= 250:
            score += 0.40
        elif len(stock_data) >= 120:
            score += 0.30
        elif len(stock_data) >= 60:
            score += 0.20
        # <60 天已在 _check_data_sufficiency 拦截
        
        # 2. 指标一致性 (35%)
        consistency_checks = []
        
        # MA 排列
        ma_short = indicators.get('ma_short', 0)
        ma_long = indicators.get('ma_long', 0)
        if ma_short > ma_long * 1.02:  # 多头排列
            consistency_checks.append(1.0)
        elif ma_short < ma_long * 0.98:  # 空头排列
            consistency_checks.append(1.0)  # 空头也是明确信号
        else:
            consistency_checks.append(0.5)  # 粘合=不确定
        
        # RSI 与价格背离检测
        rsi14 = indicators.get('rsi14', 50)
        price_trend = (stock_data['close'].iloc[-1] - stock_data['close'].iloc[-20]) / stock_data['close'].iloc[-20]
        rsi_trend = (rsi14 - 50) / 50  # 简化：50 为中性
        if price_trend * rsi_trend > 0:  # 同向=一致
            consistency_checks.append(1.0)
        else:
            consistency_checks.append(0.6)  # 背离=谨慎
        
        # 量能确认
        volume_ratio = indicators.get('volume', 0) / indicators.get('vol_20d_avg', 1)
        if volume_ratio > 1.2 or volume_ratio < 0.8:  # 显著放量/缩量
            consistency_checks.append(1.0)
        else:
            consistency_checks.append(0.8)  # 量能平淡=中性
        
        score += 0.35 * (sum(consistency_checks) / len(consistency_checks))
        
        # 3. 信号强度 (25%)
        strength_score = 0.0
        
        # 突破强度：现价距均线距离
        if ma_short > 0:
            breakout = abs(indicators.get('close', ma_short) - ma_short) / ma_short
            strength_score += min(breakout / 0.03, 1.0) * 0.5  # 3% 突破=满分
        
        # 波动率适中：ATR/价格比在 2-5% 为理想
        atr_ratio = indicators.get('atr14', 0) / indicators.get('close', 1)
        if 0.02 <= atr_ratio <= 0.05:
            strength_score += 0.5
        elif 0.01 <= atr_ratio < 0.02 or 0.05 < atr_ratio <= 0.08:
            strength_score += 0.3
        
        score += 0.25 * strength_score
        
        # 映射到 0.98~1.02 区间
        # score=0.5 → 1.00, score=1.0 → 1.02, score=0.2 → 0.98
        tech_factor = 0.98 + (score - 0.2) / 0.8 * 0.04
        tech_factor = np.clip(tech_factor, 0.98, 1.02)
        
        return round(tech_factor, 3)
    
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
            # ==================== 2. 技术面计算 + 置信度评估 ====================
            tech_calc = TechnicalCalculator(stock_data, params=params)
            tech_signals = tech_calc.get_all_signals()

            if tech_signals.get('status') != 'valid':
                self.logger.warning(f"⚠️ {code} 技术面信号无效: {tech_signals.get('status')}")
                return None

            # 新增：计算技术面置信度
            tech_conf_result = self.tech_confidence.calculate(
                indicators=tech_signals['indicators'],
                stock_data=stock_data,
                params=params
            )

            base_entry = tech_signals['entry_price']
            base_stop = tech_signals['stop_loss']
            base_target = tech_signals['target_price']
            
            tech_confidence = self._calculate_technical_confidence(tech_signals['indicators'], stock_data)
            
            # 3. 基本面计算（评分与调整因子）
            fin_calc = FundamentalCalculator(financial_data, params=params)
            fin_score = fin_calc.get_score()
            fin_factor = fin_calc.get_adjustment_factor(fin_score)
            
            min_score = params.get('min_fundamental_score', self.MIN_FUNDAMENTAL_SCORE)
            if fin_score < min_score:
                self.logger.info(f"📉 {code} 基本面评分 {fin_score} < 阈值 {min_score}，启用降权")
            # print(fin_calc.get_detailed_breakdown())
            
            # 4. 宏观面计算（联动调整因子）
            macro_config = {}
            if self.config and hasattr(self.config, 'config'):
                # 从 ConfigService 获取完整宏观配置
                macro_config = {
                    'macro_indicators': self.config.config.get('macro_indicators', {}),
                    'sector_macro_link': self.config.config.get('sector_macro_link', {}),
                    'macro_calculation': self.config.config.get('macro_calculation', {})
                }
            macro_calc = MacroCalculator(
                macro_data, 
                sector=sector, 
                params=params,
                config_macros=macro_config,
                logger_instance=self.logger
            )
            macro_factor = macro_calc.get_adjustment_factor()
            
            # 5. 三维权重融合（复合调整因子）
            # 逻辑：技术面定基准，基本面/宏观面提供乘法调整，指数加权融合
            w_tech = self.weights['technical']  # 0.40
            w_fin = self.weights['fundamental']  # 0.35
            w_macro = self.weights['macro']  # 0.25


            # 归一化权重（确保总和=1.0）
            total_w = w_tech + w_fin + w_macro
            w_tech_norm = w_tech / total_w
            w_fin_norm = w_fin / total_w
            w_macro_norm = w_macro / total_w           

            # 指数加权融合（三维都参与）
            composite_factor = (
                (tech_confidence ** w_tech_norm) * 
                (fin_factor ** w_fin_norm) * 
                (macro_factor ** w_macro_norm)
            )

            # 记录融合细节
            self.logger.debug(f"🔗 {code} 因子融合: "
                            f"tech={tech_conf_result.factor:.3f}^{w_tech_norm:.2f} × "
                            f"fin={fin_factor:.3f}^{w_fin_norm:.2f} × "
                            f"macro={macro_factor:.3f}^{w_macro_norm:.2f} = "
                            f"{composite_factor:.3f}")
            
            # 6. 应用复合因子调整目标价与入场价（止损价保持技术面刚性）
            final_entry = round(base_entry * composite_factor, 2)
            final_target = round(base_target * composite_factor, 2)
            final_stop = base_stop  # 止损不随宏观/基本面浮动，保持纪律
            # 止损距离约束
            min_stop_distance = final_entry * 0.05  # 最小 5%
            max_stop_distance = final_entry * 0.15  # 最大 15%
            current_stop_distance = final_entry - final_stop

            if current_stop_distance < min_stop_distance:
                self.logger.debug(f"🛡️ {code} 止损过紧: {current_stop_distance/final_entry:.1%} → {min_stop_distance/final_entry:.1%}")
                final_stop = final_entry - min_stop_distance
            elif current_stop_distance > max_stop_distance:
                self.logger.debug(f"🛡️ {code} 止损过松: {current_stop_distance/final_entry:.1%} → {max_stop_distance/final_entry:.1%}")
                final_stop = final_entry - max_stop_distance
                
            # 7. 盈亏比计算
            risk = final_entry - final_stop
            reward = final_target - final_entry
            pl_ratio = round(reward / risk, 2) if risk > 0 else 0.0
            # 盈亏比约束优化
            if pl_ratio < 2.0:
                self.logger.debug(f"⚠️ {code} 盈亏比 {pl_ratio:.2f}x < 2.0，启动优化")
                
                # 方案 1: 收紧止损（最小 5%）
                new_stop = max(final_stop, final_entry * 0.95)
                new_risk = final_entry - new_stop
                new_pl = reward / new_risk if new_risk > 0 else 0
                
                if new_pl >= 2.0:
                    final_stop = new_stop
                    pl_ratio = new_pl
                    self.logger.debug(f"✅ {code} 通过收紧止损提升盈亏比: {pl_ratio:.2f}x")
                else:
                    # 方案 2: 降低目标（最小 1.5:1）
                    min_reward = new_risk * 1.5
                    new_target = final_entry + min_reward
                    final_target = min(final_target, new_target)  # 只降不升
                    pl_ratio = (final_target - final_entry) / new_risk if new_risk > 0 else 0
                    self.logger.debug(f"⚠️ {code} 优化后盈亏比: {pl_ratio:.2f}x (仍<2.0，建议谨慎)")            
            
            # ==================== 7. 建议仓位计算（凯利 + 风险预算） ====================
            # 胜率估计（基本面评分映射）
            win_rate = 0.50 + (fin_score - 50) / 300  # 50 分→50%, 80 分→60%, 100 分→67%
            win_rate = np.clip(win_rate, 0.40, 0.70)  # 限制在 40-70%

            # 凯利公式: f* = (p×b - q) / b, b=盈亏比, q=1-p
            b = pl_ratio
            p = win_rate
            q = 1 - p
            kelly_fraction = (p * b - q) / b if b > 0 and p * b > q else 0
            kelly_fraction = np.clip(kelly_fraction, 0, 0.25)  # 限制 0-25%

            # 风险预算约束（单笔风险≤组合 1.5%）
            portfolio_value = self.config.get('portfolio.initial_capital', 1_000_000) if self.config else 1_000_000
            max_risk_amount = portfolio_value * 0.015  # 1.5%
            risk_per_share = final_entry - final_stop
            max_shares_by_risk = max_risk_amount / risk_per_share if risk_per_share > 0 else 0

            # 综合建议仓位
            suggested_position = min(
                kelly_fraction * portfolio_value / final_entry,  # 凯利仓位
                max_shares_by_risk  # 风险预算仓位
            )

            # # 置信度评分（数据质量 + 指标一致性 + 盈亏比）
            # confidence = (
            #     0.40 * self._calculate_data_quality(stock_data, financial_data, macro_data) +
            #     0.35 * min(pl_ratio / 3.0, 1.0) +  # 盈亏比贡献
            #     0.25 * win_rate  # 胜率贡献
            # )
            # confidence = np.clip(confidence, 0, 1)

            # 8. 投资建议生成
            recommendation = self._make_recommendation(
                pl_ratio=pl_ratio,
                fin_score=fin_score,
                macro_factor=macro_factor,
                trend=tech_signals.get('trend', 'unknown')
            )
            
            # ==================== 9. 组装增强版结果 ====================
            result = {
                'code': code,
                'name': name,
                'sector': sector,
                'calc_time': datetime.now().isoformat(),
                
                # 价格三元组
                'prices': {
                    'current': round(float(stock_data['close'].iloc[-1]), 2),
                    'entry': final_entry,
                    'stop_loss': final_stop,
                    'target': final_target
                },
                
                # 因子分解（新增）
                'factors': {
                    'technical': tech_conf_result.factor,  # ✅ 不再是硬编码 1.0
                    'fundamental': round(fin_factor, 3),
                    'macro': round(macro_factor, 3),
                    'composite': round(composite_factor, 3),
                    # 新增：贡献分解
                    'contribution': {
                        'technical_dev': round(tech_conf_result.factor - 1.0, 4),
                        'fundamental_dev': round(fin_factor - 1.0, 4),
                        'macro_dev': round(macro_factor - 1.0, 4),
                        'weighted_dev': round(composite_factor - 1.0, 4)
                    }
                },
                
                # 评分与风险
                'scores': {
                    'fundamental': fin_score,
                    'pl_ratio': round(pl_ratio, 2),
                    'win_rate_estimate': round(win_rate, 2),  # 新增
                    'kelly_fraction': round(kelly_fraction, 3)  # 新增
                },
                
                # 信号与建议
                'signals': {
                    'trend': tech_signals.get('trend'),
                    'rsi_zone': tech_signals.get('rsi_zone'),
                    # 'data_quality': round(self._calculate_data_quality(stock_data, financial_data, macro_data), 2)  # 新增
                },
                
                # 仓位建议（新增）
                'position_suggestion': {
                    'suggested_shares': int(suggested_position),
                    'risk_amount': round(risk_per_share * suggested_position, 2),
                    'expected_return': round((final_target - final_entry) * suggested_position, 2),
                    'max_loss': round(-risk_per_share * suggested_position, 2)
                },
                # 新增技术面质量信息
                'technical_quality': {
                    'factor': tech_conf_result.factor,
                    'score': tech_conf_result.score,
                    'level': tech_conf_result.level,
                    'breakdown': {
                        'data_quality': tech_conf_result.data_quality_score,
                        'consistency': tech_conf_result.consistency_score,
                        'strength': tech_conf_result.strength_score
                    },
                    'diagnostics': tech_conf_result.diagnostics
                },
                # 置信度与诊断
                # 'confidence': round(confidence, 2),
                'recommendation': recommendation,
                
                # 参数与诊断（增强）
                'params_used': {
                    'stop_loss_atr_mult': params.get('stop_loss_atr_mult', 3.0),
                    'entry_ma_period': params.get('entry_ma_period', 20),
                    'macro_sensitivity': params.get('macro_sensitivity', 1.0)
                },
                'diagnostics': {
                    'data_sufficiency': msg,  # 来自 _check_data_sufficiency
                    'optimization_applied': pl_ratio < 2.0,  # 是否触发盈亏比优化
                    'fallback_reason': None  # 可扩展：记录降级原因
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