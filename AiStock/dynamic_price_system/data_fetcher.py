#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
数据获取模块：整合 TDX 接口、外盘期货、财务数据
"""

import pandas as pd
import sqlite3
import akshare as ak
from datetime import datetime, timedelta
import logging
from config import STOCKS_CONFIG, MACRO_INDICATORS, DB_CONFIG, FILE_PATHS

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class DataFetcher:
    """数据获取器"""
    
    def __init__(self):
        self.tdx_file = FILE_PATHS['tdx_api']
        self.tdx_data = None
        self._load_tdx_data()
    
    def _load_tdx_data(self):
        """加载 TDX 接口数据"""
        try:
            self.tdx_data = pd.read_excel(self.tdx_file)
            logger.info(f"✅ TDX 数据加载成功：{len(self.tdx_data)}条记录")
        except Exception as e:
            logger.error(f"❌ TDX 数据加载失败：{e}")
            self.tdx_data = pd.DataFrame()
    
    def get_tdx_macro(self, indicator_code):
        """获取 TDX 宏观指标"""
        if self.tdx_data is None or self.tdx_data.empty:
            return None
        
        result = self.tdx_data[self.tdx_data['code'] == indicator_code]
        if not result.empty:
            return result.iloc[0]
        return None
    
    def get_stock_daily(self, code, start_date=None, end_date=None):
        """获取 A 股日线数据"""
        try:
            if start_date is None:
                start_date = (datetime.now() - timedelta(days=365)).strftime('%Y%m%d')
            if end_date is None:
                end_date = datetime.now().strftime('%Y%m%d')
            
            df = ak.stock_zh_a_hist(
                symbol=code,
                period="daily",
                start_date=start_date,
                end_date=end_date,
                adjust="qfq"
            )
            
            # 保存到数据库
            self._save_to_db(df, 'stocks_daily', code)
            
            logger.info(f"✅ {code} 日线数据获取成功：{len(df)}条")
            return df
        except Exception as e:
            logger.error(f"❌ {code} 日线数据获取失败：{e}")
            return None
    
    def get_financial_data(self, code):
        """获取财务数据"""
        try:
            # 财务指标
            finance = ak.stock_financial_analysis_indicator(symbol=code)
            
            # 估值指标
            valuation = ak.stock_value_em(symbol=code)
            
            data = {
                'finance': finance,
                'valuation': valuation,
            }
            
            # 保存到数据库
            self._save_to_db(finance, 'fundamentals', f"{code}_finance")
            
            logger.info(f"✅ {code} 财务数据获取成功")
            return data
        except Exception as e:
            logger.error(f"❌ {code} 财务数据获取失败：{e}")
            return None
    
    def get_external_futures(self, symbol):
        """获取外盘期货数据"""
        try:
            futures_map = {
                'OIL': '布伦特原油',
                'GC': 'COMEX 黄金',
                'CAD': 'LME 铜',
                'NG': 'NYMEX 天然气',
            }
            
            if symbol not in futures_map:
                return None
            
            df = ak.futures_foreign_commodity_realtime(symbol=futures_map[symbol])
            
            if not df.empty:
                price = float(df['最新价'].iloc[0])
                logger.info(f"✅ {symbol} ({futures_map[symbol]}) 价格：{price}")
                return price
            return None
        except Exception as e:
            logger.error(f"❌ {symbol} 期货数据获取失败：{e}")
            return None
    
    def get_all_macro_data(self):
        """获取所有宏观数据"""
        macro_data = {}
        
        # 外盘期货
        for key, symbol in MACRO_INDICATORS.items():
            if key in ['brent_crude', 'comex_gold', 'lme_copper', 'nymex_gas']:
                price = self.get_external_futures(symbol)
                macro_data[key] = price
            else:
                # TDX 宏观指标
                tdx_data = self.get_tdx_macro(symbol)
                if tdx_data is not None:
                    macro_data[key] = float(tdx_data.get('最新价', 0)) if '最新价' in tdx_data else None
        
        logger.info(f"✅ 宏观数据获取完成：{len(macro_data)}个指标")
        return macro_data
    
    def get_all_stocks_data(self):
        """获取所有标的日线数据"""
        stocks_data = {}
        
        for stock in STOCKS_CONFIG:
            code = stock['code']
            df = self.get_stock_daily(code)
            if df is not None:
                stocks_data[code] = df
        
        logger.info(f"✅ 所有标的数据获取完成：{len(stocks_data)}只股票")
        return stocks_data
    
    def _save_to_db(self, df, table_name, code):
        """保存数据到 SQLite 数据库"""
        try:
            db_path = DB_CONFIG.get(table_name, 'data/temp.db')
            conn = sqlite3.connect(db_path)
            df.to_sql(f"{table_name}_{code}", conn, if_exists='replace', index=False)
            conn.close()
        except Exception as e:
            logger.error(f"❌ 数据库保存失败：{e}")
    
    def load_from_db(self, table_name, code):
        """从数据库加载数据"""
        try:
            db_path = DB_CONFIG.get(table_name, 'data/temp.db')
            conn = sqlite3.connect(db_path)
            df = pd.read_sql(f"SELECT * FROM {table_name}_{code}", conn)
            conn.close()
            return df
        except Exception as e:
            logger.error(f"❌ 数据库加载失败：{e}")
            return None


# 测试
if __name__ == '__main__':
    fetcher = DataFetcher()
    
    # 测试宏观数据
    print("\n" + "="*60)
    print("测试宏观数据获取")
    print("="*60)
    macro = fetcher.get_all_macro_data()
    for k, v in macro.items():
        print(f"{k}: {v}")
    
    # 测试单只股票数据
    print("\n" + "="*60)
    print("测试股票数据获取")
    print("="*60)
    df = fetcher.get_stock_daily('600938')
    if df is not None:
        print(df.tail())