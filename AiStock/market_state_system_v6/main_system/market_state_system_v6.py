# ==================== 5.1 主系统 （系统入口：服务协调 + 数据聚合） MarketStateSystemV6_0 ====================
# market_state_system_v6_fixed.py
import pandas as pd
from typing import Dict, Optional
import logging
from datetime import datetime

from infrastructure.base_services.config_service import ConfigService
from infrastructure.data_service.data_loading_service import DataLoadingService
from services.core_services.market_state_service import MarketStateService
from services.core_services.risk_assessment_service import RiskAssessmentService
from services.core_services.allocation_service import AllocationService
from services.core_services.sentiment_analysis_service import SentimentAnalysisService
from services.core_services.commodity_engine_service import CommodityEngineService
from services.core_services.macro_analysis_service import MacroAnalysisService
from services.core_services.option_pcr_service import OptionPCRService
from services.supplementary_services.cross_market_service import CrossMarketService
from services.supplementary_services.industry_rotation_service import IndustryRotationService
from services.supplementary_services.futures_analysis_service import FuturesAnalysisService
from services.visualization_service.visualization_service import VisualizationService
from utils.data_context_preparation import prepare_visualization_data_context

logger = logging.getLogger(__name__)

class MarketStateSystemV6_0:
    """V6.0主系统（修复版：消除属性归属混乱）"""
    
    def __init__(self, config_path: str = 'system_config_v6.yaml'):
        """初始化系统（修复版）"""
        self.config = ConfigService(config_path)
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
        self.cross_market_service = CrossMarketService(self.data_service, self.config)
        self.rotation_service = IndustryRotationService(self.data_service, self.config)
        self.futures_service = FuturesAnalysisService(self.data_service, self.config)
        self.visualizer = VisualizationService({
            'chinese_font': "Microsoft YaHei, SimHei, sans-serif",
            'export_path': './reports/v6_visualization/'
        })
        
        # ✅ 修复：业务数据归属本类（非DataManager）
        self.benchmark_data: Dict[str, pd.DataFrame] = {}  # 市值基准数据
        self.micro_redundancy_data: Dict[str, pd.DataFrame] = {}  # 微盘冗余数据
        self.micro_liquidity_status: Optional[Dict] = None  # 微盘状态
        
        self.logger.info("=" * 80)
        self.logger.info("🚀 V6.0微服务化系统初始化成功")
        self.logger.info("✅ 所有服务独立运行，无循环依赖")
        self.logger.info("✅ 业务数据归属主系统，服务仅提供计算能力")
        self.logger.info("=" * 80)
        
        # 预加载数据
        self._preload_data()

        # ✅ 新增：初始化ThresholdService（可选）
        try:
            from services.threshold_service.threshold_service import ThresholdService
            self.threshold_service = ThresholdService(
                config_service=self.config_service,
                data_service=self.data_service
            )
            logger.info("✅ ThresholdService初始化成功")
        except Exception as e:
            self.threshold_service = None
            logger.warning(f"⚠️ ThresholdService初始化失败（降级到静态阈值）: {str(e)}")
        
        # 传递给需要的服务（可选依赖）
        self.risk_service = RiskAssessmentService(
            data_service=self.data_service,
            config_service=self.config_service,
            threshold_service=self.threshold_service  # ✅ 传递（非强制）
        )    
    def _preload_data(self):
        """预加载数据（修复版：数据加载到self.benchmark_data）"""
        self.logger.info("🔄 预加载基准数据...")
        
        # 加载市值基准
        for size, config in self.config.config['market_benchmarks'].items():
            code = config['code']
            df = self.data_service.load_index_data(code, min_days=500)
            if len(df) > 0:
                self.benchmark_data[size] = df  # ✅ 归属本类
                self.logger.info(f"✅ 加载{size}({code})数据: {len(df)}条")
        
        # 加载微盘冗余数据
        for role, code in self.config.config['micro_redundancy'].items():
            if role in ['primary', 'secondary']:
                df = self.data_service.load_index_data(code, min_days=500)
                if len(df) > 0:
                    self.micro_redundancy_data[role] = df  # ✅ 归属本类
        
        # 评估微盘流动性
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
        self.logger.info(f"📅 运行基准日: {self.config.config.get('base_date', datetime.now().strftime('%Y-%m-%d'))}")
        self.logger.info("✅ V6.0系统运行中（微服务架构）")
        self.logger.info("=" * 80)
        
        # 1. 判定市场状态（修复：传递self.benchmark_data）
        market_state, val_score, trend_score, diagnosis = \
            self.market_state_service.determine_market_state(self.benchmark_data)
        
        # ⭐ 强制转换为Python float
        val_score = float(val_score)
        trend_score = float(trend_score)
        
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
        
        # 3. 生成可视化data_context
        data_context = prepare_visualization_data_context(
            market_state_service=self.market_state_service,
            risk_service=self.risk_service,
            allocation_service=self.allocation_service,
            sentiment_service=self.sentiment_service,
            commodity_service=self.commodity_service,
            macro_service=self.macro_service,
            pcr_service=self.pcr_service,
            cross_market_service=self.cross_market_service,
            rotation_service=self.rotation_service,
            futures_service=self.futures_service,
            data_service=self.data_service,
            config_service=self.config
        )
        
        # 4. 生成18大图表
        charts = self.visualizer.generate_all_charts(data_context)
        
        # 5. 导出HTML报告
        output_path = self.visualizer.export_charts_to_html(
            charts,
            output_path=f'./reports/visualization_report_{datetime.now().strftime("%Y%m%d_%H%M%S")}.html'
        )
        
        if output_path:
            self.logger.info(f"\n✅ 可视化报告已导出至: {output_path}")
        
        return {
            'market_state': market_state,
            'valuation_score': val_score,
            'trend_score': trend_score,
            'micro_liquidity': self.micro_liquidity_status,
            'allocation': allocation_df,
            'charts': charts,
            'report_path': output_path,
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }