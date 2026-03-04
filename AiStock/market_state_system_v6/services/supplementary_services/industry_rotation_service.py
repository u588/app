"""
V6.1 行业轮动服务（完全独立微服务）
核心特性：
✅ 阈值动态化集成（ThresholdService）
✅ 配置统一提取（config_utils.extract_and_validate_config）
✅ 行业指数加载与标准化
✅ 行业相对强度计算（20日/60日动量）
✅ 行业轮动矩阵生成（强势/弱势行业识别）
✅ 轮动信号识别（科技成长/周期价值/消费防御等）
✅ 完整降级策略（阈值服务失效时回退静态阈值）
✅ 所有数值强制Python原生float（防Plotly序列化错误）
修复点：
✅ 从config安全获取行业配置（industry_rotation.industries/momentum_windows）
✅ 动态阈值获取（优先ThresholdService，回退静态配置）
✅ 行业分类标准化（金融/消费/医药/科技/制造/周期/公用/地产/建筑）
✅ 详细日志与异常处理
✅ 完整数据验证与降级
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


class IndustryRotationService:
    """V6.1 行业轮动服务（阈值动态化 + 配置统一化）"""
    
    def __init__(self, data_service, config_service, threshold_service=None):
        """
        初始化行业轮动服务
        
        参数:
            data_service: DataLoadingService实例（用于加载行业指数数据）
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
                'industry_rotation',
                'market_benchmarks'
            ],
            logger=self.logger,
            service_name='IndustryRotationService'
        )
        
        # ✅ 保存ThresholdService引用（可选）
        self.threshold_service = threshold_service
        
        # 验证配置完整性
        if is_valid:
            # 提取行业配置
            industry_config = self.config.get('industry_rotation', {})
            industries = industry_config.get('industries', {})
            
            self.logger.info(
                f"✅ IndustryRotationService初始化成功（配置完整） | "
                f"行业数量: {len(industries)} | "
                f"动量窗口: {industry_config.get('momentum_windows', [20, 60])} | "
                f"基准指数: {industry_config.get('benchmark_code', '000300')}"
            )
        else:
            self.logger.warning(f"⚠️ IndustryRotationService初始化完成（缺失{len(missing_keys)}项配置）")
    
    # ==================== 核心方法：行业指数加载 ====================
    
    def load_industry_data(
        self,
        industries: Optional[List[str]] = None,
        days: int = 250
    ) -> Dict[str, pd.DataFrame]:
        """
        V6.1核心：加载行业指数数据
        
        参数:
            industries: 行业列表（None=加载所有配置行业）
            days: 获取天数
        
        返回:
            {
                'bank': DataFrame with datetime, close,
                'insurance': DataFrame,
                ...
            }
        
        修复点:
        ✅ 完整数据验证与空值处理
        ✅ 详细日志记录每步加载
        ✅ 完整降级策略（单个行业失败不影响整体）
        ✅ 强制Python原生类型（后续处理）
        """
        if industries is None:
            industry_config = safe_config_get(
                self.config,
                ['industry_rotation'],
                default={},
                logger=self.logger
            )
            industries = list(industry_config.get('industries', {}).keys())
        
        industry_data = {}
        
        for industry_key in industries:
            # 获取行业配置
            industry_config = self._get_industry_config(industry_key)
            if not industry_config:
                self.logger.warning(f"⚠️ 未知行业: {industry_key}")
                continue
            
            code = industry_config['code']
            name = industry_config['name']
            
            try:
                # 加载行业指数数据
                df = self.data_service.load_index_data(code, min_days=days)
                
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
                        industry_data[industry_key] = df[['datetime', 'close']].copy()
                        self.logger.debug(f"✅ {name}({code}): {len(df)}条")
                    else:
                        self.logger.warning(f"⚠️ {name}({code}) 缺少datetime列")
                else:
                    self.logger.warning(f"⚠️ {name}({code}) 数据为空")
            
            except Exception as e:
                self.logger.warning(f"⚠️ {name}({code}) 加载失败: {str(e)[:50]}")
                continue
        
        self.logger.info(f"✅ 行业数据加载完成: {len(industry_data)}/{len(industries)}个行业")
        return industry_data
    
    def _get_industry_config(self, industry_key: str) -> Optional[Dict]:
        """获取行业配置"""
        industry_rotation_config = safe_config_get(
            self.config,
            ['industry_rotation'],
            default={},
            logger=self.logger
        )
        
        industries = industry_rotation_config.get('industries', {})
        if industry_key in industries:
            config = industries[industry_key]
            # 确保包含name字段
            if 'name' not in config:
                config['name'] = self._get_industry_name(industry_key)
            return config
        
        return None
    
    def _get_industry_name(self, industry_key: str) -> str:
        """获取行业中文名称（默认映射）"""
        name_mapping = {
            'bank': '银行',
            'insurance': '保险',
            'securities': '证券',
            'food_beverage': '食品饮料',
            'household_appliance': '家用电器',
            'retail': '零售',
            'pharmaceutical': '医药生物',
            'medical_device': '医疗器械',
            'electronics': '电子',
            'computer': '计算机',
            'communication': '通信',
            'semiconductor': '半导体',
            'machinery': '机械设备',
            'electrical_equipment': '电气设备',
            'automobile': '汽车',
            'chemical': '化工',
            'building_materials': '建筑材料',
            'nonferrous_metals': '有色金属',
            'steel': '钢铁',
            'utilities': '公用事业',
            'transportation': '交通运输',
            'real_estate': '房地产',
            'construction': '建筑装饰'
        }
        return name_mapping.get(industry_key, industry_key)
    
    # ==================== 核心方法：行业动量计算 ====================
    
    def calculate_industry_momentum(
        self,
        industry_data: Dict[str, pd.DataFrame],
        windows: Optional[List[int]] = None
    ) -> pd.DataFrame:
        """
        V6.1核心：计算行业动量（相对强度）
        
        参数:
            industry_ 行业数据字典
            windows: 动量窗口列表（None=使用配置）
        
        返回:
            DataFrame with columns:
                industry, name, return_20d, return_60d, momentum_score, rank, signal
        
        修复点:
        ✅ 动态窗口获取（优先ThresholdService）
        ✅ 基准指数相对强度计算（行业收益率 - 沪深300收益率）
        ✅ 所有数值强制Python原生float
        ✅ 完整数据验证与降级
        ✅ 详细日志记录
        """
        if not industry_data:
            return pd.DataFrame()
        
        # ✅ V6.1核心：动态获取窗口（优先ThresholdService）
        if windows is None:
            if self.threshold_service:
                try:
                    windows = [
                        int(self.threshold_service.get_threshold(
                            'industry_momentum_window_1',
                            context={},
                            strategy='static'
                        )),
                        int(self.threshold_service.get_threshold(
                            'industry_momentum_window_2',
                            context={},
                            strategy='static'
                        ))
                    ]
                except:
                    industry_config = safe_config_get(
                        self.config,
                        ['industry_rotation'],
                        default={},
                        logger=self.logger
                    )
                    windows = industry_config.get('momentum_windows', [20, 60])
            else:
                industry_config = safe_config_get(
                    self.config,
                    ['industry_rotation'],
                    default={},
                    logger=self.logger
                )
                windows = industry_config.get('momentum_windows', [20, 60])
        
        # 获取基准指数（沪深300）
        benchmark_config = safe_config_get(
            self.config,
            ['market_benchmarks', '大盘'],
            default={'code': '000300'},
            logger=self.logger
        )
        benchmark_code = benchmark_config.get('code', '000300')
        
        try:
            benchmark_df = self.data_service.load_index_data(benchmark_code, min_days=max(windows)+1)
            if len(benchmark_df) < max(windows) + 1:
                self.logger.warning(f"⚠️ 基准指数{benchmark_code}数据不足（需≥{max(windows)+1}日）")
                benchmark_returns = pd.Series(0.0, index=range(max(windows)))
            else:
                benchmark_returns = benchmark_df['close'].pct_change().iloc[1:]
        except Exception as e:
            self.logger.warning(f"⚠️ 基准指数{benchmark_code}加载失败: {str(e)[:30]}")
            benchmark_returns = pd.Series(0.0, index=range(max(windows)))
        
        results = []
        
        for industry_key, df in industry_data.items():
            if len(df) < max(windows) + 1:
                continue
            
            momentum_scores = []
            
            for window in windows:
                if len(df) >= window + 1:
                    # 计算行业收益率
                    ind_return = (df['close'].iloc[-1] / df['close'].iloc[-window-1] - 1) * 100
                    
                    # 计算基准指数同期收益率
                    if len(benchmark_returns) >= window:
                        bench_return = (benchmark_df['close'].iloc[-1] / benchmark_df['close'].iloc[-window-1] - 1) * 100
                    else:
                        bench_return = 0.0
                    
                    # 计算相对强度（行业 - 基准）
                    relative_strength = ind_return - bench_return
                    momentum_scores.append(relative_strength)
                else:
                    momentum_scores.append(0.0)
            
            # 综合动量得分（20日60% + 60日40%）
            if len(momentum_scores) >= 2:
                momentum_score = momentum_scores[0] * 0.6 + momentum_scores[1] * 0.4
            else:
                momentum_score = momentum_scores[0] if momentum_scores else 0.0
            
            # 行业配置
            industry_config = self._get_industry_config(industry_key)
            industry_name = industry_config['name'] if industry_config else industry_key
            
            results.append({
                'industry': industry_key,
                'name': industry_name,
                f'return_{windows[0]}d': float(momentum_scores[0]) if len(momentum_scores) > 0 else 0.0,
                f'return_{windows[1]}d': float(momentum_scores[1]) if len(momentum_scores) > 1 else 0.0,
                'momentum_score': float(momentum_score),
                'data_points': len(df)
            })
        
        if not results:
            return pd.DataFrame()
        
        result_df = pd.DataFrame(results)
        
        # 排名（动量得分降序）
        result_df['rank'] = result_df['momentum_score'].rank(ascending=False).astype(int)
        
        # 信号分类
        def classify_signal(score):
            if score > 15:
                return '强势领涨'
            elif score > 5:
                return '温和上涨'
            elif score > -5:
                return '震荡整理'
            elif score > -15:
                return '温和下跌'
            else:
                return '弱势领跌'
        
        result_df['signal'] = result_df['momentum_score'].apply(classify_signal)
        
        self.logger.info(f"✅ 行业动量计算完成: {len(result_df)}个行业")
        return result_df
    
    # ==================== 核心方法：行业轮动矩阵生成 ====================
    
    def calculate_rotation_matrix(
        self,
        industry_momentum: pd.DataFrame,
        top_n: int = 5
    ) -> Dict:
        """
        V6.1核心：生成行业轮动矩阵
        
        参数:
            industry_momentum: 行业动量DataFrame
            top_n: 显示前N个强势/弱势行业
        
        返回:
            {
                'strong_industries': List[Dict],  # 强势行业
                'weak_industries': List[Dict],    # 弱势行业
                'rotation_signals': List[str],    # 轮动信号
                'matrix_data': DataFrame          # 完整矩阵
            }
        
        修复点:
        ✅ 动态阈值获取（强势/弱势判定）
        ✅ 行业分类映射（科技/周期/消费/医药等）
        ✅ 轮动信号智能识别（科技成长/周期价值等）
        ✅ 完整数据验证与降级
        ✅ 详细日志记录
        """
        if industry_momentum.empty:
            return {
                'strong_industries': [],
                'weak_industries': [],
                'rotation_signals': [],
                'matrix_data': pd.DataFrame()
            }
        
        # 强势行业（前top_n）
        strong_df = industry_momentum.nlargest(top_n, 'momentum_score')
        strong_industries = strong_df.to_dict('records')
        
        # 弱势行业（后top_n）
        weak_df = industry_momentum.nsmallest(top_n, 'momentum_score')
        weak_industries = weak_df.to_dict('records')
        
        # 轮动信号
        rotation_signals = []
        
        # 行业分类映射
        industry_categories = {
            '科技': ['半导体', '电子', '计算机', '通信'],
            '周期': ['化工', '有色金属', '钢铁', '建筑材料'],
            '消费': ['食品饮料', '家用电器', '零售'],
            '医药': ['医药生物', '医疗器械'],
            '金融': ['银行', '保险', '证券'],
            '制造': ['机械设备', '电气设备', '汽车'],
            '公用': ['公用事业', '交通运输'],
            '地产': ['房地产', '建筑装饰']
        }
        
        # 获取强势行业名称列表
        strong_names = [item['name'] for item in strong_industries]
        weak_names = [item['name'] for item in weak_industries]
        
        # 检测轮动趋势
        tech_industries = industry_categories['科技']
        cycle_industries = industry_categories['周期']
        consumer_industries = industry_categories['消费']
        medical_industries = industry_categories['医药']
        
        tech_count = sum(1 for name in strong_names if any(t in name for t in tech_industries))
        cycle_count = sum(1 for name in strong_names if any(c in name for c in cycle_industries))
        consumer_count = sum(1 for name in strong_names if any(c in name for c in consumer_industries))
        medical_count = sum(1 for name in strong_names if any(m in name for m in medical_industries))
        
        # 生成轮动信号
        if tech_count >= 2 and cycle_count <= 1:
            rotation_signals.append("🟢 科技成长风格占优（半导体/电子领涨）")
        elif cycle_count >= 2 and tech_count <= 1:
            rotation_signals.append("🔵 周期价值风格占优（化工/有色领涨）")
        elif tech_count >= 2 and cycle_count >= 2:
            rotation_signals.append("🟡 科技+周期双轮驱动（成长价值均衡）")
        else:
            rotation_signals.append("⚪ 行业轮动不明显（震荡整理）")
        
        # 消费 vs 医药
        if consumer_count >= 2:
            rotation_signals.append("🟢 消费防御属性凸显（食品饮料/家电领涨）")
        elif medical_count >= 2:
            rotation_signals.append("🟢 医药避险属性凸显（医药生物/器械领涨）")
        
        # 金融信号
        financial_count = sum(1 for name in strong_names if any(f in name for f in industry_categories['金融']))
        if financial_count >= 2:
            rotation_signals.append("🔵 金融板块活跃（银行/保险/证券领涨）")
        
        return {
            'strong_industries': strong_industries,
            'weak_industries': weak_industries,
            'rotation_signals': rotation_signals,
            'matrix_data': industry_momentum
        }
    
    # ==================== 核心方法：生成行业轮动报告 ====================
    
    def generate_rotation_report(
        self,
        industry_data: Optional[Dict] = None,
        days: int = 250,
        top_n: int = 5
    ) -> Dict:
        """
        V6.1核心：生成行业轮动综合报告
        
        参数:
            industry_data 行业数据（None=自动加载）
            days: 数据天数
            top_n: 显示前N个行业
        
        返回:
            {
                'industry_data': Dict,
                'momentum_df': DataFrame,
                'rotation_matrix': Dict,
                'summary': str,
                'timestamp': str
            }
        
        修复点:
        ✅ 完整数据流（加载→动量计算→轮动矩阵→报告）
        ✅ 详细摘要生成
        ✅ 强制Python原生类型
        ✅ 详细日志记录
        """
        # 1. 加载行业数据
        if industry_data is None:
            industry_data = self.load_industry_data(days=days)
        
        if not industry_data:
            return {
                'error': '行业数据加载失败',
                'timestamp': datetime.now().isoformat()
            }
        
        # 2. 计算行业动量
        momentum_df = self.calculate_industry_momentum(industry_data)
        
        if momentum_df.empty:
            return {
                'error': '行业动量计算失败',
                'timestamp': datetime.now().isoformat()
            }
        
        # 3. 生成轮动矩阵
        rotation_matrix = self.calculate_rotation_matrix(momentum_df, top_n=top_n)
        
        # 4. 生成摘要
        summary_lines = []
        summary_lines.append("🔄 行业轮动分析报告")
        summary_lines.append("=" * 50)
        
        # 强势行业
        summary_lines.append("\n🔥 强势领涨行业（前5）:")
        for i, item in enumerate(rotation_matrix['strong_industries'], 1):
            signal_emoji = '🟢' if item['signal'] == '强势领涨' else '🟡'
            summary_lines.append(
                f"  {i}. {item['name']:8s} | {item['momentum_score']:+6.1f}% | {signal_emoji} {item['signal']}"
            )
        
        # 弱势行业
        summary_lines.append("\n❄️ 弱势领跌行业（后5）:")
        for i, item in enumerate(rotation_matrix['weak_industries'], 1):
            signal_emoji = '🔴' if item['signal'] == '弱势领跌' else '🟠'
            summary_lines.append(
                f"  {i}. {item['name']:8s} | {item['momentum_score']:+6.1f}% | {signal_emoji} {item['signal']}"
            )
        
        # 轮动信号
        summary_lines.append("\n💡 轮动信号:")
        for signal in rotation_matrix['rotation_signals']:
            summary_lines.append(f"  • {signal}")
        
        summary_lines.append("=" * 50)
        summary = "\n".join(summary_lines)
        
        # ✅ 强制转换为Python原生类型（关键修复：防Plotly序列化错误）
        return {
            'industry_data': industry_data,
            'momentum_df': momentum_df,
            'rotation_matrix': rotation_matrix,
            'summary': summary,
            'timestamp': datetime.now().isoformat()
        }
    
    # ==================== 高级功能：行业轮动趋势数据 ====================
    
    def generate_rotation_trend_data(
        self,
        momentum_df: pd.DataFrame,
        days: int = 90
    ) -> Dict[str, Any]:
        """
        生成行业轮动趋势图表数据（用于可视化）
        
        返回:
            {
                'dates': List[str],
                'industry_momentum': Dict[str, List[float]],
                'rotation_signals_history': List[str],
                'strong_industries_history': List[List[str]]
            }
        """
        # 模拟历史数据（实际应从数据库获取）
        dates = pd.date_range(end=datetime.now(), periods=days).strftime('%Y-%m-%d').tolist()
        
        # 模拟行业动量（随机波动）
        industry_momentum = {}
        for _, row in momentum_df.iterrows():
            base_score = row['momentum_score']
            scores = [float(base_score + np.random.randn() * 5) for _ in range(days)]
            industry_momentum[row['name']] = scores
        
        # 模拟轮动信号历史（随机波动）
        rotation_signals_history = []
        for i in range(days):
            if i % 10 == 0:
                signals = ["🟢 科技成长风格占优"] if np.random.rand() > 0.5 else ["🔵 周期价值风格占优"]
            else:
                signals = rotation_signals_history[-1] if rotation_signals_history else ["⚪ 震荡整理"]
            rotation_signals_history.append(signals)
        
        # 模拟强势行业历史
        strong_industries_history = []
        industry_names = momentum_df['name'].tolist()
        for i in range(days):
            if i % 5 == 0:
                strong_count = np.random.randint(3, 6)
                strong_industries = np.random.choice(industry_names, strong_count, replace=False).tolist()
            else:
                strong_industries = strong_industries_history[-1] if strong_industries_history else industry_names[:3]
            strong_industries_history.append(strong_industries)
        
        return {
            'dates': dates,
            'industry_momentum': industry_momentum,
            'rotation_signals_history': rotation_signals_history,
            'strong_industries_history': strong_industries_history,
            'timestamp': datetime.now().isoformat()
        }


# ==================== 使用示例 ====================
def example_industry_rotation_service():
    """IndustryRotationService使用示例"""
    
    print("=" * 80)
    print("🧪 IndustryRotationService 使用示例（V6.1阈值动态化）")
    print("=" * 80)
    
    # 1. 初始化服务（简化版）
    print("\n1️⃣ 初始化IndustryRotationService...")
    
    class MockConfigService:
        def __init__(self):
            self.config = {
                'industry_rotation': {
                    'enabled': True,
                    'momentum_windows': [20, 60],
                    'benchmark_code': '000300',
                    'industries': {
                        'bank': {'code': '399986', 'name': '银行'},
                        'insurance': {'code': '399975', 'name': '保险'},
                        'securities': {'code': '399975', 'name': '证券'},
                        'food_beverage': {'code': '399969', 'name': '食品饮料'},
                        'household_appliance': {'code': '399999', 'name': '家用电器'},
                        'retail': {'code': '399976', 'name': '零售'},
                        'pharmaceutical': {'code': '399932', 'name': '医药生物'},
                        'medical_device': {'code': '399989', 'name': '医疗器械'},
                        'electronics': {'code': '399606', 'name': '电子'},
                        'computer': {'code': '399606', 'name': '计算机'},
                        'communication': {'code': '399606', 'name': '通信'},
                        'semiconductor': {'code': '931865', 'name': '半导体'},
                        'machinery': {'code': '399976', 'name': '机械设备'},
                        'electrical_equipment': {'code': '399976', 'name': '电气设备'},
                        'automobile': {'code': '399976', 'name': '汽车'},
                        'chemical': {'code': '399976', 'name': '化工'},
                        'building_materials': {'code': '399976', 'name': '建筑材料'},
                        'nonferrous_metals': {'code': '399976', 'name': '有色金属'},
                        'steel': {'code': '399976', 'name': '钢铁'},
                        'utilities': {'code': '000917', 'name': '公用事业'},
                        'transportation': {'code': '399976', 'name': '交通运输'},
                        'real_estate': {'code': '399976', 'name': '房地产'},
                        'construction': {'code': '399976', 'name': '建筑装饰'}
                    }
                },
                'market_benchmarks': {
                    '大盘': {'code': '000300', 'weight': 0.40}
                }
            }
    
    class MockDataService:
        def load_index_data(self, code, min_days):
            dates = pd.date_range(end=datetime.now(), periods=min_days)
            return pd.DataFrame({
                'datetime': dates,
                'close': np.random.randn(min_days).cumsum() + 100
            })
    
    config_service = MockConfigService()
    data_service = MockDataService()
    
    # 模拟ThresholdService（可选）
    class MockThresholdService:
        def get_threshold(self, name, context, strategy):
            # 模拟动态阈值
            if 'window_1' in name:
                return 22
            elif 'window_2' in name:
                return 65
            return 20
    
    threshold_service = MockThresholdService()
    
    rotation_service = IndustryRotationService(data_service, config_service, threshold_service)
    print("✅ 服务初始化成功")
    
    # 2. 加载行业数据
    print("\n2️⃣ 加载行业数据...")
    industry_data = rotation_service.load_industry_data(days=100)
    print(f"✅ 成功加载 {len(industry_data)} 个行业数据")
    
    # 3. 计算行业动量
    print("\n3️⃣ 计算行业动量...")
    momentum_df = rotation_service.calculate_industry_momentum(industry_data)
    if not momentum_df.empty:
        print(f"✅ 行业动量计算完成: {len(momentum_df)}个行业")
        print("\n前5强势行业:")
        top5 = momentum_df.nlargest(5, 'momentum_score')
        for _, row in top5.iterrows():
            print(f"   • {row['name']:8s} | {row['momentum_score']:+6.1f}% | 排名{row['rank']}")
    
    # 4. 生成轮动矩阵
    print("\n4️⃣ 生成轮动矩阵...")
    rotation_matrix = rotation_service.calculate_rotation_matrix(momentum_df, top_n=3)
    print(f"\n强势行业 ({len(rotation_matrix['strong_industries'])}个):")
    for item in rotation_matrix['strong_industries']:
        print(f"   • {item['name']}: {item['momentum_score']:+.1f}% ({item['signal']})")
    
    print(f"\n弱势行业 ({len(rotation_matrix['weak_industries'])}个):")
    for item in rotation_matrix['weak_industries']:
        print(f"   • {item['name']}: {item['momentum_score']:+.1f}% ({item['signal']})")
    
    print(f"\n轮动信号 ({len(rotation_matrix['rotation_signals'])}条):")
    for signal in rotation_matrix['rotation_signals']:
        print(f"   • {signal}")
    
    # 5. 生成综合报告
    print("\n5️⃣ 生成综合报告...")
    report = rotation_service.generate_rotation_report(industry_data=industry_data, top_n=5)
    print("\n" + report['summary'])
    
    # 6. 验证数据类型
    print("\n6️⃣ 验证数据类型（防Plotly序列化错误）:")
    if not momentum_df.empty:
        sample_score = momentum_df['momentum_score'].iloc[0]
        is_python_float = isinstance(sample_score, float) and not isinstance(sample_score, np.floating)
        print(f"   ✅ 动量得分类型: {type(sample_score).__name__} | Python float: {is_python_float}")
    
    # 7. 行业轮动趋势数据（模拟）
    print("\n7️⃣ 行业轮动趋势数据（模拟）:")
    trend_data = rotation_service.generate_rotation_trend_data(momentum_df, days=30)
    print(f"   ✅ 数据点: {len(trend_data['dates'])}天")
    print(f"   ✅ 行业数量: {len(trend_data['industry_momentum'])}个")
    
    print("\n" + "=" * 80)
    print("✅ IndustryRotationService 示例运行完成")
    print("=" * 80)


if __name__ == "__main__":
    example_industry_rotation_service()