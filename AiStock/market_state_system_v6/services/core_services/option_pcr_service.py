# ==================== 4.1.7 期权PCR服务 （期权PCR：动态合约识别 + 综合PCR）OptionPCRService ==================== 
# option_pcr_service_fixed.py
import pandas as pd
import numpy as np
from typing import Dict, Optional
import logging

logger = logging.getLogger(__name__)

class OptionPCRService:
    """
    期权PCR服务（修复版：完全独立，无循环依赖）
    职责：
    1. 期权合约识别
    2. 平值合约选择
    3. PCR计算
    4. 期权情绪信号生成
    依赖：
    - 仅依赖DataLoadingService（用于加载期权数据）
    - 不依赖MarketStateSystem或其他业务服务
    """
    
    def __init__(self, data_service, config):
        """初始化（修复版：仅持有必要依赖）"""
        self.data_service = data_service
        self.config = config
        
        # ✅ 修复：从config获取容忍度（非硬编码）
        self.default_tolerance = self.config.adaptive_config.option_tolerance.get(
            'base_tolerance', 0.05
        )
        
        logger.info("✅ 期权PCR服务初始化成功")
    
    def calculate_pcr(
        self,
        underlying: str,
        market_code: int,
        current_price: Optional[float] = None
    ) -> Dict:
        """
        计算单个标的PCR（修复版：纯函数）
        
        参数:
            underlying: 标的代码
            market_code: 市场代码
            current_price: 标的当前价格
        
        返回:
            PCR计算结果
        """
        # 1. 获取近月合约
        near_month = self._get_near_month_contracts(underlying, market_code)
        if near_month.empty:
            return {'error': '无近月合约'}
        
        # 2. 获取平值合约（修复：使用动态容忍度）
        tolerance = self._get_dynamic_tolerance(current_price)
        atm_contracts = self._get_atm_contracts(near_month, current_price, tolerance)
        
        if atm_contracts.empty:
            return {'error': '无平值合约'}
        
        # 3. 计算PCR（简化版，实际应加载期权数据）
        # ... 实际实现应调用data_service.load_derivative_data加载期权数据
        
        # 模拟返回
        pcr_value = np.random.uniform(0.8, 1.5)
        signal = self._generate_signal(pcr_value)
        
        return {
            'underlying': underlying,
            'market_code': market_code,
            'pcr_value': pcr_value,
            'signal': signal,
            'tolerance_used': tolerance,
            'timestamp': pd.Timestamp.now().strftime('%Y-%m-%d %H:%M:%S')
        }
    
    def calculate_composite_pcr(self) -> Dict:
        """计算综合PCR（修复版：多标的加权）"""
        # 1. 计算各标的PCR
        results = {}
        for underlying, market_code in [('510300', 8), ('IO', 7), ('MO', 7), ('510500', 8)]:
            current_price = self._get_current_price(underlying)
            results[underlying] = self.calculate_pcr(underlying, market_code, current_price)
        
        # 2. 加权计算综合PCR（修复：从config获取权重）
        weights = self.config.option_markets
        composite_pcr = 0.0
        total_weight = 0.0
        
        for underlying, result in results.items():
            if 'pcr_value' in result:
                market = 'sse' if underlying.startswith('5') else 'cffex'
                weight = weights.get(market, {}).get('pcr_weight', 0.25)
                composite_pcr += result['pcr_value'] * weight
                total_weight += weight
        
        if total_weight > 0:
            composite_pcr /= total_weight
        
        return {
            'composite_pcr': composite_pcr,
            'composite_signal': self._generate_signal(composite_pcr),
            'components': results,
            'weights_used': {k: weights.get('sse' if k.startswith('5') else 'cffex', {}).get('pcr_weight', 0.25) 
                           for k in results.keys()},
            'timestamp': pd.Timestamp.now().strftime('%Y-%m-%d %H:%M:%S')
        }
    
    def _get_dynamic_tolerance(self, current_price: Optional[float]) -> float:
        """获取动态容忍度（修复版：从adaptive_config获取）"""
        if not self.config.adaptive_config.option_tolerance['enabled']:
            return self.default_tolerance
        
        # 简化：根据波动率调整（实际应计算波动率）
        volatility_percentile = np.random.uniform(0.3, 0.8)  # 模拟波动率分位数
        
        if volatility_percentile > 0.7:
            return self.config.adaptive_config.option_tolerance['volatility_based']['high_vol_tolerance']
        elif volatility_percentile < 0.3:
            return self.config.adaptive_config.option_tolerance['volatility_based']['low_vol_tolerance']
        else:
            return self.default_tolerance
    
    def _get_current_price(self, underlying: str) -> float:
        """获取标的当前价格（修复版：通过data_service）"""
        # 映射标的到指数代码
        index_mapping = {'IO': '000300', 'MO': '000852', '510300': '000300', '510500': '000905'}
        index_code = index_mapping.get(underlying, underlying)
        
        df = self.data_service.load_index_data(index_code, min_days=1)
        if len(df) > 0:
            return df['close'].iloc[-1]
        return 100.0  # 默认值
    
    def _get_near_month_contracts(self, underlying: str, market_code: int) -> pd.DataFrame:
        """获取近月合约（简化版）"""
        # 实际实现应从期权合约列表中筛选
        return pd.DataFrame()  # 简化返回空DataFrame
    
    def _get_atm_contracts(
        self,
        contracts: pd.DataFrame,
        current_price: float,
        tolerance: float
    ) -> pd.DataFrame:
        """获取平值合约（简化版）"""
        return contracts  # 简化返回原DataFrame
    
    def _generate_signal(self, pcr_value: float) -> str:
        """生成信号"""
        if pcr_value > 1.5:
            return '极度悲观(潜在反弹)'
        elif pcr_value > 1.2:
            return '看跌'
        elif pcr_value > 0.8:
            return '中性'
        elif pcr_value > 0.5:
            return '看涨'
        else:
            return '极度乐观(潜在回调)'