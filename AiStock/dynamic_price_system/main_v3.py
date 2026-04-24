#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
DynamicPriceSystem 主程序入口（两阶段架构）
职责：
  - 阶段 1：批量分析 + 智能筛选 + 结果保存
  - 阶段 2：按需加载 + 单标深度分析
架构：严格遵循依赖注入与配置驱动原则
"""

import sys
import numpy as np
from typing import Dict, List, Optional
import pandas as pd
import os
import argparse
import logging
import json
from pathlib import Path
from datetime import datetime

# ==================== 路径注入 ====================
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
os.chdir(PROJECT_ROOT)

# ==================== 参数解析 ====================
def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="AiStock 动态价格计算系统（两阶段）")
    
    # 阶段选择
    parser.add_argument("--phase", choices=["1", "2", "all"], default="all",
                        help="执行阶段: 1(批量分析)/2(单标分析)/all(全流程)")
    
    # 阶段 1 参数
    parser.add_argument("--mode", choices=["paper", "real", "backtest"], default="paper",
                        help="运行模式: paper(模拟)/real(实盘)/backtest(回测)")
    parser.add_argument("--date", type=str, default=None,
                        help="指定计算日期 (YYYY-MM-DD)，默认当日")
    parser.add_argument("--stocks", nargs="+", default=None,
                        help="指定股票代码列表 (默认全量 18 只)")
    parser.add_argument("--filter-rule", type=str, default="default",
                        help="筛选规则名称 (default/conservative/aggressive)")
    parser.add_argument("--save-results", action="store_true", default=True,
                        help="是否保存分析结果 (默认开启)")
    parser.add_argument("--charts", nargs="+", default=None,
        help="指定图表类型。可选: price_interval, factor_breakdown, confidence_gauge, diagnostics_tree, indicator_scatter, summary_card, 或直接使用 'all'")    
    # 阶段 2 参数
    parser.add_argument("--code", type=str, default=None,
                        help="单标分析：指定股票代码 (阶段 2 必需)")
    parser.add_argument("--version", type=str, default=None,
                        help="单标分析：指定结果版本 (默认 latest)")
    parser.add_argument("--charts", nargs="+", default=None,
                        help="单标分析：指定图表类型 (默认六宫格)")
    
    # 通用参数
    parser.add_argument("--export", choices=["html", "excel", "png", "json"], default="html",
                        help="可视化导出格式")
    parser.add_argument("--skip-viz", action="store_true",
                        help="跳过可视化生成（提升性能）")
    parser.add_argument("--output-dir", type=str, default="output",
                        help="输出目录根路径")
    
    return parser.parse_args()


# ==================== 核心运行器 ====================
class DynamicPriceRunner:
    """动态价格系统主流程编排器（两阶段）"""
    
    def __init__(self, args: argparse.Namespace):
        self.args = args
        self.logger = logging.getLogger("MainRunner")
        self.services = {}
        self.repo = None  # 结果仓库
        
        self._init_logging()
        self._init_services()
        self._init_repository()
    
    def _init_logging(self):
        """初始化日志"""
        log_dir = PROJECT_ROOT / "logs" / "dynamic_price"
        log_dir.mkdir(parents=True, exist_ok=True)
        
        fmt = '%(asctime)s [%(levelname)s] %(name)s: %(message)s'
        handlers = [
            logging.StreamHandler(sys.stdout),
            logging.FileHandler(log_dir / f"system_{datetime.now().strftime('%Y%m%d')}.log", encoding='utf-8')
        ]
        logging.basicConfig(level=logging.INFO, format=fmt, handlers=handlers)
    
    def _init_services(self):
        """初始化业务服务"""
        self.logger.info("🔧 初始化核心服务...")
        
        # 1. 配置服务
        from base_services.config_service import ConfigService
        self.services['config'] = ConfigService(system_name='dynamic_price')
        
        # 2. 缓存服务
        from base_services.cache_service import CacheService
        cache_cfg = self.services['config'].get('cache', {})
        self.services['cache'] = CacheService(
            max_size=cache_cfg.get('max_size', 2000),
            ttl=cache_cfg.get('ttl', 300)
        )
        
        # 3. 数据库服务
        from data_services.database_reader import DatabaseReader
        db_cfg = self.services['config'].get('database', {})
        self.services['db'] = DatabaseReader(
            db_config=db_cfg.get('DATABASE_ENGINES', {}),
            pool_config=db_cfg.get('DB_POOL_CONFIG', {})
        )
        
        # 4. 数据加载服务
        from data_services.tdx_adapter import TDXAdapter
        from data_services.ak_adapter import AKAdapter
        tdx_cfg = self.services['config'].get('tdx', {})
        self.services['tdx'] = TDXAdapter(tdx_cfg) if tdx_cfg.get('use_tdx') else None
        self.services['ak'] = AKAdapter()
        
        from data_services.data_loading_service import DataLoadingService
        self.services['loader'] = DataLoadingService(
            config_service=self.services['config'],
            cache_service=self.services['cache'],
            database_reader=self.services['db'],
            tdx_adapter=self.services['tdx'],
            ak_adapter=self.services['ak'],
            enable_cache=True
        )
        
        # 5. 价格引擎
        from dynamic_price_system.core.dynamic_price_engine import DynamicPriceEngine
        self.services['engine'] = DynamicPriceEngine(config_service=self.services['config'])

        # 7. 组合与风控
        from dynamic_price_system.portfolio.tracker import PortfolioTracker
        from dynamic_price_system.portfolio.risk_manager import RiskManager
        initial_capital = self.services['config'].get('portfolio.initial_capital', 1_000_000)
        self.services['portfolio'] = PortfolioTracker(initial_capital=initial_capital, config=self.services['config'])
        self.services['risk'] = RiskManager(config=self.services['config'], portfolio=self.services['portfolio'])
        
        # 6. 筛选引擎
        from analysis.filter_engine import FilterEngine
        filter_cfg_path = PROJECT_ROOT / "config" / "dynamic_price" / "screening_rules.yaml"
        self.services['filter'] = FilterEngine(
            config_path=str(filter_cfg_path) if filter_cfg_path.exists() else None
        )
        
        # 7. 可视化服务
        if not self.args.skip_viz:
            try:
                from visualization.services.visualization_service import VisualizationService
                viz_cfg_path = PROJECT_ROOT / "config" / "dynamic_price" / "chart_config.yaml"
                self.services['viz'] = VisualizationService(
                    config_path=str(viz_cfg_path) if viz_cfg_path.exists() else None
                )
                
                # ✅ 新增：置信度面板服务（用于阶段 2 深度分析）
                from visualization.confidence_dashboard import ConfidenceDashboard
                conf_cfg_path = PROJECT_ROOT / "config" / "dynamic_price" / "confidence_config.yaml"
                self.services['confidence_dashboard'] = ConfidenceDashboard(
                    config={'theme': 'plotly_white', 'width': 1400, 'height': 1000}
                ) if conf_cfg_path.exists() else None
                
            except Exception as e:
                self.logger.warning(f"⚠️ 可视化服务初始化失败: {e}")
                self.services['viz'] = None
                self.services['confidence_dashboard'] = None
        else:
            self.services['viz'] = None
            self.services['confidence_dashboard'] = None
        
        self.logger.info("✅ 服务初始化完成")
    
    def _init_repository(self):
        """初始化结果仓库"""
        from analysis.result_repository import ResultRepository
        output_dir = Path(self.args.output_dir) / "analysis_results"
        self.repo = ResultRepository(base_dir=str(output_dir))
        self.logger.info(f"✅ 结果仓库初始化 | 目录: {self.repo.version_dir}")
    
    def run(self):
        """执行主流程（两阶段路由）"""
        self.logger.info(f"🚀 启动动态价格系统 | 阶段: {self.args.phase} | 时间: {datetime.now().isoformat()}")
        start_time = datetime.now()
        
        try:
            if self.args.phase in ["1", "all"]:
                self._run_phase1()
            
            if self.args.phase in ["2", "all"]:
                if self.args.phase == "all" and not self.args.code:
                    # 全流程模式且未指定 code，自动使用推荐标的
                    recommended = self.repo.load_recommended_stocks()
                    if recommended:
                        self.args.code = recommended[0]['code']
                        self.logger.info(f"🔄 全流程模式：自动选择推荐标的 {self.args.code} 进行深度分析")
                
                if self.args.code:
                    self._run_phase2(self.args.code)
                elif self.args.phase == "2":
                    self.logger.error("❌ 阶段 2 必需参数: --code <股票代码>")
                    return
            
            # 性能统计
            duration = (datetime.now() - start_time).total_seconds()
            self.logger.info(f"⏱️ 总耗时: {duration:.2f}s | 🏁 流程执行完毕")
            
        except KeyboardInterrupt:
            self.logger.info("⌨️ 用户中断执行")
        except Exception as e:
            self.logger.error(f"❌ 系统运行异常: {e}", exc_info=True)
            raise
        finally:
            self._cleanup()
    
    def _run_phase1(self):
        """阶段 1：批量分析 + 筛选 + 保存"""
        self.logger.info("📊 阶段 1：批量分析 + 智能筛选 + 结果保存")
        phase1_start = datetime.now()
        
        # 1. 确定标的池
        target_stocks = self._resolve_stock_universe()
        self.logger.info(f"📋 标的池: {len(target_stocks)} 只")
        
        # 2. 加载宏观数据
        macro_codes = list(self.services['config'].get('macro_indicators').keys())
        # macro_codes = self.services['config'].get('macro_codes', [
        #     'brent_crude', 'comex_gold', 'pmi', 'm2_growth', 'cpi','ppi', 'china_10y_bond',
        #     'lme_nickel', 'usd_cny','eua_carbon','lme_copper','nymex_gas','us_10y_bond'
        # ])
        macro_data = self.services['loader'].load_all_macro_indicators(macro_codes)
        
        # 3. 批量加载行情 & 财务数据
        stock_data_map = {}
        financial_data_map = {}
        valid_stocks = []
        
        for stock in target_stocks:
            code = stock['code']
            try:
                stock_data = self.services['loader'].load_stock_daily(code, min_days=300)
                if stock_data is None or stock_data.empty:
                    continue
                
                fin_df = self.services['loader'].load_stock_financials(code)
                financial_data = fin_df.to_dict(orient='records')[0] if not fin_df.empty else {}
                
                stock_data_map[code] = stock_data
                financial_data_map[code] = financial_data
                valid_stocks.append(stock)
            except Exception as e:
                self.logger.error(f"❌ 加载 {code} 数据失败: {e}")
        
        if not valid_stocks:
            self.logger.error("❌ 无有效标的数据，阶段 1 终止")
            return
        
        # 4. 执行批量计算
        calc_inputs = [
            {
                'code': s['code'], 'name': s['name'], 'sector': s['sector'],
                'stock_data': stock_data_map[s['code']],
                'financial_data': financial_data_map[s['code']],
                'macro_data': macro_data,
                'params': s.get('params', {})
            } for s in valid_stocks
        ]
        batch_results = self.services['engine'].calculate_batch(calc_inputs)
        self.logger.info(f"✅ 批量计算完成: {len(batch_results)}/{len(calc_inputs)} 成功")
        
        if not batch_results:
            self.logger.warning("⚠️ 无有效计算结果，阶段 1 终止")
            return
        
        # 5. 智能筛选 + 评分排序
        filter_rule = self.args.filter_rule
        recommended = self.services['filter'].filter_results(batch_results, rule_name=filter_rule)
        
        # 综合评分排序（可选）
        if self.services['config'].get('analysis.enable_scoring', True):
            weights = self.services['config'].get('analysis.scoring_weights')
            recommended = self.services['filter'].score_and_rank(recommended, weights)
        
        # 6. 保存结果
        if self.args.save_results:
            metadata = {
                'mode': self.args.mode,
                'filter_rule': filter_rule,
                'total_computed': len(batch_results),
                'recommended_count': len(recommended)
            }
            self.repo.save_batch_results(batch_results, metadata)
            self.repo.save_recommended_stocks(recommended, criteria=self.services['filter'].rules.get(filter_rule, {}))
            self.repo.create_latest_symlink()  # 更新 latest 链接
        
        # 7. 阶段 1 可视化（批量对比）
        if self.services.get('viz') and not self.args.skip_viz:
            self._generate_phase1_visualizations(batch_results, recommended)
        
        phase1_duration = (datetime.now() - phase1_start).total_seconds()
        self.logger.info(f"✅ 阶段 1 完成 | 耗时: {phase1_duration:.2f}s | 推荐: {len(recommended)} 只")
    
    def _run_phase2(self, code: str):
        """阶段 2：单标深度分析"""
        self.logger.info(f"🔍 阶段 2：单标深度分析 | 标的: {code}")
        phase2_start = datetime.now()
        
        # 1. 从仓库加载基础结果
        version = self.args.version
        result = self.repo.get_stock_detail(code, version)
        
        if not result:
            self.logger.warning(f"⚠️ 未找到保存结果 {code}@{version}，尝试实时计算...")
            result = self._compute_single_stock_realtime(code)
            if not result:
                self.logger.error(f"❌ 实时计算 {code} 失败")
                return
        
        # 2. 补充深度数据
        enhanced_result = self._enhance_stock_data(result)
        
        # # 3. ✅ 生成可视化（调用新方法）
        # if self.services.get('viz') and not self.args.skip_viz:
        #     self._generate_phase2_visualizations(enhanced_result, code)
        # 3. 生成单标可视化（六宫格）
        if self.services.get('viz') and not self.args.skip_viz:
            # ✅ 完整支持的图表类型清单
            ALL_SUPPORTED_CHARTS = [
                'price_interval', 'factor_breakdown', 'confidence_gauge',
                'diagnostics_tree', 'indicator_scatter', 'summary_card'
            ]
            
            # ✅ 智能解析 --charts 参数：支持 "all" 关键字
            if self.args.charts and 'all' in self.args.charts:
                chart_types = ALL_SUPPORTED_CHARTS
                self.logger.info(f"📦 解析 --charts all → 生成 {len(chart_types)} 个深度图表")
            else:
                chart_types = self.args.charts or ALL_SUPPORTED_CHARTS

            outputs = self.services['viz'].visualize_single_result(
                enhanced_result,
                chart_types=chart_types,
                output_format=self.args.export,
                enable_cache=True
            )
            if outputs:
                self.logger.info(f"✅ 生成 {code} 深度分析: {list(outputs.keys())}")
            else:
                self.logger.warning(f"⚠️ 未生成任何图表，请检查 result 数据结构")        
        # 4. 对比分析（如指定）
        if self.args.charts and 'comparison' in self.args.charts:
            self._generate_comparison_analysis(code, enhanced_result)
        
        phase2_duration = (datetime.now() - phase2_start).total_seconds()
        self.logger.info(f"✅ 阶段 2 完成 | 标的: {code} | 耗时: {phase2_duration:.2f}s")
    
    def _compute_single_stock_realtime(self, code: str) -> Optional[Dict]:
        """实时计算单标的（回退方案）"""
        try:
            # 加载配置
            stock_cfg = next((s for s in self.services['config'].get('stocks', []) if s['code'] == code), None)
            if not stock_cfg:
                return None
            
            # 加载数据
            stock_data = self.services['loader'].load_stock_daily(code, min_days=200)
            if stock_data is None or stock_data.empty:
                return None
            
            fin_df = self.services['loader'].load_stock_financials(code)
            financial_data = fin_df.to_dict(orient='records')[0] if not fin_df.empty else {}
            
            macro_codes = list(self.services['config'].get('macro_indicators').keys())
            macro_data = self.services['loader'].load_all_macro_indicators(macro_codes)
            
            # 计算
            return self.services['engine'].calculate_single(
                code=code,
                name=stock_cfg['name'],
                sector=stock_cfg['sector'],
                stock_data=stock_data,
                financial_data=financial_data,
                macro_data=macro_data,
                stock_params=stock_cfg.get('params', {})
            )
        except Exception as e:
            self.logger.error(f"❌ 实时计算 {code} 异常: {e}")
            return None
    
    def _enhance_stock_data(self, result: Dict) -> Dict:
        """补充单标深度数据"""
        code = result['code']
        
        # 1. 加载技术指标明细
        stock_data = self.services['loader'].load_stock_daily(code, min_days=300)
        if stock_data is not None and not stock_data.empty:
            from dynamic_price_system.core.technical_calculator import TechnicalCalculator
            tech_calc = TechnicalCalculator(stock_data, params=result.get('params_used', {}))
            result['technical_indicators'] = tech_calc.get_latest_indicators()
            result['technical_signals'] = tech_calc.get_all_signals()
        
        # 2. 加载财务明细（如有）
        fin_df = self.services['loader'].load_stock_financials(code)
        if fin_df is not None and not fin_df.empty:
            result['financial_details'] = fin_df.to_dict(orient='records')
        
        # 3. 生成置信度诊断（如未包含）
        if 'technical_quality' not in result and 'technical_indicators' in result:
            from dynamic_price_system.core.technical_confidence import TechnicalConfidence
            conf_calc = TechnicalConfidence()
            conf_result = conf_calc.calculate(
                indicators=result['technical_indicators'],
                stock_data=stock_data
            )
            result['technical_quality'] = {
                'factor': conf_result.factor,
                'score': conf_result.score,
                'level': conf_result.level,
                'breakdown': {
                    'data_quality': conf_result.data_quality_score,
                    'consistency': conf_result.consistency_score,
                    'strength': conf_result.strength_score
                },
                'diagnostics': conf_result.diagnostics
            }
        
        return result
    
    def _generate_phase1_visualizations(self, batch_results, recommended):
        """
        生成阶段 1 可视化（批量分析 + 筛选结果）
        严格对齐 visualization/ 目录结构
        """
        viz = self.services.get('viz')
        if not viz:
            self.logger.info("⏭️ 可视化服务未启用，跳过阶段 1 图表生成")
            return
        
        output_dir = PROJECT_ROOT / self.args.output_dir / "visualization" / "phase1"
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # ✅ 数据标准化：统一嵌套结构，兼容 DataFrame/List
        def normalize_result(r):
            return {
                'code': r.get('code', ''),
                'name': r.get('name', '未知'),
                'sector': r.get('sector', '未知'),
                'scores': {
                    'pl_ratio': r.get('pl_ratio') or (r.get('scores', {}).get('pl_ratio') if isinstance(r.get('scores'), dict) else 0.0),
                    'fundamental': r.get('fundamental_score') or (r.get('scores', {}).get('fundamental') if isinstance(r.get('scores'), dict) else 50.0)
                },
                'factors': {
                    'composite': r.get('composite_factor') or (r.get('factors', {}).get('composite') if isinstance(r.get('factors'), dict) else 1.0)
                },
                'prices': {
                    'entry': r.get('entry_price') or (r.get('prices', {}).get('entry') if isinstance(r.get('prices'), dict) else 0.0),
                    'target': r.get('target_price') or (r.get('prices', {}).get('target') if isinstance(r.get('prices'), dict) else 0.0),
                    'stop_loss': r.get('stop_loss') or (r.get('prices', {}).get('stop_loss') if isinstance(r.get('prices'), dict) else 0.0),
                    'current': r.get('current_price') or (r.get('prices', {}).get('current') if isinstance(r.get('prices'), dict) else 0.0)
                },
                'recommendation': r.get('recommendation', '观望'),
                'technical_quality': r.get('technical_quality', {})
            }
        
        # 转换输入数据
        import pandas as pd
        safe_batch = [normalize_result(r) for r in (batch_results.to_dict('records') if isinstance(batch_results, pd.DataFrame) else batch_results)]
        safe_rec = [normalize_result(r) for r in (recommended.to_dict('records') if isinstance(recommended, pd.DataFrame) else recommended)]
        
        if not safe_batch:
            self.logger.warning("⚠️ 无有效批量数据，跳过阶段 1 可视化")
            return
        
        self.logger.info(f"🎨 开始生成阶段 1 可视化 | 批量: {len(safe_batch)} 只，推荐: {len(safe_rec)} 只")
        start_time = datetime.now()
        generated = []
        
        try:
            # ========== 1. 批量对比仪表板 ==========
            if safe_batch:
                try:
                    from visualization.phase1.batch_dashboard import create_batch_dashboard, create_risk_return_scatter
                    from visualization.components.risk_chart import create_risk_matrix_chart
                    
                    # 1.1 组合分布图
                    fig_batch = create_batch_dashboard(safe_batch, config=self.services['viz'].config.get('portfolio_chart', {}))
                    batch_path = output_dir / f"portfolio_comparison_{len(safe_batch)}_stocks.{self.args.export}"
                    viz.renderer.export(fig_batch, str(batch_path), format=self.args.export)
                    generated.append(batch_path.name)
                    self.logger.debug(f"✅ 组合对比图: {batch_path.name}")
                    
                    # 1.2 风险 - 收益散点图
                    fig_risk = create_risk_return_scatter(safe_batch, config=self.services['viz'].config.get('risk_chart', {}))
                    risk_path = output_dir / f"risk_return_scatter.{self.args.export}"
                    viz.renderer.export(fig_risk, str(risk_path), format=self.args.export)
                    generated.append(risk_path.name)
                    
                    # 1.3 风险矩阵图（需 volatility 字段）
                    if all('volatility' in r.get('signals', {}) or 'volatility' in r for r in safe_batch):
                        fig_matrix = create_risk_matrix_chart(safe_batch, config=self.services['viz'].config.get('risk_chart', {}))
                        matrix_path = output_dir / f"risk_matrix.{self.args.export}"
                        viz.renderer.export(fig_matrix, str(matrix_path), format=self.args.export)
                        generated.append(matrix_path.name)
                        
                except Exception as e:
                    self.logger.warning(f"⚠️ 批量对比图生成失败: {e}")
            
            # ========== 2. 筛选结果面板 ==========
            if safe_rec:
                try:
                    from visualization.phase1.screening_panel import create_screening_panel
                    fig_screen = create_screening_panel(
                        safe_rec, 
                        safe_batch, 
                        criteria=self.services['filter'].rules.get(self.args.filter_rule, {}),
                        config=self.services['viz'].config.get('screening_panel', {})
                    )
                    screen_path = output_dir / f"screening_results_{self.repo.version}.{self.args.export}"
                    viz.renderer.export(fig_screen, str(screen_path), format=self.args.export)
                    generated.append(screen_path.name)
                    self.logger.info(f"✅ 筛选面板: {screen_path.name}")
                except Exception as e:
                    self.logger.warning(f"⚠️ 筛选面板生成失败: {e}")
            
            # ========== 3. 分析摘要报告 ==========
            if self.args.export == 'html' and safe_batch:
                try:
                    from visualization.phase1.summary_report import generate_summary_report
                    summary_path = generate_summary_report(
                        batch_results=safe_batch,
                        recommended=safe_rec,
                        output_path=output_dir / f"summary_report_{self.repo.version}.html",
                        format='html',
                        config={'version': self.repo.version}
                    )
                    if summary_path:
                        generated.append(Path(summary_path).name)
                        self.logger.info(f"✅ 摘要报告: {Path(summary_path).name}")
                except Exception as e:
                    self.logger.warning(f"⚠️ 摘要报告生成失败: {e}")
            
            # ========== 4. 置信度批量面板（可选） ==========
            if any(r.get('technical_quality') for r in safe_batch):
                try:
                    from visualization.confidence_dashboard import ConfidenceDashboard
                    conf_dashboard = ConfidenceDashboard(config=self.services['viz'].config.get('dashboard', {}))
                    fig_conf = conf_dashboard.create_batch_comparison_dashboard(
                        safe_batch,
                        filter_config={'min_confidence': 0.99, 'min_pl_ratio': 2.0}
                    )
                    conf_path = output_dir / f"confidence_batch_{self.repo.version}.{self.args.export}"
                    viz.renderer.export(fig_conf, str(conf_path), format=self.args.export)
                    generated.append(conf_path.name)
                    self.logger.debug(f"✅ 置信度筛选面板: {conf_path.name}")
                except Exception as e:
                    self.logger.debug(f"⚠️ 置信度面板生成失败 (可选): {e}")
            
            # 性能统计
            duration = (datetime.now() - start_time).total_seconds()
            self.logger.info(
                f"🎨 阶段 1 可视化完成 | 生成 {len(generated)} 个文件 | 耗时: {duration:.2f}s | "
                f"平均: {duration/max(1,len(generated)):.2f}s/图表"
            )
            if generated:
                self.logger.info(f"📁 查看: {output_dir.relative_to(PROJECT_ROOT)}")
                
        except Exception as e:
            self.logger.error(f"❌ 阶段 1 可视化生成异常: {e}", exc_info=True)

    def _generate_phase2_visualizations(self, result: Dict, code: str):
        """
        生成阶段 2 可视化（单标深度分析）
        严格对齐 visualization/phase2/ 目录结构
        """
        viz = self.services.get('viz')
        if not viz:
            return
        
        output_dir = PROJECT_ROOT / self.args.output_dir / "visualization" / "phase2"
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # 确保结果包含 technical_quality
        if 'technical_quality' not in result and 'technical_indicators' in result:
            try:
                from dynamic_price_system.core.technical_confidence import TechnicalConfidence
                conf_calc = TechnicalConfidence()
                conf_result = conf_calc.calculate(
                    indicators=result['technical_indicators'],
                    stock_data=None  # 简化：实际应传入
                )
                result['technical_quality'] = {
                    'factor': conf_result.factor,
                    'score': conf_result.score,
                    'level': conf_result.level,
                    'breakdown': {
                        'data_quality': conf_result.data_quality_score,
                        'consistency': conf_result.consistency_score,
                        'strength': conf_result.strength_score
                    },
                    'diagnostics': conf_result.diagnostics
                }
            except Exception as e:
                self.logger.debug(f"⚠️ 置信度计算失败 (可选): {e}")
        
        self.logger.info(f"🎨 开始生成 {code} 深度分析可视化...")
        start_time = datetime.now()
        generated = []
        
        try:
            # ========== 1. 单标六宫格面板 ==========
            chart_types = self.args.charts or [
                'price_interval', 'factor_breakdown', 'confidence_gauge',
                'diagnostics_tree', 'indicator_scatter', 'summary_card'
            ]
            
            outputs = viz.visualize_single_result(
                result,
                chart_types=chart_types,
                output_format=self.args.export,
                enable_cache=True
            )
            if outputs:
                for chart_type, path in outputs.items():
                    generated.append(Path(path).name)
                self.logger.info(f"✅ 六宫格图表: {list(outputs.keys())}")
            
            # ========== 2. 置信度深度面板（可选） ==========
            if result.get('technical_quality') and 'confidence_dashboard' in self.services:
                try:
                    conf_dash = self.services['confidence_dashboard']
                    fig_conf = conf_dash.create_single_stock_dashboard(
                        code=result['code'],
                        name=result['name'],
                        confidence_result=result['technical_quality'],
                        indicators=result.get('technical_indicators', {}),
                        stock_data=None,  # 简化
                        historical_confidence=None
                    )
                    conf_path = output_dir / f"{code}_confidence_deep.{self.args.export}"
                    viz.renderer.export(fig_conf, str(conf_path), format=self.args.export)
                    generated.append(conf_path.name)
                    self.logger.debug(f"✅ 置信度深度面板: {conf_path.name}")
                except Exception as e:
                    self.logger.debug(f"⚠️ 置信度深度面板生成失败 (可选): {e}")
            
            # ========== 3. 对比分析（标的 vs 板块/推荐） ==========
            if 'comparison' in (self.args.charts or []):
                try:
                    from visualization.phase2.comparison_tool import create_comparison_chart, create_price_comparison_table
                    
                    # 3.1 雷达图对比
                    sector = result['sector']
                    query_df = self.repo.query_results(filters={'sector': {'==': sector}}, limit=50)
                    sector_results = query_df.to_dict('records') if not query_df.empty else []
                    
                    rec_list = self.repo.load_recommended_stocks()
                    
                    fig_comp = create_comparison_chart(
                        target_result=result,
                        sector_results=sector_results,
                        recommended_results=rec_list,
                        config=self.services['viz'].config.get('comparison', {})
                    )
                    comp_path = output_dir / f"{code}_comparison.{self.args.export}"
                    viz.renderer.export(fig_comp, str(comp_path), format=self.args.export)
                    generated.append(comp_path.name)
                    
                    # 3.2 价格对比表格
                    if sector_results:
                        fig_table = create_price_comparison_table(result, sector_results[:5])
                        table_path = output_dir / f"{code}_price_table.{self.args.export}"
                        viz.renderer.export(fig_table, str(table_path), format=self.args.export)
                        generated.append(table_path.name)
                    
                    self.logger.info(f"✅ 对比分析: {comp_path.name}")
                except Exception as e:
                    self.logger.warning(f"⚠️ 对比分析生成失败: {e}")
            
            # ========== 4. 交互式钻取（实验性） ==========
            if 'drill_down' in (self.args.charts or []):
                try:
                    from visualization.phase2.drill_down import DrillDownManager
                    from visualization.components.price_chart import create_price_interval_chart
                    
                    drill_mgr = DrillDownManager()
                    base_fig = create_price_interval_chart(result)
                    
                    # 注册钻取回调（示例）
                    def on_price_drill(data, history):
                        # 实际应加载更细粒度数据
                        return None
                    
                    drillable_fig = drill_mgr.create_drillable_chart(
                        base_fig,
                        drill_config={'price_point': {'handler': on_price_drill}},
                        on_drill=on_price_drill
                    )
                    
                    drill_path = output_dir / f"{code}_drillable.{self.args.export}"
                    viz.renderer.export(drillable_fig, str(drill_path), format=self.args.export)
                    generated.append(drill_path.name)
                    self.logger.debug(f"✅ 可钻取图表: {drill_path.name}")
                except Exception as e:
                    self.logger.debug(f"⚠️ 钻取功能生成失败 (实验性): {e}")
            
            # 性能统计
            duration = (datetime.now() - start_time).total_seconds()
            self.logger.info(
                f"🎨 {code} 深度分析完成 | 生成 {len(generated)} 个文件 | 耗时: {duration:.2f}s"
            )
            if generated:
                self.logger.info(f"📁 查看: {output_dir.relative_to(PROJECT_ROOT)}")
                
        except Exception as e:
            self.logger.error(f"❌ 阶段 2 可视化生成异常 {code}: {e}", exc_info=True)
            
    def _generate_comparison_analysis(self, code: str, result: Dict):
        """生成对比分析（标的 vs 板块均值/推荐列表）"""
        # 1. 加载板块均值
        sector = result['sector']
        query_results = self.repo.query_results(filters={'sector': {'==': sector}})
        if not query_results.empty:
            sector_avg = {
                'pl_ratio': query_results['pl_ratio'].mean(),
                'confidence': query_results['confidence_factor'].mean(),
                'fundamental': query_results['fundamental_score'].mean()
            }
            result['sector_comparison'] = sector_avg
        
        # 2. 加载推荐列表均值
        recommended = self.repo.load_recommended_stocks()
        if recommended:
            rec_avg = {
                'pl_ratio': np.mean([r['scores']['pl_ratio'] for r in recommended]),
                'confidence': np.mean([r.get('technical_quality', {}).get('factor', 1.0) for r in recommended])
            }
            result['recommended_comparison'] = rec_avg
        
        # 3. 生成对比图
        if self.services.get('viz'):
            from visualization.phase2.comparison_tool import create_comparison_chart
            fig = create_comparison_chart(result)
            output_dir = PROJECT_ROOT / self.args.output_dir / "visualization" / "phase2"
            output_dir.mkdir(parents=True, exist_ok=True)
            comp_path = output_dir / f"{code}_comparison.{self.args.export}"
            self.services['viz'].renderer.export(fig, str(comp_path), format=self.args.export)
            self.logger.info(f"✅ 生成对比分析: {comp_path.name}")
    
    def _resolve_stock_universe(self) -> list:
        """解析目标标的池"""
        all_stocks = self.services['config'].get('stocks', [])
        if self.args.stocks:
            filtered = [s for s in all_stocks if s['code'] in self.args.stocks]
            if not filtered:
                self.logger.warning(f"⚠️ 未找到指定标的: {self.args.stocks}，回退至全量")
                return all_stocks
            return filtered
        return all_stocks
    
    def _cleanup(self):
        """优雅关闭"""
        self.logger.info("🧹 清理服务资源...")
        for name, svc in self.services.items():
            if svc and hasattr(svc, 'close'):
                try:
                    svc.close()
                except Exception as e:
                    self.logger.debug(f"清理 {name} 失败: {e}")
        if self.repo and hasattr(self.repo, 'close'):
            self.repo.close()
        self.logger.info("✅ 资源清理完成")


# ==================== 入口函数 ====================
def main():
    args = parse_args()
    
    # 参数校验
    if args.phase == "2" and not args.code:
        print("❌ 错误: 阶段 2 (--phase 2) 必需参数: --code <股票代码>")
        print("💡 示例: python main.py --phase 2 --code 600938")
        sys.exit(1)
    
    runner = DynamicPriceRunner(args)
    runner.run()


if __name__ == '__main__':
    main()