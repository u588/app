"""
V6.1 期货分析服务（完全独立微服务）
核心特性：
✅ 阈值动态化集成（ThresholdService）
✅ 配置统一提取（config_utils.extract_and_validate_config）
✅ 商品期限结构分析（Contango/Backwardation）
✅ 股指期货基差分析（IF/IH/IC/IM）
✅ 产业景气度评估（基于期限结构）
✅ 完整降级策略（阈值服务失效时回退静态阈值）
✅ 所有数值强制Python原生float（防Plotly序列化错误）
修复点：
✅ 从config安全获取期货配置（commodity_contracts/index_futures_contracts/basis_threshold）
✅ 动态阈值获取（优先ThresholdService，回退静态配置）
✅ 商品期限结构完整实现（近月/远月价差+结构判定）
✅ 股指基差完整实现（期货-现货价差+信号生成）
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


class FuturesAnalysisService:
    """V6.1 期货分析服务（阈值动态化 + 配置统一化）"""
    
    def __init__(self, data_service, config_service, threshold_service=None):
        """
        初始化期货分析服务
        
        参数:
            data_service: DataLoadingService实例（用于加载期货数据）
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
                'commodity_contracts',
                'index_futures_contracts',
                'risk_thresholds'
            ],
            logger=self.logger,
            service_name='FuturesAnalysisService'
        )
        
        # ✅ 保存ThresholdService引用（可选）
        self.threshold_service = threshold_service
        
        # 验证配置完整性
        if is_valid:
            self.logger.info("✅ FuturesAnalysisService初始化成功（配置完整）")
            self.logger.debug(
                f"   • 商品合约: {len(self.config.get('commodity_contracts', {}))}个 | "
                f"股指期货: {len(self.config.get('index_futures_contracts', {}))}个 | "
                f"基差阈值: 已加载"
            )
        else:
            self.logger.warning(f"⚠️ FuturesAnalysisService初始化完成（缺失{len(missing_keys)}项配置）")
    
    # ==================== 核心方法：商品期限结构分析 ====================
    
    def calculate_commodity_term_structure(
        self,
        commodity_contracts: Optional[Dict] = None
    ) -> Dict[str, Dict]:
        """
        V6.1核心：计算商品期货期限结构
        
        参数:
            commodity_contracts: 商品合约配置（None=使用配置）
                {
                    'copper': ('CU2603', 'CU2606', 30),
                    'aluminum': ('AL2603', 'AL2606', 30),
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
        
        修复点:
        ✅ 完整商品合约配置（从config获取）
        ✅ 所有数值强制Python原生float
        ✅ 完整异常处理与降级
        ✅ 详细日志记录
        """
        contracts = commodity_contracts or safe_config_get(
            self.config,
            ['commodity_contracts'],
            default={
                'copper': ('CU2603', 'CU2606', 30),
                'aluminum': ('AL2603', 'AL2606', 30),
                'lithium': ('LC2603', 'LC2606', 66),
                'silicon': ('SI2603', 'SI2606', 66),
                'crude': ('SC2603', 'SC2606', 30),
                'rebar': ('RB2603', 'RB2606', 30),
                'gold': ('AU2603', 'AU2606', 30),
                'soybean': ('M2603', 'M2605', 29)
            },
            logger=self.logger
        )
        
        term_structure = {}
        
        for key, (near_code, far_code, market_code) in contracts.items():
            try:
                # 1. 加载近月合约数据
                near_df = self.data_service.load_derivative_data(near_code, market_code, days=20)
                
                # 2. 加载远月合约数据
                far_df = self.data_service.load_derivative_data(far_code, market_code, days=20)
                
                # 3. 计算价差
                if len(near_df) > 0 and len(far_df) > 0 and far_df['close'].iloc[-1] > 0:
                    near_price = near_df['close'].iloc[-1]
                    far_price = far_df['close'].iloc[-1]
                    spread = ((near_price - far_price) / far_price) * 100
                    
                    # 4. 判定期限结构
                    structure = 'backwardation' if spread > 0 else 'contango'
                    signal = '供应紧张/景气' if spread > 0 else '供应充足/疲软'
                    
                    # 5. 构建结果（强制Python原生类型）
                    term_structure[key] = {
                        'spread': round(float(spread), 2),
                        'structure': structure,
                        'signal': signal,
                        'near_price': float(near_price),
                        'far_price': float(far_price),
                        'near_code': near_code,
                        'far_code': far_code
                    }
                    
                    self.logger.debug(
                        f"✅ {key}: 价差{spread:+.1f}% ({structure}) | "
                        f"近月={near_price:.1f} | 远月={far_price:.1f}"
                    )
                else:
                    self.logger.debug(f"⚠️ {key} 期限结构数据不足或无效")
            
            except Exception as e:
                self.logger.warning(f"⚠️ {key} 期限结构计算失败: {str(e)[:30]}")
                continue
        
        self.logger.info(f"✅ 计算商品期限结构：{len(term_structure)}个品种")
        return term_structure
    
    # ==================== 核心方法：股指期货基差分析（V6.0新增） ====================
    
    def calculate_index_futures_basis(
        self,
        index_futures_contracts: Optional[Dict] = None
    ) -> Dict[str, Dict]:
        """
        V6.1核心：计算股指期货基差（IF/IH/IC/IM）
        
        参数:
            index_futures_contracts: 股指期货合约配置（None=使用配置）
                {
                    'if': ('IFL8', '000300', 47),  # 沪深300
                    'ih': ('IHL8', '000016', 47),  # 上证50
                    'ic': ('ICL8', '000905', 47),  # 中证500
                    'im': ('IML8', '000852', 47)   # 中证1000
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
                    'spot_code': str,
                    'description': str
                },
                ...
            }
        
        修复点:
        ✅ 完整股指期货配置（从config获取）
        ✅ 动态阈值获取（基差预警/极端阈值）
        ✅ 所有数值强制Python原生float
        ✅ 完整异常处理与降级
        ✅ 详细日志记录
        """
        contracts = index_futures_contracts or safe_config_get(
            self.config,
            ['index_futures_contracts'],
            default={
                'if': ['IFL8', '000300', 47],  # 沪深300
                'ih': ['IHL8', '000016', 47],  # 上证50
                'ic': ['ICL8', '000905', 47],  # 中证500
                'im': ['IML8', '000852', 47]   # 中证1000
            },
            logger=self.logger
        )
        
        basis_results = {}
        
        # ✅ V6.1核心：动态获取基差阈值（优先ThresholdService）
        warning_threshold = self._get_dynamic_basis_threshold('warning')
        extreme_threshold = self._get_dynamic_basis_threshold('extreme')
        
        for key, contract in contracts.items():
        # for key, (futures_code, spot_code, market_code) in contracts.items():
            try:
                # ✅ 修复1：增强配置解析容错
                if isinstance(contract, (list, tuple)) and len(contract) == 3:
                    futures_code, spot_code, market_code = contract
                else:
                    self.logger.warning(f"⚠️ 合约配置格式错误 {key}: {contract}")
                    continue
                
                # ✅ 修复2：加载数据并严格验证类型
                futures_df = self.data_service.load_derivative_data(futures_code, market_code, days=20)
                spot_df = self.data_service.load_index_data(spot_code, min_days=20)
                
                # 严格验证：必须是DataFrame且有数据
                if not isinstance(futures_df, pd.DataFrame) or len(futures_df) == 0:
                    self.logger.warning(f"⚠️ {key} 期货数据无效（非DataFrame或空）: {type(futures_df)}")
                    continue
                
                if not isinstance(spot_df, pd.DataFrame) or len(spot_df) == 0:
                    self.logger.warning(f"⚠️ {key} 现货数据无效（非DataFrame或空）: {type(spot_df)}")
                    continue
                
                # ✅ 修复3：安全访问列（避免KeyError）
                if 'close' not in futures_df.columns or 'close' not in spot_df.columns:
                    self.logger.warning(f"⚠️ {key} 缺少close列 | 期货列: {list(futures_df.columns)} | 现货列: {list(spot_df.columns)}")
                    continue
                # 3. 计算基差
                if len(futures_df) > 0 and len(spot_df) > 0:
                    futures_price = futures_df['close'].iloc[-1]
                    spot_price = spot_df['close'].iloc[-1]
                    
                    if spot_price > 0:
                        basis = futures_price - spot_price
                        basis_pct = (basis / spot_price) * 100
                        
                        # 4. 生成信号（使用动态阈值）
                        if basis_pct < extreme_threshold:
                            signal = '🔴 深度贴水（极度悲观）'
                        elif basis_pct < warning_threshold:
                            signal = '🟠 贴水（谨慎）'
                        elif basis_pct > 0:
                            signal = '🟢 升水（乐观）'
                        else:
                            signal = '⚪ 平水（中性）'
                        
                        # 5. 构建结果（强制Python原生类型）
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
                        
                        self.logger.debug(
                            f"✅ {key.upper()}: 基差{basis_pct:+.1f}% {signal} | "
                            f"期货={futures_price:.1f} 现货={spot_price:.1f}"
                        )
                    else:
                        self.logger.warning(f"⚠️ {key} 现货价格无效（≤0）")
                else:
                    self.logger.warning(f"⚠️ {key} 数据不足")
            
            except Exception as e:
                self.logger.warning(f"⚠️ {key} 基差计算失败: {str(e)[:30]}")
                continue
        
        self.logger.info(f"✅ 股指期货基差计算完成: {len(basis_results)}个品种")
        return basis_results
    
    # ==================== 辅助方法：动态基差阈值获取 ====================
    
    def _get_dynamic_basis_threshold(self, threshold_type: str) -> float:
        """
        V6.1核心：动态获取基差阈值
        
        参数:
            threshold_type: 阈值类型（'warning'/'extreme'）
        
        返回:
            基差阈值（float，负值表示贴水）
        """
        # ✅ V6.1核心：动态获取阈值（优先ThresholdService）
        if self.threshold_service:
            try:
                threshold_name = f"futures_basis_{threshold_type}_threshold"
                threshold_value = self.threshold_service.get_threshold(
                    threshold_name,
                    context={'threshold_type': threshold_type},
                    strategy='static'
                )
                
                self.logger.debug(
                    f"🔄 动态基差阈值 | {threshold_type} = {threshold_value:.1f}% | "
                    f"策略=static"
                )
                return float(threshold_value)
                
            except Exception as e:
                self.logger.warning(
                    f"⚠️ 动态基差阈值获取失败，回退静态配置: {str(e)[:30]}"
                )
        
        # 降级：使用静态配置阈值
        basis_threshold = safe_config_get(
            self.config,
            ['risk_thresholds', 'basis'],
            default={'warning': -1.5, 'extreme': -2.0},
            logger=self.logger
        )
        
        if threshold_type == 'warning':
            return float(basis_threshold.get('warning', -1.5))
        else:
            return float(basis_threshold.get('extreme', -2.0))
    
    # ==================== 辅助方法：期货品种描述 ====================
    
    def _get_futures_description(self, futures_key: str) -> str:
        """获取期货品种描述"""
        descriptions = {
            'if': '沪深300股指期货（大盘蓝筹）',
            'ih': '上证50股指期货（超大蓝筹）',
            'ic': '中证500股指期货（中盘成长）',
            'im': '中证1000股指期货（小盘成长）'
        }
        return descriptions.get(futures_key, futures_key.upper())
    
    # ==================== 核心方法：产业景气度评估 ====================
    
    def calculate_industry_sentiment_from_term_structure(
        self,
        term_structure: Dict[str, Dict]
    ) -> Dict[str, float]:
        """
        V6.1核心：基于期限结构计算产业景气度评分
        
        参数:
            term_structure: 期限结构数据（来自calculate_commodity_term_structure）
        
        返回:
            {'高端制造': 65.0, '新能源': 72.0, ...}  # 评分0-100
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
        
        # 初始化方向评分（默认50分）
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
        
        # ✅ 强制转换为Python原生float（关键修复：防Plotly序列化错误）
        return {k: float(v) for k, v in direction_sentiment.items()}
    
    # ==================== 核心方法：生成期货综合报告 ====================
    
    def generate_futures_report(
        self,
        commodity_contracts: Optional[Dict] = None,
        index_futures_contracts: Optional[Dict] = None
    ) -> Dict:
        """
        V6.1核心：生成期货综合分析报告
        
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
        
        修复点:
        ✅ 完整数据流（期限结构→基差→产业景气度→报告）
        ✅ 详细摘要生成
        ✅ 强制Python原生类型
        ✅ 详细日志记录
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
        
        # ✅ 强制转换为Python原生类型（关键修复：防Plotly序列化错误）
        return {
            'commodity_term_structure': commodity_term_structure,
            'index_futures_basis': index_futures_basis,
            'industry_sentiment': industry_sentiment,
            'summary': summary,
            'timestamp': datetime.now().isoformat()
        }
    
    # ==================== 高级功能：期货趋势数据 ====================
    
    def generate_futures_trend_data(
        self,
        term_structure: Dict,
        basis_data: Dict,
        days: int = 90
    ) -> Dict[str, Any]:
        """
        生成期货趋势图表数据（用于可视化）
        
        返回:
            {
                'dates': List[str],
                'commodity_spreads': Dict[str, List[float]],
                'basis_history': Dict[str, List[float]],
                'industry_sentiment_history': Dict[str, List[float]]
            }
        """
        # 模拟历史数据（实际应从数据库获取）
        dates = pd.date_range(end=datetime.now(), periods=days).strftime('%Y-%m-%d').tolist()
        
        # 模拟商品期限结构（随机波动）
        commodity_spreads = {}
        for key, data in term_structure.items():
            base_spread = data['spread']
            spreads = [float(base_spread + np.random.randn() * 2) for _ in range(days)]
            commodity_spreads[key] = spreads
        
        # 模拟基差历史（随机波动）
        basis_history = {}
        for key, data in basis_data.items():
            base_basis = data['basis_pct']
            bases = [float(base_basis + np.random.randn() * 0.5) for _ in range(days)]
            basis_history[key] = bases
        
        # 模拟产业景气度（随机波动）
        industry_sentiment_history = {
            '高端制造': [float(50 + np.random.randn() * 10) for _ in range(days)],
            '新能源': [float(50 + np.random.randn() * 10) for _ in range(days)],
            '信息技术': [float(50 + np.random.randn() * 10) for _ in range(days)],
            '生物健康': [float(50 + np.random.randn() * 10) for _ in range(days)],
            '供应链': [float(50 + np.random.randn() * 10) for _ in range(days)],
            '现代农业': [float(50 + np.random.randn() * 10) for _ in range(days)],
            '公用事业': [float(50 + np.random.randn() * 10) for _ in range(days)],
            '传统升级': [float(50 + np.random.randn() * 10) for _ in range(days)],
            '文化消费': [float(50 + np.random.randn() * 10) for _ in range(days)]
        }
        
        return {
            'dates': dates,
            'commodity_spreads': commodity_spreads,
            'basis_history': basis_history,
            'industry_sentiment_history': industry_sentiment_history,
            'timestamp': datetime.now().isoformat()
        }


# ==================== 使用示例 ====================
def example_futures_analysis_service():
    """FuturesAnalysisService使用示例"""
    
    print("=" * 80)
    print("🧪 FuturesAnalysisService 使用示例（V6.1阈值动态化）")
    print("=" * 80)
    
    # 1. 初始化服务（简化版）
    print("\n1️⃣ 初始化FuturesAnalysisService...")
    
    class MockConfigService:
        def __init__(self):
            self.config = {
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
                    'if': ('IFL8', '000300', 47),
                    'ih': ('IHL8', '000016', 47),
                    'ic': ('ICL8', '000905', 47),
                    'im': ('IML8', '000852', 47)
                },
                'risk_thresholds': {
                    'basis': {
                        'warning': -1.5,
                        'extreme': -2.0
                    }
                }
            }
    
    class MockDataService:
        def load_derivative_data(self, code, market_code, days):
            dates = pd.date_range(end=datetime.now(), periods=days)
            # 模拟期货价格（近月略高于远月=Backwardation）
            base_price = np.random.uniform(50, 100)
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
    
    config_service = MockConfigService()
    data_service = MockDataService()
    
    # 模拟ThresholdService（可选）
    class MockThresholdService:
        def get_threshold(self, name, context, strategy):
            # 模拟动态阈值
            if 'basis_warning' in name:
                return -1.6
            elif 'basis_extreme' in name:
                return -2.2
            return -1.5
    
    threshold_service = MockThresholdService()
    
    futures_service = FuturesAnalysisService(data_service, config_service, threshold_service)
    print("✅ 服务初始化成功")
    
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
    
    # 6. 验证数据类型
    print("\n6️⃣ 验证数据类型（防Plotly序列化错误）:")
    if commodity_term_structure:
        sample_spread = commodity_term_structure['copper']['spread'] if 'copper' in commodity_term_structure else 0.0
        is_python_float = isinstance(sample_spread, float) and not isinstance(sample_spread, np.floating)
        print(f"   ✅ 期限结构价差类型: {type(sample_spread).__name__} | Python float: {is_python_float}")
    
    # 7. 期货趋势数据（模拟）
    print("\n7️⃣ 期货趋势数据（模拟）:")
    trend_data = futures_service.generate_futures_trend_data(commodity_term_structure, index_futures_basis, days=30)
    print(f"   ✅ 数据点: {len(trend_data['dates'])}天")
    print(f"   ✅ 商品数量: {len(trend_data['commodity_spreads'])}个")
    print(f"   ✅ 股指期货: {len(trend_data['basis_history'])}个")
    
    print("\n" + "=" * 80)
    print("✅ FuturesAnalysisService 示例运行完成")
    print("=" * 80)


if __name__ == "__main__":
    example_futures_analysis_service()