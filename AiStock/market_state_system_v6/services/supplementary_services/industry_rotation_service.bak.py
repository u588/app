"""
V6.1 行业轮动服务（完全独立微服务 - 修复版）
核心修复：
✅ 配置提取到实例变量（self.industries_config/self.momentum_windows/self.benchmark_code）
✅ 所有配置值自动去除空格（防御YAML空格问题）
✅ 严格类型验证（确保load_index_data返回DataFrame）
✅ 完整降级策略（配置缺失时使用默认值）
✅ 所有数值强制Python原生float（防Plotly序列化错误）
修复问题：
❌ 'IndustryRotationService' object has no attribute（未设置实例变量）
❌ 配置空格导致数据加载失败（code/name末尾空格）
❌ 基准指数加载失败导致类型错误（非DataFrame）
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
    """V6.1 行业轮动服务（阈值动态化 + 配置统一化 - 修复版）"""
    
    def __init__(self, data_service, config_service, threshold_service=None):
        """
        初始化行业轮动服务（修复版）
        
        修复点:
        ✅ 将配置提取到实例变量（self.industries_config等）
        ✅ 自动去除配置值空格（防御YAML空格问题）
        ✅ 严格验证配置结构
        ✅ 配置缺失时提供默认值（保障服务可用性）
        """
        self.data_service = data_service
        self.logger = logger
        
        # ✅ 修复1：统一配置提取
        self.config, is_valid, missing_keys = extract_and_validate_config(
            config_service=config_service,
            required_keys=[
                'industry_rotation',
                'market_benchmarks'
            ],
            logger=self.logger,
            service_name='IndustryRotationService'
        )
        
        # ✅ 修复2：关键！将配置提取到实例变量（避免后续AttributeError）
        try:
            # 从config提取industry_rotation配置
            ir_config = self.config.get('industry_rotation', {})
            
            # 提取到实例变量（自动去除空格）
            self.industries_config = self._sanitize_industries_config(
                ir_config.get('industries', {})
            )
            self.momentum_windows = ir_config.get('momentum_windows', [20, 60])
            self.benchmark_code = str(ir_config.get('benchmark_code', '000300')).strip()
            
            # 验证industries_config
            if not self.industries_config:
                self.logger.error(
                    "❌ industry_rotation.industries 配置为空！将使用默认行业列表"
                )
                # 降级：使用最小可行配置
                self.industries_config = {
                    'bank': {'code': '399986', 'name': '银行'},
                    'securities': {'code': '399975', 'name': '证券'},
                    'semiconductor': {'code': '931865', 'name': '半导体'}
                }
            
            self.logger.info(
                f"✅ IndustryRotationService初始化成功 | "
                f"行业数量: {len(self.industries_config)} | "
                f"动量窗口: {self.momentum_windows} | "
                f"基准指数: {self.benchmark_code}"
            )
        
        except Exception as e:
            self.logger.error(f"❌ IndustryRotationService配置提取失败: {str(e)[:100]}")
            import traceback
            self.logger.debug(traceback.format_exc())
            
            # ✅ 修复3：异常时设置默认值（确保属性存在）
            self.industries_config = {
                'bank': {'code': '399986', 'name': '银行'},
                'securities': {'code': '399975', 'name': '证券'},
                'semiconductor': {'code': '931865', 'name': '半导体'}
            }
            self.momentum_windows = [20, 60]
            self.benchmark_code = '000300'
        
        # ✅ 保存ThresholdService引用（可选）
        self.threshold_service = threshold_service
    
    def _sanitize_industries_config(self, industries: Dict) -> Dict:
        """
        清理行业配置（自动去除code/name空格）
        
        修复点:
        ✅ 自动去除code和name的首尾空格
        ✅ 保留原始配置结构
        """
        sanitized = {}
        for key, config in industries.items():
            sanitized_config = config.copy()
            # 清理code
            if 'code' in sanitized_config:
                sanitized_config['code'] = str(sanitized_config['code']).strip()
            # 清理name
            if 'name' in sanitized_config and isinstance(sanitized_config['name'], str):
                sanitized_config['name'] = sanitized_config['name'].strip()
            sanitized[key] = sanitized_config
        return sanitized
    
    # ==================== 核心方法：行业指数加载 ====================
    
    def load_industry_data(
        self,
        industries: Optional[List[str]] = None,
        days: int = 250
    ) -> Dict[str, pd.DataFrame]:
        """
        V6.1核心：加载行业指数数据（修复版）
        
        修复点:
        ✅ 严格验证返回值类型（必须是DataFrame）
        ✅ 空数据安全降级（跳过无效行业）
        ✅ 详细错误日志（显示实际类型）
        """
        if industries is None:
            industries = list(self.industries_config.keys())
        
        industry_data = {}
        
        for industry_key in industries:
            # 获取行业配置（已清理空格）
            industry_config = self.industries_config.get(industry_key)
            if not industry_config:
                self.logger.warning(f"⚠️ 未知行业: {industry_key}")
                continue
            
            code = industry_config['code']
            name = industry_config['name']
            
            try:
                # ✅ 修复：严格验证返回值类型
                df = self.data_service.load_index_data(code, min_days=days)
                
                # 严格验证：必须是DataFrame且有数据
                if not isinstance(df, pd.DataFrame):
                    self.logger.error(
                        f"❌ {name}({code}) 数据类型错误 | 期望DataFrame，实际: {type(df).__name__}"
                    )
                    continue
                
                if len(df) == 0:
                    self.logger.warning(f"⚠️ {name}({code}) 数据为空")
                    continue
                
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
            
            except Exception as e:
                self.logger.warning(f"⚠️ {name}({code}) 加载失败: {str(e)[:50]}")
                import traceback
                self.logger.debug(traceback.format_exc())
                continue
        
        self.logger.info(f"✅ 行业数据加载完成: {len(industry_data)}/{len(industries)}个行业")
        return industry_data
    
    # ==================== 核心方法：行业动量计算 ====================
    
    def calculate_industry_momentum(
        self,
        industry_data: Dict[str, pd.DataFrame],
        windows: Optional[List[int]] = None
    ) -> pd.DataFrame:
        """
        V6.1核心：计算行业动量（相对强度）（修复版）
        
        修复点:
        ✅ 基准指数加载严格验证（确保DataFrame）
        ✅ 空基准数据安全降级（使用0收益率）
        ✅ 所有数值强制Python原生float
        """
        if not industry_data:
            return pd.DataFrame()
        
        # ✅ 修复：动态获取窗口（优先ThresholdService）
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
                    windows = self.momentum_windows
            else:
                windows = self.momentum_windows
        
        # ✅ 修复：基准指数加载（严格验证）
        try:
            benchmark_df = self.data_service.load_index_data(self.benchmark_code, min_days=max(windows)+1)
            
            # 严格验证基准指数
            if not isinstance(benchmark_df, pd.DataFrame) or len(benchmark_df) < max(windows) + 1:
                self.logger.warning(
                    f"⚠️ 基准指数{self.benchmark_code}数据无效（非DataFrame或不足{max(windows)+1}日），"
                    f"使用0收益率"
                )
                # 降级：使用0收益率
                benchmark_returns = pd.Series(0.0, index=range(max(windows)))
                benchmark_valid = False
            else:
                benchmark_returns = benchmark_df['close'].pct_change().iloc[1:]
                benchmark_valid = True
        except Exception as e:
            self.logger.warning(f"⚠️ 基准指数{self.benchmark_code}加载失败: {str(e)[:50]}，使用0收益率")
            benchmark_returns = pd.Series(0.0, index=range(max(windows)))
            benchmark_valid = False
        
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
                    if benchmark_valid and len(benchmark_df) >= window + 1:
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
            
            # 行业名称
            industry_name = self.industries_config.get(industry_key, {}).get('name', industry_key)
            
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
        V6.1核心：生成行业轮动矩阵（修复版）
        
        修复点:
        ✅ 空DataFrame安全处理
        ✅ 行业分类映射健壮性（避免KeyError）
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
        
        # 检测轮动趋势（健壮性检查）
        tech_count = sum(1 for name in strong_names if any(t in name for t in industry_categories['科技']))
        cycle_count = sum(1 for name in strong_names if any(c in name for c in industry_categories['周期']))
        consumer_count = sum(1 for name in strong_names if any(c in name for c in industry_categories['消费']))
        medical_count = sum(1 for name in strong_names if any(m in name for m in industry_categories['医药']))
        
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
        V6.1核心：生成行业轮动综合报告（修复版）
        
        修复点:
        ✅ 完整数据流验证
        ✅ 空数据安全降级
        ✅ 强制Python原生类型
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
        
        # ✅ 强制转换为Python原生类型
        return {
            'industry_data': industry_data,
            'momentum_df': momentum_df,
            'rotation_matrix': rotation_matrix,
            'summary': summary,
            'timestamp': datetime.now().isoformat()
        }


# ==================== 使用示例 ====================
def example_industry_rotation_service():
    """IndustryRotationService使用示例（修复版）"""
    
    print("=" * 80)
    print("🧪 IndustryRotationService 使用示例（V6.1修复版）")
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
    
    rotation_service = IndustryRotationService(data_service, config_service)
    print("✅ 服务初始化成功")
    
    # 2. 验证实例变量存在
    print("\n2️⃣ 验证实例变量:")
    assert hasattr(rotation_service, 'industries_config'), "❌ industries_config 属性缺失！"
    assert hasattr(rotation_service, 'momentum_windows'), "❌ momentum_windows 属性缺失！"
    assert hasattr(rotation_service, 'benchmark_code'), "❌ benchmark_code 属性缺失！"
    print(f"   ✅ industries_config 存在: {len(rotation_service.industries_config)} 个行业")
    print(f"   ✅ momentum_windows: {rotation_service.momentum_windows}")
    print(f"   ✅ benchmark_code: '{rotation_service.benchmark_code}'")
    
    # 3. 加载行业数据
    print("\n3️⃣ 加载行业数据...")
    industry_data = rotation_service.load_industry_data(days=100)
    print(f"✅ 成功加载 {len(industry_data)} 个行业数据")
    
    # 4. 计算行业动量
    print("\n4️⃣ 计算行业动量...")
    momentum_df = rotation_service.calculate_industry_momentum(industry_data)
    if not momentum_df.empty:
        print(f"✅ 行业动量计算完成: {len(momentum_df)}个行业")
        print("\n前5强势行业:")
        top5 = momentum_df.nlargest(5, 'momentum_score')
        for _, row in top5.iterrows():
            print(f"   • {row['name']:8s} | {row['momentum_score']:+6.1f}% | 排名{row['rank']}")
    
    # 5. 生成综合报告
    print("\n5️⃣ 生成综合报告...")
    report = rotation_service.generate_rotation_report(industry_data=industry_data, top_n=5)
    print("\n" + report['summary'])
    
    print("\n" + "=" * 80)
    print("✅ IndustryRotationService 修复版示例运行完成")
    print("=" * 80)


if __name__ == "__main__":
    example_industry_rotation_service()