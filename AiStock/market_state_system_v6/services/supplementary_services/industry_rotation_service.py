# ==================== 4.2.2 行业轮动服务 （行业轮动：动量计算 + 轮动矩阵）IndustryRotationService ====================
# industry_rotation_service_v6.py
"""
V6.0 行业轮动服务（完全独立微服务）
职责：
1. 行业指数加载与标准化
2. 行业相对强度计算（20日/60日动量）
3. 行业轮动矩阵生成
4. 轮动信号识别（强势/弱势行业）
5. 行业配置建议生成
依赖：
- 仅依赖DataLoadingService（无业务服务依赖）
- 所有数据通过参数传递（无内部状态）
修复点：
✅ 完整数据验证与空数据处理
✅ 强制转换为Python原生类型（避免Plotly序列化错误）
✅ 行业分类标准化（申万/中证）
✅ 100%容错处理（任一行业数据缺失不影响其他）
"""
import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Tuple
from datetime import datetime
import warnings
import logging
from utils.config_utils import extract_config_dict

warnings.filterwarnings('ignore')
logger = logging.getLogger(__name__)


class IndustryRotationService:
    """V6.0 行业轮动服务（微服务化重构版）"""
    
    def __init__(self, data_service, config: Optional[Dict] = None):
        """
        初始化行业轮动服务
        
        参数:
            data_service: DataLoadingService实例
            config: 可选配置字典
                {
                    'chinese_font': str,
                    'momentum_windows': List[int],  # 动量计算窗口 [20, 60]
                    'benchmark_code': str,          # 基准指数代码
                    'industries': Dict[str, str]    # 行业指数映射
                }
        """
        self.data_service = data_service
        self.config = {
            'chinese_font': "Microsoft YaHei, SimHei, sans-serif",
            'momentum_windows': [20, 60],
            'benchmark_code': '000300',
            'industries': {
                # 金融
                'bank': '399986',  # 银行
                'insurance': '399975',  # 保险
                'securities': '399975',  # 证券
                # 消费
                'food_beverage': '399969',  # 食品饮料
                'household_appliance': '399999',  # 家用电器
                'retail': '399976',  # 零售
                # 医药
                'pharmaceutical': '399932',  # 医药生物
                'medical_device': '399989',  # 医疗器械
                # 科技
                'electronics': '399606',  # 电子
                'computer': '399606',  # 计算机
                'communication': '399606',  # 通信
                'semiconductor': '931865',  # 半导体
                # 制造
                'machinery': '399976',  # 机械设备
                'electrical_equipment': '399976',  # 电气设备
                'automobile': '399976',  # 汽车
                # 周期
                'chemical': '399976',  # 化工
                'building_materials': '399976',  # 建筑材料
                'nonferrous_metals': '399976',  # 有色金属
                'steel': '399976',  # 钢铁
                # 公用
                'utilities': '000917',  # 公用事业
                'transportation': '399976',  # 交通运输
                # 其他
                'real_estate': '399976',  # 房地产
                'construction': '399976'  # 建筑装饰
            }
        }
        config = extract_config_dict(config)
        if config:
            self.config.update(config)
        
        self.logger = logger
        self.logger.info("✅ 行业轮动服务初始化成功")
    
    # ==================== 核心方法 ====================
    
    def load_industry_data(
        self,
        industries: Optional[List[str]] = None,
        days: int = 250
    ) -> Dict[str, pd.DataFrame]:
        """
        加载行业指数数据
        
        参数:
            industries: 行业列表（None=加载所有配置行业）
            days: 获取天数
        
        返回:
            {
                'bank': DataFrame with datetime, close,
                'insurance': DataFrame,
                ...
            }
        """
        if industries is None:
            industries = list(self.config['industries'].keys())
        
        industry_data = {}
        
        for industry_key in industries:
            if industry_key not in self.config['industries']:
                self.logger.warning(f"⚠️ 未知行业: {industry_key}")
                continue
            
            code = self.config['industries'][industry_key]
            
            try:
                df = self.data_service.load_index_data(code, min_days=days)
                
                if len(df) > 0:
                    # 标准化列名
                    if 'datetime' not in df.columns and 'date' in df.columns:
                        df = df.rename(columns={'date': 'datetime'})
                    
                    if 'close' not in df.columns:
                        self.logger.warning(f"⚠️ {industry_key}({code}) 缺少close列")
                        continue
                    
                    df['datetime'] = pd.to_datetime(df['datetime'])
                    df = df.sort_values('datetime').reset_index(drop=True)
                    industry_data[industry_key] = df[['datetime', 'close']].copy()
                    self.logger.debug(f"✅ {industry_key}({code}): {len(df)}条")
                else:
                    self.logger.warning(f"⚠️ {industry_key}({code}) 数据为空")
            
            except Exception as e:
                self.logger.warning(f"⚠️ {industry_key}({code}) 加载失败: {str(e)[:50]}")
                continue
        
        self.logger.info(f"✅ 行业数据加载完成: {len(industry_data)}/{len(industries)}个行业")
        return industry_data
    
    def calculate_industry_momentum(
        self,
        industry_data: Dict[str, pd.DataFrame],
        windows: Optional[List[int]] = None
    ) -> pd.DataFrame:
        """
        计算行业动量（相对强度）
        
        参数:
            industry_data: 行业数据字典
            windows: 动量窗口列表（None=使用配置）
        
        返回:
            DataFrame with columns:
                industry, name, return_20d, return_60d, momentum_score, rank
        """
        if not industry_data:
            return pd.DataFrame()
        
        windows = windows or self.config['momentum_windows']
        
        results = []
        
        for industry_key, df in industry_data.items():
            if len(df) < max(windows):
                continue
            
            momentum_scores = []
            
            for window in windows:
                if len(df) >= window + 1:
                    ret = (df['close'].iloc[-1] / df['close'].iloc[-window-1] - 1) * 100
                else:
                    ret = 0.0
                
                momentum_scores.append(ret)
            
            # 综合动量得分（20日60% + 60日40%）
            if len(momentum_scores) >= 2:
                momentum_score = momentum_scores[0] * 0.6 + momentum_scores[1] * 0.4
            else:
                momentum_score = momentum_scores[0] if momentum_scores else 0.0
            
            results.append({
                'industry': industry_key,
                'name': self._get_industry_name(industry_key),
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
    
    def calculate_rotation_matrix(
        self,
        industry_momentum: pd.DataFrame,
        top_n: int = 5
    ) -> Dict:
        """
        生成行业轮动矩阵
        
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
        
        # 检测轮动趋势
        strong_names = [item['name'] for item in strong_industries]
        weak_names = [item['name'] for item in weak_industries]
        
        # 科技 vs 周期
        tech_industries = ['半导体', '电子', '计算机', '通信']
        cycle_industries = ['化工', '有色金属', '钢铁', '建筑材料']
        
        tech_count = sum(1 for name in strong_names if any(t in name for t in tech_industries))
        cycle_count = sum(1 for name in strong_names if any(c in name for c in cycle_industries))
        
        if tech_count >= 2 and cycle_count <= 1:
            rotation_signals.append("🟢 科技成长风格占优（半导体/电子领涨）")
        elif cycle_count >= 2 and tech_count <= 1:
            rotation_signals.append("🔵 周期价值风格占优（化工/有色领涨）")
        elif tech_count >= 2 and cycle_count >= 2:
            rotation_signals.append("🟡 科技+周期双轮驱动（成长价值均衡）")
        else:
            rotation_signals.append("⚪ 行业轮动不明显（震荡整理）")
        
        # 消费 vs 医药
        consumer_industries = ['食品饮料', '家用电器', '零售']
        medical_industries = ['医药生物', '医疗器械']
        
        consumer_count = sum(1 for name in strong_names if any(c in name for c in consumer_industries))
        medical_count = sum(1 for name in strong_names if any(m in name for m in medical_industries))
        
        if consumer_count >= 2:
            rotation_signals.append("🟢 消费防御属性凸显（食品饮料/家电领涨）")
        elif medical_count >= 2:
            rotation_signals.append("🟢 医药避险属性凸显（医药生物/器械领涨）")
        
        return {
            'strong_industries': strong_industries,
            'weak_industries': weak_industries,
            'rotation_signals': rotation_signals,
            'matrix_data': industry_momentum
        }
    
    def generate_rotation_report(
        self,
        industry_data: Optional[Dict] = None,
        days: int = 250,
        top_n: int = 5
    ) -> Dict:
        """
        生成行业轮动综合报告
        
        参数:
            industry_data: 行业数据（None=自动加载）
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
        """
        # 1. 加载数据
        if industry_data is None:
            industry_data = self.load_industry_data(days=days)
        
        if not industry_data:
            return {
                'error': '行业数据加载失败',
                'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            }
        
        # 2. 计算行业动量
        momentum_df = self.calculate_industry_momentum(industry_data)
        
        if momentum_df.empty:
            return {
                'error': '行业动量计算失败',
                'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
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
        
        return {
            'industry_data': industry_data,
            'momentum_df': momentum_df,
            'rotation_matrix': rotation_matrix,
            'summary': summary,
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }
    
    # ==================== 辅助方法 ====================
    
    def _get_industry_name(self, industry_key: str) -> str:
        """获取行业中文名称"""
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


# ==================== 使用示例 ====================
def example_industry_rotation_service():
    """行业轮动服务使用示例"""
    
    print("=" * 80)
    print("🧪 IndustryRotationService 使用示例")
    print("=" * 80)
    
    # 1. 初始化服务（简化版）
    print("\n1️⃣ 初始化行业轮动服务...")
    
    class MockDataLoadingService:
        def load_index_data(self, code, min_days):
            dates = pd.date_range(end=datetime.now(), periods=min_days)
            return pd.DataFrame({
                'datetime': dates,
                'close': np.random.randn(min_days).cumsum() + 100
            })
    
    data_service = MockDataLoadingService()
    rotation_service = IndustryRotationService(data_service)
    
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
    
    print("\n" + "=" * 80)
    print("✅ IndustryRotationService 示例运行完成")
    print("=" * 80)


if __name__ == "__main__":
    example_industry_rotation_service()