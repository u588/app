#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
TDXAdapter：TDX 接口适配模块
职责：
1. 封装 TDX 行情接口调用
2. 实现连接池管理
3. 提供降级处理（TDX→数据库）
4. 自动重试机制
"""

import logging
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
import time

from base_services.config_service import ConfigService

logger = logging.getLogger(__name__)


class TDXAdapter:
    """TDX 接口适配器"""
    
    def __init__(self, config_service: ConfigService):
        """
        初始化 TDX 适配器
        
        参数:
            config_service: 配置服务实例
        """
        self.config = config_service
        self.tdx_exhq = None
        self.tdx_hq = None
        self.connected = False
        
        # 连接配置
        self.exhq_host = config_service.get('tdx.exhq_host', '47.112.95.207')
        self.exhq_port = config_service.get('tdx.exhq_port', 7720)
        self.hq_host = config_service.get('tdx.hq_host', '180.153.18.170')
        self.hq_port = config_service.get('tdx.hq_port', 7709)
        self.timeout = config_service.get('tdx.timeout', 30)
        self.retry_times = config_service.get('tdx.retry_times', 3)
        
        # 是否启用 TDX
        self.use_tdx = config_service.get('tdx.use_tdx', True)
        
        if self.use_tdx:
            self._connect()
        
        logger.info(f"✅ TDXAdapter 初始化成功 | 启用={self.use_tdx}")
    
    def _connect(self):
        """建立 TDX 连接"""
        if not self.use_tdx:
            return
        
        try:
            from pytdx.hq import TdxHq_API
            from pytdx.exhq import TdxExHq_API
            
            # 连接扩展行情
            self.tdx_exhq = TdxExHq_API()
            self.tdx_exhq.connect(self.exhq_host, self.exhq_port, timeout=self.timeout)
            
            # 连接普通行情
            self.tdx_hq = TdxHq_API()
            self.tdx_hq.connect(self.hq_host, self.hq_port, timeout=self.timeout)
            
            self.connected = True
            logger.info("✅ TDX 接口连接成功")
        except Exception as e:
            logger.warning(f"⚠️ TDX 接口连接失败：{e}，将降级使用数据库")
            self.use_tdx = False
            self.connected = False
    
    def _reconnect(self):
        """重新连接"""
        self.connected = False
        time.sleep(2)
        self._connect()
    
    def get_stock_daily(self, code: str, min_days: int = 500) -> Optional[Any]:
        """
        获取股票日线数据
        
        参数:
            code: 股票代码
            min_days: 最小数据天数
        
        返回:
            DataFrame 或 None
        """
        if not self.use_tdx or not self.connected:
            return None
        
        for attempt in range(self.retry_times):
            try:
                if not self.connected:
                    self._reconnect()
                
                if not self.tdx_hq:
                    return None
                
                # 解析股票代码
                market_id = 1 if code.startswith('6') else 0  # 1=上海，0=深圳
                security_id = int(code)
                
                # 获取数据
                data = self.tdx_hq.get_security_bars(
                    category=9,  # 日线
                    market=market_id,
                    code=security_id,
                    start=0,
                    count=min_days
                )
                
                if data and len(data) > 0:
                    import pandas as pd
                    df = pd.DataFrame(data)
                    
                    # 重命名列
                    df = df.rename(columns={
                        'trade': 'volume',
                        'amount': 'turnover',
                        'price': 'close'
                    })
                    
                    # 转换日期
                    if 'datetime' in df.columns:
                        df['datetime'] = pd.to_datetime(df['datetime'])
                    
                    return df
                
                return None
            except Exception as e:
                logger.warning(f"⚠️ TDX 获取股票数据失败 (尝试{attempt+1}/{self.retry_times}): {e}")
                if attempt < self.retry_times - 1:
                    time.sleep(2 ** attempt)
                else:
                    self.use_tdx = False
                    return None
        
        return None
    
    def get_macro_data(self, code: str, days: int = 60) -> Optional[Any]:
        """
        获取宏观指标数据
        
        参数:
            code: 宏观指标代码
            days: 数据天数
        
        返回:
            DataFrame 或 None
        """
        if not self.use_tdx or not self.connected:
            return None
        
        for attempt in range(self.retry_times):
            try:
                if not self.connected:
                    self._reconnect()
                
                if not self.tdx_exhq:
                    return None
                
                # 宏观指标市场代码为 38
                data = self.tdx_exhq.get_instrument_bars(
                    category=9,
                    market=38,
                    code=code,
                    start=0,
                    count=days
                )
                
                if data and len(data) > 0:
                    import pandas as pd
                    df = pd.DataFrame(data)
                    
                    if 'datetime' in df.columns:
                        df['datetime'] = pd.to_datetime(df['datetime'])
                    
                    return df
                
                return None
            except Exception as e:
                logger.warning(f"⚠️ TDX 获取宏观数据失败 (尝试{attempt+1}/{self.retry_times}): {e}")
                if attempt < self.retry_times - 1:
                    time.sleep(2 ** attempt)
                else:
                    return None
        
        return None
    
    def get_derivative_data(self, code: str, market_code: int, days: int = 60) -> Optional[Any]:
        """
        获取衍生品数据（期货/期权）
        
        参数:
            code: 合约代码
            market_code: 市场代码
            days: 数据天数
        
        返回:
            DataFrame 或 None
        """
        if not self.use_tdx or not self.connected:
            return None
        
        for attempt in range(self.retry_times):
            try:
                if not self.connected:
                    self._reconnect()
                
                if not self.tdx_exhq:
                    return None
                
                data = self.tdx_exhq.get_instrument_bars(
                    category=9,
                    market=market_code,
                    code=code,
                    start=0,
                    count=days
                )
                
                if data and len(data) > 0:
                    import pandas as pd
                    df = pd.DataFrame(data)
                    df = df.rename(columns={
                        'trade': 'volume',
                        'position': 'open_interest',
                        'amount': 'turnover',
                        'price': 'settlement'
                    })
                    
                    if 'datetime' in df.columns:
                        df['datetime'] = pd.to_datetime(df['datetime'])
                    
                    return df
                
                return None
            except Exception as e:
                logger.warning(f"⚠️ TDX 获取衍生品数据失败 (尝试{attempt+1}/{self.retry_times}): {e}")
                if attempt < self.retry_times - 1:
                    time.sleep(2 ** attempt)
                else:
                    return None
        
        return None
    
    def is_connected(self) -> bool:
        """检查连接状态"""
        return self.connected and self.use_tdx
    
    def close(self):
        """关闭连接"""
        if self.tdx_exhq:
            try:
                self.tdx_exhq.disconnect()
            except:
                pass
        
        if self.tdx_hq:
            try:
                self.tdx_hq.disconnect()
            except:
                pass
        
        self.connected = False
        logger.info("✅ TDX 连接已关闭")


# ==================== 使用示例 ====================
def example_tdx_adapter():
    """TDX 适配器使用示例"""
    
    print("=" * 80)
    print("🧪 TDXAdapter 使用示例")
    print("=" * 80)
    
    # 注意：实际使用需要完整的配置服务
    print("\n1️⃣ 初始化 TDX 适配器...")
    print("   📊 tdx = TDXAdapter(config_service)")
    
    print("\n2️⃣ 获取股票日线数据...")
    print("   📊 df = tdx.get_stock_daily('600938', min_days=500)")
    
    print("\n3️⃣ 获取宏观指标数据...")
    print("   📊 df = tdx.get_macro_data('3_PMI', days=60)")
    
    print("\n4️⃣ 获取衍生品数据...")
    print("   📊 df = tdx.get_derivative_data('OIL', market_code=38, days=60)")
    
    print("\n5️⃣ 检查连接状态...")
    print("   📊 is_connected = tdx.is_connected()")
    
    print("\n" + "=" * 80)
    print("✅ TDXAdapter 示例说明完成")
    print("=" * 80)


if __name__ == "__main__":
    example_tdx_adapter()