#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ExternalAPI：外部数据接口服务
功能：通过 AkShare 获取外盘期货/宏观数据
"""

import pandas as pd
import numpy as np
from typing import Dict, Optional, Any, List
from datetime import datetime
import logging
import time

logger = logging.getLogger(__name__)


class AKAdapter:
    """外部数据接口服务（AkShare 集成）"""
    
    # 外部期货代码映射：配置代码 -> AkShare symbol
    FUTURES_SYMBOL_MAP = {
        'OIL': '布伦特原油',
        'GC': 'COMEX 黄金',
        'CAD': 'LME 铜',
        'NG': 'NYMEX 天然气',
        'SI': 'COMEX 白银',
        'NID': 'LME 镍',
        'C': 'CBOT 玉米',
        'W': 'CBOT 小麦',
        'S': 'CBOT 大豆',
    }
    
    # 单位转换配置
    UNIT_CONVERT = {
        '布伦特原油': {'factor': 1.0, 'unit': 'USD/barrel'},
        'COMEX 黄金': {'factor': 1.0, 'unit': 'USD/oz'},
        'LME 铜': {'factor': 1.0, 'unit': 'USD/ton'},
        'NYMEX 天然气': {'factor': 1.0, 'unit': 'USD/MMBtu'},
    }
    
    def __init__(self, timeout: int = 30, retry_times: int = 3):
        """
        初始化外部数据接口
        
        参数:
            timeout: 请求超时时间（秒）
            retry_times: 重试次数
        """
        self.timeout = timeout
        self.retry_times = retry_times
        self._cache: Dict[str, Dict] = {}  # 内存缓存
        self._cache_ttl = 300  # 缓存有效期（秒）
        
        logger.info(f"✅ ExternalAPI 初始化成功 | timeout={timeout}s, retry={retry_times}")
    
    def get_futures_realtime(self, code: str) -> Optional[Dict[str, Any]]:
        """
        获取外盘期货实时数据
        
        参数:
            code: 配置中的代码（如 'OIL', 'GC'）
        
        返回:
            Dict: 标准化数据，失败返回 None
        """
        # 1. 检查内存缓存
        cache_key = f"futures_{code}"
        cached = self._get_cached(cache_key)
        if cached:
            logger.debug(f"✅ 缓存命中: {code}")
            return cached
        
        # 2. 代码映射
        ak_symbol = self.FUTURES_SYMBOL_MAP.get(code)
        if not ak_symbol:
            logger.error(f"❌ 未知外部期货代码: {code}")
            return None
        
        # 3. 调用 AkShare（带重试）
        for attempt in range(self.retry_times):
            try:
                logger.info(f"🔄 请求外部数据: {code} -> {ak_symbol} (尝试 {attempt+1}/{self.retry_times})")
                
                # 导入 akshare（延迟导入，避免未安装时崩溃）
                import akshare as ak
                
                df = ak.futures_foreign_commodity_realtime(symbol=ak_symbol)
                
                if df is None or df.empty:
                    logger.warning(f"⚠️ AkShare 返回空数据: {ak_symbol}")
                    time.sleep(1)
                    continue
                
                # 4. 数据标准化
                row = df.iloc[0]
                result = self._standardize_futures_data(code, ak_symbol, row)
                
                # 5. 存入缓存
                self._set_cached(cache_key, result)
                
                logger.info(f"✅ 外部期货获取成功: {code} | 价格={result['price']}")
                return result
                
            except ImportError:
                logger.error("❌ akshare 未安装，请执行: pip install akshare")
                return None
            except Exception as e:
                logger.warning(f"⚠️ 请求失败 (尝试 {attempt+1}): {e}")
                if attempt < self.retry_times - 1:
                    time.sleep(2 ** attempt)  # 指数退避
                else:
                    logger.error(f"❌ 外部数据获取失败 {code}: {e}")
                    return None
        
        return None
    
    def _standardize_futures_data(self, code: str, ak_symbol: str, row: pd.Series) -> Dict[str, Any]:
        """标准化期货数据格式"""
        # 获取单位转换配置
        unit_config = self.UNIT_CONVERT.get(ak_symbol, {'factor': 1.0, 'unit': 'unknown'})
        
        return {
            'code': code,
            'name': row.get('名称', ak_symbol),
            'price': float(row.get('最新价', 0)) * unit_config['factor'],
            'price_cny': float(row.get('人民币报价', 0)),
            'change': float(row.get('涨跌额', 0)),
            'change_pct': float(row.get('涨跌幅', 0)) / 100,  # 转为小数
            'open': float(row.get('开盘价', 0)),
            'high': float(row.get('最高价', 0)),
            'low': float(row.get('最低价', 0)),
            'prev_close': float(row.get('昨日结算价', 0)),
            'volume': float(row.get('持仓量', 0)),
            'bid': float(row.get('买价', 0)),
            'ask': float(row.get('卖价', 0)),
            'update_time': str(row.get('行情时间', '')),
            'update_date': str(row.get('日期', '')),
            'unit': unit_config['unit'],
            'source': 'akshare',
            'raw_symbol': ak_symbol,
            'fetch_time': datetime.now().isoformat()
        }
    
    def get_futures_batch(self, codes: List[str]) -> Dict[str, Dict]:
        """
        批量获取外部期货数据
        
        参数:
            codes: 代码列表，如 ['OIL', 'GC', 'CAD']
        
        返回:
            Dict[code -> data]
        """
        results = {}
        
        for code in codes:
            data = self.get_futures_realtime(code)
            if data:
                results[code] = data
            # 添加延迟，避免触发限流
            time.sleep(0.5)
        
        logger.info(f"✅ 批量外部期货完成: {len(results)}/{len(codes)} 成功")
        return results
    
    def _get_cached(self, key: str) -> Optional[Dict]:
        """获取缓存数据（检查有效期）"""
        if key not in self._cache:
            return None
        
        cached = self._cache[key]
        # 检查缓存是否过期
        if (datetime.now().timestamp() - cached.get('_cached_at', 0)) > self._cache_ttl:
            del self._cache[key]
            return None
        
        return cached.get('data')
    
    def _set_cached(self, key: str, data: Dict):
        """设置缓存数据"""
        self._cache[key] = {
            'data': data,
            '_cached_at': datetime.now().timestamp()
        }
    
    def clear_cache(self):
        """清空缓存"""
        self._cache.clear()
        logger.info("✅ ExternalAPI 缓存已清空")