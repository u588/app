#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
TDXAdapter：通达信接口适配模块（优化版）
✅ 三类市场分离：股票 / 指数 / 衍生品（期货/期权/基金/宏观）
✅ 彻底移除复权逻辑
✅ 接口职责单一、健壮、标准化
"""

import pandas as pd
import logging
import time
from typing import Optional, Dict, List, Any
from datetime import datetime

logger = logging.getLogger(__name__)


class TDXAdapter:
    """通达信接口适配器（只读）"""

    # 市场类型映射：market_type -> (kline_period, market_code)
    MARKET_MAP = {
        # 股票类
        'stock_sh': (9, 1),    # 上海A股
        'stock_sz': (9, 0),    # 深圳A股
        'stock_xg': (9, 31),   # 港股
        
        # 指数类
        'index_sh': (9, 1),    # 上证指数
        'index_sz': (9, 0),    # 深证指数
        'index_zz': (9, 62),   # 中证指数
        'index_gz': (9, 102),  # 国证指数
        'index_xg': (9, 27),   # 恒生指数
        
        # 衍生品类（期货/期权/基金/宏观）
        'future_zz': (9, 28),   # 郑商所
        'future_dl': (9, 29),   # 大商所
        'future_sh': (9, 30),   # 上期所
        'future_gz': (9, 66),   # 广期所
        'future_zj': (9, 47),   # 中金所期货
        'option_zj': (9, 7),    # 中金所期权
        'option_sh': (9, 8),    # 上交所期权
        'option_sz': (9, 9),    # 深交所期权
        'open_fund': (9, 33),   # 开放式基金
        'macro': (9, 38),       # 宏观指标
    }

    # 市场类型分类映射
    MARKET_CATEGORY = {
        # 股票类
        'stock_sh': 'stock',
        'stock_sz': 'stock',
        'stock_xg': 'stock',
        
        # 指数类
        'index_sh': 'index',
        'index_sz': 'index',
        'index_zz': 'index',
        'index_gz': 'index',
        'index_xg': 'index',
        
        # 衍生品类
        'future_zz': 'derivative',
        'future_dl': 'derivative',
        'future_sh': 'derivative',
        'future_gz': 'derivative',
        'future_zj': 'derivative',
        'option_zj': 'derivative',
        'option_sh': 'derivative',
        'option_sz': 'derivative',
        'open_fund': 'derivative',
        'macro': 'derivative',
    }

    def __init__(self, config: Dict[str, Any], max_retries: int = 3):
        """
        初始化 TDX 适配器
        
        参数:
            config: TDX 配置 {hq_host, hq_port, exhq_host, exhq_port, timeout, use_tdx}
            max_retries: 连接重试次数
        """
        self.config = config
        self.max_retries = max_retries
        self.use_tdx = config.get('use_tdx', True)
        
        self.tdx_hq = None    # 普通行情接口（股票/指数）
        self.tdx_exhq = None  # 扩展行情接口（衍生品）
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
            
            for attempt in range(self.max_retries):
                try:
                    # 优先初始化扩展行情（覆盖范围更广）
                    self.tdx_exhq = TdxExHq_API(heartbeat=True)
                    self.tdx_exhq.connect(
                        self.config.get('exhq_host', '47.112.95.207'),
                        self.config.get('exhq_port', 7720),
                        time_out=self.config.get('timeout', 30)
                    )
                    
                    # 初始化普通行情
                    self.tdx_hq = TdxHq_API(heartbeat=True)
                    self.tdx_hq.connect(
                        self.config.get('hq_host', '180.153.18.170'),
                        self.config.get('hq_port', 7709),
                        time_out=self.config.get('timeout', 30)
                    )
                    
                    self._connected = True
                    logger.info("✅ TDX 接口连接成功（普通+扩展行情）")
                    return True
                    
                except Exception as e:
                    logger.warning(f"⚠️ TDX 连接尝试 {attempt+1}/{self.max_retries} 失败: {e}")
                    time.sleep(1.5 ** attempt)  # 指数退避
            
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
        """检查连接有效性，失效时自动重连"""
        if not self.use_tdx:
            return False
        
        try:
            # 双接口心跳检测
            if self.tdx_hq:
                self.tdx_hq.get_security_count(0)  # 深圳股票数量
            if self.tdx_exhq:
                self.tdx_exhq.get_instrument_count()
            return True
        except:
            logger.warning("⚠️ TDX 连接失效，尝试重连...")
            return self._connect()

    def get_bars(
        self,
        code: str,
        market_type: str,
        days: int = 60
    ) -> Optional[pd.DataFrame]:
        """
        获取 K 线数据（三类市场分离处理）
        
        参数:
            code: 证券代码（如 '600000', '000300', 'IF2406'）
            market_type: 市场类型（见 MARKET_MAP）
            days: 获取天数（默认60日）
        
        返回:
            标准化 DataFrame，包含列: datetime, open, high, low, close, volume, turnover
            失败时返回 None
        """
        if not self.use_tdx or not self._check_connection():
            return None

        # 验证市场类型
        if market_type not in self.MARKET_MAP:
            logger.error(f"❌ 不支持的市场类型: {market_type}，有效类型: {list(self.MARKET_MAP.keys())}")
            return None
        
        if market_type not in self.MARKET_CATEGORY:
            logger.error(f"❌ 未分类的市场类型: {market_type}")
            return None

        category, market_code = self.MARKET_MAP[market_type]
        market_class = self.MARKET_CATEGORY[market_type]
        result = None

        try:
            # ============ 三类市场分离加载逻辑 ============
            if market_class == 'stock':
                # 股票：使用普通行情接口 + get_security_bars
                if not self.tdx_hq:
                    raise RuntimeError("普通行情接口未初始化")
                result = self.tdx_hq.get_security_bars(
                    category, market_code, code, 0, days
                )
                logger.debug(f"📊 股票K线 [{market_type}] {code} → {len(result) if result else 0} 条")

            elif market_class == 'index':
                # 指数：使用普通行情接口 + get_index_bars
                if not self.tdx_hq:
                    raise RuntimeError("普通行情接口未初始化")
                result = self.tdx_hq.get_index_bars(
                    category, market_code, code, 0, days
                )
                logger.debug(f"📊 指数K线 [{market_type}] {code} → {len(result) if result else 0} 条")

            elif market_class == 'derivative':
                # 衍生品：使用扩展行情接口 + get_instrument_bars
                if not self.tdx_exhq:
                    raise RuntimeError("扩展行情接口未初始化")
                result = self.tdx_exhq.get_instrument_bars(
                    category, market_code, code, 0, days
                )
                logger.debug(f"📊 衍生品K线 [{market_type}] {code} → {len(result) if result else 0} 条")

            else:
                logger.error(f"❌ 未知市场类别: {market_class}")
                return None

            # 空数据处理
            if not result or len(result) == 0:
                logger.warning(f"⚠️ TDX 返回空数据: {code} ({market_type})")
                return None

            # 标准化为 DataFrame
            df = self._normalize_bars(result, market_type)
            if df.empty:
                logger.warning(f"⚠️ 标准化后数据为空: {code}")
                return None

            # 按时间排序并去重
            df = df.sort_values('datetime').drop_duplicates('datetime', keep='last')
            return df.reset_index(drop=True)

        except Exception as e:
            logger.warning(f"⚠️ TDX 获取K线失败 [{market_type}] {code}: {type(e).__name__}: {e}")
            return None

    def _normalize_bars(self, bars: List[Dict], market_type: str) -> pd.DataFrame:
        """标准化 K 线数据格式（统一列名与类型）"""
        if not bars:
            return pd.DataFrame()
        
        df = pd.DataFrame(bars)
        
        # 列名标准化映射（兼容不同接口返回字段）
        col_mapping = {
            # 价格字段
            'open': 'open',
            'high': 'high',
            'low': 'low',
            'close': 'close',
            'price': 'close',          # 部分接口使用 price
            'last_close': 'prev_close',# 前收盘
            
            # 成交量/额
            'vol': 'volume',
            'volume': 'volume',
            'trade': 'volume',         # 扩展接口常用
            'amount': 'turnover',
            
            # 持仓量（期货/期权）
            'position': 'open_interest',
            'settlement': 'settlement',
            
            # 时间字段
            'date': 'date',
            'datetime': 'datetime',
            'time': 'time',
        }
        
        # 应用列映射
        for src, dst in col_mapping.items():
            if src in df.columns and dst not in df.columns:
                df[dst] = df[src]
        
        # 确保 datetime 列
        if 'datetime' not in df.columns:
            if 'date' in df.columns:
                df['datetime'] = pd.to_datetime(df['date'], errors='coerce')
            elif 'time' in df.columns:
                df['datetime'] = pd.to_datetime(df['time'], errors='coerce')
            else:
                # 尝试从索引生成（部分接口返回无时间列）
                df['datetime'] = pd.to_datetime(df.index, errors='coerce', unit='D', origin='unix')
        
        # 强制必要字段
        required_cols = ['datetime', 'open', 'high', 'low', 'close', 'volume']
        for col in required_cols:
            if col not in df.columns:
                df[col] = 0.0 if col != 'datetime' else pd.NaT
        
        # 类型转换
        df['datetime'] = pd.to_datetime(df['datetime'], errors='coerce')
        for col in ['open', 'high', 'low', 'close', 'volume', 'turnover', 'open_interest']:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0.0)
        
        # 保留标准列
        standard_cols = ['datetime', 'open', 'high', 'low', 'close', 'volume']
        if 'turnover' in df.columns:
            standard_cols.append('turnover')
        if 'open_interest' in df.columns:
            standard_cols.append('open_interest')
        
        return df[standard_cols].dropna(subset=['datetime'])

    def get_option_chain(self, underlying: str, expiry: Optional[str] = None) -> List[Dict]:
        """
        获取期权合约链（简化版，需扩展实现）
        """
        if not self.use_tdx or not self._check_connection() or not self.tdx_exhq:
            return []
        
        try:
            # TODO: 实际实现需调用 tdx_exhq.get_option_list 等接口
            logger.debug(f"⏳ 暂未实现期权链查询: {underlying} {expiry or 'all'}")
            return []
        except Exception as e:
            logger.warning(f"⚠️ 获取期权链失败: {e}")
            return []

    def is_available(self) -> bool:
        """检查 TDX 接口是否可用"""
        return self.use_tdx and self._check_connection()

    def close(self):
        """安全关闭连接"""
        for api, name in [(self.tdx_hq, "普通行情"), (self.tdx_exhq, "扩展行情")]:
            if api:
                try:
                    api.disconnect()
                    logger.debug(f"🔌 已关闭 {name} 连接")
                except Exception as e:
                    logger.debug(f"⚠️ 关闭 {name} 连接时异常: {e}")
        self._connected = False
        logger.info("✅ TDX 连接已全部关闭")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
        return False