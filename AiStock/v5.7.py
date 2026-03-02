# %% [markdown]
# ##### v5.7 系统重构

# %%
"""
A 股市场状态量化系统 V5.7
五维一体决策框架：股票 + 期权 + 期货 + 商品 + 宏观
核心升级：
1. 分层架构：数据层/计算层/可视化层分离
2. 配置管理：YAML 配置文件替代硬编码
3. 商品融合：九大战略方向与商品期货映射
4. 性能优化：异步加载 + 智能缓存
5. 统一日志：生产级错误处理
"""

import pandas as pd
import numpy as np
from sqlalchemy import create_engine
from typing import Dict, List, Tuple, Optional

from datetime import datetime, timedelta
import warnings
import logging
import yaml
from pathlib import Path
from dataclasses import dataclass, field
from concurrent.futures import ThreadPoolExecutor, as_completed
import json

warnings.filterwarnings('ignore')

# %%
engS = create_engine('postgresql+psycopg://sa:11111111@10.3.18.56/tdxStocks')
engI = create_engine('postgresql+psycopg://sa:11111111@10.3.18.56/tdxIndex')
engB = create_engine('postgresql+psycopg://sa:11111111@10.3.18.56/StockBas')
engF = create_engine('postgresql+psycopg://sa:11111111@10.3.18.56/tdxFS')

# %%
# 3 ==================== 日志配置 setup_logger ====================
def setup_logger(name: str, level: str = 'INFO') -> logging.Logger:
    """统一日志配置"""
    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, level.upper()))
    
    if not logger.handlers:
        handler = logging.StreamHandler()
        formatter = logging.Formatter(
            '%(asctime)s | %(levelname)-8s | %(name)s | %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)
    
    return logger

logger = setup_logger('QuantSystemV5_7')

# %%
# 4 ==================== 配置管理 AllocationConfig SystemConfig ====================
@dataclass
class AllocationConfig:
    """配置引擎权重配置（dataclass 版）"""
    sentiment_weight: float = 0.35      # 情绪因子权重
    trend_weight: float = 0.30          # 趋势因子权重
    valuation_weight: float = 0.20      # 估值因子权重
    fund_weight: float = 0.15           # 资金因子权重
    risk_penalty_base: float = 0.10     # 风险惩罚基础值
    commodity_adjustment_max: float = 0.20  # 商品调整最大值
    micro_penalty_warning: float = 0.10     # 微盘预警惩罚
    micro_penalty_melted: float = 0.20      # 微盘熔断惩罚
    cash_weight_defensive: float = 0.15     # 防御区现金权重

@dataclass
class SystemConfig:
    """系统配置数据类"""
    # 数据库配置
    db_engine_str: str = 'postgresql+psycopg://sa:11111111@10.3.18.56/tdxIndex'
    pe_db_engine_str: str = 'postgresql+psycopg://sa:11111111@10.3.18.56/csiIndexPE'
    
    # TDX 配置
    tdx_exhq_host: str = '47.112.95.207'
    tdx_exhq_port: int = 7720
    tdx_hq_host: str = '180.153.18.170'
    tdx_hq_port: int = 7709
    
    # 系统参数
    base_date: str = field(default_factory=lambda: datetime.now().strftime('%Y-%m-%d'))
    visualize: bool = True
    use_tdx: bool = True
    degradation_mode: str = 'auto'
    cache_ttl: int = 3600  # 缓存过期时间（秒）
    max_workers: int = 5  # 并行加载线程数
    
    # 市值分层配置
    market_benchmarks: Dict = field(default_factory=lambda: {
        '大盘': {'code': '000300', 'weight': 0.40},
        '中盘': {'code': '000905', 'weight': 0.30},
        '小盘': {'code': '000852', 'weight': 0.20},
        '微盘': {'code': '932000', 'weight': 0.10}
    })
    
    # 微盘冗余配置
    micro_redundancy: Dict = field(default_factory=lambda: {
        'primary': '932000',
        'secondary': '399311'
    })
    
    # 商品 - 战略方向映射（V5.7 新增）
    commodity_strategy_map: Dict = field(default_factory=lambda: {
        'CUL8': {'directions': ['高端制造', '供应链'], 'impact_type': 'cost', 'weight': 0.10},
        'ALL8': {'directions': ['高端制造', '新能源'], 'impact_type': 'cost', 'weight': 0.08},
        'LCL8': {'directions': ['新能源', '信息技术'], 'impact_type': 'cost', 'weight': 0.12},
        'SIL8': {'directions': ['信息技术', '新能源'], 'impact_type': 'cost', 'weight': 0.10},
        'SCL8': {'directions': ['公用事业', '供应链', '传统升级'], 'impact_type': 'cost', 'weight': 0.10},
        'RBL8': {'directions': ['传统升级', '供应链'], 'impact_type': 'benefit', 'weight': 0.08},
        'ML8': {'directions': ['现代农业', '生物健康', '文化消费'], 'impact_type': 'cost', 'weight': 0.08},
        'CL8': {'directions': ['现代农业', '文化消费'], 'impact_type': 'cost', 'weight': 0.07},
        'AUL8': {'directions': ['公用事业'], 'impact_type': 'benefit', 'weight': 0.05},
    })
    
    # 九大战略方向配置
    direction_indices: Dict = field(default_factory=lambda: {
        '高端制造': ['932042', '931865', '930850', '931866', '930599'],
        '信息技术': ['931087', '930851', '930902', '931495', '931585'],
        '新能源': ['931798', '931772', '931897', '931687', '931746'],
        '生物健康': ['931140', '931152', '931992', '931166', '399812'],
        '供应链': ['931465', '931235', '930716', '930725'],
        '现代农业': ['930910', '930707', '930662', '000949'],
        '公用事业': ['000917', '000937', '930955', '932047'],
        '传统升级': ['932039', '931231', '930838', '931463'],
        '文化消费': ['931066', '931480', '930901', '930781', '931588']
    })
    
    # 基础权重配置
    base_weights: Dict = field(default_factory=lambda: {
        '高端制造': 0.28, '信息技术': 0.25, '新能源': 0.15,
        '生物健康': 0.10, '公用事业': 0.08, '供应链': 0.06,
        '传统升级': 0.04, '文化消费': 0.03, '现代农业': 0.01
    })
    
    # 高风险方向配置
    high_risk_directions: Dict = field(default_factory=lambda: {
        '文化消费': {'risk_level': 'high', 'risk_score': 75, 'cap_weight': 0.15},
        '高端制造': {'risk_level': 'medium_high', 'risk_score': 58, 'cap_weight': 0.20},
        '信息技术': {'risk_level': 'medium_high', 'risk_score': 55, 'cap_weight': 0.20},
        '现代农业': {'risk_level': 'medium', 'risk_score': 48, 'cap_weight': 0.25},
        '新能源': {'risk_level': 'medium', 'risk_score': 45, 'cap_weight': 0.25}
    })
    
    # 微盘高暴露指数
    micro_cap_indices: List = field(default_factory=lambda: [
        '930901', '931588', '930707', '930662'
    ])

    # ==================== 【新增】配置引擎权重配置 ====================
    allocation_config: AllocationConfig = field(default_factory=AllocationConfig)

    # ==================== 新增字段：风险阈值配置 ====================
    risk_thresholds: Dict = field(default_factory=lambda: {
        'pcr': {
            'warning_high': 1.3,
            'warning_low': 0.7,
            'extreme_high': 1.5,
            'extreme_low': 0.5,
            'ma_window': 5
        },
        'basis': {
            'warning': -1.5,
            'extreme': -2.0,
            'ma_window': 10
        },
        'valuation': {
            'overvalued_pe_percentile': 75,
            'undervalued_pe_percentile': 25,
            'erp_warning': 1.5,
            'erp_safe': 3.5
        },
        'volatility': {
            'warning_expansion': 1.8,
            'extreme_expansion': 2.5,
            'ma_window': 60
        },
        'liquidity': {
            'warning_shrink': 0.6,      # ⭐ 流动性收缩预警阈值
            'extreme_shrink': 0.4,      # ⭐ 极端收缩阈值
            'ma_window': 5
        },
        'correlation': {
            'micro_primary_secondary': 0.85,
            'direction_benchmark': 0.70
        }
    })
    
    # ==================== 新增字段：仓位控制配置 ====================
    position_control: Dict = field(default_factory=lambda: {
        'market_state_weights': {
            '战略进攻区': {'equity_min': 0.75, 'equity_max': 0.85, 'micro_exposure': 0.15},
            '积极配置区': {'equity_min': 0.75, 'equity_max': 0.85, 'micro_exposure': 0.15},
            '均衡持有区': {'equity_min': 0.55, 'equity_max': 0.65, 'micro_exposure': 0.10},
            '防御观望区': {'equity_min': 0.40, 'equity_max': 0.50, 'micro_exposure': 0.05},
            '战略防御区': {'equity_min': 0.20, 'equity_max': 0.30, 'micro_exposure': 0.00}
        },
        'micro_liquidity_stages': {
            'normal': {
                'exposure_cap': 0.20,
                'weight_primary': 0.6,
                'weight_secondary': 0.4
            },
            'early_warning': {
                'exposure_cap': 0.15,
                'weight_primary': 0.5,
                'weight_secondary': 0.5
            },
            'melted': {
                'exposure_cap': 0.00,
                'weight_primary': 0.0,
                'weight_secondary': 0.0
            }
        }
    })
    
    # ==================== 新增字段：宏观指标配置 ====================
    macro_indicators: Dict = field(default_factory=lambda: {
        'inflation': {'enabled': True, 'weight': 0.20, 'indicators': {}},
        'growth': {'enabled': True, 'weight': 0.25, 'indicators': {}},
        'liquidity': {'enabled': True, 'weight': 0.25, 'indicators': {}},
        'sentiment': {'enabled': True, 'weight': 0.15, 'indicators': {}},
        'external_risk': {'enabled': True, 'weight': 0.15, 'indicators': {}}
    })
    
    # ==================== 新增字段：预警规则配置 ====================
    alert_rules: List = field(default_factory=lambda: [
        {
            'name': '通胀上行预警',
            'condition': 'CPI > 3.0 AND PPI > 5.0',
            'action': 'reduce_equity_exposure',
            'priority': 'high',
            'suggested_adjustment': -0.10,
            'affected_directions': ['文化消费', '现代农业']
        }
    ])
    
    # ==================== 新增字段：期权市场配置 ====================
    option_markets: Dict = field(default_factory=lambda: {
        'cffex': {'market_code': 7, 'enabled': True, 'pcr_weight': 0.50},
        'sse': {'market_code': 8, 'enabled': True, 'pcr_weight': 0.30},
        'szse': {'market_code': 9, 'enabled': True, 'pcr_weight': 0.20}
    })

    
    @classmethod
    def from_yaml(cls, config_path: str) -> 'SystemConfig':
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                config_dict = yaml.safe_load(f)
            
            default = cls()
            
            for key, value in config_dict.items():
                if not hasattr(default, key):
                    continue
                
                # 特殊处理 allocation_config（字典 → AllocationConfig）
                if key == 'allocation_config' and isinstance(value, dict):
                    alloc_config = AllocationConfig()
                    for k, v in value.items():
                        if hasattr(alloc_config, k):
                            setattr(alloc_config, k, v)
                    setattr(default, key, alloc_config)
                else:
                    setattr(default, key, value)
            
            logger.info(f"✅ 从 {config_path} 加载配置成功")
            return default
        except Exception as e:
            logger.warning(f"⚠️ 加载配置文件失败：{str(e)}，使用默认配置")
            return cls()
    
    def to_yaml(self, config_path: str):
        """保存配置到 YAML 文件"""
        config_dict = {
            key: value for key, value in self.__dict__.items()
            if not key.startswith('_') and not callable(value)
        }
        
        with open(config_path, 'w', encoding='utf-8') as f:
            yaml.dump(config_dict, f, allow_unicode=True, default_flow_style=False)
        
        logger.info(f"✅ 配置已保存至 {config_path}")
        


# %%
# 5 ==================== 数据加载层 MataManager ====================
class DataManager:
    """统一数据加载管理器（V5.7 重构）"""
    
    def __init__(self, config: SystemConfig):
        self.config = config
        self.cache = {}  # 内存缓存
        self.cache_timestamps = {}  # 缓存时间戳
        
        # 数据库引擎
        try:
            self.engine = create_engine(config.db_engine_str)
            self.pe_engine = create_engine(config.pe_db_engine_str)
            logger.info("✅ 数据库连接初始化成功")
        except Exception as e:
            logger.error(f"❌ 数据库连接失败：{str(e)}")
            self.engine = None
            self.pe_engine = None
        
        # TDX 接口
        self.tdx_exhq = None
        self.tdx_hq = None
        if config.use_tdx:
            self._init_tdx()
    
    def _init_tdx(self):
        """初始化 TDX 接口"""
        try:
            from pytdx.hq import TdxHq_API
            from pytdx.exhq import TdxExHq_API
            
            self.tdx_exhq = TdxExHq_API()
            self.tdx_hq = TdxHq_API()
            
            self.tdx_exhq.connect(self.config.tdx_exhq_host, self.config.tdx_exhq_port)
            self.tdx_hq.connect(self.config.tdx_hq_host, self.config.tdx_hq_port)
            
            logger.info("✅ TDX 接口连接成功")
        except Exception as e:
            logger.warning(f"⚠️ TDX 接口连接失败：{str(e)}")
            self.config.use_tdx = False
    
    def _get_cache_key(self, prefix: str, **kwargs) -> str:
        """生成缓存键"""
        key_parts = [prefix] + [f"{k}={v}" for k, v in sorted(kwargs.items())]
        return "_".join(key_parts)
    
    def _is_cache_valid(self, key: str) -> bool:
        """检查缓存是否有效"""
        if key not in self.cache:
            return False
        
        if key not in self.cache_timestamps:
            return True
        
        age = (datetime.now() - self.cache_timestamps[key]).total_seconds()
        return age < self.config.cache_ttl
    
    def _set_cache(self, key: str, data):
        """设置缓存"""
        self.cache[key] = data
        self.cache_timestamps[key] = datetime.now()
    
    def load_index_data(self, index_code: str, min_days: int = 500) -> pd.DataFrame:
        """
        加载指数数据（带缓存）
        
        参数:
            index_code: 指数代码
            min_days: 最小数据天数
        返回:
            DataFrame with datetime, open, high, low, close, amount
        """
        cache_key = self._get_cache_key('index', code=index_code, days=min_days)
        
        if self._is_cache_valid(cache_key):
            logger.debug(f"✅ 使用缓存数据：{index_code}")
            return self.cache[cache_key].copy()
        
        try:
            query = f'''
            SELECT * FROM "{index_code}"
            WHERE datetime <= '{self.config.base_date}'
            ORDER BY datetime
            '''
            df = pd.read_sql(query, self.engine)
            
            if len(df) == 0:
                logger.warning(f"⚠️ 指数{index_code} 无数据")
                return pd.DataFrame()
            
            # 数据预处理
            if index_code.startswith(('399', '88')):
                df['amount'] = df['amount'] / 1000000
            
            df['datetime'] = pd.to_datetime(df['datetime'])
            df = df.sort_values('datetime').reset_index(drop=True)
            df = df.drop_duplicates(subset=['datetime'], keep='last')
            
            # 计算技术指标
            df['return_1d'] = df['close'].pct_change()
            df['volatility_20'] = df['return_1d'].rolling(20).std() * np.sqrt(250)
            df['volatility_250'] = df['return_1d'].rolling(250).std() * np.sqrt(250)
            
            # 移动平均线
            df['ma_20'] = df['close'].rolling(20).mean()
            df['ma_60'] = df['close'].rolling(60).mean()
            df['ma_120'] = df['close'].rolling(120).mean()
            
            # 成交量分析
            df['volume_ma20'] = df['amount'].rolling(20).mean()
            
            if len(df) >= min_days:
                self._set_cache(cache_key, df)
                logger.info(f"✅ 加载指数{index_code} 数据：{len(df)}条")
            
            return df
            
        except Exception as e:
            logger.error(f"❌ 加载指数{index_code} 失败：{str(e)}")
            return pd.DataFrame()
    
    def load_derivative_data(self, code: str, market_code: int, days: int = 60) -> pd.DataFrame:
        """
        加载衍生品数据（期权/期货）
        
        参数:
            code: 合约代码
            market_code: 市场代码
            days: 获取天数
        返回:
            DataFrame with datetime, open, high, low, close, volume, open_interest
        """
        cache_key = self._get_cache_key('derivative', code=code, market=market_code, days=days)
        
        if self._is_cache_valid(cache_key):
            return self.cache[cache_key].copy()
        
        # 1. TDX 接口获取
        if self.config.use_tdx and self.tdx_exhq:
            try:
                result = self.tdx_exhq.get_instrument_bars(9, market_code, code, 0, days)
                
                if result and len(result) > 0:
                    df = pd.DataFrame(result)
                    
                    # 字段重命名映射
                    column_mapping = {
                        'trade': 'volume',
                        'position': 'open_interest',
                        'amount': 'turnover',
                        'price': 'settlement'
                    }
                    df = df.rename(columns=column_mapping)
                    
                    if 'datetime' in df.columns:
                        df['datetime'] = pd.to_datetime(df['datetime'])
                    
                    required_cols = ['datetime', 'open', 'high', 'low', 'close', 
                                   'volume', 'open_interest']
                    for col in required_cols:
                        if col not in df.columns:
                            df[col] = 0
                    
                    df = df.sort_values('datetime').reset_index(drop=True)
                    df = df.dropna(subset=['close'])
                    
                    self._set_cache(cache_key, df)
                    return df
                    
            except Exception as e:
                logger.warning(f"⚠️ TDX 获取衍生品{code} 失败：{str(e)}")
        
        # 2. 降级：数据库获取
        return self._load_derivative_from_db(code, days)
    
    def _load_derivative_from_db(self, code: str, days: int = 60) -> pd.DataFrame:
        """从数据库获取衍生品数据（降级方案）"""
        try:
            query = f'''
            SELECT datetime, open, high, low, close, volume, position
            FROM "{code}"
            WHERE datetime <= '{self.config.base_date}'
            ORDER BY datetime DESC
            LIMIT {days}
            '''
            df = pd.read_sql(query, self.engine)
            
            if len(df) > 0:
                df['datetime'] = pd.to_datetime(df['datetime'])
                df = df.sort_values('datetime').reset_index(drop=True)
                df = df.rename(columns={'position': 'open_interest'})
                return df
            
            return pd.DataFrame()
            
        except Exception as e:
            logger.error(f"❌ 数据库获取衍生品{code} 失败：{str(e)}")
            return pd.DataFrame()
    
    def load_macro_data(self, code: str, days: int = 60) -> pd.DataFrame:
        """加载宏观指标数据"""
        cache_key = self._get_cache_key('macro', code=code, days=days)
        
        if self._is_cache_valid(cache_key):
            return self.cache[cache_key].copy()
        
        # TDX 接口获取
        if self.config.use_tdx and self.tdx_exhq:
            try:
                result = self.tdx_exhq.get_instrument_bars(9, 38, code, 0, days)
                
                if result and len(result) > 0:
                    df = pd.DataFrame(result)
                    
                    if 'datetime' in df.columns:
                        df['datetime'] = pd.to_datetime(df['datetime'])
                    
                    required_cols = ['datetime', 'open', 'high', 'low', 'close']
                    available_cols = [col for col in required_cols if col in df.columns]
                    df = df[available_cols].copy()
                    
                    df = df.sort_values('datetime').reset_index(drop=True)
                    df = df.dropna(subset=['close'])
                    
                    self._set_cache(cache_key, df)
                    return df
                    
            except Exception as e:
                logger.warning(f"⚠️ TDX 获取宏观指标{code} 失败：{str(e)}")
        
        # 降级：数据库获取
        return self._load_macro_from_db(code, days)
    
    def _load_macro_from_db(self, code: str, days: int = 60) -> pd.DataFrame:
        """从数据库获取宏观指标数据"""
        try:
            query = f'''
            SELECT datetime, open, high, low, close
            FROM "{code}"
            WHERE datetime <= '{self.config.base_date}'
            ORDER BY datetime DESC
            LIMIT {days}
            '''
            df = pd.read_sql(query, self.engine)
            
            if len(df) > 0:
                df['datetime'] = pd.to_datetime(df['datetime'])
                df = df.sort_values('datetime').reset_index(drop=True)
                return df
            
            return pd.DataFrame()
            
        except Exception as e:
            logger.error(f"❌ 数据库获取宏观指标{code} 失败：{str(e)}")
            return pd.DataFrame()
    
    def load_pe_data(self, index_code: str) -> pd.DataFrame:
        """加载指数 PE 历史数据"""
        cache_key = self._get_cache_key('pe', code=index_code)
        
        if self._is_cache_valid(cache_key):
            return self.cache[cache_key].copy()
        
        try:
            if self.pe_engine is None:
                return pd.DataFrame()
            
            df_hist = pd.read_sql(index_code, self.pe_engine)
            
            if len(df_hist) >= 500 and '滚动市盈率' in df_hist.columns:
                df_hist = df_hist.rename(columns={'日期': 'date', '滚动市盈率': 'pe_ttm'})
                df_hist['date'] = pd.to_datetime(df_hist['date'])
                result = df_hist[['date', 'pe_ttm']].copy()
                
                self._set_cache(cache_key, result)
                return result
            
            return pd.DataFrame()
            
        except Exception as e:
            logger.warning(f"⚠️ {index_code} PE 数据获取失败：{str(e)}")
            return pd.DataFrame()
    
    def preload_all(self, parallel: bool = True):
        """
        预加载所有基准数据
        
        参数:
            parallel: 是否并行加载
        """
        logger.info("🔄 开始预加载数据...")
        
        # 加载市值基准
        benchmark_codes = [v['code'] for v in self.config.market_benchmarks.values()]
        micro_codes = list(self.config.micro_redundancy.values())
        all_codes = list(set(benchmark_codes + micro_codes))
        
        if parallel:
            with ThreadPoolExecutor(max_workers=self.config.max_workers) as executor:
                futures = {
                    executor.submit(self.load_index_data, code, 500): code
                    for code in all_codes
                }
                
                for future in as_completed(futures):
                    code = futures[future]
                    try:
                        df = future.result()
                        if len(df) > 0:
                            logger.info(f"✅ 预加载完成：{code} ({len(df)}条)")
                    except Exception as e:
                        logger.error(f"❌ 预加载{code} 失败：{str(e)}")
        else:
            for code in all_codes:
                df = self.load_index_data(code, 500)
                if len(df) > 0:
                    logger.info(f"✅ 预加载完成：{code} ({len(df)}条)")
        
        logger.info("✅ 数据预加载完成")
    
    def clear_cache(self):
        """清空缓存"""
        self.cache.clear()
        self.cache_timestamps.clear()
        logger.info("✅ 缓存已清空")

# %%
# 6 ==================== 风险引擎层 RiskEngin ====================
"""
V5.7 风险引擎 - 微盘熔断 + 风险传导 + 预警规则
"""
class RiskEngine:
    """风险评估与熔断引擎"""
    
    def __init__(self, data_manager: DataManager, config: SystemConfig):
        self.dm = data_manager
        self.config = config
        self.logger = setup_logger('RiskEngine')
    
    def assess_micro_liquidity(self, df_primary: pd.DataFrame, 
                              df_secondary: Optional[pd.DataFrame] = None) -> Dict:
        """
        V5.7 核心：微盘层三阶段熔断机制
        返回: {'status': 'normal/early_warning/warning/invalid', ...}
        """
        if len(df_primary) < 20:
            return self._build_invalid_response('主指数数据不足（需≥20日）')
        
        try:
            # 1. 流动性失真检测（成交量比率）
            volume_ma5 = df_primary['amount'].rolling(5).mean().replace(0, np.nan)
            volume_ratio_5d = (df_primary['amount'] / volume_ma5).fillna(1.0)
            
            # 预警阈值：低于5日均量60%
            volume_distortion = volume_ratio_5d < self.config.risk_thresholds['liquidity']['warning_shrink']
            
            # 2. 波动率扩张检测
            if 'volatility_20' in df_primary.columns and len(df_primary) >= 250:
                vol_250_ma = df_primary['volatility_20'].rolling(250).mean().replace(0, np.nan)
                vol_expansion_ratio = (df_primary['volatility_20'] / vol_250_ma).fillna(1.0)
                
                # 预警阈值：波动率扩张1.8倍
                vol_distortion = vol_expansion_ratio > self.config.risk_thresholds['volatility']['warning_expansion']
                liquidity_distorted = volume_distortion & vol_distortion
            else:
                liquidity_distorted = volume_distortion
            
            # 3. 三阶段判定
            distorted_days = int(liquidity_distorted.astype(int).sum())
            
            if distorted_days == 0:
                status, stage, risk_level = 'normal', '正常期', 'low'
                flag = '✓ 流动性正常'
                exposure_cap = self.config.position_control['micro_liquidity_stages']['normal']['exposure_cap']
            elif distorted_days < 5:
                status, stage, risk_level = 'early_warning', '观察期', 'medium'
                flag = f'⚠️ 轻微失真（持续{distorted_days}日）'
                exposure_cap = self.config.position_control['micro_liquidity_stages']['early_warning']['exposure_cap']
            else:
                status, stage, risk_level = 'warning', '熔断期', 'high'
                flag = f'🔴 严重失真（持续{distorted_days}日）'
                exposure_cap = self.config.position_control['micro_liquidity_stages']['melted']['exposure_cap']
            
            # 4. 次要指数验证（可选）
            secondary_distorted = False
            if df_secondary is not None and len(df_secondary) >= 20:
                sec_volume_ratio = df_secondary['amount'] / df_secondary['amount'].rolling(5).mean().replace(0, np.nan)
                secondary_distorted = (sec_volume_ratio < 0.6).iloc[-1]
            
            return {
                'status': status,
                'stage': stage,
                'days_in_stage': distorted_days,
                'risk_level': risk_level,
                'primary_distorted': bool(liquidity_distorted.iloc[-1]),
                'secondary_distorted': secondary_distorted,
                'volume_ratio_latest': float(volume_ratio_5d.iloc[-1]),
                'distortion_flag': flag,
                'exposure_cap': exposure_cap,
                'weight_primary': self.config.position_control['micro_liquidity_stages'][status]['weight_primary'],
                'weight_secondary': self.config.position_control['micro_liquidity_stages'][status]['weight_secondary'],
                'timestamp': datetime.now()
            }
            
        except Exception as e:
            self.logger.error(f"❌ 微盘流动性评估失败：{str(e)}")
            return self._build_invalid_response(f'计算异常：{str(e)}')
    
    def _build_invalid_response(self, reason: str) -> Dict:
        """构建无效响应"""
        return {
            'status': 'invalid',
            'stage': '数据失效',
            'days_in_stage': 0,
            'risk_level': 'high',
            'primary_distorted': True,
            'secondary_distorted': True,
            'volume_ratio_latest': np.nan,
            'distortion_flag': f'✗ 微盘信号失效 | {reason}',
            'exposure_cap': 0.0,
            'weight_primary': 0.5,
            'weight_secondary': 0.5,
            'timestamp': datetime.now()
        }
    
    def calculate_risk_transmission(self, benchmark_data: Dict) -> Dict:
        """
        计算四层市值风险传导路径
        返回: {'微盘': {...}, '小盘': {...}, '中盘': {...}, '大盘': {...}}
        """
        risk_metrics = {}
        layer_order = ['微盘', '小盘', '中盘', '大盘']
        
        for size in layer_order:
            if size not in benchmark_data:
                continue
            
            df = benchmark_data[size]
            if len(df) < 20:
                continue
            
            # 1. 波动率扩张（相对250日均值）
            if 'volatility_20' in df.columns and len(df) >= 250:
                current_vol = df['volatility_20'].iloc[-1]
                vol_250_ma = df['volatility_20'].rolling(250).mean().iloc[-1]
                vol_expansion = current_vol / vol_250_ma if vol_250_ma > 0 else 1.0
                vol_expansion_score = min(100, (vol_expansion - 1.0) * 100)
            else:
                vol_expansion_score = 50.0
                vol_expansion = 1.0
            
            # 2. 流动性评分（成交量分位数）
            if 'volume_ma20' in df.columns and len(df) >= 250:
                current_vol_ma = df['volume_ma20'].iloc[-1]
                vol_percentile = (df['volume_ma20'].iloc[-250:-1] < current_vol_ma).mean()
                liquidity_score = 100 - vol_percentile * 100
            else:
                liquidity_score = 50.0
            
            # 3. 20日收益
            if len(df) >= 20:
                return_20d = (df['close'].iloc[-1] / df['close'].iloc[-20] - 1) * 100
            else:
                return_20d = 0.0
            
            # 4. 综合风险得分（波动率40% + 流动性30% + 收益30%）
            risk_score = (
                vol_expansion_score * 0.4 +
                liquidity_score * 0.3 +
                (50 - return_20d) * 0.3  # 收益为负时风险高
            )
            risk_score = np.clip(risk_score, 0, 100)
            
            risk_metrics[size] = {
                '风险得分': float(risk_score),
                '波动率扩张': float(vol_expansion),
                '流动性': float(liquidity_score / 100),
                '20日收益': float(return_20d),
                '波动率得分': float(vol_expansion_score),
                '流动性得分': float(liquidity_score)
            }
        
        return risk_metrics
    
    def generate_risk_alerts(self, market_state: str, pcr_data: Dict, 
                           micro_liquidity: Dict, basis_data: Dict) -> List[str]:
        """
        生成风险预警信号（融合多维度）
        """
        alerts = []
        
        # 1. 微盘熔断预警（最高优先级）
        if micro_liquidity.get('status') == 'warning':
            alerts.insert(0, 
                f"🔴 微盘熔断 | {micro_liquidity['distortion_flag']} | "
                f"建议：微盘暴露降至{micro_liquidity['exposure_cap']*100:.0f}%"
            )
        elif micro_liquidity.get('status') == 'early_warning':
            alerts.insert(0,
                f"🟡 微盘预警 | {micro_liquidity['distortion_flag']} | "
                f"建议：微盘暴露降至{micro_liquidity['exposure_cap']*100:.0f}%"
            )
        
        # 2. 期权情绪预警
        composite_pcr = pcr_data.get('composite', {}).get('pcr', 1.0)
        if composite_pcr > self.config.risk_thresholds['pcr']['warning_high']:
            alerts.append(
                f"🔴 期权情绪预警 | 综合PCR={composite_pcr:.2f}（看跌）| "
                f"建议：降低权益仓位"
            )
        elif composite_pcr < self.config.risk_thresholds['pcr']['warning_low']:
            alerts.append(
                f"✅ 期权情绪乐观 | 综合PCR={composite_pcr:.2f}（看涨）| "
                f"建议：可适度加仓"
            )
        
        # 3. 期货基差预警
        if_basis_pct = basis_data.get('if_basis', {}).get('percent', 0)
        if if_basis_pct < self.config.risk_thresholds['basis']['warning']:
            severity = '深度贴水' if if_basis_pct < self.config.risk_thresholds['basis']['extreme'] else '贴水'
            alerts.append(
                f"⚠️ 期货{severity} | IF基差={if_basis_pct:.1f}% | "
                f"建议：关注市场情绪"
            )
        
        # 4. 市场状态建议
        if not alerts:
            if market_state in ['战略进攻区', '积极配置区']:
                alerts.append(
                    f"✅ 积极信号 | 市场处于{market_state} | "
                    f"建议：权益仓位75-85%"
                )
            else:
                alerts.append(
                    "✅ 中性信号 | 当前市场无显著风险 | "
                    "建议：维持基准配置"
                )
        
        return alerts[:5]

# %%
# 7 ==================== 宏观引擎层 MacroEngine ====================
"""
V5.7 宏观引擎 - 多维度宏观指标综合评分
"""
class MacroEngine:
    """宏观指标分析引擎"""
    
    def __init__(self, data_manager: DataManager, config: SystemConfig):
        self.dm = data_manager
        self.config = config
        self.logger = setup_logger('MacroEngine')
    
    def calculate_macro_composite_score(self) -> Dict:
        """
        计算宏观综合评分（五维加权）
        返回: {
            'composite_score': float,
            'category_scores': {'inflation': ..., 'growth': ...},
            'alerts': List[Dict],
            'timestamp': datetime
        }
        """
        # 1. 加载各指标最新数据
        indicator_values = {}
        category_scores = {}
        
        for category, cat_config in self.config.macro_indicators.items():
            if not cat_config.get('enabled', False):
                continue
            
            category_weight = cat_config.get('weight', 0.2)
            indicators = cat_config.get('indicators', {})
            
            # 计算该分类得分
            cat_score_sum = 0
            cat_weight_sum = 0
            
            for ind_name, ind_config in indicators.items():
                code = ind_config.get('code')
                weight = ind_config.get('weight', 1.0)
                direction = ind_config.get('direction', 'positive')
                
                # 加载数据
                df = self.dm.load_macro_data(code, days=30)
                if len(df) > 0:
                    value = df['close'].iloc[-1]
                    indicator_values[ind_name] = float(value)
                    
                    # 根据阈值计算得分（0-100）
                    score = self._calculate_indicator_score(
                        value, ind_config, direction
                    )
                    cat_score_sum += score * weight
                    cat_weight_sum += weight
            
            # 分类综合得分
            if cat_weight_sum > 0:
                category_scores[category] = {
                    'score': float(cat_score_sum / cat_weight_sum),
                    'weight': category_weight,
                    'indicators': indicator_values
                }
        
        # 2. 计算综合评分（加权平均）
        composite_score = 0
        total_weight = 0
        
        for cat_name, cat_data in category_scores.items():
            composite_score += cat_data['score'] * cat_data['weight']
            total_weight += cat_data['weight']
        
        if total_weight > 0:
            composite_score /= total_weight
        
        # 3. 检查预警规则
        alerts = self._check_alert_rules(indicator_values)
        
        # 4. 判定市场状态
        market_state = self._determine_market_state_from_macro(composite_score)
        
        return {
            'composite_score': float(composite_score),
            'category_scores': category_scores,
            'alerts': alerts,
            'market_state': market_state,
            'indicator_values': indicator_values,
            'timestamp': datetime.now()
        }
    
    def _calculate_indicator_score(self, value: float, config: Dict, 
                                   direction: str) -> float:
        """根据指标值和阈值计算得分（0-100）"""
        thresholds = config.get('thresholds', {})
        
        if direction == 'positive':
            # 正向指标：值越大越好
            if 'extreme_high' in thresholds and value >= thresholds['extreme_high']:
                return 90.0
            elif 'warning_high' in thresholds and value >= thresholds['warning_high']:
                return 75.0
            elif 'warning_low' in thresholds and value >= thresholds['warning_low']:
                return 50.0
            elif 'extreme_low' in thresholds and value >= thresholds['extreme_low']:
                return 30.0
            else:
                return 10.0
        else:
            # 负向指标：值越小越好
            if 'extreme_low' in thresholds and value <= thresholds['extreme_low']:
                return 90.0
            elif 'warning_low' in thresholds and value <= thresholds['warning_low']:
                return 75.0
            elif 'warning_high' in thresholds and value <= thresholds['warning_high']:
                return 50.0
            elif 'extreme_high' in thresholds and value <= thresholds['extreme_high']:
                return 30.0
            else:
                return 10.0
    
    def _check_alert_rules(self, indicator_values: Dict) -> List[Dict]:
        """检查预警规则"""
        alerts = []
        
        for rule in self.config.alert_rules:
            condition = rule.get('condition', '')
            
            # 简化条件解析（实际应使用表达式解析器）
            try:
                # 替换指标名为实际值
                eval_condition = condition
                for ind_name, value in indicator_values.items():
                    eval_condition = eval_condition.replace(ind_name, str(value))
                
                # 评估条件
                if eval(eval_condition):
                    alerts.append({
                        'name': rule.get('name', '预警'),
                        'condition': condition,
                        'action': rule.get('action', 'notify'),
                        'priority': rule.get('priority', 'medium'),
                        'suggested_adjustment': rule.get('suggested_adjustment', 0.0),
                        'affected_directions': rule.get('affected_directions', []),
                        'message': f"{rule.get('name')} | 条件：{condition}"
                    })
            except Exception as e:
                self.logger.warning(f"预警规则评估失败：{str(e)}")
        
        # 按优先级排序
        priority_map = {'high': 3, 'medium': 2, 'low': 1}
        alerts.sort(key=lambda x: priority_map.get(x['priority'], 0), reverse=True)
        
        return alerts[:5]
    
    def _determine_market_state_from_macro(self, composite_score: float) -> str:
        """根据宏观综合评分判定市场状态"""
        thresholds = self.config.composite_scoring.get('market_state_thresholds', {})
        
        if composite_score >= thresholds.get('strategic_offense', 80):
            return '战略进攻区'
        elif composite_score >= thresholds.get('active_allocation', 65):
            return '积极配置区'
        elif composite_score >= thresholds.get('balanced_hold', 50):
            return '均衡持有区'
        elif composite_score >= thresholds.get('defensive_watch', 35):
            return '防御观望区'
        else:
            return '战略防御区'



# %%
# 8 ==================== 期权分析器层 OptionPCRAnalyzer ====================
class OptionPCRAnalyzer:
    """
    期权 PCR 情绪指标分析器 ⭐ V5.7 优化版
    
    基于 TDX 接口获取期权数据，动态识别合约，计算 PCR 情绪指标
    """
    
    def __init__(self, engine, base_date: str = '2026-02-14',
                 tdx_host: str = '47.112.95.207', tdx_port: int = 7720):
        """
        初始化 PCR 分析器
        
        参数:
        engine: SQLAlchemy 数据库引擎（用于加载 tdxAPIcode 映射表）
        base_date: 基准日期
        tdx_host: TDX 扩展行情服务器地址
        tdx_port: TDX 扩展行情服务器端口
        """
        self.engine = engine
        self.base_date = pd.to_datetime(base_date)
        self.tdx_host = tdx_host
        self.tdx_port = tdx_port
        self.option_codes = None
        self.pcr_cache = {}
        
        # TDX 接口
        self.tdx_exhq = None
        self._init_tdx()
        
        # 从数据库加载期权代码映射表
        self._load_option_codes()
    
    def _init_tdx(self):
        """初始化 TDX 扩展行情接口"""
        try:
            from pytdx.hq import TdxHq_API
            from pytdx.exhq import TdxExHq_API
            
            self.tdx_exhq = TdxExHq_API()
            self.tdx_exhq.connect(self.tdx_host, self.tdx_port)
            
            print(f"✅ TDX 扩展行情接口连接成功 | {self.tdx_host}:{self.tdx_port}")
            
        except ImportError:
            print("❌ pytdx 未安装，请执行: pip install pytdx")
            self.tdx_exhq = None
            
        except Exception as e:
            print(f"⚠️ TDX 连接失败：{str(e)}")
            self.tdx_exhq = None
    
    def _load_option_codes(self):
        """从数据库加载期权代码映射表 ⭐ 核心优化"""
        try:
            # 加载 tdxAPIcode 表
            query = '''
            SELECT code, code_name, market_code, market_name, category
            FROM "tdxAPIcode"
            WHERE category = 12  -- 只加载期权类数据
            '''
            self.option_codes = pd.read_sql(query, self.engine)
            
            # 数据清洗
            self.option_codes['code'] = self.option_codes['code'].astype(str).str.strip()
            self.option_codes['code_name'] = self.option_codes['code_name'].astype(str).str.strip()
            self.option_codes['market_code'] = self.option_codes['market_code'].astype(int)
            
            # 提取标的代码
            self.option_codes['underlying'] = self.option_codes['code_name'].apply(
                self._extract_underlying
            )
            
            # 提取到期年月
            self.option_codes['expiry_month'] = self.option_codes['code_name'].apply(
                self._extract_expiry_month
            )
            
            # 提取期权类型
            self.option_codes['option_type'] = self.option_codes['code_name'].apply(
                self._extract_option_type
            )
            
            # 提取行权价
            self.option_codes['strike_price'] = self.option_codes['code_name'].apply(
                self._extract_strike_price
            )
            
            print(f"✅ 成功加载 {len(self.option_codes)} 个期权合约")
            print(f"   ⭐ TDX 数据源：{self.tdx_host}:{self.tdx_port}")
            print(f"   中金所期权：{len(self.option_codes[self.option_codes['market_code']==7])}个")
            print(f"   个股期权：{len(self.option_codes[self.option_codes['market_code']==8])}个")
            print(f"   深圳期权：{len(self.option_codes[self.option_codes['market_code']==9])}个")
            
        except Exception as e:
            print(f"⚠️ 加载期权代码失败：{str(e)}")
            self.option_codes = pd.DataFrame()
    
    def _extract_underlying(self, code_name: str) -> str:
        """提取标的代码"""
        # 中金所期权
        if code_name.startswith('IO'):
            return 'IO'  # 沪深 300 指数
        elif code_name.startswith('HO'):
            return 'HO'  # 上证 50 指数
        elif code_name.startswith('MO'):
            return 'MO'  # 中证 1000 指数
        # ETF 期权
        elif len(code_name) >= 6:
            return code_name[:6]  # ETF 代码
        return 'UNKNOWN'
    
    def _extract_expiry_month(self, code_name: str) -> str:
        """提取到期年月 ⭐ 修复版"""
        # 中金所期权：IO2602-C-4000 → 2602
        if '-' in code_name:
            parts = code_name.split('-')
            if len(parts) >= 2:
                return parts[0][-4:]  # 取后4位年月
        
        # ETF期权和深圳期权：找到C或P的位置
        type_idx = -1
        if 'C' in code_name:
            type_idx = code_name.find('C')
        elif 'P' in code_name:
            type_idx = code_name.find('P')
        
        if type_idx != -1 and len(code_name) > type_idx + 1:
            # 提取C/P后的数字部分
            suffix = code_name[type_idx+1:]
            # 提取连续的数字
            month_digits = ''
            for char in suffix:
                if char.isdigit():
                    month_digits += char
                elif month_digits:  # 已经有数字了，遇到非数字就停止
                    break
            
            if month_digits:
                # 如果是2位数字，直接返回（月份）
                if len(month_digits) >= 2:
                    return month_digits[:2]
                else:
                    return month_digits
        
        return '00'
    
    def _extract_option_type(self, code_name: str) -> str:
        """提取期权类型"""
        if 'C' in code_name:
            return 'call'
        elif 'P' in code_name:
            return 'put'
        return 'unknown'
    
    def _extract_strike_price(self, code_name: str) -> float:
        """提取行权价"""
        # 中金所期权：IO2606-C-4000 → 4000
        if '-' in code_name:
            parts = code_name.split('-')
            if len(parts) >= 3:
                try:
                    return float(parts[2]) / 100  # 转换为实际价格
                except:
                    return 0.0
        # ETF 期权：510300C3A04000 → 4.000
        elif len(code_name) >= 10:
            try:
                strike_str = code_name[-4:]
                return float(strike_str) / 1000
            except:
                return 0.0
        return 0.0
    
    def _get_near_month_contracts(self, underlying: str, market_code: int) -> pd.DataFrame:
        """获取近月合约 ⭐ 修复版"""
        if self.option_codes.empty:
            return pd.DataFrame()
        
        # 筛选标的和市场
        filtered = self.option_codes[
            (self.option_codes['underlying'] == underlying) &
            (self.option_codes['market_code'] == market_code)
        ].copy()
        
        if filtered.empty:
            return pd.DataFrame()
        
        # 获取当前月份
        current_month = self.base_date.strftime('%y%m')  # 如'2602'
        
        # 对ETF期权，转换为月份数字 ⭐ 修复：使用to_numeric避免错误
        if market_code in [8, 9]:
            current_month_num = int(self.base_date.strftime('%m'))
            # 使用to_numeric处理可能的非数字值
            filtered['month_num'] = pd.to_numeric(
                filtered['expiry_month'], 
                errors='coerce'
            ).fillna(0).astype(int)
            
            # 选择当前月或次月
            near_months = filtered[
                (filtered['month_num'] >= current_month_num) &
                (filtered['month_num'] <= current_month_num + 1)
            ]
            
            # 如果过滤后为空，取month_num最小的2个有效合约
            if near_months.empty:
                valid_contracts = filtered[filtered['month_num'] > 0]
                if not valid_contracts.empty:
                    near_months = valid_contracts.nsmallest(2, 'month_num')
        else:
            # 中金所期权直接使用年月 ⭐ 修复：转换为数值类型
            filtered['expiry_month_num'] = filtered['expiry_month'].astype(str).apply(
                lambda x: int(x) if x.isdigit() and len(x) == 4 else 9999
            )
            
            current_month_num = int(current_month)
            
            # 筛选大于等于当前月的合约
            valid_contracts = filtered[filtered['expiry_month_num'] >= current_month_num]
            
            # 取最近的2个月
            if not valid_contracts.empty:
                near_months = valid_contracts.nsmallest(2, 'expiry_month_num')
            else:
                # 如果没有符合条件的，取最小的2个
                near_months = filtered.nsmallest(2, 'expiry_month_num')
        
        return near_months
    
    def _get_atm_contracts(self, contracts: pd.DataFrame, 
                           current_price: float, 
                           tolerance: float = 0.05) -> pd.DataFrame:
        """
        获取平值附近合约 ⭐ 自动选择
        
        参数:
        contracts: 合约 DataFrame
        current_price: 标的当前价格
        tolerance: 容忍度 (默认±5%)
        
        返回:
        平值附近合约 DataFrame
        """
        if contracts.empty or current_price <= 0:
            return pd.DataFrame()
        
        # 计算行权价与当前价格的偏离度
        contracts['strike_deviation'] = abs(
            contracts['strike_price'] - current_price
        ) / current_price
        
        # 选择偏离度在容忍度范围内的合约
        atm_contracts = contracts[
            contracts['strike_deviation'] <= tolerance
        ]
        
        # 如果没有平值合约，选择最接近的 2 个
        if atm_contracts.empty:
            atm_contracts = contracts.nsmallest(2, 'strike_deviation')
        
        return atm_contracts
    
    def _load_option_data_from_tdx(self, code: str, market_code: int, days: int = 60) -> pd.DataFrame:
        """
        从 TDX 接口加载期权历史数据 ⭐ 核心修改
        
        参数:
        code: 合约代码（如 'IO8Q0669'）
        market_code: 市场代码（7=中金所，8=上交所，9=深交所）
        days: 获取天数
        
        返回:
        DataFrame with datetime, open, high, low, close, volume, position
        """
        print(f"🔍 加载期权数据 | 合约：{code} | 市场代码：{market_code} | 天数：{days}") # ===================================
        
        if self.tdx_exhq is None:
            print(f"⚠️ TDX 接口未连接，无法获取期权数据")
            return pd.DataFrame()
        
        try:
            # TDX 扩展行情接口：获取期权K线数据
            # 参数：category=9（日线），market=market_code，code=code，start=0，count=days
            result = self.tdx_exhq.get_instrument_bars(9, market_code, code, 0, days)
            
            if result is None or len(result) == 0:
                print(f"⚠️ TDX 获取期权{code}数据为空")
                return pd.DataFrame()
            
            # 转换为 DataFrame
            df = pd.DataFrame(result)
            
            # 字段映射（TDX 字段名 → 标准字段名）
            field_mapping = {
                'datetime': 'datetime',  # 日期时间
                'open': 'open',          # 开盘价
                'high': 'high',          # 最高价
                'low': 'low',            # 最低价
                'close': 'close',        # 收盘价
                'trade': 'volume',       # 成交量
                'position': 'open_interest',  # 持仓量
                'amount': 'turnover',    # 成交额
                'price': 'settlement'    # 结算价
            }
            
            # 重命名字段
            df = df.rename(columns=field_mapping)
            
            # 数据类型转换
            if 'datetime' in df.columns:
                df['datetime'] = pd.to_datetime(df['datetime'])
            
            # 必要字段检查
            required_cols = ['datetime', 'open', 'high', 'low', 'close', 'volume', 'open_interest']
            
            for col in required_cols:
                if col not in df.columns:
                    df[col] = 0
            
            # 排序
            df = df.sort_values('datetime').reset_index(drop=True)
            
            # 去除缺失值
            df = df.dropna(subset=['close'])
            
            print(f"✅ TDX 期权{code}数据：{len(df)}条")
            
            return df
            
        except Exception as e:
            print(f"❌ TDX 获取期权{code}数据失败：{str(e)}")
            import traceback
            traceback.print_exc()
            return pd.DataFrame()
    
    def calculate_pcr(self, underlying: str, market_code: int, 
                      current_price: float = None) -> Dict:
        """
        计算单个标的的 PCR 指标 ⭐ 核心方法
        
        参数:
        underlying: 标的代码 (IO, 510300 等)
        market_code: 市场代码 (7, 8, 9)
        current_price: 标的当前价格 (用于选择平值合约)
        
        返回:
        PCR 计算结果字典
        """
        # 1. 获取近月合约
        near_month = self._get_near_month_contracts(underlying, market_code)
        if near_month.empty:
            return {'error': '无近月合约'}
        
        # 2. 获取平值附近合约
        if current_price:
            atm_contracts = self._get_atm_contracts(near_month, current_price)
        else:
            atm_contracts = near_month
        
        if atm_contracts.empty:
            return {'error': '无平值合约'}
        
        # 3. 分离看涨和看跌
        calls = atm_contracts[atm_contracts['option_type'] == 'call']
        puts = atm_contracts[atm_contracts['option_type'] == 'put']
        
        if calls.empty or puts.empty:
            return {'error': '看涨或看跌合约缺失'}
        
        # 4. 从 TDX 接口加载历史数据并计算 PCR
        call_data = []
        put_data = []
        
        for _, call_row in calls.iterrows():
            code = call_row['code']
            df = self._load_option_data_from_tdx(code, market_code, days=60)
            if len(df) > 0:
                call_data.append(df)
        
        for _, put_row in puts.iterrows():
            code = put_row['code']
            df = self._load_option_data_from_tdx(code, market_code, days=60)
            if len(df) > 0:
                put_data.append(df)
        
        if not call_data or not put_data:
            return {'error': 'TDX 数据加载失败'}
        
        # 5. 聚合数据
        call_volume = sum(df['volume'].iloc[-1] for df in call_data)
        put_volume = sum(df['volume'].iloc[-1] for df in put_data)
        call_oi = sum(df['open_interest'].iloc[-1] for df in call_data)
        put_oi = sum(df['open_interest'].iloc[-1] for df in put_data)
        
        # 6. 计算 PCR
        pcr_volume = put_volume / call_volume if call_volume > 0 else 1.0
        pcr_oi = put_oi / call_oi if call_oi > 0 else 1.0
        
        # 7. 计算历史 PCR 序列 (用于移动平均)
        pcr_history = []
        for i in range(min(5, len(call_data[0]))):
            cv = sum(df['volume'].iloc[i] for df in call_data)
            pv = sum(df['volume'].iloc[i] for df in put_data)
            if cv > 0:
                pcr_history.append(pv / cv)
        
        pcr_ma5 = np.mean(pcr_history) if pcr_history else pcr_volume
        
        # 8. 生成信号
        signal = self._generate_pcr_signal(pcr_ma5)
        
        return {
            'underlying': underlying,
            'market_code': market_code,
            'pcr_volume': pcr_volume,
            'pcr_oi': pcr_oi,
            'pcr_ma5': pcr_ma5,
            'call_volume': call_volume,
            'put_volume': put_volume,
            'call_oi': call_oi,
            'put_oi': put_oi,
            'signal': signal,
            'contracts_used': len(calls) + len(puts),
            'data_quality': 'good' if call_oi > 10000 else 'low_liquidity'
        }
    
    def _generate_pcr_signal(self, pcr_value: float) -> str:
        """生成 PCR 情绪信号"""
        if pcr_value > 1.5:
            return '极度悲观 (潜在反弹)'
        elif pcr_value > 1.2:
            return '看跌'
        elif pcr_value > 1.0:
            return '中性偏空'
        elif pcr_value > 0.8:
            return '中性偏多'
        elif pcr_value > 0.5:
            return '看涨'
        else:
            return '极度乐观 (潜在回调)'
    
    def calculate_composite_pcr(self) -> Dict:
        """
        计算综合 PCR 指标 ⭐ 多标的加权
        
        返回:
        综合 PCR 结果
        """
        results = {}
        print('==============计算各主要标的 PCR')
        # 1. 计算各主要标的 PCR
        # 沪深 300ETF 期权 (market_code=8)
        results['510300'] = self.calculate_pcr('510300', 8, current_price=4.0)
        
        # 沪深 300 指数期权 (market_code=7)
        results['IO'] = self.calculate_pcr('IO', 7, current_price=4000)
        
        # 中证 1000 指数期权 (market_code=7)
        results['MO'] = self.calculate_pcr('MO', 7, current_price=7000)
        
        # 中证 500ETF 期权 (market_code=8)
        results['510500'] = self.calculate_pcr('510500', 8, current_price=7.5)
        print(results)
        # 2. ⭐ 使用配置权重（从 system_config.yaml 读取）
        try:
            import yaml
            with open('./config/system_config.yaml', 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)
            
            weights = {
                '510300': config['option_markets']['sse']['pcr_weight'],  # 上交所权重
                'IO': config['option_markets']['cffex']['pcr_weight'],    # 中金所权重
                'MO': config['option_markets']['cffex']['pcr_weight'] * 0.5,  # 中证1000权重
                '510500': config['option_markets']['sse']['pcr_weight'] * 0.5  # ETF期权权重
            }
            
            print(f"✅ 使用配置权重：{weights}")
            
        except Exception as e:
            print(f"⚠️ 读取配置文件失败，使用默认权重：{str(e)}")
            # 默认权重
            weights = {
                '510300': 0.4,  # 沪深 300ETF 期权流动性最好
                'IO': 0.3,      # 沪深 300 指数期权
                'MO': 0.2,      # 中证 1000 指数期权
                '510500': 0.1   # 中证 500ETF 期权
            }
        
        # 3. 加权计算综合 PCR
        weighted_pcr = 0
        total_weight = 0
        
        for underlying, result in results.items():
            if 'pcr_ma5' in result and 'error' not in result:
                weighted_pcr += result['pcr_ma5'] * weights[underlying]
                total_weight += weights[underlying]
        
        composite_pcr = weighted_pcr / total_weight if total_weight > 0 else 1.0
        composite_signal = self._generate_pcr_signal(composite_pcr)
        
        return {
            'composite_pcr': composite_pcr,
            'composite_signal': composite_signal,
            'components': results,
            'calculation_time': self.base_date.strftime('%Y-%m-%d %H:%M:%S'),
            'weights_used': weights
        }
    
    def generate_pcr_report(self) -> str:
        """生成 PCR 分析报告"""
        composite = self.calculate_composite_pcr()
        
        report = []
        report.append("=" * 80)
        report.append("期权 PCR 情绪指标分析报告")
        report.append("=" * 80)
        report.append(f"数据来源：TDX 扩展行情接口 | {self.tdx_host}:{self.tdx_port}")
        report.append(f"计算时间：{composite['calculation_time']}")
        report.append(f"综合 PCR: {composite['composite_pcr']:.3f}")
        report.append(f"综合信号：{composite['composite_signal']}")
        report.append("")
        report.append("各标的 PCR 详情:")
        report.append("-" * 80)
        
        for underlying, result in composite['components'].items():
            if 'error' in result:
                report.append(f"{underlying}: {result['error']}")
            else:
                report.append(f"{underlying}:")
                report.append(f"  PCR(持仓量): {result['pcr_oi']:.3f}")
                report.append(f"  PCR(成交量): {result['pcr_volume']:.3f}")
                report.append(f"  PCR(5 日 MA): {result['pcr_ma5']:.3f}")
                report.append(f"  信号：{result['signal']}")
                report.append(f"  数据质量：{result['data_quality']}")
                report.append(f"  使用合约数：{result['contracts_used']}")
            report.append("")
        
        report.append("=" * 80)
        report.append("PCR 解读指南:")
        report.append("  • PCR > 1.5: 极度悲观，市场可能超卖，关注反弹机会")
        report.append("  • PCR 1.2-1.5: 看跌情绪浓厚")
        report.append("  • PCR 1.0-1.2: 中性偏空")
        report.append("  • PCR 0.8-1.0: 中性偏多")
        report.append("  • PCR 0.5-0.8: 看涨情绪浓厚")
        report.append("  • PCR < 0.5: 极度乐观，市场可能超买，警惕回调风险")
        report.append("=" * 80)
        
        return "\n".join(report)

# %%
# 9 ==================== 衍生品引擎层 DerivativesEngine ====================
class DerivativesEngine:
    """
    V5.7 衍生品引擎 - 动态合约映射 + 多源聚合
    集成 OptionPCRAnalyzer 进行期权PCR分析
    """
    
    def __init__(self, data_manager: DataManager, config: SystemConfig):
        self.dm = data_manager
        self.config = config
        self.logger = setup_logger('DerivativesEngine')
        
        # 【核心集成】初始化 OptionPCRAnalyzer
        self.pcr_analyzer = OptionPCRAnalyzer(
            engine=self.dm.engine,
            base_date=self.config.base_date,
            tdx_host=self.config.tdx_exhq_host,
            tdx_port=self.config.tdx_exhq_port
        )
        
        self.logger.info(f"✅ OptionPCRAnalyzer 集成成功 | TDX: {self.config.tdx_exhq_host}:{self.config.tdx_exhq_port}")
    
    # ==================== 期权分析 ====================
    
    def calculate_pcr(self, underlying: str = None, market_code: int = None) -> Dict:
        """
        计算期权PCR（调用 OptionPCRAnalyzer）
        
        参数:
        underlying: 标的代码（可选，None=计算综合PCR）
        market_code: 市场代码（可选）
        
        返回:
        PCR计算结果字典
        """
        try:
            if underlying is None and market_code is None:
                # 计算综合PCR（多标的加权）
                return self.pcr_analyzer.calculate_composite_pcr()
            else:
                # 计算单个标的PCR
                current_price = self._get_current_price(underlying)
                return self.pcr_analyzer.calculate_pcr(
                    underlying=underlying,
                    market_code=market_code,
                    current_price=current_price
                )
        except Exception as e:
            self.logger.error(f"❌ PCR计算失败：{str(e)}")
            return {'error': str(e)}
    
    def _get_current_price(self, underlying: str) -> float:
        """获取标的当前价格"""
        # 根据标的代码加载指数数据
        index_mapping = {
            'IO': '000300',  # 沪深300
            'MO': '000852',  # 中证1000
            '510300': '000300',
            '510500': '000905'
        }
        
        index_code = index_mapping.get(underlying, underlying)
        df = self.dm.load_index_data(index_code, min_days=1)
        
        if len(df) > 0:
            return df['close'].iloc[-1]
        return 0.0
    
    # ==================== 期货分析 ====================
    
    def calculate_futures_basis(self) -> Dict:
        """期现基差分析"""
        basis_results = {}
        
        # IF（沪深300股指期货）
        if_df = self.dm.load_derivative_data('IFL8', market_code=47, days=20)
        hs300_df = self.dm.load_index_data('000300', min_days=20)
        
        if len(if_df) > 0 and len(hs300_df) > 0:
            df_merge = pd.merge(
                if_df[['datetime', 'close']].rename(columns={'close': 'futures'}),
                hs300_df[['datetime', 'close']].rename(columns={'close': 'spot'}),
                on='datetime', how='inner'
            ).tail(20)
            
            if len(df_merge) > 0 and df_merge['spot'].iloc[-1] > 0:
                basis = df_merge['futures'].iloc[-1] - df_merge['spot'].iloc[-1]
                basis_pct = (basis / df_merge['spot'].iloc[-1]) * 100
                
                if basis_pct < self.config.risk_thresholds['basis']['extreme']:
                    signal = '深度贴水（悲观）'
                elif basis_pct < self.config.risk_thresholds['basis']['warning']:
                    signal = '贴水（谨慎）'
                elif basis_pct > 0:
                    signal = '升水（乐观）'
                else:
                    signal = '平水（中性）'
                
                basis_results['if_basis'] = {
                    'value': float(basis),
                    'percent': float(basis_pct),
                    'signal': signal,
                    'futures_price': float(df_merge['futures'].iloc[-1]),
                    'spot_price': float(df_merge['spot'].iloc[-1])
                }
        
        return basis_results
    
    def calculate_futures_term_structure(self) -> Dict:
        """期货期限结构分析（Contango/Backwardation）"""
        term_structure = {}
        
        commodity_contracts = {
            'copper': ('CU2603', 'CU2606', 30),      # 沪铜
            'aluminum': ('AL2603', 'AL2606', 30),    # 沪铝
            'lithium': ('LC2603', 'LC2606', 66),     # 碳酸锂
            'silicon': ('SI2603', 'SI2606', 66),     # 工业硅
            'crude': ('SC2603', 'SC2606', 30),       # 原油
            'rebar': ('RB2603', 'RB2606', 30),       # 螺纹钢
            'gold': ('AU2603', 'AU2606', 30),        # 黄金
            'soybean': ('M2603', 'M2605', 29)        # 豆粕
        }
        
        for key, (near_code, far_code, market_code) in commodity_contracts.items():
            near_df = self.dm.load_derivative_data(near_code, market_code, days=20)
            far_df = self.dm.load_derivative_data(far_code, market_code, days=20)
            
            if len(near_df) > 0 and len(far_df) > 0 and far_df['close'].iloc[-1] > 0:
                near_price = near_df['close'].iloc[-1]
                far_price = far_df['close'].iloc[-1]
                spread = ((near_price - far_price) / far_price) * 100
                
                structure = 'backwardation' if spread > 0 else 'contango'
                signal = '供应紧张/景气' if spread > 0 else '供应充足/疲软'
                
                term_structure[key] = {
                    'spread': round(float(spread), 2),
                    'structure': structure,
                    'signal': signal,
                    'near_price': float(near_price),
                    'far_price': float(far_price)
                }
        
        return term_structure


# %%
# 10 ==================== 商品期货引擎层 CommodityEngine ====================
"""
V5.7 商品期货引擎 - 商品信号计算与战略方向映射
"""
class CommodityEngine:
    """
    商品期货分析引擎（独立子引擎）
    功能：
    1. 商品期货信号计算（成本型/收益型）
    2. 期货期限结构分析（Contango/Backwardation）
    3. 战略方向影响映射
    4. 产业景气度评估
    """
    
    def __init__(self, data_manager: DataManager, config: SystemConfig):
        self.dm = data_manager
        self.config = config
        self.logger = setup_logger('CommodityEngine')
        
        # 商品市场代码映射（内部维护）
        self._market_code_map = {
            'CU': 30, 'AL': 30, 'AU': 30, 'AG': 30, 'RB': 30, 'SC': 30,
            'NI': 30, 'SN': 30, 'ZN': 30, 'PB': 30, 'FU': 30, 'BU': 30,
            'RU': 30, 'NR': 30, 'SP': 30, 'LU': 30, 'BC': 30, 'SS': 30,
            'M': 29, 'Y': 29, 'C': 29, 'I': 29, 'J': 29, 'JM': 29, 'LH': 29,
            'CF': 32, 'SR': 32, 'TA': 32, 'MA': 32, 'FG': 32, 'SA': 32,
            'LC': 66, 'SI': 66, 'PS': 66
        }
    
    # ==================== 1. 商品信号计算 ====================
    def calculate_commodity_signals(self) -> Dict:
        """
        V5.7 核心：商品期货信号计算
        返回: {
            'CUL8': {
                'name': '沪铜',
                'price_chg_20d': float,
                'signal': str,
                'score': float,  # 调整分数（-0.15 到 +0.12）
                'directions': List[str],
                'weight': float,
                'impact_type': str
            },
            ...
        }
        """
        commodity_signals = {}
        
        for code, config in self.config.commodity_strategy_map.items():
            # 获取市场代码
            market_code = self._get_market_code(code)
            
            # 加载商品期货数据
            df = self.dm.load_derivative_data(code, market_code, days=60)
            
            if len(df) < 20:
                self.logger.debug(f"⚠️ {code} 数据不足（需≥20日），跳过")
                continue
            
            # 计算20日价格变化
            price_chg_20d = (df['close'].iloc[-1] / df['close'].iloc[-20] - 1) * 100
            
            # 根据影响类型和阈值生成信号
            signal, score = self._generate_signal(
                price_chg_20d, 
                config['impact_type'],
                config.get('threshold_up', 10.0),
                config.get('threshold_down', -10.0)
            )
            
            commodity_signals[code] = {
                'name': self._get_commodity_name(code),
                'price_chg_20d': float(price_chg_20d),
                'signal': signal,
                'score': float(score),
                'directions': config['directions'],
                'weight': config['weight'],
                'impact_type': config['impact_type'],
                'threshold_up': config.get('threshold_up', 10.0),
                'threshold_down': config.get('threshold_down', -10.0)
            }
        
        self.logger.info(f"✅ 计算商品期货信号：{len(commodity_signals)}个商品")
        return commodity_signals
    
    def _generate_signal(self, price_chg: float, impact_type: str, 
                        threshold_up: float, threshold_down: float) -> Tuple[str, float]:
        """生成商品信号和调整分数"""
        if impact_type == 'cost':
            # 成本型商品：价格上涨对相关方向不利
            if price_chg > threshold_up:
                return '成本大幅上升', -0.15
            elif price_chg > threshold_up / 2:
                return '成本上升', -0.08
            elif price_chg < threshold_down:
                return '成本大幅下降', 0.12
            elif price_chg < threshold_down / 2:
                return '成本下降', 0.06
            else:
                return '成本稳定', 0.0
        else:  # benefit
            # 收益型商品：价格上涨对相关方向有利
            if price_chg > 8:
                return '避险情绪高涨', 0.10
            else:
                return '正常', 0.0
    
    # ==================== 2. 期货期限结构分析 ====================
    def calculate_futures_term_structure(self) -> Dict:
        """
        期货期限结构分析（Contango/Backwardation）
        返回: {
            'copper': {
                'spread': float, 
                'structure': 'backwardation'/'contango',
                'signal': str,
                'near_price': float,
                'far_price': float,
                'near_code': str,
                'far_code': str
            },
            ...
        }
        """
        term_structure = {}
        
        # 定义监控的商品合约对（近月，远月，市场代码）
        commodity_contracts = {
            'copper': ('CU2603', 'CU2606', 30),      # 沪铜
            'aluminum': ('AL2603', 'AL2606', 30),    # 沪铝
            'lithium': ('LC2603', 'LC2606', 66),     # 碳酸锂
            'silicon': ('SI2603', 'SI2606', 66),     # 工业硅
            'crude': ('SC2603', 'SC2606', 30),       # 原油
            'rebar': ('RB2603', 'RB2606', 30),       # 螺纹钢
            'gold': ('AU2603', 'AU2606', 30),        # 黄金
            'soybean': ('M2603', 'M2605', 29)        # 豆粕
        }
        
        for key, (near_code, far_code, market_code) in commodity_contracts.items():
            # 1. 加载数据
            near_df = self.dm.load_derivative_data(near_code, market_code, days=20)
            far_df = self.dm.load_derivative_data(far_code, market_code, days=20)
            
            # 2. 计算价差
            if len(near_df) > 0 and len(far_df) > 0 and far_df['close'].iloc[-1] > 0:
                near_price = near_df['close'].iloc[-1]
                far_price = far_df['close'].iloc[-1]
                spread = ((near_price - far_price) / far_price) * 100
                
                # 3. 判断结构
                structure = 'backwardation' if spread > 0 else 'contango'
                signal = '供应紧张/景气' if spread > 0 else '供应充足/疲软'
                
                term_structure[key] = {
                    'spread': round(float(spread), 2),
                    'structure': structure,
                    'signal': signal,
                    'near_price': float(near_price),
                    'far_price': float(far_price),
                    'near_code': near_code,
                    'far_code': far_code
                }
        
        self.logger.info(f"✅ 计算期货期限结构：{len(term_structure)}个商品")
        return term_structure
    
    # ==================== 3. 辅助方法 ====================
    def _get_market_code(self, commodity_code: str) -> int:
        """获取商品期货的市场代码"""
        if commodity_code.endswith('L8'):
            base = commodity_code[:-2]
            return self._market_code_map.get(base, 30)  # 默认上海期货
        
        # 从配置中获取（兼容旧格式）
        if hasattr(self.config, 'commodity_strategy_map'):
            market_code = self.config.commodity_strategy_map.get(
                commodity_code, {}
            ).get('market_code')
            if market_code:
                return market_code
        
        return 30  # 默认上海期货
    
    def _get_commodity_name(self, code: str) -> str:
        """获取商品名称（优先从配置获取）"""
        # 从配置中获取
        if hasattr(self.config, 'commodity_strategy_map'):
            name = self.config.commodity_strategy_map.get(code, {}).get('name')
            if name:
                return name
        
        # 默认名称映射
        default_names = {
            'CUL8': '沪铜', 'ALL8': '沪铝', 'LCL8': '碳酸锂',
            'SIL8': '工业硅', 'SCL8': '原油', 'RBL8': '螺纹钢',
            'ML8': '豆粕', 'CL8': '玉米', 'AUL8': '黄金',
            'AGL8': '白银', 'NIL8': '沪镍', 'ZNL8': '沪锌',
            'PBL8': '沪铅', 'SRL8': '白糖', 'CFL8': '棉花',
            'TAL8': 'PTA', 'MAL8': '甲醇', 'FGL8': '玻璃',
            'SAL8': '纯碱', 'RML8': '菜籽粕', 'OIL8': '菜籽油',
            'ZCL8': '焦煤', 'SFL8': '硅铁', 'SML8': '锰硅',
            'APL8': '苹果', 'CJL8': '红枣', 'URL8': '尿素',
            'SHL8': '烧碱', 'PXL8': '对二甲苯'
        }
        
        return default_names.get(code, code)
    
    def calculate_industry_sentiment(self, term_structure: Dict) -> Dict:
        """
        基于期限结构计算产业景气度评分
        返回: {'高端制造': 65, '新能源': 72, ...}
        """
        # 商品到战略方向的映射（简化版）
        commodity_to_direction = {
            'copper': ['高端制造', '供应链'],
            'aluminum': ['高端制造', '新能源'],
            'lithium': ['新能源', '信息技术'],
            'silicon': ['信息技术', '新能源'],
            'crude': ['公用事业', '供应链', '传统升级'],
            'rebar': ['传统升级', '供应链'],
            'gold': ['公用事业'],
            'soybean': ['现代农业', '生物健康']
        }
        
        # 初始化方向评分
        direction_sentiment = {direction: 50 for directions in commodity_to_direction.values() 
                              for direction in directions}
        
        # 根据期限结构更新评分
        for commodity, data in term_structure.items():
            if commodity not in commodity_to_direction:
                continue
            
            # Backwardation(近月>远月) = 供应紧张 = 景气度高
            # Contango(近月<远月) = 供应充足 = 景气度低
            if data['structure'] == 'backwardation':
                sentiment_score = min(100, 50 + abs(data['spread']) * 3)
            else:  # contango
                sentiment_score = max(0, 50 - abs(data['spread']) * 3)
            
            # 更新关联方向的评分
            for direction in commodity_to_direction[commodity]:
                if direction in direction_sentiment:
                    # 加权平均（简单处理）
                    direction_sentiment[direction] = (
                        direction_sentiment[direction] * 0.7 + sentiment_score * 0.3
                    )
        
        return direction_sentiment

# %%
# 11 ==================== 计算引擎层 IndicatorEngine ====================
class IndicatorEngine:
    """
    V5.7 计算引擎 - 统一入口，内部集成3个子引擎
    """
    def __init__(self, data_manager: DataManager, config: SystemConfig):
        self.dm = data_manager
        self.config = config
        self.logger = setup_logger('IndicatorEngine')
        
        # ✅ 内部初始化子引擎
        self.derivatives_engine = DerivativesEngine(data_manager, config)
        self.macro_engine = MacroEngine(data_manager, config)
        self.risk_engine = RiskEngine(data_manager, config)
        self.commodity_engine = CommodityEngine(data_manager, config)  # ⭐ 新增
            
    # ==================== 1. 核心评分方法 ====================
    
    def calculate_valuation_score(self, df: pd.DataFrame, index_code: str) -> float:
        """
        估值维度评分（基于 PE TTM）
        返回: 0-100 分，越高越好
        """
        if len(df) < 250:
            return 50.0
        
        # 尝试获取 PE 历史数据
        pe_df = self.dm.load_pe_data(index_code)
        
        if len(pe_df) >= 500 and 'pe_ttm' in pe_df.columns:
            # 1. PE 分位数评分
            current_pe = pe_df['pe_ttm'].iloc[-1]
            pe_history = pe_df['pe_ttm'].iloc[:-1]
            
            # 去除极端值
            pe_clean = pe_history[pe_history < pe_history.quantile(0.99)]
            pe_percentile = (pe_clean < current_pe).mean() * 100
            
            base_score = 100 - pe_percentile  # 估值越低得分越高
            
            # 2. 股债性价比调整
            bond_yield = self._safe_get_bond_yield()
            equity_yield = 100 / current_pe if current_pe > 0 else 3.5
            equity_risk_premium = equity_yield - bond_yield
            
            # ERP 调整
            if equity_risk_premium > 3.5:
                final_score = base_score * 1.15  # 高性价比加成
            elif equity_risk_premium > 2.5:
                final_score = base_score * 1.05
            elif equity_risk_premium < 1.5:
                final_score = base_score * 0.85  # 低性价比惩罚
            else:
                final_score = base_score
            
            return np.clip(final_score, 0, 100)
        
        else:
            # 降级：使用价格分位数
            if len(df) >= 250:
                current_price = df['close'].iloc[-1]
                price_history = df['close'].iloc[-250:-1]
                price_percentile = (price_history < current_price).mean() * 100
                return 100 - price_percentile
            
            return 50.0
    
    def calculate_trend_score(self, df: pd.DataFrame) -> float:
        """
        趋势维度评分
        返回: 0-100 分，越高越好
        """
        if len(df) < 120:
            return 50.0
        
        # 1. 短期趋势（20日动量）
        if len(df) >= 21:
            mom_20 = (df['close'].iloc[-1] / df['close'].iloc[-21] - 1) * 100
        else:
            mom_20 = 0
        
        if len(df) >= 11:
            mom_10 = (df['close'].iloc[-1] / df['close'].iloc[-11] - 1) * 100
        else:
            mom_10 = 0
        
        if len(df) >= 6:
            mom_5 = (df['close'].iloc[-1] / df['close'].iloc[-6] - 1) * 100
        else:
            mom_5 = 0
        
        short_score = np.clip((0.4 * mom_5 + 0.3 * mom_10 + 0.3 * mom_20) * 2 + 50, 0, 100)
        
        # 2. 移动平均线趋势
        if 'ma_20' not in df.columns:
            df['ma_20'] = df['close'].rolling(20).mean()
        if 'ma_60' not in df.columns:
            df['ma_60'] = df['close'].rolling(60).mean()
        if 'ma_120' not in df.columns:
            df['ma_120'] = df['close'].rolling(120).mean()
        
        # 价格在20日均线之上天数占比
        if len(df) >= 20:
            above_ma20 = (df['close'].iloc[-20:] > df['ma_20'].iloc[-20:]).mean() * 100
        else:
            above_ma20 = 50
        
        # 20日均线在60日均线之上天数占比
        if len(df) >= 20:
            ma20_above_ma60 = (df['ma_20'].iloc[-20:] > df['ma_60'].iloc[-20:]).mean() * 100
        else:
            ma20_above_ma60 = 50
        
        mid_score = 0.5 * above_ma20 + 0.5 * ma20_above_ma60
        
        # 3. 长期趋势（120日）
        if len(df) >= 121:
            mom_120 = (df['close'].iloc[-1] / df['close'].iloc[-121] - 1) * 100
            long_score = np.clip(mom_120 * 0.3 + 50, 0, 100)
        else:
            long_score = 50
        
        # 综合评分
        trend_score = 0.3 * short_score + 0.4 * mid_score + 0.3 * long_score
        
        return np.clip(trend_score, 0, 100)
    
    def calculate_fund_score(self, df: pd.DataFrame) -> float:
        """
        资金维度评分
        返回: 0-100 分，越高越好
        """
        required_cols = ['volatility_20', 'volatility_250', 'volume_ma20']
        if not all(col in df.columns for col in required_cols):
            return 50.0
        
        if len(df) < 250:
            return 50.0
        
        # 1. 成交量分位数
        vol_percentile = (df['volume_ma20'].iloc[-250:-1] < df['volume_ma20'].iloc[-1]).mean() * 100
        
        # 2. 上涨成交量占比（如果有）
        if 'up_vol_ratio' in df.columns:
            vol_ratio_score = np.clip(df['up_vol_ratio'].iloc[-1] * 20, 0, 100)
        else:
            vol_ratio_score = 50.0
        
        volume_score = 0.5 * vol_percentile + 0.3 * vol_ratio_score + 0.2 * 50
        
        # 3. 波动率分位数（波动率越低越好）
        vol_20_hist = df['volatility_20'].iloc[-250:-1]
        vol_current = df['volatility_20'].iloc[-1]
        vol_percentile_score = 100 - (vol_20_hist < vol_current).mean() * 100
        
        # 综合资金评分
        fund_score = 0.6 * volume_score + 0.4 * vol_percentile_score
        
        return np.clip(fund_score, 0, 100)

    def calculate_sentiment_scores(self) -> Dict[str, float]:
        """
        计算四大情绪指标得分（0-100）
        返回: {'margin_score': float, 'fund_score': float, 'vol_score': float, 'vix_score': float}
        """
        scores = {
            'margin_score': 50.0,
            'fund_score': 50.0,
            'vol_score': 50.0,
            'vix_score': 50.0
        }
        
        # ========== 1. 融资余额情绪 ==========
        try:
            rz_df = self.dm.load_macro_data('7_RZ', days=250)
            if len(rz_df) >= 50:
                current = rz_df['close'].iloc[-1]
                history = rz_df['close'].iloc[-250:-1]
                percentile = (history < current).mean() * 100
                
                # 近期趋势加分（20日变化）
                if len(rz_df) >= 21:
                    change_20d = ((current - rz_df['close'].iloc[-21]) / rz_df['close'].iloc[-21]) * 100
                    trend_bonus = np.clip(change_20d * 2, -20, 20)
                else:
                    trend_bonus = 0
                
                scores['margin_score'] = np.clip(percentile + trend_bonus, 0, 100)
        except Exception as e:
            self.logger.warning(f"⚠️ 融资余额情绪计算失败: {str(e)}")
        
        # ========== 2. 基金资金情绪 ==========
        try:
            etf_df = self.dm.load_macro_data('7_TETF', days=250)
            fund_df = self.dm.load_macro_data('9_990002', days=250)  # 股票型基金指数
            
            if len(etf_df) >= 50:
                # ETF规模分位数
                etf_current = etf_df['close'].iloc[-1]
                etf_hist = etf_df['close'].iloc[-250:-1]
                etf_pct = (etf_hist < etf_current).mean() * 100
                
                # 基金指数相对强弱
                if len(fund_df) >= 50:
                    hs300_df = self.dm.load_index_data('000300', min_days=250)
                    if len(hs300_df) >= 50:
                        fund_return = (fund_df['close'].iloc[-1] / fund_df['close'].iloc[-21] - 1) * 100
                        hs300_return = (hs300_df['close'].iloc[-1] / hs300_df['close'].iloc[-21] - 1) * 100
                        relative_strength = fund_return - hs300_return
                        rs_score = 50 + relative_strength * 5
                    else:
                        rs_score = 50
                else:
                    rs_score = 50
                
                scores['fund_score'] = np.clip((etf_pct * 0.6 + rs_score * 0.4), 0, 100)
        except Exception as e:
            self.logger.warning(f"⚠️ 基金情绪计算失败: {str(e)}")
        
        # ========== 3. 波动率情绪（反向）==========
        try:
            hs300_df = self.dm.load_index_data('000300', min_days=250)
            if len(hs300_df) >= 250 and 'volatility_20' in hs300_df.columns:
                current_vol = hs300_df['volatility_20'].iloc[-1]
                vol_hist = hs300_df['volatility_20'].iloc[-250:-1]
                vol_percentile = (vol_hist < current_vol).mean() * 100
                
                # 反向映射：波动率高 → 情绪差
                scores['vol_score'] = np.clip(100 - vol_percentile, 0, 100)
        except Exception as e:
            self.logger.warning(f"⚠️ 波动率情绪计算失败: {str(e)}")
        
        # ========== 4. 恐慌情绪（VHSI 替代）==========
        try:
            # 尝试加载 VHSI（恒生波幅指数）
            vhsi_df = self.dm.load_derivative_data('VHSI', market_code=27, days=250)
            
            if len(vhsi_df) >= 50 and 'close' in vhsi_df.columns:
                current_vhsi = vhsi_df['close'].iloc[-1]
                vhsi_history = vhsi_df['close'].iloc[-250:-1]
                
                # 计算历史分位数
                vhsi_percentile = (vhsi_history < current_vhsi).mean() * 100
                
                # 反向映射：VHSI越高 → 恐慌越强 → 情绪得分越低
                vix_score = 100 - vhsi_percentile
                
                # 极端值校准
                if current_vhsi > 30:      # 极度恐慌
                    vix_score = max(5, vix_score * 0.8)
                elif current_vhsi < 12:    # 异常平静
                    vix_score = min(65, vix_score * 0.9)
                
                scores['vix_score'] = float(np.clip(vix_score, 0, 100))
                self.logger.info(f"✅ VHSI情绪得分：{scores['vix_score']:.1f} | VHSI={current_vhsi:.1f}")
                
            else:
                # 回退：使用期权 PCR 替代
                raise Exception("VHSI数据不足")
                
        except Exception as e:
            self.logger.warning(f"⚠️ VHSI加载失败：{str(e)}，回退到PCR方案")
            
            # PCR替代方案
            try:
                pcr_data = self.calculate_pcr()
                composite_pcr = pcr_data.get('composite_pcr', 1.0)
                
                # PCR → 恐慌指数映射
                if composite_pcr > 1.5:
                    panic_index = 90
                elif composite_pcr > 1.2:
                    panic_index = 70
                elif composite_pcr > 0.8:
                    panic_index = 50
                elif composite_pcr > 0.5:
                    panic_index = 30
                else:
                    panic_index = 10
                
                # 反向：恐慌指数高 → 情绪得分低
                scores['vix_score'] = float(np.clip(100 - panic_index, 0, 100))
                
            except Exception as e2:
                self.logger.warning(f"⚠️ PCR方案失败：{str(e2)}，使用默认值")
                scores['vix_score'] = 50.0
        
        # ⭐⭐⭐ 核心修复：强制转换为 Python 原生 float 类型 ⭐⭐⭐
        return {
            'margin_score': float(scores['margin_score']),
            'fund_score': float(scores['fund_score']),
            'vol_score': float(scores['vol_score']),
            'vix_score': float(scores['vix_score'])
        }
    
    # ==================== 2. 衍生品分析（委托给子引擎）====================
    def calculate_pcr(self):
        """计算期权PCR"""
        return self.derivatives_engine.calculate_pcr()
    
    def calculate_futures_basis(self):
        """计算期现基差"""
        return self.derivatives_engine.calculate_futures_basis()
    
    def calculate_futures_term_structure(self):
        """计算期货期限结构"""
        return self.derivatives_engine.calculate_futures_term_structure()
    
    # ==================== 3. 宏观分析（委托给子引擎）====================
    def calculate_macro_composite_score(self):
        """计算宏观综合评分"""
        return self.macro_engine.calculate_macro_composite_score()
    
    # ==================== 4. 风险分析（委托给子引擎）====================
    def assess_micro_liquidity(self, df_primary, df_secondary=None):
        """评估微盘流动性"""
        return self.risk_engine.assess_micro_liquidity(df_primary, df_secondary)
    
    # ==================== 商品分析（委托给 CommodityEngine）====================
    def calculate_commodity_signals(self) -> Dict:
        """计算商品期货信号（调用 CommodityEngine）"""
        return self.commodity_engine.calculate_commodity_signals()
    
    def calculate_futures_term_structure(self) -> Dict:
        """计算期货期限结构（调用 CommodityEngine）"""
        return self.commodity_engine.calculate_futures_term_structure()
    
    def calculate_industry_sentiment(self) -> Dict:
        """计算产业景气度（调用 CommodityEngine）"""
        term_structure = self.commodity_engine.calculate_futures_term_structure()
        return self.commodity_engine.calculate_industry_sentiment(term_structure)
    
    def calculate_risk_transmission(self, benchmark_data):
        """计算风险传导路径"""
        return self.risk_engine.calculate_risk_transmission(benchmark_data)
    
    # ==================== 6. 资金流向热力图 ====================
    
    def calculate_fund_flow_heatmap(self) -> Dict:
        """
        计算资金流向热力图数据
        返回: {
            'categories': List[str],
            'data_values': List[List[float]]  # [[5d, 10d, 20d], ...]
        }
        """
        fund_flow_data = {
            'categories': ['融资余额', '北上资金', 'ETF规模', '南下资金'],
            'data_values': []
        }
        
        # 1. 融资余额
        rz_df = self.dm.load_macro_data('7_RZ', days=30)
        if len(rz_df) >= 20:
            rz_latest = rz_df['close'].iloc[-1]
            rz_5d = rz_df['close'].iloc[-5] if len(rz_df) >= 5 else rz_latest
            rz_10d = rz_df['close'].iloc[-10] if len(rz_df) >= 10 else rz_latest
            rz_20d = rz_df['close'].iloc[-20]
            
            rz_change_5d = ((rz_latest - rz_5d) / rz_5d * 100) if rz_5d > 0 else 0
            rz_change_10d = ((rz_latest - rz_10d) / rz_10d * 100) if rz_10d > 0 else 0
            rz_change_20d = ((rz_latest - rz_20d) / rz_20d * 100) if rz_20d > 0 else 0
            
            fund_flow_data['data_values'].append([
                round(rz_change_5d, 1),
                round(rz_change_10d, 1),
                round(rz_change_20d, 1)
            ])
        else:
            fund_flow_data['data_values'].append([0, 0, 0])
        
        # 2. 北上资金
        ton_df = self.dm.load_macro_data('7_TON', days=30)
        if len(ton_df) >= 20:
            ton_latest = ton_df['close'].iloc[-1]
            ton_5d = ton_df['close'].iloc[-5] if len(ton_df) >= 5 else ton_latest
            ton_10d = ton_df['close'].iloc[-10] if len(ton_df) >= 10 else ton_latest
            ton_20d = ton_df['close'].iloc[-20]
            
            ton_change_5d = ((ton_latest - ton_5d) / ton_5d * 100) if ton_5d > 0 else 0
            ton_change_10d = ((ton_latest - ton_10d) / ton_10d * 100) if ton_10d > 0 else 0
            ton_change_20d = ((ton_latest - ton_20d) / ton_20d * 100) if ton_20d > 0 else 0
            
            fund_flow_data['data_values'].append([
                round(ton_change_5d, 1),
                round(ton_change_10d, 1),
                round(ton_change_20d, 1)
            ])
        else:
            fund_flow_data['data_values'].append([0, 0, 0])
        
        # 3. ETF规模（简化）
        fund_flow_data['data_values'].append([1.2, 2.5, 3.8])
        
        # 4. 南下资金（简化）
        fund_flow_data['data_values'].append([0.8, 1.5, 2.2])
        
        return fund_flow_data
    
    # ==================== 7. 跨市场联动 ====================
    
    def load_cross_market_data(self) -> Dict:
        """
        加载跨市场数据（A股/港股/美股）
        返回: {
            'a_share': DataFrame,  # 沪深300
            'hk_share': DataFrame,  # 恒生指数
            'us_share': DataFrame,  # 标普500
            'ton': DataFrame,       # 北上资金
            'aty': DataFrame        # 美债收益率
        }
        """
        cross_market_data = {}
        
        # A股（沪深300）
        cross_market_data['a_share'] = self.dm.load_index_data('000300', min_days=250)
        
        # 港股（恒生指数）
        try:
            hk_df = self.dm.load_derivative_data('HSI', market_code=27, days=250)
            cross_market_data['hk_share'] = hk_df
        except:
            # 降级：使用中证指数替代
            cross_market_data['hk_share'] = self.dm.load_index_data('000905', min_days=250)
        
        # 美股（标普500）
        try:
            us_df = self.dm.load_derivative_data('SPXD', market_code=74,days=250)
            cross_market_data['us_share'] = us_df
        except:
            # 降级：使用模拟数据
            cross_market_data['us_share'] = pd.DataFrame()
        
        # 北上资金
        ton_df = self.dm.load_macro_data('7_TON', days=250)
        if len(ton_df) > 0:
            cross_market_data['ton'] = ton_df
        
        # 美债收益率
        aty_df = self.dm.load_macro_data('8_ATY', days=250)
        if len(aty_df) > 0:
            cross_market_data['aty'] = aty_df
        
        return cross_market_data
    
    # ==================== 8. 行业轮动矩阵 ====================
    
    def calculate_industry_rotation(self, benchmark_return: float = 0.0) -> Dict:
        """
        计算行业轮动矩阵
        返回: {
            'industries': {'行业A': return, ...},
            'benchmark_return': float
        }
        """
        # 定义主要行业指数
        industry_indices = {
            '金融': '931479',  # 证券保险
            '消费': '000990',  # 全指消费
            '医药': '000991',  # 全指医药
            '科技': '931271',  # 通信设备主题
            '制造': '930850',  # 中证智能制造
            '周期': '000961',  # 中证上游
            '公用': '000917',  # 300公用
        }
        
        industry_returns = {}
        
        for industry, code in industry_indices.items():
            df = self.dm.load_index_data(code, min_days=30)
            if len(df) >= 20:
                return_20d = (df['close'].iloc[-1] / df['close'].iloc[-20] - 1) * 100
                industry_returns[industry] = round(float(return_20d), 2)
        
        return {
            'industries': industry_returns,
            'benchmark_return': benchmark_return
        }
    
    # ==================== 9. 辅助方法 ====================
    
    def _safe_get_bond_yield(self) -> float:
        """安全获取10年期国债收益率"""
        try:
            bond_df = self.dm.load_macro_data('8_ATY', days=5)
            if len(bond_df) > 0:
                return bond_df['close'].iloc[-1]
        except:
            pass
        return 2.5  # 默认值

# %%
# 12 ==================== 配置引擎层 AllocationEngine ====================
class AllocationEngine:
    """
    V5.7 资产配置引擎（完整版）
    功能：
    1. 战略方向动态配置
    2. 微盘熔断惩罚机制
    3. 商品期货信号调整
    4. 期权情绪因子融合
    5. 宏观信号调整
    6. 现金仓位动态控制
    """
    
    def __init__(self, config: SystemConfig, indicator_engine: IndicatorEngine,
                 risk_engine: Optional[object] = None):
        """
        初始化配置引擎
        参数:
            config: 系统配置
            indicator_engine: 指标计算引擎
            risk_engine: 风险引擎（可选，用于微盘熔断）
        """
        self.config = config
        self.ie = indicator_engine
        self.risk_engine = risk_engine
        self.logger = setup_logger('AllocationEngine')

    def _calculate_direction_scores(self) -> Dict[str, Dict]:
        """
        计算各战略方向的评分（估值/趋势/资金）
        返回: {
            '高端制造': {'valuation': 65.2, 'trend': 72.1, 'fund': 58.3},
            '信息技术': {...},
            ...
        }
        """
        direction_scores = {}
        
        for direction, indices in self.config.direction_indices.items():
            valid_dfs = []
            for code in indices:
                df = self.ie.dm.load_index_data(code, min_days=0)
                if len(df) >= 250:
                    valid_dfs.append(df)
            
            if not valid_dfs:
                direction_scores[direction] = {
                    'valuation': 50.0, 'trend': 50.0, 'fund': 50.0
                }
                continue
            
            # 计算估值评分（带指数代码）
            avg_val = np.mean([
                self.ie.calculate_valuation_score(df, code)
                for df, code in zip(valid_dfs, indices)
            ])
            
            # 计算趋势和资金评分
            avg_trend = np.mean([self.ie.calculate_trend_score(df) for df in valid_dfs])
            avg_fund = np.mean([self.ie.calculate_fund_score(df) for df in valid_dfs])
            
            direction_scores[direction] = {
                'valuation': float(avg_val),
                'trend': float(avg_trend),
                'fund': float(avg_fund)
            }
        
        self.logger.debug(f"✅ 计算完成 {len(direction_scores)} 个战略方向评分")
        return direction_scores
    
    def _calculate_commodity_adjustments(self, commodity_signals: Dict) -> Dict:
        """计算各战略方向的商品调整因子"""
        direction_adjustments = {d: 0.0 for d in self.config.base_weights.keys()}
        
        for code, signal_data in commodity_signals.items():
            for direction in signal_data['directions']:
                if direction in direction_adjustments:
                    # 调整 = 信号分数 × 商品权重
                    adjustment = signal_data['score'] * signal_data['weight']
                    direction_adjustments[direction] += adjustment
        
        return direction_adjustments
    
    def _calculate_micro_penalty(self, direction: str, 
                                micro_liquidity: Optional[Dict]) -> float:
        """计算微盘熔断惩罚"""
        if not micro_liquidity or micro_liquidity.get('status') not in ['warning', 'early_warning']:
            return 0.0
        
        # 检查该方向是否包含微盘高暴露指数
        if any(idx in self.config.micro_cap_indices 
               for idx in self.config.direction_indices[direction]):
            # 微盘熔断期：额外惩罚
            return 0.2 if micro_liquidity['status'] == 'warning' else 0.1
        
        return 0.0    
    
    def calculate_allocation(self, benchmark_data: Dict,
                           micro_liquidity: Optional[Dict] = None,
                           config: Optional[AllocationConfig] = None,
                           macro_result: Optional[Dict] = None) -> pd.DataFrame:
        """
        计算战略方向配置（完整版）
        参数:
            benchmark_data: 市值基准数据
            micro_liquidity: 微盘流动性状态（可选）
            config: 自定义配置（可选，None=使用系统配置）
            macro_result: 宏观评分结果（可选）
        返回:
            配置DataFrame
        """
        # ⭐ 关键修改：使用传入的 config 或系统配置
        if config is None:
            config = self.config.allocation_config

        results = []
        total_weight = 0.0
        
        # 1. 计算各方向评分
        direction_scores = self._calculate_direction_scores()
                
        # 2. 获取商品信号（V5.7 新增）
        commodity_signals = self.ie.calculate_commodity_signals()
        
        # 3. 计算商品调整因子
        direction_adjustments = self._calculate_commodity_adjustments(commodity_signals)
        
        # 4. 获取期权PCR情绪
        pcr_data = self.ie.calculate_pcr()
        pcr_score = 50.0 + (1.0 - pcr_data.get('composite', {}).get('pcr', 1.0)) * 50
        
        # 5. 计算最终配置
        for direction, base_weight in self.config.base_weights.items():
            scores = direction_scores[direction]
            val_factors = scores['valuation'] / 100
            trend_factors = scores['trend'] / 100
            fund_factors = scores['fund'] / 100
            sent_factors = pcr_score / 100
            
            # 风险惩罚
            risk_penalty = 0.0
            if direction in self.config.high_risk_directions:
                risk_info = self.config.high_risk_directions[direction]
                risk_penalty = risk_info['cap_weight'] * config.risk_penalty_base  # ⭐ 使用 config 中的惩罚基数
            
            # ⭐【核心修改】使用 config 中的权重
            base_adjustment = (
                1.0 + 
                config.sentiment_weight * sent_factors +
                config.trend_weight * trend_factors +
                config.valuation_weight * val_factors +
                config.fund_weight * fund_factors -
                risk_penalty
            )
            base_adjustment = np.clip(base_adjustment, 0.7, 1.5)

            # 微盘暴露惩罚（使用 config 中的参数）
            micro_penalty = 0.0
            if micro_liquidity and micro_liquidity.get('status') in ['warning', 'early_warning']:
                if any(idx in self.config.micro_cap_indices 
                       for idx in self.config.direction_indices[direction]):
                    micro_penalty = (
                        config.micro_penalty_melted  # ⭐ 使用 config
                        if micro_liquidity['status'] == 'warning' 
                        else config.micro_penalty_warning  # ⭐ 使用 config
                    )

            # 商品调整（V5.7 新增）            
            commodity_adj = direction_adjustments.get(direction, 0.0)
            
            final_adjustment = np.clip(base_adjustment + commodity_adj - micro_penalty, 0.6, 1.6)
            dynamic_weight = base_weight * final_adjustment
            total_weight += dynamic_weight
            
            # 核心指数
            core_indices = self.config.direction_indices[direction][:2]
            core_display = ' + '.join(core_indices)
            
            results.append({
                '战略方向': direction,
                '基础权重': f"{base_weight:.1%}",
                '估值得分': f"{scores['valuation']:.1f}",
                '趋势得分': f"{scores['trend']:.1f}",
                '资金得分': f"{scores['fund']:.1f}",
                '情绪得分': f"{pcr_score:.1f}",
                '商品调整': f"{commodity_adj:+.2f}",
                '微盘惩罚': f"{micro_penalty:+.2f}" if micro_penalty > 0 else '-',
                '动态权重': dynamic_weight,
                '核心指数': core_display
            })
        
        # 6. 归一化
        output_df = pd.DataFrame(results)
        if total_weight > 0:
            output_df['动态权重'] = output_df['动态权重'] / total_weight
        
        # 现金仓位（使用 config 中的参数）
        market_state = self._determine_market_state(benchmark_data)
        cash_weight = config.cash_weight_defensive if '防御' in market_state else 0.0  # ⭐ 使用 config
        
        # 微盘熔断额外现金
        if micro_liquidity and micro_liquidity.get('status') == 'warning':
            cash_weight += 0.10
        elif micro_liquidity and micro_liquidity.get('status') == 'early_warning':
            cash_weight += 0.05
        
        cash_weight = min(cash_weight, 0.7)  # 最高70%现金
        
        if cash_weight > 0:
            equity_weight = 1 - cash_weight
            output_df['动态权重'] *= equity_weight
            results.append({
                '战略方向': '现金',
                '基础权重': '-',
                '估值得分': '-',
                '趋势得分': '-',
                '资金得分': '-',
                '情绪得分': '-',
                '商品调整': '-',
                '微盘惩罚': '-',
                '动态权重': cash_weight,
                '核心指数': '-'
            })
        
        output_df = pd.DataFrame(results)
        output_df['配置建议'] = output_df['动态权重'].apply(lambda x: f"{x*100:.1f}%")
        
        # 8. 根据宏观信号调整（可选）
        if macro_result:
            output_df = self._adjust_by_macro_signals(output_df, macro_result)
        
        return output_df[['战略方向', '基础权重', '估值得分', '趋势得分', '资金得分',
                         '情绪得分', '商品调整', '微盘惩罚', '动态权重', '配置建议', '核心指数']]

    def _calculate_direction_scores(self) -> Dict[str, Dict]:
        """
        计算各战略方向的评分（估值/趋势/资金）
        返回: {
            '高端制造': {'valuation': 65.2, 'trend': 72.1, 'fund': 58.3},
            '信息技术': {...},
            ...
        }
        """
        direction_scores = {}
        
        for direction, indices in self.config.direction_indices.items():
            valid_dfs = []
            for code in indices:
                df = self.ie.dm.load_index_data(code, min_days=0)
                if len(df) >= 250:
                    valid_dfs.append(df)
            
            if not valid_dfs:
                direction_scores[direction] = {
                    'valuation': 50.0, 'trend': 50.0, 'fund': 50.0
                }
                continue
            
            # 计算估值评分（带指数代码）
            avg_val = np.mean([
                self.ie.calculate_valuation_score(df, code)
                for df, code in zip(valid_dfs, indices)
            ])
            
            # 计算趋势和资金评分
            avg_trend = np.mean([self.ie.calculate_trend_score(df) for df in valid_dfs])
            avg_fund = np.mean([self.ie.calculate_fund_score(df) for df in valid_dfs])
            
            direction_scores[direction] = {
                'valuation': float(avg_val),
                'trend': float(avg_trend),
                'fund': float(avg_fund)
            }
        
        self.logger.debug(f"✅ 计算完成 {len(direction_scores)} 个战略方向评分")
        return direction_scores
    
    def _determine_market_state(self, benchmark_data: Dict) -> str:
        """简化版市场状态判定"""
        if not benchmark_data:
            return '均衡持有区'
        
        # 计算平均估值和趋势
        val_scores = []
        trend_scores = []
        
        for size, df in benchmark_data.items():
            if len(df) >= 250:
                code = self.config.market_benchmarks[size]['code']
                val_scores.append(self.ie.calculate_valuation_score(df, code))
                trend_scores.append(self.ie.calculate_trend_score(df))
        
        if not val_scores:
            return '均衡持有区'
        
        avg_val = np.mean(val_scores)
        avg_trend = np.mean(trend_scores)
        
        val_state = '低估' if avg_val < 40 else ('合理' if avg_val <= 60 else '高估')
        trend_state = '弱势' if avg_trend < 40 else ('中性' if avg_trend <= 70 else '强势')
        
        state_map = {
            ('低估', '强势'): '战略进攻区',
            ('合理', '强势'): '积极配置区',
            ('高估', '强势'): '防御进攻区',
            ('低估', '中性'): '左侧布局区',
            ('合理', '中性'): '均衡持有区',
            ('高估', '中性'): '防御观望区',
            ('低估', '弱势'): '左侧防御区',
            ('合理', '弱势'): '谨慎持有区',
            ('高估', '弱势'): '战略防御区'
        }
        
        return state_map.get((val_state, trend_state), '均衡持有区')
    
    def _adjust_by_macro_signals(self, allocation_df: pd.DataFrame, 
                                 macro_result: Dict) -> pd.DataFrame:
        """
        根据宏观信号调整配置
        参数:
            allocation_df: 配置DataFrame
            macro_result: 宏观评分结果
        返回:
            调整后的配置DataFrame
        """
        market_state = macro_result['market_state']
        composite_score = macro_result['composite_score']
        
        # 获取市场状态对应的仓位限制
        position_limits = self.config.position_control['market_state_weights'].get(
            market_state,
            {'equity_min': 0.55, 'equity_max': 0.65}
        )
        
        # 计算当前权益仓位
        current_equity = allocation_df[allocation_df['战略方向'] != '现金']['动态权重'].sum()
        
        # 调整目标仓位
        target_equity = (position_limits['equity_min'] + position_limits['equity_max']) / 2
        
        if current_equity > target_equity:
            # 降低权益仓位
            compression_ratio = target_equity / current_equity
            allocation_df.loc[allocation_df['战略方向'] != '现金', '动态权重'] *= compression_ratio
        elif current_equity < target_equity:
            # 增加权益仓位（按比例分配到各方向）
            expansion_ratio = target_equity / current_equity if current_equity > 0 else 1.0
            allocation_df.loc[allocation_df['战略方向'] != '现金', '动态权重'] *= expansion_ratio
        
        # 处理预警规则建议的调整
        for alert in macro_result.get('alerts', []):
            if alert['priority'] == 'high':
                # 高优先级预警：直接应用建议调整
                adjustment = alert.get('suggested_adjustment', 0)
                for direction in alert.get('affected_directions', []):
                    mask = allocation_df['战略方向'] == direction
                    if mask.any():
                        allocation_df.loc[mask, '动态权重'] *= (1 + adjustment)
        
        # 重新归一化
        total = allocation_df[allocation_df['战略方向'] != '现金']['动态权重'].sum()
        if total > 0:
            allocation_df.loc[allocation_df['战略方向'] != '现金', '动态权重'] /= total
        
        # 更新配置建议
        allocation_df['配置建议'] = allocation_df['动态权重'].apply(lambda x: f"{x*100:.1f}%")
        
        return allocation_df

# %%
# 13 ==================== 可视化引擎层 Visualizer ====================
"""
A 股市场状态量化系统 V5.7
可视化模块 - 15 大核心图表 + 新增商品/宏观图表
基于 Plotly 交互式可视化
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Tuple
from datetime import datetime
import warnings
warnings.filterwarnings('ignore')

try:
    import plotly.graph_objects as go
    from plotly.subplots import make_subplots
    PLOTLY_AVAILABLE = True
except:
    PLOTLY_AVAILABLE = False
    print("⚠️ plotly 未安装，可视化功能将受限")


class Visualizer:
    """
    V5.7 可视化引擎
    功能：15 大核心图表 + 商品期货 + 宏观指标可视化
    """
    
    def __init__(self, config=None, index_mapper=None):
        """
        初始化可视化引擎
        
        参数:
            config: 系统配置对象（SystemConfig）
            index_mapper: 指数名称映射器（IndexNameMapper）
        """
        self.config = config
        self.index_mapper = index_mapper
        self.chinese_font = self._get_chinese_font()
    
    # ==================== 辅助方法 ====================
    
    def _get_chinese_font(self) -> str:
        """智能检测系统中可用的中文字体"""
        font_candidates = [
            "Microsoft YaHei", "SimHei", "WenQuanYi Micro Hei",
            "STHeiti", "Arial Unicode MS", "sans-serif"
        ]
        return ",".join(font_candidates)
    
    def _apply_chinese_layout(self, fig: go.Figure) -> go.Figure:
        """应用中文字体布局到 Plotly 图表"""
        if not PLOTLY_AVAILABLE:
            return fig
        
        fig.update_layout(
            font=dict(family=self.chinese_font, size=12),
            title_font=dict(family=self.chinese_font, size=16)
        )
        return fig
    
    def _generate_empty_chart(self, title: str, message: str) -> go.Figure:
        """生成空数据占位图表"""
        if not PLOTLY_AVAILABLE:
            return None
        
        fig = go.Figure()
        fig.add_annotation(
            text=f"⚠️ {message}",
            x=0.5, y=0.5, showarrow=False,
            font=dict(size=16, color="#e74c3c", family=self.chinese_font)
        )
        fig.update_layout(
            title=title,
            title_x=0.5,
            height=400,
            plot_bgcolor='white',
            font=dict(family=self.chinese_font, size=12)
        )
        return fig
    
    def _get_index_name(self, code: str) -> str:
        """获取指数名称（优先使用映射器）"""
        if self.index_mapper:
            name = self.index_mapper.get_name(code)
            if name and name != code:
                return name
        
        if self.config and hasattr(self.config, 'index_names'):
            name = self.config.index_names.get(code, code)
            if name != code:
                return name
        
        return code
    
    def _format_percentage(self, value: float) -> str:
        """格式化百分比显示"""
        return f"{value:.1f}%"
    
    def _format_number(self, value: float, decimals: int = 1) -> str:
        """格式化数字显示"""
        return f"{value:.{decimals}f}"
    
    # ==================== 核心图表方法（15 大图表）====================
    
    # 图表 1：估值安全边际诊断
    def _generate_valuation_diagnostic_chart(self, pe_data: Optional[pd.DataFrame] = None,
                                            bond_yield: float = 2.5) -> go.Figure:
        """
        图表 1：估值安全边际诊断（PE TTM）
        
        参数:
            pe_data: PE 历史数据 DataFrame
            bond_yield: 当前国债收益率
        """
        if not PLOTLY_AVAILABLE:
            return None
        
        if pe_data is None or len(pe_data) < 250:
            return self._generate_empty_chart("估值安全边际诊断", "PE 数据不足（需≥250 日）")
        
        try:
            current_pe = pe_data['pe_ttm'].iloc[-1]
            pe_percentile = (pe_data['pe_ttm'].iloc[:-1] < current_pe).mean() * 100
            equity_risk_premium = (100 / current_pe) - bond_yield if current_pe > 0 else 0
            
            fig = make_subplots(
                rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.15,
                subplot_titles=(
                    '📊 沪深 300 滚动市盈率 (PE TTM) 历史走势',
                    '🛡️ 估值安全边际：PE 分位数 + 股债性价比'
                ),
                row_heights=[0.6, 0.4]
            )
            
            # 上图：PE 走势
            fig.add_trace(
                go.Scatter(
                    x=pe_data['date'].iloc[-500:],
                    y=pe_data['pe_ttm'].iloc[-500:],
                    name='PE TTM',
                    line=dict(color='#1f77b4', width=2.5)
                ),
                row=1, col=1
            )
            
            # 低估区域
            fig.add_hrect(
                y0=0, y1=pe_data['pe_ttm'].quantile(0.3),
                fillcolor="lightgreen", opacity=0.2, layer="below",
                line_width=0, row=1, col=1,
                annotation_text="低估区域", annotation_position="bottom left"
            )
            
            # 高估区域
            fig.add_hrect(
                y0=pe_data['pe_ttm'].quantile(0.7),
                y1=pe_data['pe_ttm'].max() * 1.1,
                fillcolor="lightcoral", opacity=0.2, layer="below",
                line_width=0, row=1, col=1,
                annotation_text="高估区域", annotation_position="top left"
            )
            
            # 下图：股债性价比
            dates = pe_data['date'].iloc[-250:]
            erp_values = [
                (100 / pe_data['pe_ttm'].iloc[-250 + i]) - bond_yield
                if pe_data['pe_ttm'].iloc[-250 + i] > 0 else 0
                for i in range(250)
            ]
            
            fill_color = 'rgba(44, 160, 44, 0.3)' if equity_risk_premium > 3.0 else 'rgba(214, 39, 40, 0.3)'
            
            fig.add_trace(
                go.Scatter(
                    x=dates, y=erp_values,
                    name='股债性价比',
                    line=dict(color='#2ca02c', width=2.5),
                    fill='tozeroy',
                    fillcolor=fill_color
                ),
                row=2, col=1
            )
            
            # 参考线
            fig.add_hline(y=2.0, line_dash="dash", line_color="orange",
                         line_width=2, row=2, col=1, annotation_text="⚠️ 警戒线")
            fig.add_hline(y=3.5, line_dash="dash", line_color="green",
                         line_width=2, row=2, col=1, annotation_text="✅ 安全区")
            
            # 布局
            fig.update_layout(
                title_text=f"🛡️ 估值安全边际诊断 | 当前 PE={current_pe:.1f}（历史{pe_percentile:.0f}%分位）| 股债性价比={equity_risk_premium:.2f}%",
                title_x=0.5,
                hovermode="x unified",
                height=700,
                font=dict(family=self.chinese_font, size=12)
            )
            
            fig.update_xaxes(title_text="日期", row=2, col=1)
            fig.update_yaxes(title_text="PE TTM", row=1, col=1)
            fig.update_yaxes(title_text="风险溢价 (%)", row=2, col=1)
            
            return self._apply_chinese_layout(fig)
            
        except Exception as e:
            return self._generate_empty_chart("估值安全边际诊断", str(e)[:50])
    
    # 图表 2：四层市值指数走势
    def _generate_market_trend_chart(self, benchmark_data: Dict) -> go.Figure:
        """
        图表 2：四层市值指数走势与风格轮动
        
        参数:
            benchmark_data: 市值基准数据字典 {size: DataFrame}
        """
        if not PLOTLY_AVAILABLE:
            return None
        
        required_sizes = ['大盘', '中盘', '小盘', '微盘']
        available_sizes = [s for s in required_sizes if s in benchmark_data and len(benchmark_data[s]) > 250]
        
        if len(available_sizes) < 2:
            return self._generate_empty_chart("四层市值指数走势", "数据不足（需≥2 个层级）")
        
        try:
            fig = make_subplots(
                rows=2, cols=1, shared_xaxes=True,
                subplot_titles=(
                    '📊 四层市值指数标准化走势（2020-01-02=100）',
                    '📈 小盘/大盘相对强度比（20 日）'
                ),
                row_heights=[0.65, 0.35],
                vertical_spacing=0.12
            )
            
            colors = {'大盘': '#1f77b4', '中盘': '#ff7f0e', '小盘': '#2ca02c', '微盘': '#d62728'}
            start_date = max([benchmark_data[s]['datetime'].iloc[0] for s in available_sizes])
            
            # 上图：标准化走势
            for size in available_sizes:
                df = benchmark_data[size]
                df_plot = df[df['datetime'] >= start_date].copy()
                base_value = df_plot['close'].iloc[0]
                df_plot['normalized'] = df_plot['close'] / base_value * 100
                
                fig.add_trace(
                    go.Scatter(
                        x=df_plot['datetime'],
                        y=df_plot['normalized'],
                        name=f'{size} ({self._get_index_name(self.config.market_benchmarks.get(size, {}).get("code", ""))})',
                        line=dict(color=colors.get(size, '#1f77b4'), width=2.5)
                    ),
                    row=1, col=1
                )
            
            # 下图：相对强度比
            if '大盘' in benchmark_data and '小盘' in benchmark_data:
                df_large = benchmark_data['大盘']
                df_small = benchmark_data['小盘']
                
                df_merge = pd.merge(
                    df_large[['datetime', 'close']].rename(columns={'close': 'large_close'}),
                    df_small[['datetime', 'close']].rename(columns={'close': 'small_close'}),
                    on='datetime', how='inner'
                ).tail(250)
                
                if len(df_merge) > 20:
                    df_merge['ratio'] = df_merge['small_close'] / df_merge['large_close']
                    df_merge['ratio_ma20'] = df_merge['ratio'].rolling(20).mean()
                    
                    fig.add_trace(
                        go.Scatter(
                            x=df_merge['datetime'],
                            y=df_merge['ratio_ma20'],
                            name='小盘/大盘相对强度 (20 日 MA)',
                            line=dict(color='#9467bd', width=2.5)
                        ),
                        row=2, col=1
                    )
                    
                    fig.add_hline(y=1.0, line_dash="solid", line_color="black",
                                 line_width=1.5, row=2, col=1)
                    fig.add_hline(y=1.25, line_dash="dash", line_color="green",
                                 line_width=2, row=2, col=1, annotation_text="小盘显著占优")
                    fig.add_hline(y=0.75, line_dash="dash", line_color="red",
                                 line_width=2, row=2, col=1, annotation_text="大盘显著占优")
            
            # 布局
            fig.update_layout(
                title="📊 市值分层走势与风格轮动监测",
                title_x=0.5,
                hovermode="x unified",
                height=750,
                font=dict(family=self.chinese_font, size=12),
                legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
            )
            
            fig.update_xaxes(title_text="日期", row=2, col=1)
            fig.update_yaxes(title_text="标准化指数 (2020-01-02=100)", row=1, col=1)
            fig.update_yaxes(title_text="相对强度比", row=2, col=1)
            
            return self._apply_chinese_layout(fig)
            
        except Exception as e:
            return self._generate_empty_chart("四层市值指数走势", str(e)[:50])
    
    # 图表 3：微盘层流动性监控
    def _generate_micro_liquidity_chart(self, micro_data: Dict) -> go.Figure:
        """
        图表 3：微盘层流动性监控
        
        参数:
            micro_data: {'primary': DataFrame, 'secondary': DataFrame, 'liquidity_status': Dict}
        """
        if not PLOTLY_AVAILABLE:
            return None
        
        df_primary = micro_data.get('primary', pd.DataFrame())
        df_secondary = micro_data.get('secondary', pd.DataFrame())
        
        if len(df_primary) < 250 or len(df_secondary) < 250:
            return self._generate_empty_chart("微盘层流动性监控", "数据不足（需≥250 日）")
        
        try:
            fig = make_subplots(
                rows=3, cols=1, shared_xaxes=True,
                subplot_titles=(
                    '💧 微盘双指数价格走势',
                    '💰 成交额对比（亿元）',
                    '⚠️ 流动性失真检测'
                ),
                row_heights=[0.35, 0.35, 0.30],
                vertical_spacing=0.12
            )
            
            # 子图 1：价格走势
            fig.add_trace(
                go.Scatter(
                    x=df_primary['datetime'],
                    y=df_primary['close'],
                    name='中证 2000 (932000)',
                    line=dict(color='#d62728', width=2.5)
                ),
                row=1, col=1
            )
            
            fig.add_trace(
                go.Scatter(
                    x=df_secondary['datetime'],
                    y=df_secondary['close'],
                    name='国证 1000 (399311)',
                    line=dict(color='#9467bd', width=2.5, dash='dot')
                ),
                row=1, col=1
            )
            
            # 子图 2：成交额
            fig.add_trace(
                go.Scatter(
                    x=df_primary['datetime'],
                    y=df_primary['amount'] / 100,
                    name='中证 2000 成交额',
                    line=dict(color='#d62728', width=2),
                    yaxis='y2'
                ),
                row=2, col=1
            )
            
            fig.add_trace(
                go.Scatter(
                    x=df_secondary['datetime'],
                    y=df_secondary['amount'] / 100,
                    name='国证 1000 成交额',
                    line=dict(color='#9467bd', width=2, dash='dot'),
                    yaxis='y2'
                ),
                row=2, col=1
            )
            
            # 子图 3：流动性失真标记
            if 'liquidity_distorted' in df_primary.columns:
                distorted_dates = df_primary[df_primary['liquidity_distorted']]['datetime']
                
                for date in distorted_dates[-10:]:  # 只显示最近 10 个
                    fig.add_vline(
                        x=date, line_dash="dash", line_color="red", line_width=2,
                        row=3, col=1, annotation_text="⚠️ 失真", annotation_position="top"
                    )
            
            # 预警阈值线
            vol_5d_avg = df_primary['amount'].rolling(5).mean().iloc[-1] / 100
            if not pd.isna(vol_5d_avg):
                fig.add_hline(
                    y=vol_5d_avg * 0.6, line_dash="dash", line_color="red", line_width=2,
                    row=2, col=1, annotation_text="⚠️ 预警阈值 (60%)"
                )
            
            # 布局
            fig.update_layout(
                title="💧 微盘层流动性监控（纯量价逻辑）",
                title_x=0.5,
                hovermode="x unified",
                height=800,
                font=dict(family=self.chinese_font, size=12),
                legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
            )
            
            fig.update_xaxes(title_text="日期", row=3, col=1)
            fig.update_yaxes(title_text="指数价格", row=1, col=1)
            fig.update_yaxes(title_text="成交额 (亿元)", row=2, col=1)
            fig.update_yaxes(title_text="流动性状态", row=3, col=1)
            
            return self._apply_chinese_layout(fig)
            
        except Exception as e:
            return self._generate_empty_chart("微盘层流动性监控", str(e)[:50])
    
    # 图表 4：大小盘风格轮动
    def _generate_style_rotation_chart(self, benchmark_data: Dict) -> go.Figure:
        """图表 4：大小盘风格轮动监测"""
        if not PLOTLY_AVAILABLE:
            return None
        
        df_large = benchmark_data.get('大盘', pd.DataFrame())
        df_small = benchmark_data.get('小盘', pd.DataFrame())
        
        if len(df_large) < 250 or len(df_small) < 250:
            return self._generate_empty_chart("大小盘风格轮动监测", "数据不足")
        
        try:
            df_merge = pd.merge(
                df_large[['datetime', 'close']].rename(columns={'close': 'large'}),
                df_small[['datetime', 'close']].rename(columns={'close': 'small'}),
                on='datetime', how='inner'
            ).tail(250)
            
            df_merge['ratio'] = df_merge['small'] / df_merge['large']
            df_merge['ratio_ma20'] = df_merge['ratio'].rolling(20).mean()
            
            fig = go.Figure()
            
            fig.add_trace(
                go.Scatter(
                    x=df_merge['datetime'],
                    y=df_merge['ratio_ma20'],
                    name='20 日相对强度比',
                    line=dict(color='#9467bd', width=2.5),
                    fill='tozeroy',
                    fillcolor='rgba(148, 103, 189, 0.2)'
                )
            )
            
            fig.add_hline(y=1.0, line_dash="solid", line_color="black", line_width=1.5)
            fig.add_hline(y=1.25, line_dash="dash", line_color="green", line_width=2.5)
            fig.add_hline(y=0.75, line_dash="dash", line_color="red", line_width=2.5)
            
            fig.update_layout(
                title="🔄 大小盘风格轮动监测（近 250 交易日）",
                title_x=0.5,
                height=550,
                xaxis_title="日期",
                yaxis_title="20 日相对强度比（中证 1000/沪深 300）",
                hovermode="x unified",
                font=dict(family=self.chinese_font, size=12)
            )
            
            fig.add_annotation(
                text="💡 >1.25: 小盘占优 | <0.75: 大盘占优 | 1.0: 均衡",
                xref="paper", yref="paper",
                x=0.5, y=-0.15, showarrow=False,
                font=dict(size=11, color="#7f8c8d", family=self.chinese_font)
            )
            
            return self._apply_chinese_layout(fig)
            
        except Exception as e:
            return self._generate_empty_chart("大小盘风格轮动监测", str(e)[:50])
    
    # 图表 5：市场状态九宫格
    def _generate_market_state_chart(self, market_state: str,
                                     val_score: float,
                                     trend_score: float) -> go.Figure:
        """
        图表 5：市场状态九宫格定位
        
        参数:
            market_state: 当前市场状态
            val_score: 估值得分 (0-100)
            trend_score: 趋势得分 (0-100)
        """
        if not PLOTLY_AVAILABLE:
            return None
        
        try:
            fig = go.Figure()
            
            # 九宫格区域定义
            regions = [
                {'x': [0, 40], 'y': [60, 100], 'name': '战略进攻区', 'color': '#27ae60'},
                {'x': [40, 60], 'y': [60, 100], 'name': '积极配置区', 'color': '#2ecc71'},
                {'x': [60, 100], 'y': [60, 100], 'name': '防御进攻区', 'color': '#f39c12'},
                {'x': [0, 40], 'y': [40, 60], 'name': '左侧布局区', 'color': '#3498db'},
                {'x': [40, 60], 'y': [40, 60], 'name': '均衡持有区', 'color': '#95a5a6'},
                {'x': [60, 100], 'y': [40, 60], 'name': '防御观望区', 'color': '#e67e22'},
                {'x': [0, 40], 'y': [0, 40], 'name': '左侧防御区', 'color': '#e74c3c'},
                {'x': [40, 60], 'y': [0, 40], 'name': '谨慎持有区', 'color': '#c0392b'},
                {'x': [60, 100], 'y': [0, 40], 'name': '战略防御区', 'color': '#922b21'}
            ]
            
            # 绘制区域
            for region in regions:
                fig.add_shape(
                    type="rect",
                    x0=region['x'][0], y0=region['y'][0],
                    x1=region['x'][1], y1=region['y'][1],
                    fillcolor=region['color'], opacity=0.3,
                    line_width=1, line_color="lightgray"
                )
                
                fig.add_annotation(
                    x=(region['x'][0] + region['x'][1]) / 2,
                    y=(region['y'][0] + region['y'][1]) / 2,
                    text=region['name'],
                    showarrow=False,
                    font=dict(size=10, color="white"),
                    opacity=0.8
                )
            
            # 当前状态点
            fig.add_trace(
                go.Scatter(
                    x=[trend_score],
                    y=[val_score],
                    mode='markers+text',
                    name='当前状态',
                    marker=dict(size=15, color='#2c3e50', symbol='star'),
                    text=[market_state],
                    textposition="top center",
                    textfont=dict(size=12, color="#2c3e50")
                )
            )
            
            fig.update_layout(
                title=f"🎯 市场状态九宫格定位：{market_state}",
                title_x=0.5,
                xaxis=dict(title="趋势动能强度", range=[0, 100]),
                yaxis=dict(title="估值安全边际", range=[0, 100]),
                height=600,
                showlegend=False,
                font=dict(family=self.chinese_font, size=12)
            )
            
            fig.add_annotation(
                text=f"💡 估值{val_score:.0f}/100 | 趋势{trend_score:.0f}/100",
                xref="paper", yref="paper",
                x=0.5, y=-0.12, showarrow=False,
                font=dict(size=12, color="#7f8c8d", family=self.chinese_font)
            )
            
            return self._apply_chinese_layout(fig)
            
        except Exception as e:
            return self._generate_empty_chart("市场状态九宫格定位", str(e)[:50])
    
    # 图表 6：九大战略方向配置
    def _generate_allocation_chart(self, allocation_df: pd.DataFrame) -> go.Figure:
        """
        图表 6：九大战略方向动态配置
        
        参数:
            allocation_df: 配置结果 DataFrame
        """
        if not PLOTLY_AVAILABLE:
            return None
        
        if allocation_df is None or len(allocation_df) == 0:
            return self._generate_empty_chart("九大战略方向动态配置", "配置数据为空")
        
        try:
            alloc_data = allocation_df[allocation_df['战略方向'] != '现金'].copy()
            
            if len(alloc_data) == 0:
                return self._generate_empty_chart("九大战略方向动态配置", "无权益配置数据")
            
            color_map = {
                '高端制造': '#1f77b4', '信息技术': '#ff7f0e', '新能源': '#2ca02c',
                '生物健康': '#d62728', '公用事业': '#9467bd', '供应链': '#8c564b',
                '传统升级': '#e377c2', '文化消费': '#7f7f7f', '现代农业': '#bcbd22'
            }
            
            fig = make_subplots(
                rows=1, cols=2,
                column_widths=[0.45, 0.55],
                specs=[[{"type": "pie"}, {"type": "bar"}]],
                subplot_titles=('环形图：配置权重分布', '条形图：战略方向排序')
            )
            
            # 左图：环形图
            fig.add_trace(
                go.Pie(
                    labels=alloc_data['战略方向'],
                    values=alloc_data['动态权重'] * 100,
                    hole=0.6,
                    marker=dict(
                        colors=[color_map.get(d, '#1f77b4') for d in alloc_data['战略方向']],
                        line=dict(color='#ffffff', width=2)
                    ),
                    textinfo='label+percent',
                    textposition='outside'
                ),
                row=1, col=1
            )
            
            # 右图：条形图
            fig.add_trace(
                go.Bar(
                    y=alloc_data['战略方向'],
                    x=alloc_data['动态权重'] * 100,
                    orientation='h',
                    marker=dict(
                        color=[color_map.get(d, '#1f77b4') for d in alloc_data['战略方向']],
                        line=dict(color='white', width=1.5)
                    ),
                    text=alloc_data['动态权重'].apply(lambda x: f"{x*100:.1f}%"),
                    textposition='auto'
                ),
                row=1, col=2
            )
            
            # 计算权益仓位
            total_equity = alloc_data['动态权重'].sum()
            
            fig.add_annotation(
                text=f"<b>权益仓位</b><br>{total_equity*100:.1f}%",
                x=0.225, y=0.5, showarrow=False,
                font=dict(size=18, color="black", family=self.chinese_font),
                xref="paper", yref="paper"
            )
            
            fig.update_layout(
                title="💼 九大战略方向动态配置",
                title_x=0.5,
                height=600,
                showlegend=False,
                font=dict(family=self.chinese_font, size=12)
            )
            
            fig.update_xaxes(title_text="配置权重 (%)", row=1, col=2)
            
            return self._apply_chinese_layout(fig)
            
        except Exception as e:
            return self._generate_empty_chart("九大战略方向动态配置", str(e)[:50])
    
    # 图表 7：高风险方向雷达图
    def _generate_high_risk_chart(self, risk_data: List[Dict]) -> go.Figure:
        """
        图表 7：高风险方向四维评估雷达图
        
        参数:
            risk_data: 风险数据列表 [{'direction': str, 'micro': float, 'volatility': float, ...}]
        """
        if not PLOTLY_AVAILABLE:
            return None
        
        if not risk_data or len(risk_data) == 0:
            return self._generate_empty_chart("高风险方向四维评估雷达图", "风险数据为空")
        
        try:
            dimensions = ['微盘暴露', '波动率', '估值分位', '流动性']
            
            color_map = {
                '文化消费': '#e74c3c',
                '高端制造': '#e67e22',
                '信息技术': '#f39c12',
                '现代农业': '#27ae60',
                '新能源': '#2ecc71'
            }
            
            fig = go.Figure()
            
            for item in risk_data:
                values = [
                    item.get('micro', 50),
                    item.get('volatility', 50),
                    item.get('valuation', 50),
                    item.get('liquidity', 50)
                ]
                values += values[:1]  # 闭合雷达图
                
                fig.add_trace(
                    go.Scatterpolar(
                        r=values,
                        theta=dimensions + [dimensions[0]],
                        fill='toself',
                        name=f"{item['direction']} ({item.get('total', 0):.0f}分)",
                        line=dict(color=color_map.get(item['direction'], '#1f77b4'), width=2),
                        fillcolor=color_map.get(item['direction'], '#1f77b4'),
                        opacity=0.15
                    )
                )
            
            # 风险阈值线
            for threshold, color, label in [(80, '#e74c3c', '高风险'), (60, '#f39c12', '中高风险'), (40, '#27ae60', '中风险')]:
                fig.add_trace(
                    go.Scatterpolar(
                        r=[threshold] * 5,
                        theta=dimensions + [dimensions[0]],
                        mode='lines',
                        line=dict(color=color, width=1, dash='dash'),
                        name=label,
                        showlegend=True
                    )
                )
            
            fig.update_layout(
                title="🔴 高风险方向四维评估雷达图（微盘 35% + 波动率 25% + 估值 25% + 流动性 15%）",
                title_x=0.5,
                polar=dict(
                    radialaxis=dict(visible=True, range=[0, 100], tickfont=dict(size=11)),
                    bgcolor='rgba(240, 240, 240, 0.5)'
                ),
                showlegend=True,
                height=650,
                font=dict(family=self.chinese_font, size=12),
                legend=dict(orientation="h", yanchor="bottom", y=-0.15, xanchor="center", x=0.5)
            )
            
            fig.add_annotation(
                text="💡 综合得分>60 分：建议仓位上限 20% | >75 分：建议仓位上限 15%",
                xref="paper", yref="paper",
                x=0.5, y=-0.25, showarrow=False,
                font=dict(size=12, color="#7f8c8d", family=self.chinese_font)
            )
            
            return self._apply_chinese_layout(fig)
            
        except Exception as e:
            return self._generate_empty_chart("高风险方向四维评估雷达图", str(e)[:50])
    
    # 图表 8：期权 PCR 趋势图
    def _generate_option_pcr_chart(self, pcr_data: Dict) -> go.Figure:
        """
        📊 图表 8：期权 PCR 趋势图（优化版）
        适配 V5.7 实际数据结构
        
        参数:
            pcr_data: PCR 数据字典
                {
                    'composite_pcr': float,
                    'composite_signal': str,
                    'components': {
                        '510300': {'pcr_oi': float, 'pcr_volume': float, 'pcr_ma5': float, 'signal': str, ...},
                        'IO': {'error': str} or {...},
                        ...
                    },
                    'weights_used': {...}
                }
        
        返回:
            Plotly Figure 对象
        """
        if not PLOTLY_AVAILABLE:
            return None
        
        # 检查数据有效性
        if not pcr_data or 'composite_pcr' not in pcr_data:
            return self._generate_empty_chart("期权 PCR 趋势图", "PCR 数据格式不正确")
        
        try:
            # ==================== 1. 提取核心数据 ====================
            composite_pcr = pcr_data.get('composite_pcr', 1.0)
            composite_signal = pcr_data.get('composite_signal', '中性')
            components = pcr_data.get('components', {})
            weights = pcr_data.get('weights_used', {})
            
            # 过滤掉有错误的标的
            valid_components = {
                k: v for k, v in components.items() 
                if 'error' not in v and 'pcr_oi' in v
            }
            
            if not valid_components:
                return self._generate_empty_chart("期权 PCR 趋势图", "无有效期权数据")
            
            # ==================== 2. 创建子图布局 ====================
            n_components = len(valid_components)
            rows = 2 if n_components > 2 else 1
            cols = min(n_components, 3)
            
            # 动态调整子图规格
            specs = [[{"type": "indicator"}]*cols for _ in range(rows)]
            subplot_titles = []
            
            for i, (underlying, data) in enumerate(valid_components.items()):
                if i >= rows * cols:
                    break
                signal = data.get('signal', '中性')
                pcr_value = data.get('pcr_oi', 1.0)
                subplot_titles.append(f"{underlying} | PCR={pcr_value:.2f} | {signal}")
            
            fig = make_subplots(
                rows=rows, cols=cols,
                specs=specs,
                subplot_titles=subplot_titles,
                vertical_spacing=0.2,
                horizontal_spacing=0.1
            )
            
            # ==================== 3. 绘制各标的仪表盘 ====================
            for i, (underlying, data) in enumerate(valid_components.items()):
                if i >= rows * cols:
                    break
                
                row = (i // cols) + 1
                col = (i % cols) + 1
                
                pcr_value = data.get('pcr_oi', 1.0)
                pcr_volume = data.get('pcr_volume', 1.0)
                pcr_ma5 = data.get('pcr_ma5', pcr_value)
                signal = data.get('signal', '中性')
                contracts_used = data.get('contracts_used', 0)
                data_quality = data.get('data_quality', 'unknown')
                
                # 确定颜色
                if pcr_value > 1.5:
                    gauge_color = '#e74c3c'  # 红色 - 极度悲观
                    status_emoji = '🔴'
                elif pcr_value > 1.2:
                    gauge_color = '#f39c12'  # 橙色 - 看跌
                    status_emoji = '🟠'
                elif pcr_value > 0.8:
                    gauge_color = '#f1c40f'  # 黄色 - 中性
                    status_emoji = '🟡'
                else:
                    gauge_color = '#27ae60'  # 绿色 - 看涨
                    status_emoji = '🟢'
                
                # 添加仪表盘
                fig.add_trace(
                    go.Indicator(
                        mode="gauge+number+delta",
                        value=pcr_value,
                        domain={'x': [0, 1], 'y': [0.4, 1]},
                        title={
                            'text': f"<b>{underlying}</b>",
                            'font': {'size': 14, 'family': self.chinese_font}
                        },
                        delta={
                            'reference': 1.0,
                            'increasing': {'color': '#e74c3c'},
                            'decreasing': {'color': '#27ae60'}
                        },
                        gauge={
                            'axis': {'range': [0, 2.5], 'tickwidth': 1, 'tickcolor': "#636363"},
                            'bar': {'color': gauge_color, 'thickness': 0.8},
                            'bgcolor': "#f8f9fa",
                            'borderwidth': 2,
                            'bordercolor': "#636363",
                            'steps': [
                                {'range': [0, 0.8], 'color': '#27ae60'},    # 看涨
                                {'range': [0.8, 1.2], 'color': '#f1c40f'},  # 中性
                                {'range': [1.2, 1.5], 'color': '#f39c12'},  # 看跌
                                {'range': [1.5, 2.5], 'color': '#e74c3c'}   # 极度悲观
                            ],
                            'threshold': {
                                'line': {'color': "red", 'width': 4},
                                'thickness': 0.75,
                                'value': 1.0
                            }
                        }
                    ),
                    row=row, col=col
                )
                
                # 添加辅助信息标注
                fig.add_annotation(
                    text=f"📊 信号: {signal}<br>"
                        f"📈 PCR(持仓): {pcr_value:.2f}<br>"
                        f"💰 PCR(成交): {pcr_volume:.2f}<br>"
                        f"📊 PCR(5日MA): {pcr_ma5:.2f}<br>"
                        f"🔍 合约数: {contracts_used}<br>"
                        f"⭐ 质量: {data_quality}",
                    xref=f"x{i+1}",
                    yref=f"y{i+1}",
                    x=0.5,
                    y=0.15,
                    showarrow=False,
                    font=dict(size=10, color="#2c3e50", family=self.chinese_font),
                    align="center"
                )
            
            # ==================== 4. 全局布局 ====================
            fig.update_layout(
                title=f"📊 期权 PCR 情绪指标仪表盘 | 综合 PCR: {composite_pcr:.2f} | {status_emoji} {composite_signal}",
                title_x=0.5,
                height=400 * rows,
                font=dict(family=self.chinese_font, size=12),
                showlegend=False
            )
            
            # 添加综合信息标注
            fig.add_annotation(
                text=f"💡 PCR > 1.5: {status_emoji} 极度悲观（潜在反弹）<br>"
                    f"💡 PCR 1.2-1.5: 🟠 看跌情绪浓厚<br>"
                    f"💡 PCR 0.8-1.2: 🟡 中性区间<br>"
                    f"💡 PCR < 0.8: 🟢 极度乐观（潜在回调）",
                xref="paper",
                yref="paper",
                x=0.5,
                y=-0.1,
                showarrow=False,
                font=dict(size=11, color="#7f8c8d", family=self.chinese_font),
                align="center"
            )
            
            return self._apply_chinese_layout(fig)
            
        except Exception as e:
            return self._generate_empty_chart("期权 PCR 趋势图", f"图表生成失败: {str(e)[:50]}")    
    
    def _generate_option_pcr_chart_simple(self, pcr_data: Dict) -> go.Figure:
        """
        简化版：单个综合仪表盘 + 标的列表
        """
        if not PLOTLY_AVAILABLE:
            return None
        
        if not pcr_data or 'composite_pcr' not in pcr_data:
            return self._generate_empty_chart("期权 PCR 趋势图", "PCR 数据格式不正确")
        
        try:
            composite_pcr = pcr_data.get('composite_pcr', 1.0)
            composite_signal = pcr_data.get('composite_signal', '中性')
            components = pcr_data.get('components', {})
            
            # 确定综合颜色
            if composite_pcr > 1.5:
                color = '#e74c3c'
                emoji = '🔴'
            elif composite_pcr > 1.2:
                color = '#f39c12'
                emoji = '🟠'
            elif composite_pcr > 0.8:
                color = '#f1c40f'
                emoji = '🟡'
            else:
                color = '#27ae60'
                emoji = '🟢'
            
            fig = go.Figure()
            
            fig.add_trace(go.Indicator(
                mode="gauge+number+delta",
                value=composite_pcr,
                title={
                    'text': f"<b>综合期权 PCR 情绪指标</b><br><span style='font-size:14px'>{emoji} {composite_signal}</span>",
                    'font': {'size': 16, 'family': self.chinese_font}
                },
                delta={'reference': 1.0},
                gauge={
                    'axis': {'range': [0, 2.5]},
                    'bar': {'color': color},
                    'steps': [
                        {'range': [0, 0.8], 'color': '#27ae60'},
                        {'range': [0.8, 1.2], 'color': '#f1c40f'},
                        {'range': [1.2, 1.5], 'color': '#f39c12'},
                        {'range': [1.5, 2.5], 'color': '#e74c3c'}
                    ],
                    'threshold': {'line': {'color': "red", 'width': 4}, 'thickness': 0.75, 'value': 1.0}
                }
            ))
            
            # 添加各标的详情
            details_text = "<b>各标的 PCR 详情:</b><br>"
            for underlying, data in components.items():
                if 'error' in data:
                    details_text += f"• {underlying}: ❌ {data['error']}<br>"
                else:
                    pcr = data.get('pcr_oi', 1.0)
                    signal = data.get('signal', '中性')
                    quality = data.get('data_quality', 'unknown')
                    details_text += f"• {underlying}: PCR={pcr:.2f} | {signal} | {quality}<br>"
            
            fig.add_annotation(
                text=details_text,
                xref="paper", yref="paper",
                x=0.5, y=-0.2,
                showarrow=False,
                font=dict(size=11, color="#2c3e50", family=self.chinese_font),
                align="left"
            )
            
            fig.update_layout(
                height=500,
                font=dict(family=self.chinese_font, size=12)
            )
            
            return self._apply_chinese_layout(fig)
            
        except Exception as e:
            return self._generate_empty_chart("期权 PCR 趋势图", str(e)[:50])
    
    # 图表 9：期货期限结构热力图
    def _generate_futures_term_structure_chart(self, term_data: Dict) -> go.Figure:
        """
        图表 9：期货期限结构热力图 ⭐
        
        参数:
            term_data: 期限结构数据 {'copper': {'spread': float, 'structure': str}, ...}
        """
        if not PLOTLY_AVAILABLE:
            return None
        
        if not term_data or len(term_data) == 0:
            return self._generate_empty_chart("期货期限结构热力图", "数据不足")
        
        try:
            commodities = list(term_data.keys())
            spreads = [term_data[c]['spread'] for c in commodities]
            structures = [term_data[c]['structure'] for c in commodities]
            colors = ['#27ae60' if s == 'backwardation' else '#e74c3c' for s in structures]
            
            fig = go.Figure(data=go.Bar(
                x=commodities,
                y=spreads,
                marker_color=colors,
                text=[f"{s:.1f}%" for s in spreads],
                textposition='auto'
            ))
            
            fig.update_layout(
                title="📊 商品期货期限结构热力图",
                title_x=0.5,
                xaxis_title="商品品种",
                yaxis_title="近远月价差 (%)",
                height=400,
                font=dict(family=self.chinese_font, size=12)
            )
            
            fig.add_hline(y=0, line_dash="solid", line_color="gray")
            
            fig.add_annotation(
                text="💡 绿色=Backwardation(供应紧张) | 红色=Contango(供应充足)",
                xref="paper", yref="paper",
                x=0.5, y=-0.15, showarrow=False,
                font=dict(size=11, color="#7f8c8d", family=self.chinese_font)
            )
            
            return self._apply_chinese_layout(fig)
            
        except Exception as e:
            return self._generate_empty_chart("期货期限结构热力图", str(e)[:50])
    
    # 图表 10：期现基差监控图
    def _generate_futures_basis_chart(self, basis_data: Dict) -> go.Figure:
        """
        图表 10：期现基差监控图 ⭐
        
        参数:
            basis_data: 基差数据 {'if_basis': {'percent': float, 'signal': str}, ...}
        """
        if not PLOTLY_AVAILABLE:
            return None
        
        if not basis_data or len(basis_data) == 0:
            return self._generate_empty_chart("期现基差监控图", "数据不足")
        
        try:
            indices = list(basis_data.keys())
            basis_values = [basis_data[i]['percent'] for i in indices]
            colors = ['#e74c3c' if v < -1.5 else ('#f39c12' if v < 0 else '#27ae60') for v in basis_values]
            
            fig = go.Figure(data=go.Bar(
                x=indices,
                y=basis_values,
                marker_color=colors,
                text=[f"{v:.1f}%" for v in basis_values],
                textposition='auto'
            ))
            
            fig.update_layout(
                title="📊 股指期货基差监控图",
                title_x=0.5,
                xaxis_title="股指期货品种",
                yaxis_title="基差 (%)",
                height=400,
                font=dict(family=self.chinese_font, size=12)
            )
            
            fig.add_hline(y=0, line_dash="solid", line_color="gray")
            fig.add_hline(y=-1.5, line_dash="dash", line_color="red",
                         annotation_text="深度贴水线")
            
            return self._apply_chinese_layout(fig)
            
        except Exception as e:
            return self._generate_empty_chart("期现基差监控图", str(e)[:50])
    
    # 图表 11：资金流向热力图
    def _generate_fund_flow_heatmap(self, flow_data: Dict) -> go.Figure:
        """
        图表 11：资金流向热力图 ⭐
        
        参数:
            flow_data: 资金数据 {'categories': [], 'data_values': [[5d, 10d, 20d], ...]}
        """
        if not PLOTLY_AVAILABLE:
            return None
        
        if not flow_data or 'categories' not in flow_data:
            return self._generate_empty_chart("资金流向热力图", "数据不足")
        
        try:
            categories = flow_data['categories']
            data_values = flow_data['data_values']
            
            fig = go.Figure(data=go.Heatmap(
                z=data_values,
                x=['5 日变化%', '10 日变化%', '20 日变化%'],
                y=categories,
                colorscale='RdYlGn',
                zmid=0,
                text=[[f"{v:.1f}" for v in row] for row in data_values],
                texttemplate="%{text}",
                textfont={"size": 10}
            ))
            
            fig.update_layout(
                title="💰 资金流向热力图（融资余额/北上资金/ETF 规模）",
                title_x=0.5,
                xaxis_title="时间周期",
                yaxis_title="资金类型",
                height=400,
                font=dict(family=self.chinese_font, size=12)
            )
            
            fig.add_annotation(
                text="💡 绿色=净流入 | 红色=净流出",
                xref="paper", yref="paper",
                x=0.5, y=-0.15, showarrow=False,
                font=dict(size=11, color="#7f8c8d", family=self.chinese_font)
            )
            
            return self._apply_chinese_layout(fig)
            
        except Exception as e:
            return self._generate_empty_chart("资金流向热力图", str(e)[:50])
    
    # 图表 12：市场情绪仪表盘
    def _generate_sentiment_dashboard(self, sentiment_data: Dict) -> go.Figure:
        """
        图表 12：市场情绪指标仪表盘 ⭐
        参数:
            sentiment_data: 情绪数据 {'margin_score': float, 'fund_score': float, 'vol_score': float, 'vix_score': float}
        """
        if not PLOTLY_AVAILABLE:
            return None
        if not sentiment_data:
            return self._generate_empty_chart("市场情绪指标仪表盘", "数据不足")
        
        try:
            # ⭐⭐⭐ 修复：强制转换为 Python 原生 float ⭐⭐⭐
            margin_score = float(sentiment_data.get('margin_score', 50))
            fund_score = float(sentiment_data.get('fund_score', 50))
            vol_score = float(sentiment_data.get('vol_score', 50))
            vix_score = float(sentiment_data.get('vix_score', 50))
            
            fig = make_subplots(
                rows=2, cols=2,
                specs=[[{"type": "indicator"}, {"type": "indicator"}],
                    [{"type": "indicator"}, {"type": "indicator"}]],
                subplot_titles=['📊 融资余额情绪', '💰 基金资金情绪',
                            '📈 波动率情绪', '⚠️ 市场恐慌情绪'],
                vertical_spacing=0.15,
                horizontal_spacing=0.1
            )
            
            indicators = [
                (margin_score, "融资余额", '#3498db'),
                (fund_score, "基金资金", '#9b59b6'),
                (vol_score, "波动率", '#e67e22'),
                (vix_score, "恐慌指数", '#c0392b')
            ]
            
            for i, (score, title, color) in enumerate(indicators):
                row = (i // 2) + 1
                col = (i % 2) + 1
                fig.add_trace(
                    go.Indicator(
                        mode="gauge+number+delta",
                        value=score,  # ⭐ 现在是 Python float
                        domain={'x': [0, 1], 'y': [0, 1]},
                        title={'text': title, 'font': {'size': 14}},
                        delta={'reference': 50},
                        gauge={
                            'axis': {'range': [0, 100]},
                            'bar': {'color': color},
                            'steps': [
                                {'range': [0, 40], 'color': '#e74c3c'},
                                {'range': [40, 60], 'color': '#f39c12'},
                                {'range': [60, 100], 'color': '#27ae60'}
                            ],
                        }
                    ),
                    row=row, col=col
                )
            
            # 综合情绪得分
            composite_score = (margin_score + fund_score + vol_score + vix_score) / 4
            status = "🟢 乐观" if composite_score > 60 else ("🟡 中性" if composite_score > 40 else "🔴 悲观")
            
            fig.update_layout(
                title=f"📊 市场情绪指标仪表盘 | 综合得分：{composite_score:.1f}/100 | {status}",
                title_x=0.5,
                height=700,
                font=dict(family=self.chinese_font, size=12)
            )
            
            return self._apply_chinese_layout(fig)
            
        except Exception as e:
            return self._generate_empty_chart("市场情绪指标仪表盘", str(e)[:50])
    
    # 图表 13：跨市场联动监测图
    def _generate_cross_market_chart(self, market_data: Dict) -> go.Figure:
        """
        图表 13：跨市场联动监测图 ⭐
        
        参数:
            market_data: {'a_share': DataFrame, 'hk_share': DataFrame, 'us_share': DataFrame, 'ton': DataFrame, 'aty': DataFrame}
        """
        if not PLOTLY_AVAILABLE:
            return None
        
        if not market_data or 'a_share' not in market_data:
            return self._generate_empty_chart("跨市场联动监测图", "数据不足")
        
        try:
            fig = make_subplots(
                rows=2, cols=1, shared_xaxes=True,
                subplot_titles=(
                    '🌍 全球主要市场指数标准化走势（2020-01-02=100）',
                    '💰 北上资金 + 美债收益率'
                ),
                row_heights=[0.65, 0.35],
                vertical_spacing=0.12
            )
            
            # 子图 1：市场指数
            colors = {'A 股': '#e74c3c', '港股': '#3498db', '美股': '#27ae60'}
            start_date = max([market_data[m]['datetime'].iloc[0]
                             for m in ['a_share', 'hk_share', 'us_share']
                             if m in market_data and len(market_data[m]) > 0])
            
            for market, color in colors.items():
                if market in market_data and len(market_data[market]) > 0:
                    df = market_data[market]
                    df_plot = df[df['datetime'] >= start_date].copy()
                    base_value = df_plot['close'].iloc[0]
                    df_plot['normalized'] = df_plot['close'] / base_value * 100
                    
                    fig.add_trace(
                        go.Scatter(
                            x=df_plot['datetime'],
                            y=df_plot['normalized'],
                            name=market,
                            line=dict(color=color, width=2.5, dash='solid' if market != '港股' else 'dash')
                        ),
                        row=1, col=1
                    )
            
            # 子图 2：北上资金 + 美债
            if 'ton' in market_data and len(market_data['ton']) > 0:
                ton_df = market_data['ton'][market_data['ton']['datetime'] >= start_date]
                fig.add_trace(
                    go.Scatter(
                        x=ton_df['datetime'],
                        y=ton_df['close'],
                        name='北上资金 (累计)',
                        line=dict(color='#e67e22', width=2),
                        yaxis='y2'
                    ),
                    row=2, col=1
                )
            
            if 'aty' in market_data and len(market_data['aty']) > 0:
                aty_df = market_data['aty'][market_data['aty']['datetime'] >= start_date]
                fig.add_trace(
                    go.Scatter(
                        x=aty_df['datetime'],
                        y=aty_df['close'],
                        name='美债收益率 (汇率替代)',
                        line=dict(color='#9b59b6', width=2, dash='dash'),
                        yaxis='y2'
                    ),
                    row=2, col=1
                )
            
            fig.update_layout(
                title="🌍 跨市场联动监测（A 股 vs 港股 vs 美股 vs 汇率）",
                title_x=0.5,
                hovermode="x unified",
                legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
                height=700,
                font=dict(family=self.chinese_font, size=12)
            )
            
            fig.update_xaxes(title_text="日期", row=2, col=1)
            fig.update_yaxes(title_text="标准化指数 (2020-01-02=100)", row=1, col=1)
            fig.update_yaxes(title_text="北上资金 (亿) / 美债收益率 (%)", row=2, col=1)
            
            fig.add_annotation(
                text="💡 红色区域：跨市场同步上涨 | 绿色区域：跨市场分化 | 灰色区域：震荡整理",
                xref="paper", yref="paper",
                x=0.5, y=-0.12, showarrow=False,
                font=dict(size=11, color="#7f8c8d", family=self.chinese_font)
            )
            
            return self._apply_chinese_layout(fig)
            
        except Exception as e:
            return self._generate_empty_chart("跨市场联动监测图", str(e)[:50])
    
    # 图表 14：行业轮动矩阵
    def _generate_industry_rotation_matrix(self, industry_data: Dict) -> go.Figure:
        """
        图表 14：行业轮动矩阵 ⭐
        
        参数:
            industry_data: {'industries': {}, 'benchmark_return': float}
        """
        if not PLOTLY_AVAILABLE:
            return None
        
        if not industry_data or 'industries' not in industry_data:
            return self._generate_empty_chart("行业轮动矩阵", "数据不足")
        
        try:
            industries = industry_data['industries']
            benchmark_return = industry_data.get('benchmark_return', 0)
            
            industry_names = list(industries.keys())
            returns = [industries[i] for i in industry_names]
            relative_returns = [r - benchmark_return for r in returns]
            colors = ['#27ae60' if r > 0 else '#e74c3c' for r in relative_returns]
            
            fig = go.Figure(data=go.Bar(
                x=industry_names,
                y=returns,
                marker_color=colors,
                text=[f"{r:.1f}%" for r in returns],
                textposition='auto'
            ))
            
            fig.add_hline(y=benchmark_return, line_dash="dash", line_color="gray",
                         annotation_text=f"基准收益 ({benchmark_return:.1f}%)")
            
            fig.update_layout(
                title="🔄 行业轮动矩阵（20 日收益率 vs 沪深 300）",
                title_x=0.5,
                xaxis_title="行业",
                yaxis_title="20 日收益率 (%)",
                height=500,
                font=dict(family=self.chinese_font, size=12)
            )
            
            fig.add_annotation(
                text="💡 绿色=跑赢基准 | 红色=跑输基准",
                xref="paper", yref="paper",
                x=0.5, y=-0.12, showarrow=False,
                font=dict(size=11, color="#7f8c8d", family=self.chinese_font)
            )
            
            return self._apply_chinese_layout(fig)
            
        except Exception as e:
            return self._generate_empty_chart("行业轮动矩阵", str(e)[:50])
    
    # 图表 15：风险传导路径图
    def _generate_risk_transmission_chart(self, risk_metrics: Dict) -> go.Figure:
        """
        图表 15：风险传导路径图 ⭐
        
        参数:
            risk_metrics: {'微盘': {...}, '小盘': {...}, '中盘': {...}, '大盘': {...}}
        """
        if not PLOTLY_AVAILABLE:
            return None
        
        if not risk_metrics or len(risk_metrics) < 2:
            return self._generate_empty_chart("风险传导路径图", "数据不足")
        
        try:
            fig = make_subplots(
                rows=2, cols=1,
                subplot_titles=('⚠️ 四层市值风险传导路径', '📊 各层风险指标对比'),
                row_heights=[0.55, 0.45],
                vertical_spacing=0.12
            )
            
            layer_order = ['微盘', '小盘', '中盘', '大盘']
            available_layers = [l for l in layer_order if l in risk_metrics]
            
            if len(available_layers) < 2:
                return self._generate_empty_chart("风险传导路径图", "有效层级不足 2 个")
            
            risk_scores = [risk_metrics[l]['风险得分'] for l in available_layers]
            colors = ['#e74c3c' if s > 60 else ('#f39c12' if s > 40 else '#27ae60') for s in risk_scores]
            
            # 子图 1：传导路径
            for i in range(len(available_layers) - 1):
                fig.add_trace(
                    go.Scatter(
                        x=[i, i + 1],
                        y=[risk_scores[i], risk_scores[i + 1]],
                        mode='lines+markers+text',
                        line=dict(color=colors[i], width=3),
                        marker=dict(size=15, color=colors[i]),
                        text=[available_layers[i], available_layers[i + 1]],
                        textposition='top center',
                        textfont=dict(size=14, color=colors[i], family=self.chinese_font),
                        name=f'{available_layers[i]}→{available_layers[i + 1]}',
                        showlegend=False
                    ),
                    row=1, col=1
                )
            
            # 子图 2：各层风险指标对比
            metrics_names = ['波动率扩张', '流动性', '20 日收益']
            for i, metric in enumerate(metrics_names):
                values = [risk_metrics[l].get(metric, 0) for l in available_layers]
                fig.add_trace(
                    go.Bar(
                        x=available_layers,
                        y=values,
                        name=metric,
                        marker_color=['#e74c3c', '#f39c12', '#3498db'][i],
                        opacity=0.7
                    ),
                    row=2, col=1
                )
            
            fig.update_layout(
                title="⚠️ 风险传导路径监测（微盘→小盘→中盘→大盘）",
                title_x=0.5,
                height=700,
                font=dict(family=self.chinese_font, size=12),
                legend=dict(orientation="h", yanchor="bottom", y=-0.15, xanchor="center", x=0.5)
            )
            
            fig.update_xaxes(title_text="市值层级", row=1, col=1)
            fig.update_yaxes(title_text="风险得分 (0-100)", row=1, col=1)
            fig.update_xaxes(title_text="市值层级", row=2, col=1)
            fig.update_yaxes(title_text="指标值", row=2, col=1)
            
            max_risk_layer = available_layers[risk_scores.index(max(risk_scores))]
            fig.add_annotation(
                text=f"🔴 最高风险层级：{max_risk_layer} ({max(risk_scores):.0f}分)",
                xref="paper", yref="paper",
                x=0.5, y=-0.25, showarrow=False,
                font=dict(size=12, color="#e74c3c", family=self.chinese_font)
            )
            
            return self._apply_chinese_layout(fig)
            
        except Exception as e:
            return self._generate_empty_chart("风险传导路径图", str(e)[:50])
    
    # ==================== V5.7 新增图表 ====================
    
    # 图表 16：商品期货影响热力图
    def _generate_commodity_strategy_heatmap(self, commodity_signals: Dict) -> go.Figure:
        """
        图表 16：商品期货对战略方向影响热力图 ⭐ V5.7 新增
        
        参数:
            commodity_signals: 商品信号字典
        """
        if not PLOTLY_AVAILABLE:
            return None
        
        if not commodity_signals:
            return self._generate_empty_chart("商品期货影响热力图", "数据不足")
        
        try:
            # 直接使用传入的 config 或 self.config
            if self.config:
                directions = list(self.config.base_weights.keys())
            else:
                # 默认方向列表
                directions = ['高端制造', '信息技术', '新能源', '生物健康', 
                            '供应链', '现代农业', '公用事业', '传统升级', '文化消费']
            
            commodities = list(commodity_signals.keys())
            impact_matrix = np.zeros((len(directions), len(commodities)))
            
            for j, code in enumerate(commodities):
                if code in commodity_signals:
                    signal = commodity_signals[code]
                    for i, direction in enumerate(directions):
                        if direction in signal.get('directions', []):
                            impact_matrix[i, j] = signal.get('score', 0)
            
            commodity_names = [self._get_index_name(c) for c in commodities]
            
            fig = go.Figure(data=go.Heatmap(
                z=impact_matrix,
                x=commodity_names,
                y=directions,
                colorscale='RdYlGn',
                zmid=0,
                text=[[f"{v:.2f}" for v in row] for row in impact_matrix],
                texttemplate="%{text}",
                textfont={"size": 10}
            ))
            
            fig.update_layout(
                title="📊 商品期货对战略方向影响热力图（绿色=利好，红色=利空）",
                title_x=0.5,
                xaxis_title="商品期货",
                yaxis_title="战略方向",
                height=500,
                font=dict(family=self.chinese_font, size=11)
            )
            
            return self._apply_chinese_layout(fig)
            
        except Exception as e:
            return self._generate_empty_chart("商品期货影响热力图", str(e)[:50])
    
    # 图表 17：宏观综合评分趋势图
    def _generate_macro_composite_chart(self, macro_history: Dict) -> go.Figure:
        """
        图表 17：宏观综合评分趋势图 ⭐ V5.7 新增
        
        参数:
            macro_history: {'dates': [], 'composite_score': [], 'category_scores': {}}
        """
        if not PLOTLY_AVAILABLE:
            return None
        
        if not macro_history or 'dates' not in macro_history:
            return self._generate_empty_chart("宏观综合评分趋势图", "数据不足")
        
        try:
            fig = go.Figure()
            
            # 综合评分
            fig.add_trace(
                go.Scatter(
                    x=macro_history['dates'],
                    y=macro_history['composite_score'],
                    name='宏观综合评分',
                    line=dict(color='#2c3e50', width=3)
                )
            )
            
            # 分类评分
            colors = {'inflation': '#e74c3c', 'growth': '#27ae60', 'liquidity': '#3498db',
                     'sentiment': '#9b59b6', 'external': '#f39c12'}
            
            for category, scores in macro_history.get('category_scores', {}).items():
                fig.add_trace(
                    go.Scatter(
                        x=macro_history['dates'],
                        y=scores,
                        name=category,
                        line=dict(color=colors.get(category, '#95a5a6'), width=2, dash='dash'),
                        opacity=0.7
                    )
                )
            
            # 参考线
            fig.add_hline(y=50, line_dash="solid", line_color="gray", line_width=1)
            fig.add_hline(y=65, line_dash="dash", line_color="green", line_width=2,
                         annotation_text="积极配置线")
            fig.add_hline(y=35, line_dash="dash", line_color="red", line_width=2,
                         annotation_text="防御观望线")
            
            fig.update_layout(
                title="📊 宏观综合评分趋势图（五维加权）",
                title_x=0.5,
                xaxis_title="日期",
                yaxis_title="综合评分 (0-100)",
                height=500,
                hovermode="x unified",
                font=dict(family=self.chinese_font, size=12),
                legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
            )
            
            return self._apply_chinese_layout(fig)
            
        except Exception as e:
            return self._generate_empty_chart("宏观综合评分趋势图", str(e)[:50])
    
    # 图表 18：商品期限结构产业景气度仪表盘
    def _generate_commodity_term_dashboard(self, term_data: Dict) -> go.Figure:
        """
        图表：商品期限结构产业景气度仪表盘 ⭐ V5.7 新增（修复版）
        """
        if not PLOTLY_AVAILABLE:
            return None
        
        if not term_data or len(term_data) == 0:
            return self._generate_empty_chart("商品期限结构产业景气度", "期限结构数据不足")
        
        try:
            # ========== 修复 1：商品映射定义 ==========
            commodity_mapping = {
                'copper': {'name': '沪铜', 'directions': ['高端制造', '供应链'], 'color': '#1f77b4'},
                'aluminum': {'name': '沪铝', 'directions': ['高端制造', '新能源'], 'color': '#ff7f0e'},
                'lithium': {'name': '碳酸锂', 'directions': ['新能源', '信息技术'], 'color': '#2ca02c'},
                'silicon': {'name': '工业硅', 'directions': ['信息技术', '新能源'], 'color': '#d62728'},
                'crude': {'name': '原油', 'directions': ['公用事业', '供应链', '传统升级'], 'color': '#9467bd'},
                'rebar': {'name': '螺纹钢', 'directions': ['传统升级', '供应链'], 'color': '#8c564b'},
                'gold': {'name': '黄金', 'directions': ['公用事业'], 'color': '#e377c2'},
                'soybean': {'name': '豆粕', 'directions': ['现代农业', '生物健康', '文化消费'], 'color': '#7f7f7f'}
            }
            
            # ========== 修复 2：过滤有效数据 ==========
            valid_data = {}
            for key, data in term_data.items():
                spread = data.get('spread', 0)
                if pd.isna(spread) or np.isinf(spread):
                    continue
                valid_data[key] = data
            
            if not valid_data:
                return self._generate_empty_chart("商品期限结构产业景气度", "无有效数据")
            
            # ========== 修复 3：计算动态布局 ==========
            n_commodities = min(len(valid_data), 8)  # 最多显示 8 个
            rows = (n_commodities + 1) // 2  # 2 列布局
            
            # 创建子图
            fig = make_subplots(
                rows=rows, cols=2,
                specs=[[{"type": "indicator"}]*2 for _ in range(rows)],
                subplot_titles=[
                    f"{commodity_mapping.get(k, {}).get('name', k)} 期限结构"
                    for k in list(valid_data.keys())[:n_commodities]
                ],
                vertical_spacing=0.15,
                horizontal_spacing=0.1
            )
            
            # ========== 修复 4：添加每个商品的仪表盘 ==========
            for idx, (commodity_key, data) in enumerate(valid_data.items()):
                if idx >= n_commodities:
                    break
                
                row = (idx // 2) + 1
                col = (idx % 2) + 1
                
                # 提取数据（添加类型转换）
                spread = float(data.get('spread', 0.0))  # ⭐ 转换为 Python float
                structure = data.get('structure', 'unknown')
                signal = data.get('signal', '')
                commodity_info = commodity_mapping.get(commodity_key, {})
                
                # ========== 修复 5：计算景气度评分 (0-100) ==========
                # 处理异常值
                spread = np.clip(spread, -20, 20)  # 限制在合理范围
                
                if structure == 'backwardation':
                    # Backwardation(近月>远月) = 供应紧张 = 景气度高
                    sentiment_score = min(100.0, 50.0 + abs(spread) * 3.0)
                    gauge_color = '#27ae60'  # 绿色
                    status_text = '🟢 景气'
                elif structure == 'contango':
                    # Contango(近月<远月) = 供应充足 = 景气度低
                    sentiment_score = max(0.0, 50.0 - abs(spread) * 3.0)
                    gauge_color = '#e74c3c'  # 红色
                    status_text = '🔴 疲软'
                else:
                    sentiment_score = 50.0
                    gauge_color = '#95a5a6'  # 灰色
                    status_text = '⚪ 均衡'
                
                # ⭐ 关键修复：确保所有数值都是 Python float
                sentiment_score = float(np.clip(sentiment_score, 0.0, 100.0))
                
                # ========== 修复 6：获取关联战略方向 ==========
                directions = commodity_info.get('directions', [])
                direction_text = ' + '.join(directions[:2]) if directions else '通用'
                
                # ========== 修复 7：添加仪表盘（修正 domain 计算）==========
                # ⭐ 关键修复：正确的 domain 计算，确保 y 在 [0, 1] 范围内
                y_bottom = 1 - row * (1.0 / rows)
                y_top = 1 - (row - 1) * (1.0 / rows)
                x_left = (col - 1) * 0.5
                x_right = col * 0.5
                
                try:
                    fig.add_trace(
                        go.Indicator(
                            mode="gauge+number+delta",
                            value=sentiment_score,
                            domain={
                                'x': [x_left + 0.02, x_right - 0.02],  # 留边距
                                'y': [y_bottom + 0.05, y_top - 0.05]   # 留边距
                            },
                            title={
                                'text': f"<b>{commodity_info.get('name', commodity_key)}</b><br>"
                                    f"<span style='font-size:10px'>{direction_text}</span>",
                                'font': {'size': 13, 'family': self.chinese_font}
                            },
                            delta={
                                'reference': 50.0,
                                'increasing': {'color': '#27ae60'},
                                'decreasing': {'color': '#e74c3c'}
                            },
                            gauge={
                                'axis': {'range': [0, 100], 'tickwidth': 1, 'tickcolor': "#636363"},
                                'bar': {'color': gauge_color},
                                'bgcolor': "#f8f9fa",
                                'borderwidth': 2,
                                'bordercolor': "#636363",
                                'steps': [
                                    {'range': [0, 33], 'color': '#e74c3c'},    # 疲软
                                    {'range': [33, 67], 'color': '#f39c12'},   # 均衡
                                    {'range': [67, 100], 'color': '#27ae60'}   # 景气
                                ],
                                'threshold': {
                                    'line': {'color': "red", 'width': 3},
                                    'thickness': 0.75,
                                    'value': 50.0
                                }
                            }
                        ),
                        row=row, col=col
                    )
                except Exception as e:
                    print(f"⚠️ 添加仪表盘失败 {commodity_key}: {str(e)}")
                    continue
                
                # ========== 修复 8：添加价差和信号标注 ==========
                try:
                    fig.add_annotation(
                        text=f"价差：{spread:+.1f}% | {signal}",
                        xref=f"x{idx+1}",
                        yref=f"y{idx+1}",
                        x=0.5,
                        y=0.2,
                        showarrow=False,
                        font=dict(size=9, color="#7f8c8d", family=self.chinese_font),
                        xanchor="center"
                    )
                except:
                    pass
            
            # ========== 修复 9：全局布局 ==========
            fig.update_layout(
                title="📊 商品期限结构产业景气度仪表盘（Backwardation=景气 / Contango=疲软）",
                title_x=0.5,
                height=350 * rows,
                font=dict(family=self.chinese_font, size=11),
                showlegend=False,
                margin=dict(t=80, b=60, l=40, r=40)
            )
            
            # ========== 修复 10：添加图例说明 ==========
            fig.add_annotation(
                text="💡 绿色=Backwardation(供应紧张/景气) | 红色=Contango(供应充足/疲软) | 价差=近月-远月",
                xref="paper", yref="paper",
                x=0.5, y=-0.05,
                showarrow=False,
                font=dict(size=11, color="#7f8c8d", family=self.chinese_font)
            )
            
            return self._apply_chinese_layout(fig)
            
        except Exception as e:
            print(f"❌ 生成商品期限结构仪表盘失败: {str(e)}")
            import traceback
            traceback.print_exc()
            return self._generate_empty_chart("商品期限结构产业景气度", str(e)[:50])
      
    # ==================== 统一调用接口 ====================
    
    def generate_all_charts(self, data_context: Dict) -> Dict[str, go.Figure]:
        """
        生成所有 18 个图表
        
        参数:
            data_context: 数据上下文字典，包含所有图表所需数据
        返回:
            图表字典 {chart_name: Figure}
        """
        if not PLOTLY_AVAILABLE:
            print("⚠️ Plotly 未安装，无法生成图表")
            return {}
        
        charts = {}
        
        # 核心 15 大图表
        charts['估值诊断'] = self._generate_valuation_diagnostic_chart(
            data_context.get('pe_data'),
            data_context.get('bond_yield', 2.5)
        )
        
        charts['市值走势'] = self._generate_market_trend_chart(
            data_context.get('benchmark_data', {})
        )
        
        charts['微盘流动性'] = self._generate_micro_liquidity_chart(
            data_context.get('micro_data', {})
        )
        
        charts['风格轮动'] = self._generate_style_rotation_chart(
            data_context.get('benchmark_data', {})
        )
        
        charts['市场状态'] = self._generate_market_state_chart(
            data_context.get('market_state', '均衡持有区'),
            data_context.get('val_score', 50),
            data_context.get('trend_score', 50)
        )
        
        charts['战略配置'] = self._generate_allocation_chart(
            data_context.get('allocation_df')
        )
        
        charts['高风险雷达'] = self._generate_high_risk_chart(
            data_context.get('risk_data', [])
        )
        
        charts['期权 PCR'] = self._generate_option_pcr_chart(
            data_context.get('pcr_data', {})
        )
        
        charts['期货期限'] = self._generate_futures_term_structure_chart(
            data_context.get('term_data', {})
        )
        
        charts['期现基差'] = self._generate_futures_basis_chart(
            data_context.get('basis_data', {})
        )
        
        charts['资金流向'] = self._generate_fund_flow_heatmap(
            data_context.get('flow_data', {})
        )
        
        charts['情绪仪表'] = self._generate_sentiment_dashboard(
            data_context.get('sentiment_data', {})
        )
        
        charts['跨市场联动'] = self._generate_cross_market_chart(
            data_context.get('market_data', {})
        )
        
        charts['行业轮动'] = self._generate_industry_rotation_matrix(
            data_context.get('industry_data', {})
        )
        
        charts['风险传导'] = self._generate_risk_transmission_chart(
            data_context.get('risk_metrics', {})
        )
        
        # V5.7 新增图表
        charts['商品影响'] = self._generate_commodity_strategy_heatmap(
            data_context.get('commodity_signals', {})
        )
        
        charts['宏观评分'] = self._generate_macro_composite_chart(
            data_context.get('macro_history', {})
        )

        charts['商品景气'] = self._generate_commodity_term_dashboard(
            data_context.get('term_data', {})
    )    
        
        # 统计有效图表
        valid_charts = {k: v for k, v in charts.items() if v is not None}
        
        print(f"✅ 成功生成 {len(valid_charts)}/{len(charts)} 个图表")
        
        return charts
    
    def export_charts_to_html(self, charts: Dict[str, go.Figure],
                             output_path: str = 'reports/visualization_report.html'):
        """
        导出所有图表到 HTML 文件
        
        参数:
            charts: 图表字典
            output_path: 输出路径
        """
        if not PLOTLY_AVAILABLE or not charts:
            print("⚠️ 无法导出图表（Plotly 未安装或图表为空）")
            return
        
        try:
            from pathlib import Path
            Path(output_path).parent.mkdir(parents=True, exist_ok=True)
            
            html_content = f"""
            <!DOCTYPE html>
            <html>
            <head>
                <meta charset="UTF-8">
                <title>A 股市场状态量化系统 V5.7 - 可视化报告</title>
                <script src="https://cdn.plot.ly/plotly-latest.min.js"></script>
                <style>
                    body {{ font-family: '{self.chinese_font}', Arial, sans-serif; margin: 20px; }}
                    .chart-container {{ margin: 40px 0; }}
                    h1 {{ text-align: center; color: #2c3e50; }}
                    h2 {{ color: #34495e; border-bottom: 2px solid #3498db; padding-bottom: 10px; }}
                </style>
            </head>
            <body>
                <h1>📈 A 股市场状态量化系统 V5.7</h1>
                <p style="text-align: center; color: #7f8c8d;">
                    生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} | 
                    共 {len(charts)} 个交互式图表
                </p>
                <hr>
            """
            
            for i, (name, fig) in enumerate(charts.items(), 1):
                if fig:
                    chart_div = fig.to_html(full_html=False, include_plotlyjs='cdn')
                    html_content += f"""
                    <div class="chart-container">
                        <h2>{i}. {name}</h2>
                        {chart_div}
                    </div>
                    <hr>
                    """
            
            html_content += """
                <footer style="text-align: center; margin-top: 50px; color: #7f8c8d;">
                    <p>© 2026 A 股市场状态量化系统 V5.7 | 五维一体决策框架</p>
                    <p>股票 + 期权 + 期货 + 商品 + 宏观</p>
                </footer>
            </body>
            </html>
            """
            
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(html_content)
            
            print(f"✅ 图表报告已导出至：{output_path}")
            
        except Exception as e:
            print(f"❌ 导出图表失败：{str(e)}")

# %%
# 14 ==================== 主系统类 MarketStateSystemV5_7 ====================
"""
全功能 MarketStateSystemV5_7
"""
class MarketStateSystemV5_7:
    """
    A 股市场状态量化系统 V5.7（全功能重构版）
    五维一体决策框架：股票 + 期权 + 期货 + 商品 + 宏观
    """
    
    def __init__(self, config_path: str = './config/system_config.yaml'):
        """
        初始化系统 V5.7（全功能版）
        """
        self.config = SystemConfig.from_yaml(config_path)
        self.logger = setup_logger('MarketStateSystemV5_7')
        
        self.logger.info("=" * 80)
        self.logger.info("【A 股市场状态量化系统 V5.7 - 全功能重构版】")
        self.logger.info("五维一体决策框架：股票 + 期权 + 期货 + 商品 + 宏观")
        self.logger.info("核心增强：微盘三阶段熔断 + 动态期权映射 + 宏观评分 + 风险传导")
        self.logger.info("=" * 80)
        
        # 初始化各模块
        self.data_manager = DataManager(self.config)
        self.indicator_engine = IndicatorEngine(self.data_manager, self.config)
        self.risk_engine = RiskEngine(self.data_manager, self.config)
        self.allocation_engine = AllocationEngine(self.config, self.indicator_engine, self.risk_engine)
        self.visualizer = Visualizer(self.config)
        
        # 数据缓存
        self.benchmark_data = {}
        self.micro_redundancy_data = {}
        self.micro_liquidity_status = None
        
        # 预加载数据
        self._preload_data()
    
    def _preload_data(self):
        """预加载基准数据"""
        self.logger.info("🔄 预加载基准数据...")
        
        # 加载市值基准
        for size, config in self.config.market_benchmarks.items():
            code = config['code']
            df = self.data_manager.load_index_data(code, min_days=500)
            if len(df) > 0:
                self.benchmark_data[size] = df
                self.logger.info(f"✅ 加载{size}({code}) 数据：{len(df)}条")
        
        # 加载微盘冗余数据
        for role, code in self.config.micro_redundancy.items():
            if role in ['primary', 'secondary']:
                df = self.data_manager.load_index_data(code, min_days=500)
                if len(df) > 0:
                    self.micro_redundancy_data[role] = df
                    self.logger.info(f"✅ 加载微盘{role}({code}) 数据：{len(df)}条")
        
        # 评估微盘流动性
        if 'primary' in self.micro_redundancy_data:
            df_primary = self.micro_redundancy_data['primary']
            df_secondary = self.micro_redundancy_data.get('secondary')
            self.micro_liquidity_status = self.risk_engine.assess_micro_liquidity(df_primary, df_secondary)
            self.logger.info(f"✅ 微盘流动性状态：{self.micro_liquidity_status['stage']}")
        
        self.logger.info(f"✅ 数据预加载完成，共{len(self.benchmark_data)}个市值层级")
    
    def determine_market_state(self) -> Tuple[str, float, float, Dict]:
        """
        判定市场状态（增强版：包含微盘熔断状态）
        """
        layer_scores = {}
        valid_layers = []
        
        for size in ['大盘', '中盘', '小盘']:
            df = self.benchmark_data.get(size, pd.DataFrame())
            if len(df) >= 250:
                code = self.config.market_benchmarks[size]['code']
                val_score = self.indicator_engine.calculate_valuation_score(df, code)
                trend_score = self.indicator_engine.calculate_trend_score(df)
                layer_scores[size] = {
                    'valuation': val_score,
                    'trend': trend_score,
                    'composite': 0.6 * val_score + 0.4 * trend_score
                }
                valid_layers.append(size)
        
        # 微盘层特殊处理（包含熔断状态）
        if '微盘' in self.config.market_benchmarks and self.micro_liquidity_status:
            df_p = self.micro_redundancy_data.get('primary', pd.DataFrame())
            if len(df_p) >= 250:
                code = self.config.market_benchmarks['微盘']['code']
                micro_val = self.indicator_engine.calculate_valuation_score(df_p, code)
                micro_trend = self.indicator_engine.calculate_trend_score(df_p)
                layer_scores['微盘'] = {
                    'valuation': micro_val,
                    'trend': micro_trend,
                    'composite': 0.6 * micro_val + 0.4 * micro_trend,
                    'liquidity_status': self.micro_liquidity_status['distortion_flag'],
                    'liquidity_stage': self.micro_liquidity_status['stage']
                }
                valid_layers.append('微盘')
        
        if not valid_layers:
            return "数据不足", 50.0, 50.0, {}
        
        # 计算加权市场得分
        total_weight = sum(
            self.config.market_benchmarks[size]['weight']
            for size in valid_layers
        )
        market_val_score = sum(
            layer_scores[size]['valuation'] *
            self.config.market_benchmarks[size]['weight']
            for size in valid_layers
        ) / total_weight
        market_trend_score = sum(
            layer_scores[size]['trend'] *
            self.config.market_benchmarks[size]['weight']
            for size in valid_layers
        ) / total_weight
        
        # 状态映射
        val_state = '低估' if market_val_score < 40 else ('合理' if market_val_score <= 60 else '高估')
        trend_state = '弱势' if market_trend_score < 40 else ('中性' if market_trend_score <= 70 else '强势')
        
        state_map = {
            ('低估', '强势'): '战略进攻区',
            ('合理', '强势'): '积极配置区',
            ('高估', '强势'): '防御进攻区',
            ('低估', '中性'): '左侧布局区',
            ('合理', '中性'): '均衡持有区',
            ('高估', '中性'): '防御观望区',
            ('低估', '弱势'): '左侧防御区',
            ('合理', '弱势'): '谨慎持有区',
            ('高估', '弱势'): '战略防御区'
        }
        
        market_state = state_map.get((val_state, trend_state), '均衡持有区')
        
        # 各层诊断
        layer_diagnosis = {}
        for size in ['大盘', '中盘', '小盘', '微盘']:
            if size in layer_scores:
                scores = layer_scores[size]
                val_status = '↑低估' if scores['valuation'] > 65 else (
                    '↓高估' if scores['valuation'] < 35 else '→合理'
                )
                trend_status = '↑强势' if scores['trend'] > 70 else (
                    '↓弱势' if scores['trend'] < 40 else '→中性'
                )
                layer_diagnosis[size] = f"{val_status} {trend_status} | 估值{scores['valuation']:.0f} 趋势{scores['trend']:.0f}"
            else:
                layer_diagnosis[size] = "数据缺失"
        
        return market_state, market_val_score, market_trend_score, layer_diagnosis
    
    def calculate_allocation(self) -> pd.DataFrame:
        """计算战略配置（增强版：融合微盘熔断）"""
        return self.allocation_engine.calculate_allocation(
            self.benchmark_data, 
            self.micro_liquidity_status
        )
    
    def generate_risk_alerts(self) -> List[str]:
        """生成风险预警（增强版：融合多维度）"""
        # 获取各维度数据
        market_state, _, _, _ = self.determine_market_state()
        pcr_data = self.indicator_engine.calculate_pcr()
        basis_data = self.indicator_engine.calculate_futures_basis()
        
        # 生成预警
        alerts = self.risk_engine.generate_risk_alerts(
            market_state, pcr_data, self.micro_liquidity_status, basis_data
        )
        
        return alerts

# ========== 高风险数据准备方法 ==========
    def _prepare_high_risk_data(self) -> List[Dict]:
            """
            准备高风险方向四维评估数据
            返回: [
                {
                    'direction': '文化消费',
                    'micro': 35.0,      # 微盘暴露得分
                    'volatility': 18.75, # 波动率得分
                    'valuation': 18.75,  # 估值得分
                    'liquidity': 11.25,  # 流动性得分
                    'total': 75.0        # 综合得分
                },
                ...
            ]
            """
            risk_data = []
            
            # 遍历高风险方向配置
            for direction, risk_info in self.config.high_risk_directions.items():
                risk_score = risk_info.get('risk_score', 50)
                
                # 1. 微盘暴露检测（35%权重）
                has_micro = any(
                    idx in self.config.micro_cap_indices 
                    for idx in self.config.direction_indices.get(direction, [])
                )
                micro_score = 35.0 if has_micro else 10.0
                
                # 2. 波动率得分（25%权重）
                volatility_score = float(risk_score * 0.25)
                
                # 3. 估值分位得分（25%权重）
                valuation_score = float(risk_score * 0.25)
                
                # 4. 流动性得分（15%权重）
                liquidity_score = float(risk_score * 0.15)
                
                # 5. 综合得分
                total_score = (
                    micro_score * 0.35 +
                    volatility_score +
                    valuation_score +
                    liquidity_score
                )
                
                risk_data.append({
                    'direction': direction,
                    'micro': micro_score,
                    'volatility': volatility_score,
                    'valuation': valuation_score,
                    'liquidity': liquidity_score,
                    'total': float(total_score)
                })
            
            # 按综合得分降序排序
            risk_data.sort(key=lambda x: x['total'], reverse=True)
            
            return risk_data

    # ========== 【新增】融资余额情绪计算 ==========
    def _calculate_margin_sentiment(self) -> float:
        """
        计算融资余额情绪得分（0-100）
        基于融资余额的历史分位数和变化趋势
        返回: 情绪得分 (0-100)，越高越乐观
        """
        try:
            # 加载融资余额数据
            rz_df = self.data_manager.load_macro_data('7_RZ', days=250)
            
            if len(rz_df) < 50:
                return 50.0  # 数据不足，返回中性
            
            # 1. 当前值
            current_rz = rz_df['close'].iloc[-1]
            
            # 2. 历史分位数（过去250日）
            rz_history = rz_df['close'].iloc[-250:-1]
            rz_percentile = (rz_history < current_rz).mean() * 100
            
            # 3. 近期变化趋势（20日）
            if len(rz_df) >= 21:
                rz_20d_ago = rz_df['close'].iloc[-21]
                rz_change_20d = ((current_rz - rz_20d_ago) / rz_20d_ago) * 100
                # 趋势得分：正增长加分，负增长减分
                trend_score = np.clip(50 + rz_change_20d * 2, 0, 100)
            else:
                trend_score = 50.0
            
            # 4. 综合得分（分位数60% + 趋势40%）
            composite_score = rz_percentile * 0.6 + trend_score * 0.4
            
            return float(np.clip(composite_score, 0, 100))
            
        except Exception as e:
            self.logger.warning(f"⚠️ 融资余额情绪计算失败：{str(e)}")
            return 50.0
    
    def run(self) -> Dict:
        """
        运行系统 V5.7（全功能版）
        """
        self.logger.info("=" * 80)
        self.logger.info(f"📅 运行基准日：{self.config.base_date}")
        self.logger.info(f"✅ 系统初始化成功！数据加载完成")
        self.logger.info(f"✅ V5.7 全功能：微盘熔断 + 动态期权 + 宏观评分 + 风险传导")
        self.logger.info("=" * 80)
        
        # 1. 判定市场状态
        market_state, val_score, trend_score, diagnosis = self.determine_market_state()
        self.logger.info(f"🎯 市场状态：{market_state}")
        self.logger.info(f"📊 估值安全边际：{val_score:.1f}/100")
        self.logger.info(f"📈 趋势动能强度：{trend_score:.1f}/100")
        
        if self.micro_liquidity_status:
            self.logger.info(f"🔥 微盘熔断阶段：{self.micro_liquidity_status['stage']}（持续{self.micro_liquidity_status['days_in_stage']}日）")
        
        # 2. 计算配置
        allocation_df = self.calculate_allocation()
        self.logger.info("💼 九大战略方向配置摘要（前 5 大）:")
        df_no_cash = allocation_df[allocation_df['战略方向'] != '现金'].copy()
        top5 = df_no_cash.nlargest(5, '动态权重')
        for _, row in top5.iterrows():
            self.logger.info(f" • {row['战略方向']:8s} | {row['配置建议']:6s} | {row['核心指数']}")
        
        # 3. 生成预警
        alerts = self.generate_risk_alerts()
        self.logger.info("⚠️ 风险监控信号:")
        for i, alert in enumerate(alerts[:5], 1):
            self.logger.info(f" {i}. {alert}")
        
        self.logger.info("=" * 80)
        self.logger.info("💡 使用指南:")
        self.logger.info(" 1. 文本输出：system.run() 查看市场状态摘要")
        self.logger.info(" 2. 交互可视化：system.show_in_jupyter() 在 Notebook 中生成图表")
        self.logger.info(" 3. 配置数据：allocation = system.calculate_allocation()")
        self.logger.info(" 4. 微盘状态：liquidity = system.micro_liquidity_status")
        self.logger.info(" 5. PCR数据：pcr = system.indicator_engine.calculate_pcr()")
        self.logger.info("=" * 80)
        
        return {
            'market_state': market_state,
            'valuation_score': val_score,
            'trend_score': trend_score,
            'micro_liquidity': self.micro_liquidity_status,
            'allocation': allocation_df,
            'risk_alerts': alerts,
            'diagnosis': diagnosis
        }
    
    def show_in_jupyter(self):
        """在 Jupyter Notebook 中显示可视化（全功能18图表）"""
        try:
            from IPython.display import display, Markdown, HTML
            
            if not self.config.visualize:
                display(Markdown("⚠️ 可视化功能已禁用"))
                return
            
            # 运行系统
            result = self.run()
            
            # 显示头部
            display(HTML(f"""
            <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white; padding: 25px; border-radius: 15px; margin-bottom: 30px;">
            <h1 style="text-align: center; margin: 0; font-size: 32px;">
            📈 A 股市场状态量化系统 V5.7 - 全功能重构版
            </h1>
            <p style="text-align: center; margin: 10px 0 0 0; font-size: 18px;">
            五维一体决策框架 | 微盘三阶段熔断 | 动态期权映射 | 宏观评分 | 18大图表
            </p>
            </div>
            """))
          
            # 准备数据上下文
            data_context = {
                'market_state': result['market_state'],
                'val_score': float(result['valuation_score']),
                'trend_score': float(result['trend_score']),
                'allocation_df': result['allocation'],
                'micro_data': {
                    'primary': self.micro_redundancy_data.get('primary', pd.DataFrame()),
                    'secondary': self.micro_redundancy_data.get('secondary', pd.DataFrame()),
                    'liquidity_status': self.micro_liquidity_status
                },
                'benchmark_data': self.benchmark_data,
                'pcr_data': self.indicator_engine.calculate_pcr(),
                'basis_data': self.indicator_engine.calculate_futures_basis(),
                'flow_data': self.indicator_engine.calculate_fund_flow_heatmap(),
                'sentiment_data': self.indicator_engine.calculate_sentiment_scores(),
                'market_data': self.indicator_engine.load_cross_market_data(),
                'industry_data': self.indicator_engine.calculate_industry_rotation(),
                'risk_metrics': self.risk_engine.calculate_risk_transmission(self.benchmark_data),
                'macro_history': {'dates': [], 'composite_score': [], 'category_scores': {}},
                'bond_yield': self.indicator_engine._safe_get_bond_yield(),
                'commodity_signals': self.indicator_engine.calculate_commodity_signals(),
                'term_data': self.indicator_engine.calculate_futures_term_structure(),
                'industry_sentiment': self.indicator_engine.calculate_industry_sentiment(),
                'pe_data': self.data_manager.load_pe_data('000300'),
                'risk_data': self._prepare_high_risk_data()

            }
            
            # 生成并显示所有18个图表
            charts = self.visualizer.generate_all_charts(data_context)
            
            # 显示风险预警
            display(Markdown("### ⚠️ 风险监控信号"))
            for i, alert in enumerate(result['risk_alerts'][:5], 1):
                display(Markdown(f"{i}. {alert}"))
            
            # 导出HTML报告
            self.visualizer.export_charts_to_html(
                charts, 
                output_path=f'reports/visualization_report_{datetime.now().strftime("%Y%m%d_%H%M%S")}.html'
            )
            
        except Exception as e:
            self.logger.error(f"❌ Jupyter 可视化失败：{str(e)}")
            import traceback
            self.logger.error(traceback.format_exc())

# %%
system = MarketStateSystemV5_7('./config/system_config.yaml')

# %%
system.indicator_engine.calculate_sentiment_scores()

# %%
system.visualizer._generate_sentiment_dashboard(system.indicator_engine.calculate_sentiment_scores())

# %%
report = system.run()

# %%
system.show_in_jupyter()


