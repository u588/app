# main_system/market_state_system_v6_1.py
"""
V6.1 主系统（阈值动态化 + 配置统一化）
核心变更：
✅ 初始化ThresholdService并传递给5个核心服务
✅ 所有服务使用extract_and_validate_config统一配置提取
✅ 完整异常处理与降级策略
"""
import pandas as pd
from typing import Dict, Optional
import logging
from datetime import datetime

from infrastructure.base_services.config_service import ConfigService
from infrastructure.base_services.cache_service import CacheService
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
from services.threshold_service.threshold_service import ThresholdService  # ✅ V6.1新增
from utils.data_context_preparation import prepare_visualization_data_context

logger = logging.getLogger(__name__)


class MarketStateSystem:
    """V6.1主系统（阈值动态化 + 配置统一化）"""
    
    def __init__(self, config_path: str = 'config/system_config_v6.yaml'):
        """初始化系统（V6.1增强版）"""
        self.config = ConfigService(config_path)
        self.logger = logger
        
        # ✅ 初始化缓存服务（从配置读取参数）
        cache_config = self.config.config.get('cache', {})
        self.cache_service = CacheService(
            max_size=cache_config.get('max_size', 1000),
            ttl=cache_config.get('ttl', 3600)
        )
        
        # ✅ 初始化数据加载服务
        self.data_service = DataLoadingService(self.config, self.cache_service)
        
        # ✅ V6.1核心：初始化ThresholdService（带降级）
        self.threshold_service = self._init_threshold_service()
        
        # ✅ 初始化所有业务服务（传递threshold_service给需要的服务）
        self._init_business_services()
        
        # ✅ 预加载数据
        self._preload_data()
        
        self.logger.info("=" * 80)
        self.logger.info("🚀 V6.1微服务化系统初始化成功（阈值动态化 + 配置统一化）")
        self.logger.info(f"✅ ThresholdService: {'已启用' if self.threshold_service else '未启用（降级到静态阈值）'}")
        self.logger.info("=" * 80)
    
    def _init_threshold_service(self) -> Optional[ThresholdService]:
        """初始化ThresholdService（带完整降级）"""
        try:
            threshold_service = ThresholdService(
                config_service=self.config,
                data_service=self.data_service
            )
            self.logger.info("✅ ThresholdService初始化成功 | 策略: 动态阈值计算")
            return threshold_service
        except Exception as e:
            self.logger.warning(
                f"⚠️ ThresholdService初始化失败（降级到静态阈值）: {str(e)[:50]}"
            )
            import traceback
            self.logger.debug(traceback.format_exc())
            return None
    
    def _init_business_services(self):
        """初始化所有业务服务（统一配置提取 + ThresholdService传递）"""
        # 核心服务（5个需要ThresholdService）
        self.market_state_service = MarketStateService(
            data_service=self.data_service,
            config_service=self.config,
            threshold_service=self.threshold_service  # ✅ 传递ThresholdService
        )
        
        self.risk_service = RiskAssessmentService(
            data_service=self.data_service,
            config_service=self.config,
            threshold_service=self.threshold_service  # ✅ 传递ThresholdService
        )
        
        self.allocation_service = AllocationService(
            config_service=self.config,
            threshold_service=self.threshold_service  # ✅ 传递ThresholdService
        )
        
        self.pcr_service = OptionPCRService(
            data_service=self.data_service,
            config_service=self.config,
            threshold_service=self.threshold_service  # ✅ 传递ThresholdService
        )
        
        self.macro_service = MacroAnalysisService(
            data_service=self.data_service,
            config_service=self.config,
            threshold_service=self.threshold_service  # ✅ 传递ThresholdService
        )
        
        # 其他服务（7个仅需配置统一）
        self.sentiment_service = SentimentAnalysisService(self.data_service, self.config)
        self.commodity_service = CommodityEngineService(self.data_service, self.config)
        self.cross_market_service = CrossMarketService(self.data_service, self.config)
        self.rotation_service = IndustryRotationService(self.data_service, self.config)
        self.futures_service = FuturesAnalysisService(self.data_service, self.config)
        self.visualizer = VisualizationService({
            'chinese_font': "Microsoft YaHei, SimHei, sans-serif",
            'export_path': './reports/v6_visualization/'
        })
    
    def _preload_data(self):
        """预加载基准数据（修复版：正确保存到 self.benchmark_data）"""
        self.logger.info("🔄 预加载基准数据...")
        
        # ✅ 核心修复1：初始化 benchmark_data 实例变量
        self.benchmark_data = {}
        
        # ✅ 核心修复2：从配置获取市值基准
        market_benchmarks = self.config.config.get('market_benchmarks', {})
        
        # ✅ 核心修复3：加载并保存各层级数据
        for size, config in market_benchmarks.items():
            code = config['code']
            min_days = self.config.config.get('system', {}).get('data_min_days', 500)
            
            try:
                # 加载数据
                df = self.data_service.load_index_data(code, min_days=min_days)
                
                # 验证数据量
                if len(df) >= min_days:
                    # ✅ 核心修复4：保存到实例变量（关键！）
                    self.benchmark_data[size] = df
                    self.logger.info(f"✅ 加载{size}({code})数据: {len(df)}条")
                else:
                    self.logger.warning(f"⚠️ {size}({code}) 数据不足（{len(df)} < {min_days}）")
                    # 降级：仍保存但标记为不完整
                    self.benchmark_data[size] = df if len(df) > 0 else pd.DataFrame()
            
            except Exception as e:
                self.logger.error(f"❌ {size}({code}) 数据加载失败: {str(e)[:50]}")
                import traceback
                self.logger.debug(traceback.format_exc())
                # 降级：保存空DataFrame
                self.benchmark_data[size] = pd.DataFrame()
        
        # ✅ 核心修复5：验证数据完整性
        required_sizes = ['大盘', '中盘', '小盘', '微盘']
        valid_sizes = [s for s in required_sizes if s in self.benchmark_data and len(self.benchmark_data[s]) > 0]
        
        if len(valid_sizes) < 2:
            self.logger.error(f"❌ 基准数据严重不足（需≥2个层级，当前{len(valid_sizes)}个）")
            raise RuntimeError("基准数据加载失败，系统无法运行")
        
        self.logger.info(f"✅ 基准数据加载完成: {len(valid_sizes)}/{len(required_sizes)}个层级有效")
        
        # ✅ 核心修复6：评估微盘流动性（使用已加载的 benchmark_data）
        if '微盘' in self.benchmark_data and len(self.benchmark_data['微盘']) > 0:
            df_primary = self.benchmark_data['微盘']
            df_secondary = self.benchmark_data.get('小盘', pd.DataFrame())
            
            try:
                self.micro_liquidity_status = self.risk_service.assess_micro_liquidity(
                    df_primary,
                    df_secondary if len(df_secondary) > 0 else None
                )
                self.logger.info(f"✅ 微盘流动性状态: {self.micro_liquidity_status['stage']}")
            except Exception as e:
                self.logger.warning(f"⚠️ 微盘流动性评估失败: {str(e)[:50]}，使用默认状态")
                self.micro_liquidity_status = {
                    'status': 'normal',
                    'stage': '正常期',
                    'days_in_stage': 0,
                    'risk_level': 'low',
                    'exposure_cap': 0.20
                }
        else:
            self.logger.warning("⚠️ 微盘数据缺失，使用默认流动性状态")
            self.micro_liquidity_status = {
                'status': 'normal',
                'stage': '正常期',
                'days_in_stage': 0,
                'risk_level': 'low',
                'exposure_cap': 0.20
            }
    
    def run(self) -> Dict:
        """运行系统（V6.1增强版）"""
        self.logger.info("\n" + "=" * 80)
        self.logger.info(f"📅 运行基准日: {self.config.config.get('base_date', datetime.now().strftime('%Y-%m-%d'))}")
        self.logger.info("✅ V6.1系统运行中（阈值动态化 + 配置统一化）")
        self.logger.info("=" * 80)
        
        # 1. 判定市场状态（动态阈值）
        market_state, val_score, trend_score, _ = \
            self.market_state_service.determine_market_state(self.benchmark_data)
        
        self.logger.info(f"🎯 市场状态: {market_state}")
        self.logger.info(f"📊 估值安全边际: {val_score:.1f}/100")
        self.logger.info(f"📈 趋势动能强度: {trend_score:.1f}/100")
        
        # 2. 计算配置（动态阈值）
        allocation_df = self.allocation_service.calculate_allocation(
            benchmark_data=self.benchmark_data,
            micro_liquidity=self.micro_liquidity_status,
            market_state=market_state
        )
        
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
            config_service=self.config,
            benchmark_data=self.benchmark_data,  # ✅ 传递 benchmark_data
            micro_liquidity=self.micro_liquidity_status  # ✅ 传递微盘状态            
        )
        
        # 4. 生成18大图表
        charts = self.visualizer.generate_all_charts(data_context)
        
        # 5. 导出HTML报告
        output_path = self.visualizer.export_charts_to_html(
            charts,
            output_path=f'./reports/visualization_report_v6_1_{datetime.now().strftime("%Y%m%d_%H%M%S")}.html'
        )
        
        return {
            'market_state': market_state,
            'valuation_score': val_score,
            'trend_score': trend_score,
            'allocation': allocation_df,
            'charts': charts,
            'report_path': output_path,
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'threshold_service_enabled': self.threshold_service is not None
        }