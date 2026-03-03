# ==================== 4.2.3 期货分析服务 （期货分析：商品期限 + 股指基差）FuturesAnalysisService ====================
# futures_analysis_service_v6.py
"""
V6.0 期货分析服务（完全独立微服务，扩展版）
职责：
1. 商品期货期限结构分析（Contango/Backwardation）
2. 股指期货基差分析（IF/IH/IC/IM）
3. 期货情绪信号生成
4. 期限结构产业景气度评估
5. 期货-现货联动分析
依赖：
- 仅依赖DataLoadingService（无业务服务依赖）
- 所有数据通过参数传递（无内部状态）
修复点：
✅ 完整数据验证与空数据处理
✅ 强制转换为Python原生类型（避免Plotly序列化错误）
✅ 商品+股指期货统一接口
✅ 100%容错处理（任一合约数据缺失不影响其他）
"""
import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Tuple
from datetime import datetime
import warnings
import logging

warnings.filterwarnings('ignore')
logger = logging.getLogger(__name__)


class FuturesAnalysisService:
    """V6.0 期货分析服务（微服务化重构版，扩展股指期货）"""
    
    def __init__(self, data_service, config: Optional[Dict] = None):
        """
        初始化期货分析服务
        
        参数:
            data_service: DataLoadingService实例
            config: 可选配置字典
                {
                    'chinese_font': str,
                    'commodity_contracts': Dict,  # 商品合约配置
                    'index_futures_contracts': Dict,  # 股指期货合约配置
                    'basis_threshold': Dict  # 基差阈值
                }
        """
        self.data_service = data_service
        self.config = {
            'chinese_font': "Microsoft YaHei, SimHei, sans-serif",
            'commodity_contracts': {
                'copper': ('CU2603', 'CU2606', 30),
                'aluminum': ('AL2603', 'AL2606', 30),
                'lithium': ('LC2603', 'LC2606', 66),
                'silicon': ('SI2603', 'SI2606', 66),
                'crude': ('SC2603', 'SC2606', 30),
                'rebar': ('RB2603', 'RB2606', 30),
                'gold': ('AU2603', 'AU2606', 30),
                'soybean': ('M2603', 'M2605', 29)
            },
            'index_futures_contracts': {
                'if': ('IFL8', '000300', 47),  # 沪深300
                'ih': ('IHL8', '000016', 47),  # 上证50
                'ic': ('ICL8', '000905', 47),  # 中证500
                'im': ('IML8', '000852', 47)   # 中证1000
            },
            'basis_threshold': {
                'warning': -1.5,
                'extreme': -2.0
            }
        }
        
        if config:
            self.config.update(config)
        
        self.logger = logger
        self.logger.info("✅ 期货分析服务初始化成功（含商品+股指）")
    
    # ==================== 商品期货分析 ====================
    
    def calculate_commodity_term_structure(
        self,
        commodity_contracts: Optional[Dict] = None
    ) -> Dict[str, Dict]:
        """
        计算商品期货期限结构
        
        参数:
            commodity_contracts: 商品合约配置（None=使用配置）
                {
                    'copper': ('near_code', 'far_code', market_code),
                    ...
                }
        
        返回:
            {
                'copper': {
                    'spread': float,          # 价差(%)
                    'structure': 'backwardation'/'contango',
                    'signal': str,            # 信号描述
                    'near_price': float,
                    'far_price': float,
                    'near_code': str,
                    'far_code': str
                },
                ...
            }
        """
        contracts = commodity_contracts or self.config['commodity_contracts']
        term_structure = {}
        
        for key, (near_code, far_code, market_code) in contracts.items():
            try:
                # 1. 加载数据
                near_df = self.data_service.load_derivative_data(near_code, market_code, days=20)
                far_df = self.data_service.load_derivative_data(far_code, market_code, days=20)
                
                # 2. 计算价差
                if len(near_df) > 0 and len(far_df) > 0 and far_df['close'].iloc[-1] > 0:
                    near_price = near_df['close'].iloc[-1]
                    far_price = far_df['close'].iloc[-1]
                    spread = ((near_price - far_price) / far_price) * 100
                    
                    # 3. 判断结构
                    structure = 'backwardation' if spread > 0 else 'contango'
                    signal = '供应紧张/景气' if spread > 0 else '供应充足/疲软'
                    
                    term_structure[key] = {
                        'spread': round(float(spread), 2),  # ⭐ 强制转换
                        'structure': structure,
                        'signal': signal,
                        'near_price': float(near_price),
                        'far_price': float(far_price),
                        'near_code': near_code,
                        'far_code': far_code
                    }
                    self.logger.debug(f"✅ {key}: {spread:+.1f}% ({structure})")
                else:
                    self.logger.warning(f"⚠️ {key} 数据不足或无效")
            
            except Exception as e:
                self.logger.warning(f"⚠️ {key} 期限结构计算失败: {str(e)[:50]}")
                continue
        
        self.logger.info(f"✅ 商品期限结构计算完成: {len(term_structure)}个品种")
        return term_structure
    
    # ==================== 股指期货基差分析（V6.0新增） ====================
    
    def calculate_index_futures_basis(
        self,
        index_futures_contracts: Optional[Dict] = None
    ) -> Dict[str, Dict]:
        """
        V6.0核心新增：计算股指期货基差
        
        参数:
            index_futures_contracts: 股指期货合约配置（None=使用配置）
                {
                    'if': ('futures_code', 'spot_code', market_code),
                    ...
                }
        
        返回:
            {
                'if': {
                    'futures_price': float,     # 期货价格
                    'spot_price': float,        # 现货价格
                    'basis': float,             # 基差(绝对值)
                    'basis_pct': float,         # 基差(%)
                    'signal': str,              # 信号描述
                    'futures_code': str,
                    'spot_code': str
                },
                ...
            }
        """
        contracts = index_futures_contracts or self.config['index_futures_contracts']
        basis_results = {}
        
        warning_threshold = self.config['basis_threshold']['warning']
        extreme_threshold = self.config['basis_threshold']['extreme']
        
        for key, (futures_code, spot_code, market_code) in contracts.items():
            try:
                # 1. 加载期货数据
                futures_df = self.data_service.load_derivative_data(futures_code, market_code, days=20)
                
                # 2. 加载现货指数数据
                spot_df = self.data_service.load_index_data(spot_code, min_days=20)
                
                # 3. 计算基差
                if len(futures_df) > 0 and len(spot_df) > 0:
                    futures_price = futures_df['close'].iloc[-1]
                    spot_price = spot_df['close'].iloc[-1]
                    
                    if spot_price > 0:
                        basis = futures_price - spot_price
                        basis_pct = (basis / spot_price) * 100
                        
                        # 4. 生成信号
                        if basis_pct < extreme_threshold:
                            signal = '🔴 深度贴水（极度悲观）'
                        elif basis_pct < warning_threshold:
                            signal = '🟠 贴水（谨慎）'
                        elif basis_pct > 0:
                            signal = '🟢 升水（乐观）'
                        else:
                            signal = '⚪ 平水（中性）'
                        
                        basis_results[key] = {
                            'futures_price': float(futures_price),
                            'spot_price': float(spot_price),
                            'basis': float(basis),
                            'basis_pct': float(basis_pct),
                            'signal': signal,
                            'futures_code': futures_code,
                            'spot_code': spot_code,
                            'description': self._get_futures_description(key)
                        }
                        self.logger.debug(f"✅ {key.upper()}: 基差{basis_pct:+.1f}% {signal}")
                    else:
                        self.logger.warning(f"⚠️ {key} 现货价格无效")
                else:
                    self.logger.warning(f"⚠️ {key} 数据不足")
            
            except Exception as e:
                self.logger.warning(f"⚠️ {key} 基差计算失败: {str(e)[:50]}")
                continue
        
        self.logger.info(f"✅ 股指期货基差计算完成: {len(basis_results)}个品种")
        return basis_results
    
    def _get_futures_description(self, futures_key: str) -> str:
        """获取期货品种描述"""
        descriptions = {
            'if': '沪深300股指期货（大盘蓝筹）',
            'ih': '上证50股指期货（超大蓝筹）',
            'ic': '中证500股指期货（中盘成长）',
            'im': '中证1000股指期货（小盘成长）'
        }
        return descriptions.get(futures_key, futures_key.upper())
    
    # ==================== 综合分析 ====================
    
    def calculate_industry_sentiment_from_term_structure(
        self,
        term_structure: Dict[str, Dict]
    ) -> Dict[str, float]:
        """
        基于期限结构计算产业景气度评分
        
        参数:
            term_structure: 期限结构数据（来自calculate_commodity_term_structure）
        
        返回:
            {
                '高端制造': 65.0,
                '新能源': 72.0,
                ...
            }
        """
        # 商品到战略方向的映射
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
        direction_sentiment = {
            '高端制造': 50.0,
            '信息技术': 50.0,
            '新能源': 50.0,
            '生物健康': 50.0,
            '供应链': 50.0,
            '现代农业': 50.0,
            '公用事业': 50.0,
            '传统升级': 50.0,
            '文化消费': 50.0
        }
        
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
            
            # 更新关联方向的评分（加权平均）
            for direction in commodity_to_direction[commodity]:
                if direction in direction_sentiment:
                    # 70%保留原评分 + 30%新评分
                    direction_sentiment[direction] = (
                        direction_sentiment[direction] * 0.7 +
                        sentiment_score * 0.3
                    )
        
        # 强制转换为Python float
        return {k: float(v) for k, v in direction_sentiment.items()}
    
    def generate_futures_report(
        self,
        commodity_contracts: Optional[Dict] = None,
        index_futures_contracts: Optional[Dict] = None
    ) -> Dict:
        """
        生成期货综合分析报告
        
        参数:
            commodity_contracts: 商品合约配置
            index_futures_contracts: 股指期货合约配置
        
        返回:
            {
                'commodity_term_structure': Dict,
                'index_futures_basis': Dict,
                'industry_sentiment': Dict,
                'summary': str,
                'timestamp': str
            }
        """
        # 1. 计算商品期限结构
        commodity_term_structure = self.calculate_commodity_term_structure(commodity_contracts)
        
        # 2. 计算股指期货基差（V6.0新增）
        index_futures_basis = self.calculate_index_futures_basis(index_futures_contracts)
        
        # 3. 计算产业景气度
        industry_sentiment = self.calculate_industry_sentiment_from_term_structure(commodity_term_structure)
        
        # 4. 生成摘要
        summary_lines = []
        summary_lines.append("📊 期货市场综合分析报告")
        summary_lines.append("=" * 50)
        
        # 商品期限结构摘要
        if commodity_term_structure:
            summary_lines.append("\n🛢️ 商品期货期限结构:")
            backwardation_count = sum(1 for v in commodity_term_structure.values() if v['structure'] == 'backwardation')
            contango_count = len(commodity_term_structure) - backwardation_count
            summary_lines.append(f"  • Backwardation(供应紧张): {backwardation_count}个")
            summary_lines.append(f"  • Contango(供应充足): {contango_count}个")
            
            # 显示具体品种
            for key, data in list(commodity_term_structure.items())[:3]:
                summary_lines.append(f"    - {key}: {data['spread']:+.1f}% ({data['signal']})")
        
        # 股指期货基差摘要（V6.0新增）
        if index_futures_basis:
            summary_lines.append("\n📈 股指期货基差分析:")
            for key, data in index_futures_basis.items():
                summary_lines.append(f"  • {data['description']}: {data['basis_pct']:+.1f}% {data['signal']}")
        
        # 产业景气度摘要
        if industry_sentiment:
            summary_lines.append("\n🏭 产业景气度评分（前3）:")
            top3 = sorted(industry_sentiment.items(), key=lambda x: x[1], reverse=True)[:3]
            for direction, score in top3:
                status = '🟢 景气' if score > 65 else ('🟡 稳健' if score > 50 else '🔴 疲软')
                summary_lines.append(f"  • {direction}: {score:.0f}分 {status}")
        
        summary_lines.append("=" * 50)
        summary = "\n".join(summary_lines)
        
        return {
            'commodity_term_structure': commodity_term_structure,
            'index_futures_basis': index_futures_basis,
            'industry_sentiment': industry_sentiment,
            'summary': summary,
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }


# ==================== 使用示例 ====================
def example_futures_analysis_service():
    """期货分析服务使用示例"""
    
    print("=" * 80)
    print("🧪 FuturesAnalysisService 使用示例（含股指期货基差）")
    print("=" * 80)
    
    # 1. 初始化服务（简化版）
    print("\n1️⃣ 初始化期货分析服务...")
    
    class MockDataLoadingService:
        def load_derivative_data(self, code, market_code, days):
            dates = pd.date_range(end=datetime.now(), periods=days)
            # 模拟期货价格（近月略高于远月=Backwardation）
            base_price = 100 + np.random.randn() * 10
            if 'near' in code.lower() or '2603' in code:
                prices = np.random.randn(days).cumsum() + base_price + 1
            else:
                prices = np.random.randn(days).cumsum() + base_price
            return pd.DataFrame({
                'datetime': dates,
                'close': prices
            })
        
        def load_index_data(self, code, min_days):
            dates = pd.date_range(end=datetime.now(), periods=min_days)
            return pd.DataFrame({
                'datetime': dates,
                'close': np.random.randn(min_days).cumsum() + 100
            })
    
    data_service = MockDataLoadingService()
    futures_service = FuturesAnalysisService(data_service)
    
    # 2. 计算商品期限结构
    print("\n2️⃣ 计算商品期限结构...")
    commodity_term_structure = futures_service.calculate_commodity_term_structure()
    if commodity_term_structure:
        print(f"✅ 检测到 {len(commodity_term_structure)} 个商品期限结构")
        for key, data in list(commodity_term_structure.items())[:3]:
            print(f"   • {key:10s}: {data['spread']:+6.1f}% | {data['structure']:15s} | {data['signal']}")
    
    # 3. 计算股指期货基差（V6.0新增）
    print("\n3️⃣ 计算股指期货基差（V6.0新增）...")
    index_futures_basis = futures_service.calculate_index_futures_basis()
    if index_futures_basis:
        print(f"✅ 检测到 {len(index_futures_basis)} 个股指期货基差")
        for key, data in index_futures_basis.items():
            print(f"   • {data['description']:25s}: {data['basis_pct']:+6.1f}% {data['signal']}")
    
    # 4. 计算产业景气度
    print("\n4️⃣ 计算产业景气度...")
    industry_sentiment = futures_service.calculate_industry_sentiment_from_term_structure(commodity_term_structure)
    if industry_sentiment:
        print(f"✅ 评估 {len(industry_sentiment)} 个产业景气度")
        top3 = sorted(industry_sentiment.items(), key=lambda x: x[1], reverse=True)[:3]
        for direction, score in top3:
            status = '🟢' if score > 65 else ('🟡' if score > 50 else '🔴')
            print(f"   • {direction:8s}: {score:5.1f}分 {status}")
    
    # 5. 生成综合报告
    print("\n5️⃣ 生成综合报告...")
    report = futures_service.generate_futures_report()
    print("\n" + report['summary'])
    
    print("\n" + "=" * 80)
    print("✅ FuturesAnalysisService 示例运行完成")
    print("=" * 80)


if __name__ == "__main__":
    example_futures_analysis_service()