#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ExternalAPI：外部数据接口服务（增强版）
功能：通过 AkShare 获取外盘期货实时数据 + 历史数据
"""

import pandas as pd
import numpy as np
from typing import Dict, Optional, Any, List, Union, Tuple
from datetime import datetime, timedelta
import logging
import time
import threading
from dataclasses import dataclass, asdict, field
from enum import Enum
import hashlib
import json

logger = logging.getLogger(__name__)


class DataType(Enum):
    """数据类型枚举"""
    FUTURES_REALTIME = "futures_realtime"
    FUTURES_HISTORY = "futures_history"
    MACRO = "macro"
    FOREX = "forex"


class Frequency(Enum):
    """数据频率枚举"""
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"


@dataclass
class FuturesRealtimeData:
    """期货实时数据标准化模型"""
    code: str
    name: str
    price: float
    price_cny: Optional[float]
    change: float
    change_pct: float
    open: Optional[float]
    high: Optional[float]
    low: Optional[float]
    prev_close: Optional[float]
    volume: Optional[float]
    bid: Optional[float]
    ask: Optional[float]
    update_time: Optional[str]
    update_date: Optional[str]
    unit: str
    source: str
    raw_symbol: str
    fetch_time: str
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
    
    @property
    def is_valid(self) -> bool:
        return self.price > 0 and self.fetch_time is not None


@dataclass
class FuturesHistoryData:
    """期货历史数据标准化模型"""
    code: str
    name: str
    date: str  # YYYY-MM-DD
    open: float
    high: float
    low: float
    close: float
    volume: float
    position: Optional[float]  # 持仓量（外盘部分品种可能为空）
    change: float  # 涨跌额 = close - prev_close
    change_pct: float  # 涨跌幅 = (close - prev_close) / prev_close
    unit: str
    source: str
    raw_symbol: str
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
    
    def to_series(self) -> pd.Series:
        """转换为pandas Series，便于批量处理"""
        return pd.Series({
            'date': pd.to_datetime(self.date),
            'open': self.open,
            'high': self.high,
            'low': self.low,
            'close': self.close,
            'volume': self.volume,
            'position': self.position,
            'change': self.change,
            'change_pct': self.change_pct
        })


class AKAdapter:
    """外部数据接口服务（AkShare 集成 - 增强版）"""
    
    # ─────────────────────────────────────────────────────────────
    # 外部期货代码映射：配置代码 -> AkShare symbol
    # ─────────────────────────────────────────────────────────────
    FUTURES_SYMBOL_MAP = {
        # 能源化工
        'CL': 'NYMEX原油',           # 能源定价锚/通胀因子
        'OIL': '布伦特原油',         # 欧洲/亚太原油基准
        'NG': 'NYMEX天然气',         # 化工原料/冬季取暖
        'EUA': 'EUA碳排放权',        # 碳约束力度/绿色转型
        
        # 贵金属
        'GC': 'COMEX黄金',           # 期货金避险/实际利率核心指标
        'XAU': '伦敦金',             # 现货黄金基准/期货互补
        'SI': 'COMEX白银',           # 工业+避险双属性
        'XAG': '伦敦银',             # 白银现货基准
        'XPT': '伦敦铂金',           # 汽车催化剂/氢能
        
        # 有色金属
        'CAD': 'LME铜',              # 全球制造业景气先行指标
        'HG': 'COMEX铜',             # 美洲铜价/跨市套利
        'AHD': 'LME铝',              # 电解铝定价锚/新能源
        'NID': 'LME镍',              # 不锈钢/新能源电池
        'ZSD': 'LME锌',              # 镀锌/基建需求
        
        # 黑色金属
        'FEF': '新加坡铁矿石',        # 全球铁矿石定价基准
        
        # 农产品
        'S': 'CBOT大豆',             # 农产品链定价锚
        'C': 'CBOT玉米',             # 饲料成本核心因子
        'W': 'CBOT小麦',             # 口粮安全信号
        'CT': 'NYBOT棉花',           # 纺织产业链定价基准
        'RS': '美国原糖',            # 食糖定价锚
    }
    
    # ─────────────────────────────────────────────────────────────
    # 单位转换配置
    # ─────────────────────────────────────────────────────────────
    UNIT_CONVERT = {
        '布伦特原油': {'factor': 1.0, 'unit': 'USD/barrel'},
        'NYMEX原油': {'factor': 1.0, 'unit': 'USD/barrel'},
        'COMEX黄金': {'factor': 1.0, 'unit': 'USD/oz'},
        '伦敦金': {'factor': 1.0, 'unit': 'USD/oz'},
        'LME铜': {'factor': 1.0, 'unit': 'USD/ton'},
        'COMEX铜': {'factor': 1.0, 'unit': 'USD/ton'},
        'LME铜3个月': {'factor': 1.0, 'unit': 'USD/ton'},  # 适配历史数据返回名称
        '新加坡铁矿石': {'factor': 1.0, 'unit': 'USD/ton'},
        'LME铝': {'factor': 1.0, 'unit': 'USD/ton'},
        'LME镍': {'factor': 1.0, 'unit': 'USD/ton'},
        'LME锌': {'factor': 1.0, 'unit': 'USD/ton'},
        'NYMEX天然气': {'factor': 1.0, 'unit': 'USD/MMBtu'},
        'COMEX白银': {'factor': 1.0, 'unit': 'USD/oz'},
        '伦敦银': {'factor': 1.0, 'unit': 'USD/oz'},
        'CBOT大豆': {'factor': 1.0, 'unit': 'USD/bushel'},
        'CBOT玉米': {'factor': 1.0, 'unit': 'USD/bushel'},
        'CBOT小麦': {'factor': 1.0, 'unit': 'USD/bushel'},
        'NYBOT棉花': {'factor': 1.0, 'unit': 'USD/lb'},
        '美国原糖': {'factor': 1.0, 'unit': 'USD/lb'},
        'EUA碳排放权': {'factor': 1.0, 'unit': 'EUR/ton'},
        '欧洲碳排放': {'factor': 1.0, 'unit': 'EUR/ton'},  # 适配实时数据返回名称
    }
    
    # ─────────────────────────────────────────────────────────────
    # 实时数据字段映射（适配AkShare返回列名）
    # ─────────────────────────────────────────────────────────────
    REALTIME_FIELD_MAP = {
        'name': '名称',
        'price': '最新价',
        'price_cny': '人民币报价',
        'change': '涨跌额',
        'change_pct': '涨跌幅',
        'open': '开盘价',
        'high': '最高价',
        'low': '最低价',
        'prev_close': '昨日结算价',
        'volume': '持仓量',
        'bid': '买价',
        'ask': '卖价',
        'update_time': '行情时间',
        'update_date': '日期',
    }
    
    # ─────────────────────────────────────────────────────────────
    # 历史数据字段映射（适配AkShare返回列名）
    # ─────────────────────────────────────────────────────────────
    HISTORY_FIELD_MAP = {
        'date': 'date',
        'open': 'open',
        'high': 'high',
        'low': 'low',
        'close': 'close',
        'volume': 'volume',
        'position': 'position',
    }
    
    def __init__(self, timeout: int = 30, retry_times: int = 3, 
                 realtime_cache_ttl: int = 300, history_cache_ttl: int = 3600):
        """
        初始化外部数据接口
        
        参数:
            timeout: 请求超时时间（秒）
            retry_times: 重试次数
            realtime_cache_ttl: 实时数据缓存有效期（秒）
            history_cache_ttl: 历史数据缓存有效期（秒，默认1小时）
        """
        self.timeout = timeout
        self.retry_times = retry_times
        self._realtime_cache_ttl = realtime_cache_ttl
        self._history_cache_ttl = history_cache_ttl
        
        # 分离缓存：实时数据 & 历史数据
        self._realtime_cache: Dict[str, Dict] = {}
        self._history_cache: Dict[str, Dict] = {}
        self._cache_lock = threading.RLock()
        
        # 历史数据请求频率限制（避免触发限流）
        self._last_history_request: Dict[str, float] = {}
        self._history_request_interval = 1.0  # 秒
        
        logger.info(f"✅ ExternalAPI 初始化成功 | timeout={timeout}s, retry={retry_times}")
        logger.info(f"   缓存配置: 实时={realtime_cache_ttl}s, 历史={history_cache_ttl}s")
    
    # ═════════════════════════════════════════════════════════════
    # 【实时数据接口】
    # ═════════════════════════════════════════════════════════════
    
    def get_futures_realtime(self, code: str, use_cache: bool = True) -> Optional[Dict[str, Any]]:
        """
        获取外盘期货实时数据（单品种）
        
        参数:
            code: 配置中的代码（如 'OIL', 'GC'）
            use_cache: 是否使用缓存
        
        返回:
            Dict: 标准化数据，失败返回 None
        """
        if use_cache:
            cache_key = f"realtime_{code}"
            cached = self._get_cached(cache_key, self._realtime_cache, self._realtime_cache_ttl)
            if cached:
                logger.debug(f"✅ 实时缓存命中: {code}")
                return cached
        
        ak_symbol = self.FUTURES_SYMBOL_MAP.get(code)
        if not ak_symbol:
            logger.error(f"❌ 未知外部期货代码: {code}")
            return None
        
        for attempt in range(self.retry_times):
            try:
                logger.info(f"🔄 请求实时数据: {code} -> {ak_symbol} (尝试 {attempt+1}/{self.retry_times})")
                import akshare as ak
                
                # AkShare 实时接口：symbol 传配置代码
                df = ak.futures_foreign_commodity_realtime(symbol=code)
                
                if df is None or df.empty:
                    logger.warning(f"⚠️ AkShare 返回空数据: {ak_symbol}")
                    if attempt < self.retry_times - 1:
                        time.sleep(1)
                    continue
                
                # 多品种返回时，按名称匹配当前品种
                row = self._find_row_by_symbol(df, ak_symbol)
                if row is None:
                    logger.warning(f"⚠️ 未找到品种 {ak_symbol} 的实时数据")
                    return None
                
                result = self._standardize_realtime_data(code, ak_symbol, row)
                
                if use_cache:
                    self._set_cached(f"realtime_{code}", result, self._realtime_cache)
                
                logger.info(f"✅ 实时数据获取成功: {code} | 价格={result['price']} {result['unit']}")
                return result
                
            except ImportError:
                logger.error("❌ akshare 未安装，请执行: pip install akshare")
                return None
            except Exception as e:
                logger.warning(f"⚠️ 实时请求失败 (尝试 {attempt+1}): {type(e).__name__}: {e}")
                if attempt < self.retry_times - 1:
                    time.sleep(min(2 ** attempt, 10))
                else:
                    logger.error(f"❌ 实时数据获取失败 {code}: {e}")
                    return None
        return None
    
    def get_futures_realtime_batch(self, codes: List[str], use_cache: bool = True,
                                   delay: float = 0.3) -> Dict[str, Dict]:
        """
        批量获取外盘期货实时数据
        
        参数:
            codes: 代码列表，如 ['OIL', 'GC', 'CAD']
            use_cache: 是否使用缓存
            delay: 请求间隔（秒），避免限流
        
        返回:
            Dict[code -> data]
        """
        results = {}
        failed = []
        
        # 优化：尝试一次性请求多品种（AkShare支持逗号分隔）
        valid_codes = [c for c in codes if c in self.FUTURES_SYMBOL_MAP]
        if len(valid_codes) >= 2:
            try:
                import akshare as ak
                symbol_str = ','.join(valid_codes)
                logger.info(f"🔄 批量请求实时数据: {symbol_str}")
                df = ak.futures_foreign_commodity_realtime(symbol=symbol_str)
                
                if df is not None and not df.empty:
                    for code in valid_codes:
                        ak_symbol = self.FUTURES_SYMBOL_MAP[code]
                        row = self._find_row_by_symbol(df, ak_symbol)
                        if row is not None:
                            result = self._standardize_realtime_data(code, ak_symbol, row)
                            if use_cache:
                                self._set_cached(f"realtime_{code}", result, self._realtime_cache)
                            results[code] = result
                            logger.debug(f"✅ 批量实时: {code} 成功")
                        else:
                            failed.append(code)
                    logger.info(f"✅ 批量实时完成: {len(results)}/{len(valid_codes)} 成功")
                    return results
            except Exception as e:
                logger.warning(f"⚠️ 批量实时请求失败，降级为单品种轮询: {e}")
        
        # 降级：单品种轮询
        for i, code in enumerate(codes):
            data = self.get_futures_realtime(code, use_cache=use_cache)
            if data:
                results[code] = data
            else:
                failed.append(code)
            if i < len(codes) - 1:
                time.sleep(delay)
        
        logger.info(f"✅ 批量实时完成: {len(results)}/{len(codes)} 成功")
        if failed:
            logger.warning(f"⚠️ 失败代码: {failed}")
        return results
    
    def _find_row_by_symbol(self, df: pd.DataFrame, symbol_name: str) -> Optional[pd.Series]:
        """在实时数据DataFrame中查找指定品种的行"""
        # 精确匹配
        mask = df['名称'] == symbol_name
        if mask.any():
            return df[mask].iloc[0]
        # 模糊匹配（处理"3个月"等后缀差异）
        mask = df['名称'].astype(str).str.contains(symbol_name.replace('3个月', ''), na=False)
        if mask.any():
            return df[mask].iloc[0]
        return None
    
    def _standardize_realtime_data(self, code: str, ak_symbol: str, row: pd.Series) -> Dict[str, Any]:
        """标准化实时数据格式"""
        unit_config = self.UNIT_CONVERT.get(ak_symbol, {'factor': 1.0, 'unit': 'unknown'})
        
        def _safe_float(val: Any, default: float = 0.0) -> float:
            if val is None or pd.isna(val):
                return default
            try:
                return float(str(val).replace('%', ''))
            except (ValueError, TypeError):
                return default
        
        price_raw = _safe_float(row.get(self.REALTIME_FIELD_MAP['price'], 0))
        price = price_raw * unit_config['factor']
        
        change_pct_raw = _safe_float(row.get(self.REALTIME_FIELD_MAP['change_pct'], 0))
        change_pct = change_pct_raw / 100 if abs(change_pct_raw) > 1 else change_pct_raw  # 兼容百分比/小数
        
        return {
            'code': code,
            'name': row.get(self.REALTIME_FIELD_MAP['name'], ak_symbol),
            'price': price,
            'price_cny': _safe_float(row.get(self.REALTIME_FIELD_MAP['price_cny'])),
            'change': _safe_float(row.get(self.REALTIME_FIELD_MAP['change'])),
            'change_pct': change_pct,
            'open': _safe_float(row.get(self.REALTIME_FIELD_MAP['open'])),
            'high': _safe_float(row.get(self.REALTIME_FIELD_MAP['high'])),
            'low': _safe_float(row.get(self.REALTIME_FIELD_MAP['low'])),
            'prev_close': _safe_float(row.get(self.REALTIME_FIELD_MAP['prev_close'])),
            'volume': _safe_float(row.get(self.REALTIME_FIELD_MAP['volume'])),
            'bid': _safe_float(row.get(self.REALTIME_FIELD_MAP['bid'])),
            'ask': _safe_float(row.get(self.REALTIME_FIELD_MAP['ask'])),
            'update_time': str(row.get(self.REALTIME_FIELD_MAP['update_time'], '')),
            'update_date': str(row.get(self.REALTIME_FIELD_MAP['update_date'], '')),
            'unit': unit_config['unit'],
            'source': 'akshare',
            'raw_symbol': ak_symbol,
            'fetch_time': datetime.now().isoformat()
        }
    
    # ═════════════════════════════════════════════════════════════
    # 【历史数据接口 - 新增核心功能】
    # ═════════════════════════════════════════════════════════════
    
    def get_futures_history(self, code: str, start_date: Optional[str] = None,
                           end_date: Optional[str] = None, adjust: bool = True,
                           use_cache: bool = True) -> Optional[pd.DataFrame]:
        """
        获取外盘期货历史日线数据
        
        参数:
            code: 配置代码（如 'OIL', 'GC'）
            start_date: 起始日期 'YYYY-MM-DD'，默认获取全部可用数据
            end_date: 结束日期 'YYYY-MM-DD'，默认至今日
            adjust: 是否自动计算涨跌额/涨跌幅（基于close列）
            use_cache: 是否使用缓存
        
        返回:
            pd.DataFrame: 标准化历史数据，索引为date，包含OHLCV等字段
                         失败返回 None
        """
        ak_symbol = self.FUTURES_SYMBOL_MAP.get(code)
        if not ak_symbol:
            logger.error(f"❌ 未知外部期货代码: {code}")
            return None
        
        # 生成缓存key（含日期范围，避免不同范围请求冲突）
        cache_key = f"history_{code}_{start_date or 'all'}_{end_date or 'today'}"
        if use_cache:
            cached = self._get_cached(cache_key, self._history_cache, self._history_cache_ttl)
            if cached is not None:
                logger.debug(f"✅ 历史缓存命中: {code} [{start_date}:{end_date}]")
                return cached
        
        # 频率限制：避免短时间内重复请求同一品种
        self._apply_history_rate_limit(code)
        
        for attempt in range(self.retry_times):
            try:
                logger.info(f"🔄 请求历史数据: {code} -> {ak_symbol} (尝试 {attempt+1}/{self.retry_times})")
                import akshare as ak
                
                # AkShare 历史接口：symbol 传配置代码
                df = ak.futures_foreign_hist(symbol=code)
                
                if df is None or df.empty:
                    logger.warning(f"⚠️ AkShare 返回空历史数据: {ak_symbol}")
                    return None
                
                # 标准化处理
                result_df = self._standardize_history_data(code, ak_symbol, df)
                
                # 日期范围过滤
                if start_date or end_date:
                    result_df = self._filter_date_range(result_df, start_date, end_date)
                
                # 计算衍生指标（涨跌额/涨跌幅）
                if adjust and not result_df.empty:
                    result_df = self._calculate_derived_fields(result_df)
                
                # 缓存结果（按日期范围分段缓存）
                if use_cache and not result_df.empty:
                    self._set_cached(cache_key, result_df, self._history_cache)
                
                logger.info(f"✅ 历史数据获取成功: {code} | 行数={len(result_df)}")
                return result_df
                
            except ImportError:
                logger.error("❌ akshare 未安装，请执行: pip install akshare")
                return None
            except Exception as e:
                logger.warning(f"⚠️ 历史请求失败 (尝试 {attempt+1}): {type(e).__name__}: {e}")
                if attempt < self.retry_times - 1:
                    time.sleep(min(2 ** attempt, 10))
                else:
                    logger.error(f"❌ 历史数据获取失败 {code}: {e}")
                    return None
        return None
    
    def get_futures_history_batch(self, codes: List[str], start_date: Optional[str] = None,
                                  end_date: Optional[str] = None, adjust: bool = True,
                                  use_cache: bool = True, delay: float = 1.0) -> Dict[str, pd.DataFrame]:
        """
        批量获取外盘期货历史数据
        
        参数:
            codes: 代码列表
            start_date/end_date: 日期范围
            adjust: 是否计算衍生字段
            use_cache: 是否使用缓存
            delay: 请求间隔（秒），历史接口限流较严，建议≥1秒
        
        返回:
            Dict[code -> DataFrame]
        """
        results = {}
        failed = []
        
        for i, code in enumerate(codes):
            df = self.get_futures_history(
                code=code, start_date=start_date, end_date=end_date,
                adjust=adjust, use_cache=use_cache
            )
            if df is not None and not df.empty:
                results[code] = df
            else:
                failed.append(code)
            
            if i < len(codes) - 1:
                time.sleep(delay)
        
        logger.info(f"✅ 批量历史完成: {len(results)}/{len(codes)} 成功")
        if failed:
            logger.warning(f"⚠️ 失败代码: {failed}")
        return results
    
    def _standardize_history_data(self, code: str, ak_symbol: str, 
                                  df: pd.DataFrame) -> pd.DataFrame:
        """标准化历史数据格式"""
        if df.empty:
            return df
        
        # 重命名字段（保持与AkShare一致，便于后续扩展）
        df = df.rename(columns={k: v for k, v in self.HISTORY_FIELD_MAP.items() if k in df.columns})
        
        # 确保日期列为datetime类型
        if 'date' in df.columns:
            df['date'] = pd.to_datetime(df['date'], errors='coerce')
            df = df.dropna(subset=['date']).sort_values('date').reset_index(drop=True)
        
        # 数值列类型转换
        numeric_cols = ['open', 'high', 'low', 'close', 'volume', 'position']
        for col in numeric_cols:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
        
        # 添加元数据列
        unit_config = self.UNIT_CONVERT.get(ak_symbol, {'factor': 1.0, 'unit': 'unknown'})
        df['code'] = code
        df['name'] = ak_symbol
        df['unit'] = unit_config['unit']
        df['source'] = 'akshare'
        df['raw_symbol'] = ak_symbol
        
        # 设置日期索引
        if 'date' in df.columns:
            df = df.set_index('date')
        
        return df
    
    def _calculate_derived_fields(self, df: pd.DataFrame) -> pd.DataFrame:
        """计算衍生字段：涨跌额、涨跌幅"""
        if df.empty or 'close' not in df.columns:
            return df
        
        df = df.copy()
        # 计算前一交易日收盘价（用于计算当日涨跌）
        df['_prev_close'] = df['close'].shift(1)
        
        # 涨跌额 = 当日收盘 - 前一日收盘
        df['change'] = df['close'] - df['_prev_close']
        
        # 涨跌幅 = 涨跌额 / 前一日收盘（避免除零）
        df['change_pct'] = np.where(
            df['_prev_close'] != 0,
            df['change'] / df['_prev_close'],
            0.0
        )
        
        # 清理临时列
        df = df.drop(columns=['_prev_close'])
        
        return df
    
    def _filter_date_range(self, df: pd.DataFrame, start_date: Optional[str],
                          end_date: Optional[str]) -> pd.DataFrame:
        """按日期范围过滤数据"""
        if df.empty:
            return df
        
        df = df.copy()
        if start_date:
            df = df[df.index >= pd.to_datetime(start_date)]
        if end_date:
            df = df[df.index <= pd.to_datetime(end_date)]
        return df
    
    def _apply_history_rate_limit(self, code: str):
        """应用历史数据请求频率限制"""
        with self._cache_lock:
            last_req = self._last_history_request.get(code, 0)
            elapsed = time.time() - last_req
            if elapsed < self._history_request_interval:
                sleep_time = self._history_request_interval - elapsed
                logger.debug(f"⏱️ 历史请求限流: {code} 等待 {sleep_time:.2f}s")
                time.sleep(sleep_time)
            self._last_history_request[code] = time.time()
    
    # ═════════════════════════════════════════════════════════════
    # 【缓存管理 - 线程安全】
    # ═════════════════════════════════════════════════════════════
    
    def _get_cached(self, key: str, cache: Dict, ttl: int) -> Optional[Any]:
        """通用缓存获取方法"""
        with self._cache_lock:
            if key not in cache:
                return None
            cached = cache[key]
            if (datetime.now().timestamp() - cached.get('_cached_at', 0)) > ttl:
                del cache[key]
                logger.debug(f"🗑️ 缓存过期: {key}")
                return None
            return cached.get('data')
    
    def _set_cached(self, key: str, data: Any, cache: Dict):
        """通用缓存设置方法"""
        with self._cache_lock:
            # DataFrame缓存需特殊处理（转换为字典或pickle）
            if isinstance(data, pd.DataFrame):
                cache[key] = {
                    'data': data.to_dict(orient='split'),  # 保留索引和列名
                    '_cached_at': datetime.now().timestamp(),
                    '_type': 'dataframe'
                }
            else:
                cache[key] = {
                    'data': data,
                    '_cached_at': datetime.now().timestamp()
                }
            logger.debug(f"💾 缓存更新: {key}")
    
    def _retrieve_cached_dataframe(self, key: str, cache: Dict, ttl: int) -> Optional[pd.DataFrame]:
        """专门获取DataFrame类型的缓存"""
        with self._cache_lock:
            if key not in cache:
                return None
            cached = cache[key]
            if (datetime.now().timestamp() - cached.get('_cached_at', 0)) > ttl:
                del cache[key]
                return None
            if cached.get('_type') == 'dataframe' and 'data' in cached:
                df_dict = cached['data']
                return pd.DataFrame(**df_dict)
            return cached.get('data')
    
    def clear_cache(self, pattern: Optional[str] = None, cache_type: str = 'all'):
        """
        清空缓存
        
        参数:
            pattern: 按前缀清理
            cache_type: 'realtime' / 'history' / 'all'
        """
        with self._cache_lock:
            caches = []
            if cache_type in ['realtime', 'all']:
                caches.append(self._realtime_cache)
            if cache_type in ['history', 'all']:
                caches.append(self._history_cache)
            
            count = 0
            for cache in caches:
                if pattern:
                    keys = [k for k in cache if k.startswith(pattern)]
                    for k in keys:
                        del cache[k]
                        count += 1
                else:
                    count += len(cache)
                    cache.clear()
            
            logger.info(f"✅ 缓存清理完成: {count} items | type={cache_type}, pattern={pattern}")
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """获取缓存统计信息"""
        with self._cache_lock:
            def _count_valid(cache: Dict, ttl: int) -> Tuple[int, int]:
                now = datetime.now().timestamp()
                valid = sum(1 for v in cache.values() 
                           if (now - v.get('_cached_at', 0)) <= ttl)
                return len(cache), valid
            
            rt_total, rt_valid = _count_valid(self._realtime_cache, self._realtime_cache_ttl)
            hist_total, hist_valid = _count_valid(self._history_cache, self._history_cache_ttl)
            
            return {
                'realtime': {'total': rt_total, 'valid': rt_valid, 'ttl': self._realtime_cache_ttl},
                'history': {'total': hist_total, 'valid': hist_valid, 'ttl': self._history_cache_ttl},
                'timestamp': datetime.now().isoformat()
            }
    
    # ═════════════════════════════════════════════════════════════
    # 【工具方法】
    # ═════════════════════════════════════════════════════════════
    
    def list_supported_codes(self, category: Optional[str] = None) -> Dict[str, str]:
        """列出支持的期货代码"""
        category_map = {
            'energy': ['CL', 'OIL', 'NG'],
            'metal': ['CAD', 'HG', 'AHD', 'NID', 'ZSD', 'FEF'],
            'precious': ['GC', 'XAU', 'SI', 'XAG', 'XPT'],
            'agri': ['S', 'C', 'W', 'CT', 'RS'],
            'carbon': ['EUA'],
        }
        if category and category in category_map:
            return {k: v for k, v in self.FUTURES_SYMBOL_MAP.items() if k in category_map[category]}
        return self.FUTURES_SYMBOL_MAP.copy()
    
    def validate_code(self, code: str) -> bool:
        """校验代码是否支持"""
        return code in self.FUTURES_SYMBOL_MAP
    
    def get_symbol_info(self, code: str) -> Optional[Dict[str, str]]:
        """获取品种详细信息"""
        if code not in self.FUTURES_SYMBOL_MAP:
            return None
        ak_symbol = self.FUTURES_SYMBOL_MAP[code]
        unit_config = self.UNIT_CONVERT.get(ak_symbol, {'factor': 1.0, 'unit': 'unknown'})
        return {
            'config_code': code,
            'ak_symbol': ak_symbol,
            'unit': unit_config['unit'],
            'factor': unit_config['factor']
        }


# ─────────────────────────────────────────────────────────────
# 使用示例
# ─────────────────────────────────────────────────────────────
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format='%(asctime)s | %(levelname)s | %(message)s')
    
    adapter = AKAdapter()
    
    # ▶ 示例1：获取实时数据
    print("\n📊 实时数据示例:")
    gold_rt = adapter.get_futures_realtime('GC')
    if gold_rt:
        print(f"  {gold_rt['name']}: {gold_rt['price']} {gold_rt['unit']} "
              f"({gold_rt['change_pct']*100:+.2f}%)")

    # ▶ 示例2：获取历史数据
    print("\n📈 历史数据示例 (布伦特原油 最近5日):")
    oil_hist = adapter.get_futures_history('OIL', start_date='2026-05-15')
    if oil_hist is not None and not oil_hist.empty:
        print(oil_hist[['close', 'volume', 'change_pct']].tail(5).to_string(
            formatters={'change_pct': '{:+.2%}'.format}))

    # ▶ 示例5：缓存统计
    print("\n💾 缓存状态:")
    stats = adapter.get_cache_stats()
    print(f"  实时缓存: {stats['realtime']['valid']}/{stats['realtime']['total']}")
    print(f"  历史缓存: {stats['history']['valid']}/{stats['history']['total']}")