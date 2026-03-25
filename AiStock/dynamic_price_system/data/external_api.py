#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ExternalAPI：外部 API 数据获取模块
职责：
1. 获取外盘期货数据（原油/黄金/铜等）
2. 获取国际宏观指标
3. 实现数据缓存和降级处理
4. 统一的 API 调用接口
"""

import logging
from typing import Optional, Dict, Any
from datetime import datetime
import time

from base_services.config_service import ConfigService

logger = logging.getLogger(__name__)


class ExternalAPI:
    """外部 API 数据服务"""
    
    def __init__(self, config_service: ConfigService):
        """
        初始化外部 API 服务
        
        参数:
            config_service: 配置服务实例
        """
        self.config = config_service
        self.cache = {}
        self.cache_ttl = 300  # 5 分钟缓存
        
        logger.info("✅ ExternalAPI 初始化成功")
    
    def get_external_futures(self, code: str) -> Optional[float]:
        """
        获取外盘期货价格
        
        参数:
            code: 期货代码（OIL/GC/CAD/NG 等）
        
        返回:
            价格或 None
        """
        # 检查缓存
        cache_key = f"futures_{code}"
        if cache_key in self.cache:
            cached_time, cached_value = self.cache[cache_key]
            if (datetime.now() - cached_time).total_seconds() < self.cache_ttl:
                logger.debug(f"✅ 缓存命中：{code}")
                return cached_value
        
        # 映射代码
        code_map = {
            'OIL': '布伦特原油',
            'GC': 'COMEX 黄金',
            'CAD': 'LME 铜',
            'NG': 'NYMEX 天然气',
            'SI': 'COMEX 白银',
        }
        
        symbol = code_map.get(code)
        if not symbol:
            logger.warning(f"⚠️ 未知外盘期货代码：{code}")
            return None
        
        # 调用 akshare 获取数据
        try:
            import akshare as ak
            df = ak.futures_foreign_commodity_realtime(symbol=symbol)
            
            if df is not None and len(df) > 0:
                price = float(df['最新价'].iloc[0])
                
                # 存入缓存
                self.cache[cache_key] = (datetime.now(), price)
                
                logger.info(f"✅ 获取外盘期货 {code}={symbol}: {price}")
                return price
            
            return None
        except Exception as e:
            logger.error(f"❌ 获取外盘期货失败 {code}: {e}")
            return None
    
    def get_exchange_rate(self, pair: str = 'USDCNY') -> Optional[float]:
        """
        获取汇率
        
        参数:
            pair: 货币对（默认 USDCNY）
        
        返回:
            汇率或 None
        """
        cache_key = f"exchange_{pair}"
        if cache_key in self.cache:
            cached_time, cached_value = self.cache[cache_key]
            if (datetime.now() - cached_time).total_seconds() < self.cache_ttl:
                return cached_value
        
        try:
            import akshare as ak
            df = ak.fx_currency_pair_em(symbol="美元人民币")
            
            if df is not None and len(df) > 0:
                rate = float(df['最新价'].iloc[0])
                self.cache[cache_key] = (datetime.now(), rate)
                return rate
            
            return None
        except Exception as e:
            logger.error(f"❌ 获取汇率失败 {pair}: {e}")
            return None
    
    def get_us_treasury_yield(self, year: int = 10) -> Optional[float]:
        """
        获取美国国债收益率
        
        参数:
            year: 年期（默认 10 年）
        
        返回:
            收益率或 None
        """
        cache_key = f"ustreasury_{year}y"
        if cache_key in self.cache:
            cached_time, cached_value = self.cache[cache_key]
            if (datetime.now() - cached_time).total_seconds() < self.cache_ttl:
                return cached_value
        
        try:
            import akshare as ak
            df = ak.usa_bond_rate_em()
            
            if df is not None and len(df) > 0:
                # 根据年期选择对应列
                col_name = f'{year}年'
                if col_name in df.columns:
                    yield_rate = float(df[col_name].iloc[0])
                    self.cache[cache_key] = (datetime.now(), yield_rate)
                    return yield_rate
            
            return None
        except Exception as e:
            logger.error(f"❌ 获取美债收益率失败 {year}年：{e}")
            return None
    
    def get_all_external_data(self) -> Dict[str, Any]:
        """
        获取所有外部数据
        
        返回:
            外部数据字典
        """
        data = {}
        
        # 外盘期货
        futures_codes = ['OIL', 'GC', 'CAD', 'NG']
        for code in futures_codes:
            price = self.get_external_futures(code)
            if price:
                data[code.lower()] = price
        
        # 汇率
        rate = self.get_exchange_rate()
        if rate:
            data['usd_cny'] = rate
        
        # 美债收益率
        yield_rate = self.get_us_treasury_yield()
        if yield_rate:
            data['us_10y_yield'] = yield_rate
        
        logger.info(f"✅ 获取外部数据完成：{len(data)}个指标")
        return data
    
    def clear_cache(self):
        """清空缓存"""
        self.cache.clear()
        logger.info("✅ 外部 API 缓存已清空")


# ==================== 使用示例 ====================
def example_external_api():
    """外部 API 使用示例"""
    
    print("=" * 80)
    print("🧪 ExternalAPI 使用示例")
    print("=" * 80)
    
    # 注意：实际使用需要完整的配置服务
    print("\n1️⃣ 获取外盘期货价格...")
    print("   📊 oil_price = api.get_external_futures('OIL')")
    print("   📊 gold_price = api.get_external_futures('GC')")
    
    print("\n2️⃣ 获取汇率...")
    print("   📊 usd_cny = api.get_exchange_rate('USDCNY')")
    
    print("\n3️⃣ 获取美债收益率...")
    print("   📊 us_10y = api.get_us_treasury_yield(10)")
    
    print("\n4️⃣ 获取所有外部数据...")
    print("   📊 all_data = api.get_all_external_data()")
    
    print("\n" + "=" * 80)
    print("✅ ExternalAPI 示例说明完成")
    print("=" * 80)


if __name__ == "__main__":
    example_external_api()