#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
DynamicPriceEngine：三维动态价格计算引擎
"""

import logging
from typing import Dict, Optional, List
from datetime import datetime

from base_services.config_service import ConfigService
from base_services.cache_service import CacheService
from dynamic_price_system.core.technical_calculator import TechnicalCalculator
from dynamic_price_system.core.fundamental_calculator import FundamentalCalculator
from dynamic_price_system.core.macro_calculator import MacroCalculator
from dynamic_price_system.core.price_validator import PriceValidator

logger = logging.getLogger(__name__)


class DynamicPriceEngine:
    """三维动态价格计算引擎"""
    
    def __init__(
        self,
        config_service: ConfigService,
        cache_service: Optional[CacheService] = None
    ):
        """
        初始化计算引擎
        
        参数:
            config_service: 配置服务实例
            cache_service: 缓存服务实例（可选）
        """
        self.config = config_service
        self.cache = cache_service
        
        # 加载三维权重
        self.weights = self.config.get('weights', {})
        
        logger.info(f"✅ DynamicPriceEngine 初始化成功 | 权重={self.weights}")
    
    def calculate_all(
        self,
        stocks_data: Dict,
        financial_data: Dict,
        macro_data: Dict
    ) -> List[Dict]:
        """
        计算所有标的的动态价格
        
        参数:
            stocks_data: 股票日线数据 {code: df}
            financial_data: 财务数据 {code: data}
            macro_data: 宏观数据字典
        
        返回:
            动态价格结果列表
        """
        results = []
        
        for stock_config in self.config.get('stocks', []):
            code = stock_config['code']
            sector = stock_config['sector']
            
            result = self.calculate_single(
                code=code,
                sector=sector,
                stock_data=stocks_data.get(code),
                financial_data=financial_data.get(code, {}),
                macro_data=macro_data,
                stock_params=stock_config.get('params', {})
            )
            
            if result:
                results.append(result)
        
        logger.info(f"✅ 动态价格计算完成：{len(results)}只标的")
        return results
    
    def calculate_single(
        self,
        code: str,
        sector: str,
        stock_data,
        financial_data: Dict,
        macro_data: Dict,
        stock_params: Dict
    ) -> Optional[Dict]:
        """计算单只标的动态价格"""
        try:
            if stock_data is None or stock_data.empty:
                logger.warning(f"⚠️ {code} 无日线数据")
                return None
            
            # ========== 1. 技术面计算 ==========
            tech_calc = TechnicalCalculator(stock_data, params=stock_params)
            tech_entry = tech_calc.get_entry_price()
            tech_stop = tech_calc.get_stop_loss()
            tech_target = tech_calc.get_target_price()
            
            if not all([tech_entry, tech_stop, tech_target]):
                return None
            
            # ========== 2. 基本面计算 ==========
            fin_calc = FundamentalCalculator(financial_data, params=stock_params)
            fin_factor = fin_calc.get_adjustment_factor()
            fin_score = fin_calc.get_score()
            fin_rec = fin_calc.get_recommendation()
            
            # ========== 3. 宏观面计算 ==========
            macro_calc = MacroCalculator(macro_data, sector=sector, config=self.config)
            macro_factor = macro_calc.get_adjustment_factor()
            
            # ========== 4. 三维加权综合 ==========
            final_entry = self._comprehensive_price(tech_entry, fin_factor, macro_factor)
            final_stop = self._comprehensive_price(tech_stop, fin_factor, macro_factor)
            final_target = self._comprehensive_price(tech_target, fin_factor, macro_factor)
            
            # ========== 5. 价格验证 ==========
            validator = PriceValidator()
            final_entry = validator.validate(final_entry, stock_data['close'].iloc[-1])
            final_stop = validator.validate_stop(final_stop, final_entry)
            final_target = validator.validate_target(final_target, final_entry)
            
            # ========== 6. 盈亏比计算 ==========
            profit_loss_ratio = (final_target - final_entry) / (final_entry - final_stop) \
                if (final_entry - final_stop) > 0 else 0
            
            # ========== 7. 投资建议 ==========
            recommendation = self._get_recommendation(profit_loss_ratio, fin_score)
            
            result = {
                'code': code,
                'sector': sector,
                'current_price': round(float(stock_data['close'].iloc[-1]), 2),
                'entry_price': round(final_entry, 2),
                'stop_loss': round(final_stop, 2),
                'target_price': round(final_target, 2),
                'profit_loss_ratio': round(profit_loss_ratio, 2),
                'fundamental_score': fin_score,
                'fundamental_rec': fin_rec,
                'macro_factor': round(macro_factor, 3),
                'technical_factor': 1.0,  # 技术面为基准
                'recommendation': recommendation,
                'calc_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            }
            
            logger.debug(f"✅ {code} 动态价格计算完成")
            return result
            
        except Exception as e:
            logger.error(f"❌ {code} 动态价格计算失败：{e}", exc_info=True)
            return None
    
    def _comprehensive_price(self, tech_price: float, fin_factor: float, macro_factor: float) -> float:
        """三维加权综合价格计算"""
        w_tech = self.weights.get('technical', 0.40)
        w_fin = self.weights.get('fundamental', 0.35)
        w_macro = self.weights.get('macro', 0.25)
        
        comprehensive = (
            tech_price * w_tech +
            tech_price * fin_factor * w_fin +
            tech_price * macro_factor * w_macro
        )
        
        return comprehensive
    
    def _get_recommendation(self, pl_ratio: float, fin_score: float) -> str:
        """生成投资建议"""
        min_score = self.config.get(f'stocks.{pl_ratio}.params.min_fundamental_score', 50)
        
        if pl_ratio >= 3 and fin_score >= min_score:
            return "强烈推荐"
        elif pl_ratio >= 2 and fin_score >= min_score - 10:
            return "推荐"
        elif pl_ratio >= 1.5 and fin_score >= min_score - 20:
            return "观望"
        else:
            return "谨慎"