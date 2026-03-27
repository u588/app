#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
TDXAdapter：通达信接口适配模块
✅ 单一职责：只负责与 TDX 接口交互
✅ 健壮：连接重试 + 超时控制 + 降级标记
✅ 统一：标准化返回格式（DataFrame）
"""

import pandas as pd
import logging
import time
from typing import Optional, Dict, List, Any
from datetime import datetime

logger = logging.getLogger(__name__)


class TDXAdapter:
    """通达信接口适配器（只读）"""
    
    # 市场代码映射（可扩展）
    MARKET_MAP = {
        'stock_sh': (1, 1),    # 上海股票
        'stock_sz': (0, 1),    # 深圳股票
        'index_sh': (1, 2),    # 上海指数
        'index_sz': (0, 2),    # 深圳指数
        'future': (8, 31),     # 期货
        'option': (8, 41),     # 期权
        'macro': (38, 9),      # 宏观指标
    }
    
    def __init__(self, config: Dict[str, Any], max_retries: int = 3):
        """
        初始化 TDX 适配器
        
        参数:
            config: TDX 配置 {hq_host, hq_port, exhq_host, exhq_port, timeout}
            max_retries: 连接重试次数
        """
        self.config = config
        self.max_retries = max_retries
        self.use_tdx = config.get('use_tdx', True)
        
        self.tdx_hq = None    # 行情接口
        self.tdx_exhq = None  # 扩展行情接口
        self._connected = False
        
        if self.use_tdx:
            self._connect()
    
    def _connect(self) -> bool:
        """建立 TDX 连接（带重试）"""
        if not self.use_tdx:
            return False
        
        try:
            from pytdx.hq import TdxHq_API
            from pytdx.exhq import TdxExHq_API
            
            # 重试连接
            for attempt in range(self.max_retries):
                try:
                    # 扩展行情（期货/期权/宏观）
                    self.tdx_exhq = TdxExHq_API()
                    self.tdx_exhq.connect(
                        self.config.get('exhq_host', '47.112.95.207'),
                        self.config.get('exhq_port', 7720),
                        time_out=self.config.get('timeout', 30)
                    )
                    
                    # 普通行情（股票/指数）
                    self.tdx_hq = TdxHq_API()
                    self.tdx_hq.connect(
                        self.config.get('hq_host', '180.153.18.170'),
                        self.config.get('hq_port', 7709),
                        time_out=self.config.get('timeout', 30)
                    )
                    
                    self._connected = True
                    logger.info("✅ TDX 接口连接成功")
                    return True
                    
                except Exception as e:
                    logger.warning(f"⚠️ TDX 连接尝试 {attempt+1}/{self.max_retries} 失败: {e}")
                    time.sleep(2 ** attempt)  # 指数退避
            
            # 全部重试失败
            logger.error("❌ TDX 接口连接失败，降级使用数据库")
            self.use_tdx = False
            return False
            
        except ImportError:
            logger.warning("⚠️ pytdx 未安装，跳过 TDX 初始化")
            self.use_tdx = False
            return False
        except Exception as e:
            logger.error(f"❌ TDX 初始化异常: {e}")
            self.use_tdx = False
            return False
    
    def _check_connection(self) -> bool:
        """检查并重连"""
        if not self.use_tdx:
            return False
        
        # 简单心跳检测
        try:
            if self.tdx_hq:
                self.tdx_hq.get_index_bars(1, 1, '000001', 0, 1)
            return True
        except:
            logger.warning("⚠️ TDX 连接失效，尝试重连...")
            return self._connect()
    
    def get_bars(
        self,
        code: str,
        market_type: str,
        days: int = 60,
        adjust: str = 'none'
    ) -> Optional[pd.DataFrame]:
        """
        获取 K 线数据（股票/指数/期货/期权/宏观）
        
        参数:
            code: 代码（如 '000001', 'IF2406'）
            market_type: 市场类型（见 MARKET_MAP）
            days: 获取天数
            adjust: 复权类型（none/forward/backward，仅股票有效）
        """
        if not self.use_tdx or not self._check_connection():
            return None
        
        if market_type not in self.MARKET_MAP:
            logger.error(f"❌ 不支持的市场类型: {market_type}")
            return None
        
        category, market_code = self.MARKET_MAP[market_type]
        
        try:
            # 扩展行情接口（期货/期权/宏观/部分指数）
            if category in [8, 9, 31, 38, 41]:
                result = self.tdx_exhq.get_instrument_bars(
                    category, market_code, code, 0, days
                )
            # 普通行情接口（股票/指数）
            else:
                result = self.tdx_hq.get_security_bars(
                    category, market_code, code, 0, days
                )
            
            if not result:
                logger.warning(f"⚠️ TDX 返回空数据: {code}")
                return None
            
            # 标准化 DataFrame
            df = self._normalize_bars(result, market_type)
            
            # 简单复权处理（如需完整复权建议用专业库）
            if adjust != 'none' and market_type.startswith('stock'):
                df = self._simple_adjust(df, adjust)
            
            return df
            
        except Exception as e:
            logger.warning(f"⚠️ TDX 获取数据失败 {code}: {e}")
            return None
    
    def _normalize_bars(self, bars: List[Dict], market_type: str) -> pd.DataFrame:
        """标准化 K 线数据格式"""
        df = pd.DataFrame(bars)
        
        # 统一列名映射
        column_map = {
            'open': 'open',
            'high': 'high', 
            'low': 'low',
            'close': 'close',
            'vol': 'volume',
            'amount': 'turnover',
            'position': 'open_interest',
            'price': 'settlement',
            'trade': 'volume',  # TDX 扩展接口字段
        }
        
        # 重命名列
        for old_name, new_name in column_map.items():
            if old_name in df.columns:
                df[new_name] = df[old_name]
        
        # 确保 datetime 列
        if 'datetime' not in df.columns and 'date' in df.columns:
            df['datetime'] = pd.to_datetime(df['date'], errors='coerce')
        elif 'datetime' in df.columns:
            df['datetime'] = pd.to_datetime(df['datetime'], errors='coerce')
        
        # 确保必要列存在
        required = ['datetime', 'open', 'high', 'low', 'close', 'volume']
        for col in required:
            if col not in df.columns:
                df[col] = 0.0 if col != 'datetime' else pd.NaT
        
        # 排序去重
        df = df.sort_values('datetime').drop_duplicates('datetime', keep='last')
        
        return df.reset_index(drop=True)
    
    def _simple_adjust(self, df: pd.DataFrame, adjust: str) -> pd.DataFrame:
        """简单前/后复权（示意，生产建议用专业复权因子）"""
        if 'adj_factor' not in df.columns:
            logger.warning("⚠️ 无复权因子，跳过复权处理")
            return df
        
        factor_col = 'adj_factor'
        price_cols = ['open', 'high', 'low', 'close']
        
        if adjust == 'forward':
            for col in price_cols:
                df[col] = df[col] * df[factor_col]
        elif adjust == 'backward':
            last_factor = df[factor_col].iloc[-1]
            for col in price_cols:
                df[col] = df[col] * last_factor / df[factor_col]
        
        return df
    
    def get_option_chain(self, underlying: str, expiry: Optional[str] = None) -> List[Dict]:
        """
        获取期权合约链（简化版）
        
        参数:
            underlying: 标的代码
            expiry: 到期月份（如 '2406'）
        """
        if not self.use_tdx or not self._check_connection():
            return []
        
        try:
            # 实际需调用 TDX 的 get_option_list 等接口
            # 此处为框架示意
            logger.debug(f"⏳ 获取期权链: {underlying} {expiry or 'all'}")
            return []
        except Exception as e:
            logger.warning(f"⚠️ 获取期权链失败: {e}")
            return []
    
    def is_available(self) -> bool:
        """检查 TDX 接口是否可用"""
        return self.use_tdx and self._check_connection()
    
    def close(self):
        """关闭连接"""
        if self.tdx_hq:
            try:
                self.tdx_hq.disconnect()
            except:
                pass
        if self.tdx_exhq:
            try:
                self.tdx_exhq.disconnect()
            except:
                pass
        logger.info("✅ TDX 连接已关闭")
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
        return False