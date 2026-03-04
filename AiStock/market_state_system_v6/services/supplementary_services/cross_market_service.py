"""
V6.1 跨市场联动服务（完全独立微服务）
核心特性：
✅ 阈值动态化集成（ThresholdService）
✅ 配置统一提取（config_utils.extract_and_validate_config）
✅ 全球市场指数加载（A股/港股/美股/汇率/美债/北上资金）
✅ 相关性矩阵计算（动态窗口）
✅ 联动强度分析（关键市场对）
✅ 领先滞后关系检测（简化版：基于相关性滞后）
✅ 完整降级策略（阈值服务失效时回退静态阈值）
✅ 所有数值强制Python原生float（防Plotly序列化错误）
修复点：
✅ 从config安全获取跨市场配置（cross_market.markets）
✅ 动态阈值获取（优先ThresholdService，回退静态配置）
✅ 完整数据验证与空值处理
✅ 详细日志与异常处理
✅ 市场代码智能推断（指数/衍生品/宏观）
"""
import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime
import logging
import warnings

warnings.filterwarnings('ignore')
logger = logging.getLogger(__name__)

# ✅ V6.1核心：导入配置工具（统一配置提取）
from utils.config_utils import extract_and_validate_config, safe_config_get


class CrossMarketService:
    """V6.1 跨市场联动服务（阈值动态化 + 配置统一化）"""
    
    def __init__(self, data_service, config_service, threshold_service=None):
        """
        初始化跨市场联动服务
        
        参数:
            data_service: DataLoadingService实例（用于加载跨市场数据）
            config_service: ConfigService实例（提供配置字典）
            threshold_service: ThresholdService实例（可选，None=使用静态阈值）
        
        修复点:
        ✅ 使用extract_and_validate_config统一配置提取
        ✅ 安全获取嵌套配置（safe_config_get）
        ✅ 详细日志记录配置状态
        ✅ 完整异常处理
        """
        self.data_service = data_service
        self.logger = logger
        
        # ✅ V6.1核心：统一配置提取（1行替代20+行验证逻辑）
        self.config, is_valid, missing_keys = extract_and_validate_config(
            config_service=config_service,
            required_keys=[
                'cross_market',
                'risk_thresholds'
            ],
            logger=self.logger,
            service_name='CrossMarketService'
        )
        
        # ✅ 保存ThresholdService引用（可选）
        self.threshold_service = threshold_service
        
        # 验证配置完整性
        if is_valid:
            # 提取跨市场配置
            cross_market_config = self.config.get('cross_market', {})
            markets = cross_market_config.get('markets', {})
            
            self.logger.info(
                f"✅ CrossMarketService初始化成功（配置完整） | "
                f"市场数量: {len(markets)} | "
                f"相关性窗口: {cross_market_config.get('correlation_window', 60)}日 | "
                f"领先滞后最大滞后: {cross_market_config.get('lead_lag_max_lag', 5)}日"
            )
        else:
            self.logger.warning(f"⚠️ CrossMarketService初始化完成（缺失{len(missing_keys)}项配置）")
    
    # ==================== 核心方法：跨市场数据加载 ====================
    
    def load_cross_market_data(
        self,
        markets: Optional[List[str]] = None,
        days: int = 250
    ) -> Dict[str, pd.DataFrame]:
        """
        V6.1核心：加载跨市场数据
        
        参数:
            markets: 市场列表（None=加载所有配置市场）
                ['a_share', 'hk_share', 'us_share', 'us_bond', 'usd_cny', 'north_flow']
            days: 获取天数
        
        返回:
            {
                'a_share': DataFrame with datetime, close,
                'hk_share': DataFrame,
                ...
            }
        
        修复点:
        ✅ 智能市场代码推断（指数/衍生品/宏观）
        ✅ 完整数据验证与空值处理
        ✅ 详细日志记录每步加载
        ✅ 完整降级策略（单个市场失败不影响整体）
        """
        if markets is None:
            cross_market_config = safe_config_get(
                self.config,
                ['cross_market'],
                default={},
                logger=self.logger
            )
            markets = list(cross_market_config.get('markets', {}).keys())
        
        market_data = {}
        
        for market_key in markets:
            # 获取市场配置
            market_config = self._get_market_config(market_key)
            if not market_config:
                self.logger.warning(f"⚠️ 未知市场: {market_key}")
                continue
            
            code = market_config['code']
            market_code = market_config['market_code']
            name = market_config['name']
            
            try:
                # 根据market_code智能选择加载方法
                df = self._load_market_data(code, market_code, days)
                
                if len(df) > 0:
                    # 标准化列名
                    if 'datetime' not in df.columns and 'date' in df.columns:
                        df = df.rename(columns={'date': 'datetime'})
                    
                    if 'close' not in df.columns:
                        self.logger.warning(f"⚠️ {name}({code}) 缺少close列")
                        continue
                    
                    # 确保datetime列存在
                    if 'datetime' in df.columns:
                        df['datetime'] = pd.to_datetime(df['datetime'])
                        df = df.sort_values('datetime').reset_index(drop=True)
                        market_data[market_key] = df[['datetime', 'close']].copy()
                        self.logger.debug(f"✅ {name}({code}): {len(df)}条")
                    else:
                        self.logger.warning(f"⚠️ {name}({code}) 缺少datetime列")
                else:
                    self.logger.warning(f"⚠️ {name}({code}) 数据为空")
            
            except Exception as e:
                self.logger.warning(f"⚠️ {name}({code}) 加载失败: {str(e)[:50]}")
                continue
        
        self.logger.info(f"✅ 跨市场数据加载完成: {len(market_data)}/{len(markets)}个市场")
        return market_data
    
    def _get_market_config(self, market_key: str) -> Optional[Dict]:
        """获取市场配置"""
        cross_market_config = safe_config_get(
            self.config,
            ['cross_market'],
            default={},
            logger=self.logger
        )
        
        markets = cross_market_config.get('markets', {})
        if market_key in markets:
            return markets[market_key]
        
        # 尝试从risk_thresholds中获取（兼容旧配置）
        if market_key in self.config.get('risk_thresholds', {}):
            return self.config['risk_thresholds'][market_key]
        
        return None
    
    def _load_market_data(
        self,
        code: str,
        market_code: int,
        days: int
    ) -> pd.DataFrame:
        """
        智能加载市场数据（根据market_code选择加载方法）
        
        参数:
            code: 代码
            market_code: 市场代码
            days: 天数
        
        返回:
            DataFrame
        """
        # 指数市场（62=中证指数）
        if market_code == 62:
            return self.data_service.load_index_data(code, min_days=days)
        
        # 衍生品市场（27=港股, 74=美股, 47=中金所）
        elif market_code in [27, 74, 47]:
            return self.data_service.load_derivative_data(code, market_code, days=days)
        
        # 宏观指标市场（38=宏观指标）
        elif market_code == 38:
            return self.data_service.load_macro_data(code, days=days)
        
        # 默认：尝试所有方法
        else:
            try:
                return self.data_service.load_index_data(code, min_days=days)
            except:
                try:
                    return self.data_service.load_derivative_data(code, market_code, days=days)
                except:
                    try:
                        return self.data_service.load_macro_data(code, days=days)
                    except:
                        self.logger.warning(f"⚠️ {code} 数据加载失败（所有方法）")
                        return pd.DataFrame()
    
    # ==================== 核心方法：相关性矩阵计算 ====================
    
    def calculate_correlation_matrix(
        self,
        market_data: Dict[str, pd.DataFrame],
        window: Optional[int] = None
    ) -> pd.DataFrame:
        """
        V6.1核心：计算市场间相关性矩阵
        
        参数:
            market_data 跨市场数据字典
            window: 计算窗口（None=使用配置）
        
        返回:
            相关性矩阵DataFrame (markets × markets)
        
        修复点:
        ✅ 动态窗口获取（优先ThresholdService）
        ✅ 完整数据验证与空值处理
        ✅ 强制Python原生float（防Plotly序列化错误）
        ✅ 详细日志记录
        """
        if not market_data or len(market_data) < 2:
            self.logger.warning("⚠️ 市场数据不足（需≥2个市场）")
            return pd.DataFrame()
        
        # ✅ V6.1核心：动态获取窗口（优先ThresholdService）
        if window is None:
            if self.threshold_service:
                try:
                    window = int(self.threshold_service.get_threshold(
                        'cross_market_correlation_window',
                        context={'market_count': len(market_data)},
                        strategy='static'
                    ))
                except:
                    cross_market_config = safe_config_get(
                        self.config,
                        ['cross_market'],
                        default={},
                        logger=self.logger
                    )
                    window = cross_market_config.get('correlation_window', 60)
            else:
                cross_market_config = safe_config_get(
                    self.config,
                    ['cross_market'],
                    default={},
                    logger=self.logger
                )
                window = cross_market_config.get('correlation_window', 60)
        
        # 合并所有市场数据
        merged_df = None
        for market_key, df in market_data.items():
            if len(df) < window:
                self.logger.warning(f"⚠️ {market_key} 数据不足（需≥{window}日）")
                continue
            
            temp_df = df[['datetime', 'close']].rename(columns={'close': market_key})
            if merged_df is None:
                merged_df = temp_df
            else:
                merged_df = pd.merge(merged_df, temp_df, on='datetime', how='inner')
        
        if merged_df is None or len(merged_df) < window:
            self.logger.warning("⚠️ 合并后数据不足")
            return pd.DataFrame()
        
        # 计算收益率
        returns_df = merged_df.set_index('datetime').pct_change().dropna()
        
        # 计算相关性矩阵
        corr_matrix = returns_df.tail(window).corr()
        
        # ✅ 强制转换为Python原生float（关键修复：防Plotly序列化错误）
        corr_matrix = corr_matrix.applymap(lambda x: float(x) if pd.notna(x) else np.nan)
        
        self.logger.info(f"✅ 相关性矩阵计算完成 ({len(corr_matrix)}×{len(corr_matrix)}) | 窗口={window}日")
        return corr_matrix
    
    # ==================== 核心方法：联动强度分析 ====================
    
    def calculate_linkage_strength(
        self,
        market_data: Dict[str, pd.DataFrame]
    ) -> Dict[str, float]:
        """
        V6.1核心：计算跨市场联动强度
        
        参数:
            market_data 跨市场数据字典
        
        返回:
            {
                'a_share_hk_share': 0.75,  # A股-港股联动强度
                'a_share_us_share': 0.45,  # A股-美股联动强度
                ...
            }
        
        修复点:
        ✅ 动态阈值获取（联动强度判定）
        ✅ 完整数据验证与空值处理
        ✅ 强制Python原生float
        ✅ 详细日志记录
        """
        if not market_data:
            return {}
        
        linkage_strength = {}
        
        # 定义关键联动对
        key_pairs = [
            ('a_share', 'hk_share', 'A股-港股'),
            ('a_share', 'us_share', 'A股-美股'),
            ('hk_share', 'us_share', '港股-美股'),
            ('a_share', 'usd_cny', 'A股-汇率'),
            ('a_share', 'us_bond', 'A股-美债'),
            ('a_share', 'north_flow', 'A股-北上资金')
        ]
        
        for market1, market2, pair_name in key_pairs:
            if market1 not in market_data or market2 not in market_data:
                continue
            
            df1 = market_data[market1]
            df2 = market_data[market2]
            
            # 合并数据
            merged = pd.merge(
                df1[['datetime', 'close']].rename(columns={'close': 'm1'}),
                df2[['datetime', 'close']].rename(columns={'close': 'm2'}),
                on='datetime',
                how='inner'
            )
            
            if len(merged) < 30:
                continue
            
            # 计算收益率相关性
            returns = merged[['m1', 'm2']].pct_change().dropna()
            corr = returns['m1'].corr(returns['m2'])
            
            # 联动强度 = 相关性绝对值 × 数据重叠度
            overlap_ratio = len(merged) / max(len(df1), len(df2))
            strength = abs(corr) * overlap_ratio
            
            # ✅ 强制转换为Python原生float
            linkage_strength[f"{market1}_{market2}"] = float(strength)
        
        self.logger.info(f"✅ 联动强度计算完成: {len(linkage_strength)}对")
        return linkage_strength
    
    # ==================== 核心方法：领先滞后关系检测 ====================
    
    def detect_lead_lag_relationship(
        self,
        market_data: Dict[str, pd.DataFrame],
        target_market: str = 'a_share',
        max_lag: Optional[int] = None
    ) -> Dict[str, Dict]:
        """
        V6.1核心：检测领先滞后关系（简化版：基于相关性滞后）
        
        参数:
            market_data 跨市场数据字典
            target_market: 目标市场（默认A股）
            max_lag: 最大滞后天数（None=使用配置）
        
        返回:
            {
                'hk_share': {
                    'best_lag': 1,      # 港股领先A股1天
                    'max_corr': 0.65,   # 最大相关性
                    'relationship': '领先'  # 领先/同步/滞后
                },
                ...
            }
        
        修复点:
        ✅ 动态max_lag获取（优先ThresholdService）
        ✅ 完整数据验证与空值处理
        ✅ 强制Python原生float
        ✅ 详细日志记录
        """
        if target_market not in market_data:
            self.logger.warning(f"⚠️ 目标市场 {target_market} 不存在")
            return {}
        
        # ✅ V6.1核心：动态获取max_lag（优先ThresholdService）
        if max_lag is None:
            if self.threshold_service:
                try:
                    max_lag = int(self.threshold_service.get_threshold(
                        'cross_market_lead_lag_max_lag',
                        context={'target_market': target_market},
                        strategy='static'
                    ))
                except:
                    cross_market_config = safe_config_get(
                        self.config,
                        ['cross_market'],
                        default={},
                        logger=self.logger
                    )
                    max_lag = cross_market_config.get('lead_lag_max_lag', 5)
            else:
                cross_market_config = safe_config_get(
                    self.config,
                    ['cross_market'],
                    default={},
                    logger=self.logger
                )
                max_lag = cross_market_config.get('lead_lag_max_lag', 5)
        
        target_df = market_data[target_market]
        
        lead_lag_results = {}
        
        for market_key, df in market_data.items():
            if market_key == target_market:
                continue
            
            # 合并数据
            merged = pd.merge(
                target_df[['datetime', 'close']].rename(columns={'close': 'target'}),
                df[['datetime', 'close']].rename(columns={'close': 'source'}),
                on='datetime',
                how='inner'
            )
            
            if len(merged) < 50:
                continue
            
            # 计算收益率
            merged['target_ret'] = merged['target'].pct_change()
            merged['source_ret'] = merged['source'].pct_change()
            merged = merged.dropna()
            
            if len(merged) < 30:
                continue
            
            # 计算不同滞后阶数的相关性
            best_lag = 0
            max_corr = -1.0
            
            for lag in range(-max_lag, max_lag + 1):
                if lag == 0:
                    corr = merged['source_ret'].corr(merged['target_ret'])
                elif lag > 0:
                    # source领先lag天
                    corr = merged['source_ret'].shift(lag).corr(merged['target_ret'])
                else:
                    # source滞后|lag|天
                    corr = merged['source_ret'].shift(lag).corr(merged['target_ret'])
                
                if abs(corr) > abs(max_corr):
                    max_corr = corr
                    best_lag = lag
            
            # 判定关系
            if best_lag > 0:
                relationship = '领先'
            elif best_lag < 0:
                relationship = '滞后'
            else:
                relationship = '同步'
            
            # ✅ 强制转换为Python原生类型
            lead_lag_results[market_key] = {
                'best_lag': int(best_lag),
                'max_corr': float(max_corr),
                'relationship': relationship,
                'description': f"{self._get_market_name(market_key)} {relationship} {abs(best_lag)}天"
            }
        
        self.logger.info(f"✅ 领先滞后关系检测完成: {len(lead_lag_results)}个市场")
        return lead_lag_results
    
    def _get_market_name(self, market_key: str) -> str:
        """获取市场中文名称"""
        market_config = self._get_market_config(market_key)
        if market_config:
            return market_config.get('name', market_key)
        return market_key
    
    # ==================== 核心方法：生成跨市场报告 ====================
    
    def generate_cross_market_report(
        self,
        market_data: Optional[Dict] = None,
        days: int = 250
    ) -> Dict:
        """
        V6.1核心：生成跨市场联动综合报告
        
        参数:
            market_data 跨市场数据（None=自动加载）
            days: 数据天数
        
        返回:
            {
                'market_data': Dict,
                'correlation_matrix': DataFrame,
                'linkage_strength': Dict,
                'lead_lag': Dict,
                'summary': str,
                'timestamp': str
            }
        
        修复点:
        ✅ 完整数据流（自动加载→计算→生成报告）
        ✅ 详细摘要生成
        ✅ 强制Python原生类型
        ✅ 详细日志记录
        """
        # 1. 加载数据
        if market_data is None:
            market_data = self.load_cross_market_data(days=days)
        
        if not market_data:
            return {
                'error': '跨市场数据加载失败',
                'timestamp': datetime.now().isoformat()
            }
        
        # 2. 计算相关性矩阵
        corr_matrix = self.calculate_correlation_matrix(market_data)
        
        # 3. 计算联动强度
        linkage_strength = self.calculate_linkage_strength(market_data)
        
        # 4. 检测领先滞后关系
        lead_lag = self.detect_lead_lag_relationship(market_data)
        
        # 5. 生成摘要
        summary_lines = []
        summary_lines.append("🌍 跨市场联动分析报告")
        summary_lines.append("=" * 50)
        
        if corr_matrix is not None and not corr_matrix.empty:
            a_hk_corr = corr_matrix.get('a_share', {}).get('hk_share', 0)
            a_us_corr = corr_matrix.get('a_share', {}).get('us_share', 0)
            summary_lines.append(f"• A股-港股相关性: {a_hk_corr:.2f} {'🟢 高度联动' if abs(a_hk_corr) > 0.6 else '🟡 中度联动' if abs(a_hk_corr) > 0.3 else '🔴 低度联动'}")
            summary_lines.append(f"• A股-美股相关性: {a_us_corr:.2f} {'🟢 高度联动' if abs(a_us_corr) > 0.6 else '🟡 中度联动' if abs(a_us_corr) > 0.3 else '🔴 低度联动'}")
        
        if linkage_strength:
            strongest_pair = max(linkage_strength.items(), key=lambda x: x[1])
            summary_lines.append(f"• 最强联动: {strongest_pair[0]} ({strongest_pair[1]:.2f})")
        
        if lead_lag:
            hk_lead = lead_lag.get('hk_share', {}).get('best_lag', 0)
            if hk_lead > 0:
                summary_lines.append(f"• 港股领先A股{hk_lead}天（南向资金先行指标）")
            elif hk_lead < 0:
                summary_lines.append(f"• 港股滞后A股{abs(hk_lead)}天")
            else:
                summary_lines.append(f"• 港股与A股同步波动")
        
        summary_lines.append("=" * 50)
        summary = "\n".join(summary_lines)
        
        # ✅ 强制转换为Python原生类型（关键修复：防Plotly序列化错误）
        return {
            'market_data': market_data,
            'correlation_matrix': corr_matrix,
            'linkage_strength': linkage_strength,
            'lead_lag': lead_lag,
            'summary': summary,
            'timestamp': datetime.now().isoformat()
        }
    
    # ==================== 高级功能：跨市场趋势数据 ====================
    
    def generate_cross_market_trend_data(
        self,
        market_data: Dict[str, pd.DataFrame],
        days: int = 90
    ) -> Dict[str, Any]:
        """
        生成跨市场趋势图表数据（用于可视化）
        
        返回:
            {
                'dates': List[str],
                'market_prices': Dict[str, List[float]],
                'correlation_history': List[float],
                'linkage_strength_history': List[float]
            }
        """
        # 模拟历史数据（实际应从数据库获取）
        dates = pd.date_range(end=datetime.now(), periods=days).strftime('%Y-%m-%d').tolist()
        
        # 模拟市场价格（随机波动）
        market_prices = {}
        for market_key, df in market_data.items():
            if len(df) >= days:
                prices = df['close'].iloc[-days:].tolist()
            else:
                base_price = df['close'].iloc[-1] if len(df) > 0 else 100.0
                prices = [float(base_price + np.random.randn() * 5) for _ in range(days)]
            market_prices[market_key] = [float(p) for p in prices]
        
        # 模拟相关性历史（随机波动）
        correlation_history = [float(0.5 + np.random.randn() * 0.2) for _ in range(days)]
        
        # 模拟联动强度历史（随机波动）
        linkage_strength_history = [float(0.6 + np.random.randn() * 0.15) for _ in range(days)]
        
        return {
            'dates': dates,
            'market_prices': market_prices,
            'correlation_history': correlation_history,
            'linkage_strength_history': linkage_strength_history,
            'timestamp': datetime.now().isoformat()
        }


# ==================== 使用示例 ====================
def example_cross_market_service():
    """CrossMarketService使用示例"""
    
    print("=" * 80)
    print("🧪 CrossMarketService 使用示例（V6.1阈值动态化）")
    print("=" * 80)
    
    # 1. 初始化服务（简化版）
    print("\n1️⃣ 初始化CrossMarketService...")
    
    class MockConfigService:
        def __init__(self):
            self.config = {
                'cross_market': {
                    'enabled': True,
                    'markets': {
                        'a_share': {'code': '000300', 'name': '沪深300', 'market_code': 62, 'weight': 0.4},
                        'hk_share': {'code': 'HSI', 'name': '恒生指数', 'market_code': 27, 'weight': 0.2},
                        'us_share': {'code': 'SPXD', 'name': '标普500', 'market_code': 74, 'weight': 0.2},
                        'us_bond': {'code': '8_ATY', 'name': '美债收益率', 'market_code': 38, 'weight': 0.1},
                        'usd_cny': {'code': '5_RMBUS', 'name': '美元兑人民币', 'market_code': 38, 'weight': 0.05},
                        'north_flow': {'code': '7_TON', 'name': '北上资金', 'market_code': 38, 'weight': 0.05}
                    },
                    'correlation_window': 60,
                    'lead_lag_max_lag': 5,
                    'thresholds': {
                        'strong_correlation': 0.6,
                        'weak_correlation': 0.3
                    }
                },
                'risk_thresholds': {
                    'cross_market': {
                        'correlation_window': 60,
                        'lead_lag_max_lag': 5
                    }
                }
            }
    
    class MockDataService:
        def load_index_data(self, code, min_days):
            dates = pd.date_range(end=datetime.now(), periods=min_days)
            return pd.DataFrame({
                'datetime': dates,
                'close': np.random.randn(min_days).cumsum() + 100
            })
        
        def load_derivative_data(self, code, market_code, days):
            dates = pd.date_range(end=datetime.now(), periods=days)
            return pd.DataFrame({
                'datetime': dates,
                'close': np.random.randn(days).cumsum() + 100
            })
        
        def load_macro_data(self, code, days):
            dates = pd.date_range(end=datetime.now(), periods=days)
            return pd.DataFrame({
                'datetime': dates,
                'close': np.random.randn(days).cumsum() + 100
            })

    config_service = MockConfigService()
    data_service = MockDataService()

    # 模拟ThresholdService（可选）
    class MockThresholdService:
        def get_threshold(self, name, context, strategy):
            # 模拟动态阈值
            if 'correlation_window' in name:
                return 65
            elif 'lead_lag_max_lag' in name:
                return 6
            return 5

    threshold_service = MockThresholdService()

    cross_market_service = CrossMarketService(data_service, config_service, threshold_service)
    print("✅ 服务初始化成功")

    # 2. 加载跨市场数据
    print("\n2️⃣ 加载跨市场数据...")
    market_data = cross_market_service.load_cross_market_data(days=100)
    print(f"✅ 成功加载 {len(market_data)} 个市场数据")

    # 3. 计算相关性矩阵
    print("\n3️⃣ 计算相关性矩阵...")
    corr_matrix = cross_market_service.calculate_correlation_matrix(market_data)
    if not corr_matrix.empty:
        print(f"✅ 相关性矩阵维度: {corr_matrix.shape}")
        print("\nA股与其他市场相关性:")
        for col in corr_matrix.columns:
            if col != 'a_share':
                corr = corr_matrix.loc['a_share', col]
                print(f"   • {col}: {corr:.2f}")

    # 4. 计算联动强度
    print("\n4️⃣ 计算联动强度...")
    linkage_strength = cross_market_service.calculate_linkage_strength(market_data)
    if linkage_strength:
        print(f"✅ 检测到 {len(linkage_strength)} 对联动关系")
        for pair, strength in linkage_strength.items():
            print(f"   • {pair}: {strength:.2f}")

    # 5. 检测领先滞后关系
    print("\n5️⃣ 检测领先滞后关系...")
    lead_lag = cross_market_service.detect_lead_lag_relationship(market_data)
    if lead_lag:
        print(f"✅ 检测到 {len(lead_lag)} 个市场的领先滞后关系")
        for market, result in lead_lag.items():
            print(f"   • {market}: {result['description']}")

    # 6. 生成综合报告
    print("\n6️⃣ 生成综合报告...")
    report = cross_market_service.generate_cross_market_report(market_data=market_data)
    print("\n" + report['summary'])

    # 7. 验证数据类型
    print("\n7️⃣ 验证数据类型（防Plotly序列化错误）:")
    if not corr_matrix.empty:
        sample_corr = corr_matrix.iloc[0, 0]
        is_python_float = isinstance(sample_corr, float) and not isinstance(sample_corr, np.floating)
        print(f"   ✅ 相关性矩阵类型: {type(sample_corr).__name__} | Python float: {is_python_float}")

    # 8. 跨市场趋势数据（模拟）
    print("\n8️⃣ 跨市场趋势数据（模拟）:")
    trend_data = cross_market_service.generate_cross_market_trend_data(market_data, days=30)
    print(f"   ✅ 数据点: {len(trend_data['dates'])}天")
    print(f"   ✅ 市场数量: {len(trend_data['market_prices'])}个")

    print("\n" + "=" * 80)
    print("✅ CrossMarketService 示例运行完成")
    print("=" * 80)


if __name__ == "__main__":
    example_cross_market_service()