# ==================== 5.1 主系统 （系统入口：服务协调 + 数据聚合） MarketStateSystemV6_0 ====================
# market_state_system_v6_fixed.py
import pandas as pd
from typing import Dict, Optional
import logging
from datetime import datetime

from system_config_v6_fixed import SystemConfig
from data_loading_service import DataLoadingService
from market_state_service import MarketStateService
from risk_assessment_service import RiskAssessmentService
from allocation_service import AllocationService
from sentiment_analysis_service import SentimentAnalysisService
from commodity_engine_service import CommodityEngineService
from macro_analysis_service import MacroAnalysisService
from option_pcr_service import OptionPCRService

logger = logging.getLogger(__name__)

class MarketStateSystemV6_0:
    """
    V6.0主系统（修复版：消除属性归属混乱）
    核心原则：
    1. 所有业务数据归属本类（benchmark_data, micro_liquidity_status等）
    2. 服务仅作为工具，不持有业务状态
    3. 通过方法参数传递数据，避免服务间直接访问
    """
    
    def __init__(self, config_path: str = './config/system_config_v6.yaml'):
        """初始化系统（修复版）"""
        self.config = SystemConfig.from_yaml(config_path)
        self.logger = logger
        
        # ✅ 修复：初始化服务（服务不持有业务数据）
        self.data_service = DataLoadingService(self.config)
        self.market_state_service = MarketStateService(self.data_service, self.config)
        self.risk_service = RiskAssessmentService(self.data_service, self.config)
        self.allocation_service = AllocationService(self.config)
        self.sentiment_service = SentimentAnalysisService(self.data_service, self.config)
        self.commodity_service = CommodityEngineService(self.data_service, self.config)
        self.macro_service = MacroAnalysisService(self.data_service, self.config)
        self.pcr_service = OptionPCRService(self.data_service, self.config)
        
        # ✅ 修复：业务数据归属本类（非DataManager）
        self.benchmark_data: Dict[str, pd.DataFrame] = {}
        self.micro_redundancy_data: Dict[str, pd.DataFrame] = {}
        self.micro_liquidity_status: Optional[Dict] = None
        
        self.logger.info("=" * 80)
        self.logger.info("🚀 V6.0微服务化系统初始化成功")
        self.logger.info("✅ 所有服务独立运行，无循环依赖")
        self.logger.info("✅ 业务数据归属主系统，服务仅提供计算能力")
        self.logger.info("=" * 80)
    
    def _preload_data(self):
        """预加载数据（修复版：数据归属本类）"""
        self.logger.info("🔄 预加载基准数据...")
        
        # ✅ 修复：数据加载到self.benchmark_data（非self.data_manager.benchmark_data）
        for size, config in self.config.market_benchmarks.items():
            code = config['code']
            df = self.data_service.load_index_data(code, min_days=500)
            if len(df) > 0:
                self.benchmark_data[size] = df
                self.logger.info(f"✅ 加载{size}({code})数据: {len(df)}条")
        
        # 加载微盘冗余数据
        for role, code in self.config.micro_redundancy.items():
            if role in ['primary', 'secondary']:
                df = self.data_service.load_index_data(code, min_days=500)
                if len(df) > 0:
                    self.micro_redundancy_data[role] = df
        
        # 评估微盘流动性（修复：传递DataFrame，非服务内部持有）
        if 'primary' in self.micro_redundancy_data:
            df_primary = self.micro_redundancy_data['primary']
            df_secondary = self.micro_redundancy_data.get('secondary')
            self.micro_liquidity_status = self.risk_service.assess_micro_liquidity(
                df_primary, df_secondary
            )
            self.logger.info(f"✅ 微盘流动性状态: {self.micro_liquidity_status['stage']}")
    
    def run(self) -> Dict:
        """运行系统（修复版：清晰的数据流）"""
        self.logger.info("\n" + "=" * 80)
        self.logger.info(f"📅 运行基准日: {self.config.base_date or datetime.now().strftime('%Y-%m-%d')}")
        self.logger.info("✅ V6.0系统运行中（微服务架构）")
        self.logger.info("=" * 80)
        
        # 1. 判定市场状态（修复：传递self.benchmark_data）
        market_state, val_score, trend_score, diagnosis = \
            self.market_state_service.determine_market_state(self.benchmark_data)
        self.logger.info(f"🎯 市场状态: {market_state}")
        self.logger.info(f"📊 估值安全边际: {val_score:.1f}/100")
        self.logger.info(f"📈 趋势动能强度: {trend_score:.1f}/100")
        
        if self.micro_liquidity_status:
            self.logger.info(
                f"🔥 微盘熔断阶段: {self.micro_liquidity_status['stage']} "
                f"(持续{self.micro_liquidity_status['days_in_stage']}日)"
            )
        
        # 2. 计算配置（修复：传递必要参数）
        allocation_df = self.allocation_service.calculate_allocation(
            benchmark_data=self.benchmark_data,
            micro_liquidity=self.micro_liquidity_status,
            market_state=market_state
        )
        
        self.logger.info("💼 九大战略方向配置摘要（前5大）:")
        df_no_cash = allocation_df[allocation_df['战略方向'] != '现金'].copy()
        top5 = df_no_cash.nlargest(5, '动态权重')
        for _, row in top5.iterrows():
            self.logger.info(f" • {row['战略方向']:8s} | {row['配置建议']:6s} | {row['核心指数']}")
        
        # 3. 生成预警
        alerts = self._generate_risk_alerts(market_state)
        self.logger.info("⚠️ 风险监控信号:")
        for i, alert in enumerate(alerts[:5], 1):
            self.logger.info(f"  {i}. {alert}")
        
        return {
            'market_state': market_state,
            'valuation_score': val_score,
            'trend_score': trend_score,
            'micro_liquidity': self.micro_liquidity_status,
            'allocation': allocation_df,
            'risk_alerts': alerts,
            'diagnosis': diagnosis
        }
    
    def _generate_risk_alerts(self, market_state: str) -> list:
        """生成风险预警（修复：通过服务调用，非直接访问）"""
        # 1. 获取PCR数据
        pcr_data = self.pcr_service.calculate_composite_pcr()
        pcr_value = pcr_data.get('composite_pcr', 1.0)
        
        # 2. 获取基差数据
        basis_data = self.commodity_service.calculate_futures_basis()
        basis_value = basis_data.get('if_basis', {}).get('percent', 0.0)
        
        # 3. 调用风险服务生成预警
        alerts = self.risk_service.generate_risk_alerts(
            market_state=market_state,
            pcr_value=pcr_value,
            micro_liquidity=self.micro_liquidity_status,
            basis_value=basis_value
        )
        
        return alerts