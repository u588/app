#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
DynamicPriceSystem 主程序入口
职责：服务编排、流程控制、异常处理、参数解析
架构：严格遵循依赖注入与配置驱动原则，业务逻辑全部下沉至 Service 层
"""

import sys
import numpy as np
from typing import Dict, List, Optional
import os
import argparse
import logging
import json
from pathlib import Path
from datetime import datetime

# ==================== 路径注入 ====================
# 假设 main.py 位于 AiStock/dynamic_price_system/
PROJECT_ROOT = Path(__file__).resolve().parent.parent
# PROJECT_ROOT = Path.cwd().parent
# 确保项目根目录在 sys.path 最前面
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
os.chdir(PROJECT_ROOT)

print(f"✅ 项目根目录: {PROJECT_ROOT}")
print(f"📁 当前工作目录: {os.getcwd()}")
print(f"🐍 sys.path[0]: {sys.path[0]}")
# ==================== 参数解析 ====================
def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="AiStock 动态价格计算系统")
    parser.add_argument("--mode", choices=["paper", "real", "backtest"], default="paper",
                        help="运行模式: paper(模拟)/real(实盘)/backtest(回测)")
    parser.add_argument("--date", type=str, default=None,
                        help="指定计算日期 (YYYY-MM-DD)，默认当日")
    parser.add_argument("--stocks", nargs="+", default=None,
                        help="指定股票代码列表 (默认全量 18 只)")
    parser.add_argument("--export", choices=["html", "excel", "png", "json"], default="html",
                        help="可视化导出格式")
    parser.add_argument("--skip-viz", action="store_true",
                        help="跳过可视化生成（提升批量计算性能）")
    return parser.parse_args()


# ==================== 核心运行器 ====================
class DynamicPriceRunner:
    """动态价格系统主流程编排器"""
    
    def __init__(self, args: argparse.Namespace):
        self.args = args
        self.logger = logging.getLogger("MainRunner")
        self.services = {}
        self._init_logging()
        self._init_services()
    
    def _init_logging(self):
        """初始化日志配置（可替换为自定义 LoggerService）"""
        log_dir = PROJECT_ROOT / "logs" / "dynamic_price"
        log_dir.mkdir(parents=True, exist_ok=True)
        
        fmt = '%(asctime)s [%(levelname)s] %(name)s: %(message)s'
        handlers = [
            logging.StreamHandler(sys.stdout),
            logging.FileHandler(log_dir / f"system_{datetime.now().strftime('%Y%m%d')}.log", encoding='utf-8')
        ]
        logging.basicConfig(level=logging.INFO, format=fmt, handlers=handlers)
    
    def _init_services(self):
        """初始化所有业务服务（依赖注入）"""
        self.logger.info("🔧 初始化核心服务...")
        
        # 1. 配置服务
        from base_services.config_service import ConfigService

        def on_config_change(new_config: Dict):
            """配置变更回调：动态更新引擎参数"""
            self.logger.info("🔄 检测到配置变更，正在更新引擎...")
            
            # 1.1 更新三维权重
            new_weights = new_config.get('weights', {})
            if new_weights and 'engine' in self.services:
                try:
                    self.services['engine'].update_weights(new_weights)
                    self.logger.info(f"✅ 引擎权重已更新: {new_weights}")
                except Exception as e:
                    self.logger.warning(f"⚠️ 更新权重失败: {e}")
            
            # 1.2 更新风控阈值（可选扩展）
            new_risk_cfg = new_config.get('risk_control', {})
            if new_risk_cfg and 'risk' in self.services:
                try:
                    self.services['risk'].update_config(new_risk_cfg)
                    self.logger.info(f"✅ 风控配置已更新")
                except Exception as e:
                    self.logger.warning(f"⚠️ 更新风控配置失败: {e}")
            
            # 1.3 记录变更摘要（便于审计）
            changed_keys = [k for k in ['weights', 'risk_control'] if k in new_config]
            if changed_keys:
                self.logger.debug(f"📝 配置变更项: {changed_keys}")

        # 初始化配置服务（启用热重载 + 注册回调）
        self.services['config'] = ConfigService(
            system_name='dynamic_price',
            enable_hot_reload=True,
            reload_callbacks=[on_config_change]  # ✅ 注册回调
        )
        
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
        
        # 4. 数据源适配器
        from data_services.tdx_adapter import TDXAdapter
        from data_services.ak_adapter import AKAdapter
        tdx_cfg = self.services['config'].get('tdx', {})
        self.services['tdx'] = TDXAdapter(tdx_cfg) if tdx_cfg.get('use_tdx') else None
        self.services['ak'] = AKAdapter()
        
        # 5. 数据加载服务
        from data_services.data_loading_service import DataLoadingService
        self.services['loader'] = DataLoadingService(
            config_service=self.services['config'],
            cache_service=self.services['cache'],
            database_reader=self.services['db'],
            tdx_adapter=self.services['tdx'],
            ak_adapter=self.services['ak'],
            enable_cache=True
        )
        
        # 6. 三维价格引擎
        from dynamic_price_system.core.dynamic_price_engine import DynamicPriceEngine
        self.services['engine'] = DynamicPriceEngine(config_service=self.services['config'])
        
        # 7. 组合与风控
        from dynamic_price_system.portfolio.tracker import PortfolioTracker
        from dynamic_price_system.portfolio.risk_manager import RiskManager
        initial_capital = self.services['config'].get('portfolio.initial_capital', 1_000_000)
        self.services['portfolio'] = PortfolioTracker(initial_capital=initial_capital, config=self.services['config'])
        self.services['risk'] = RiskManager(config=self.services['config'], portfolio=self.services['portfolio'])
        
        # 8. 可视化服务（增强版）
        if not self.args.skip_viz:
            try:
                from visualization.services.visualization_service import VisualizationService
                from visualization.confidence_dashboard import ConfidenceDashboard
                
                # 加载可视化配置
                viz_cfg_path = PROJECT_ROOT / "config" / "dynamic_price" / "chart_config.yaml"
                conf_cfg_path = PROJECT_ROOT / "config" / "dynamic_price" / "confidence_config.yaml"
                
                self.services['viz'] = VisualizationService(
                    config_path=str(viz_cfg_path) if viz_cfg_path.exists() else None
                )
                
                # 置信度面板（可选，用于深度分析）
                self.services['conf_dashboard'] = ConfidenceDashboard(
                    config={'theme': 'plotly_white', 'width': 1400, 'height': 900}
                ) if conf_cfg_path.exists() else None
                
                self.logger.info("✅ 可视化服务初始化完成")
                
            except ImportError as e:
                self.logger.warning(f"⚠️ 可视化模块导入失败: {e}，将跳过图表生成")
                self.services['viz'] = None
                self.services['conf_dashboard'] = None
            except Exception as e:
                self.logger.error(f"❌ 可视化服务初始化异常: {e}", exc_info=True)
                self.services['viz'] = None
                self.services['conf_dashboard'] = None
        else:
            self.services['viz'] = None
            self.services['conf_dashboard'] = None
    
    def run(self):
        """执行主流程"""
        self.logger.info(f"🚀 启动动态价格系统 | 模式: {self.args.mode} | 时间: {datetime.now().isoformat()}")
        start_time = datetime.now()
        
        try:
            # 1. 确定标的池
            target_stocks = self._resolve_stock_universe()
            self.logger.info(f"📋 标的池: {len(target_stocks)} 只 -> {[s['code'] for s in target_stocks]}")
            
            # 2. 加载宏观数据
            macro_codes = ['brent_crude', 'comex_gold', 'pmi', 'm2_growth', 'cpi','ppi', 'china_10y_bond','lme_nickel', 'usd_cny','eua_carbon','lme_copper','nymex_gas','us_10y_bond']
            self.logger.info("🌍 加载宏观指标数据...")
            macro_data = self.services['loader'].load_all_macro_indicators(macro_codes)
            # print(macro_data)
            
            # 3. 批量加载行情 & 财务数据
            self.logger.info("📥 加载标的行情与财务数据...")
            stock_data_map = {}
            financial_data_map = {}
            valid_stocks = []
            
            for stock in target_stocks:
                code = stock['code']
                try:
                    stock_data_map[code] = self.services['loader'].load_stock_daily(code, min_days=300)
                    if stock_data_map[code] is None or stock_data_map[code].empty:
                        self.logger.warning(f"⚠️ 行情数据不足跳过: {code}")
                        continue
                    
                    fin_df = self.services['loader'].load_stock_financials(code)
                    financial_data_map[code] = fin_df.to_dict(orient='records')[0] if not fin_df.empty else {}
                    valid_stocks.append(stock)
                except Exception as e:
                    self.logger.error(f"❌ 加载 {code} 数据失败: {e}")
            
            if not valid_stocks:
                self.logger.error("❌ 无有效标的数据，流程终止")
                return
            
            # 4. 执行三维价格计算
            self.logger.info("🧮 执行动态价格计算...")
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
            self.logger.info(f"✅ 计算完成: 成功 {len(batch_results)}/{len(calc_inputs)} 只")
            
            if not batch_results:
                self.logger.warning("⚠️ 无有效计算结果，流程终止")
                return
            
            # 5. 组合更新与风控检查
            self.logger.info("🛡️ 执行组合更新与风控检查...")
            current_prices = {r['code']: r['prices']['current'] for r in batch_results}
            
            if hasattr(self.services['portfolio'], 'mark_to_market'):
                self.services['portfolio'].mark_to_market(current_prices)
            elif hasattr(self.services['portfolio'], 'update_prices'):
                self.services['portfolio'].update_prices(current_prices)
            
            risk_alerts = self.services['risk'].check_alerts(batch_results, current_prices)
            if risk_alerts:
                for alert in risk_alerts:
                    self.logger.warning(f"⚠️ 风控预警: {alert.get('code')} | {alert.get('message')}")
            
            # 6. 可视化与导出（替换原代码）
            if self.services.get('viz'):
                self.logger.info("🎨 生成可视化图表...")
                
                # 准备单标的结果（用于深度分析）
                single_results = None
                if self.args.stocks:  # 只生成指定标的的深度分析
                    single_results = [r for r in batch_results if r['code'] in self.args.stocks]
                
                # 生成可视化
                generated_count = self._generate_visualizations(
                    batch_results=batch_results,
                    single_results=single_results
                )
                
                if generated_count > 0:
                    self.logger.info(f"✅ 已生成 {generated_count} 个可视化文件，查看: output/visualization/")
                else:
                    self.logger.warning("⚠️ 未生成任何可视化文件，请检查配置或日志")
            
            # 7. 持久化结果
            self._persist_results(batch_results)
            
            # 8. 性能统计
            duration = (datetime.now() - start_time).total_seconds()
            cache_stats = self.services['cache'].get_stats()
            self.logger.info(f"⏱️ 执行耗时: {duration:.2f}s | 缓存命中率: {cache_stats['hit_rate']:.1%}")
            self.logger.info("🏁 流程执行完毕")
            
        except KeyboardInterrupt:
            self.logger.info("⌨️ 用户中断执行")
        except Exception as e:
            self.logger.error(f"❌ 系统运行异常: {e}", exc_info=True)
            raise
        finally:
            self._cleanup()
    
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
    
    def _persist_results(self, results: list):
        """持久化计算结果（JSON + 可选数据库）"""
        output_dir = PROJECT_ROOT / "output" / "results"
        output_dir.mkdir(parents=True, exist_ok=True)
        
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        json_path = output_dir / f"dynamic_prices_{ts}.json"
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(results, f, ensure_ascii=False, indent=2, default=str)
        self.logger.info(f"💾 结果已保存: {json_path}")
        
        # 可扩展：写入 PostgreSQL / CSV / 消息队列
        # if hasattr(self.services['db'], 'insert_batch'):
        #     self.services['db'].insert_batch('dynamic_prices', results)

    def _generate_visualizations(self, batch_results: List[Dict], single_results: Optional[List[Dict]] = None):
        """
        生成可视化图表（单标的 + 批量）
        
        参数:
            batch_results: 批量计算结果列表
            single_results: 单标的详细结果（可选，用于深度分析）
        """
        if not self.services.get('viz'):
            self.logger.info("⏭️ 可视化服务未启用，跳过图表生成")
            return
        
        viz_service = self.services['viz']
        conf_dashboard = self.services.get('conf_dashboard')
        export_format = self.args.export
        output_dir = PROJECT_ROOT / "output" / "visualization"
        output_dir.mkdir(parents=True, exist_ok=True)
        
        start_time = datetime.now()
        generated_count = 0
        
        self.logger.info(f"🎨 开始生成可视化图表 | 格式: {export_format} | 标的数: {len(batch_results)}")
        
        try:
            # ========== 1. 单标的深度分析（可选，仅当 --stocks 指定时生成） ==========
            if single_results and self.args.stocks:  # 只生成指定标的的深度分析
                self.logger.info(f"📊 生成 {len(single_results)} 个单标的深度分析...")
                
                for result in single_results:
                    try:
                        code = result['code']
                        name = result['name']
                        
                        # 1.1 价格区间 + 因子分解图
                        viz_outputs = viz_service.visualize_single_result(
                            result,
                            chart_types=['price_interval', 'factor_decomposition'],
                            output_format=export_format
                        )
                        
                        # 1.2 置信度面板（如果启用）
                        if conf_dashboard and 'technical_quality' in result:
                            # 需要额外数据：指标 + 历史置信度（此处简化）
                            fig_conf = conf_dashboard.create_single_stock_dashboard(
                                code=code,
                                name=name,
                                confidence_result=result['technical_quality'],
                                indicators=result.get('signals', {}),
                                stock_data=None,  # 实际应传入
                                historical_confidence=None
                            )
                            conf_path = output_dir / f"{code}_confidence.{export_format}"
                            viz_service.renderer.export(fig_conf, str(conf_path), format=export_format)
                            self.logger.debug(f"✅ 置信度面板: {conf_path.name}")
                        
                        if viz_outputs:
                            generated_count += len(viz_outputs)
                            self.logger.debug(f"✅ {code} 可视化: {list(viz_outputs.keys())}")
                            
                    except Exception as e:
                        self.logger.warning(f"⚠️ 生成 {result.get('code', 'unknown')} 单标可视化失败: {e}")
                        continue
            
            # ========== 2. 批量对比面板（必选） ==========
            if batch_results:
                self.logger.info("📊 生成批量对比面板...")
                
                # 2.1 组合分布图
                portfolio_path = viz_service.visualize_batch_results(
                    batch_results,
                    chart_type='portfolio_comparison',
                    output_format=export_format
                )
                if portfolio_path:
                    generated_count += 1
                    self.logger.info(f"✅ 组合对比图: {Path(portfolio_path).name}")
                
                # 2.2 风险矩阵图（波动率×盈亏比）
                if all('volatility' in r.get('signals', {}) or 'volatility' in r for r in batch_results):
                    risk_path = viz_service.visualize_batch_results(
                        batch_results,
                        chart_type='risk_matrix',
                        output_format=export_format
                    )
                    if risk_path:
                        generated_count += 1
                        self.logger.info(f"✅ 风险矩阵图: {Path(risk_path).name}")
                
                # 2.3 置信度筛选面板（如果包含 technical_quality）
                if conf_dashboard and any('technical_quality' in r for r in batch_results):
                    # 过滤出有置信度数据的标的
                    conf_results = [r for r in batch_results if 'technical_quality' in r]
                    if conf_results:
                        conf_fig = conf_dashboard.create_batch_comparison_dashboard(
                            conf_results,
                            filter_config={'min_confidence': 0.99, 'min_pl_ratio': 2.0}
                        )
                        conf_batch_path = output_dir / f"confidence_batch_{datetime.now().strftime('%Y%m%d')}.{export_format}"
                        viz_service.renderer.export(conf_fig, str(conf_batch_path), format=export_format)
                        generated_count += 1
                        self.logger.info(f"✅ 置信度筛选面板: {conf_batch_path.name}")
                
                # 2.4 生成汇总报告（HTML + JSON）
                if export_format == 'html':
                    report_path = self._generate_summary_report(batch_results, output_dir)
                    if report_path:
                        generated_count += 1
                        self.logger.info(f"✅ 汇总报告: {Path(report_path).name}")
            
            # ========== 3. 性能统计 ==========
            duration = (datetime.now() - start_time).total_seconds()
            self.logger.info(
                f"🎨 可视化生成完成 | 生成 {generated_count} 个图表 | 耗时: {duration:.2f}s | "
                f"平均: {duration/max(1,generated_count):.2f}s/图表"
            )
            
        except Exception as e:
            self.logger.error(f"❌ 可视化生成异常: {e}", exc_info=True)
        
        return generated_count

    def _generate_summary_report(self, results: List[Dict], output_dir: Path) -> Optional[str]:
        """
        生成汇总报告（修复版：兼容 domain/xy 子图类型）
        """
        try:
            import numpy as np
            import plotly.graph_objects as go
            from plotly.subplots import make_subplots
            
            if not results:
                self.logger.warning("⚠️ 无计算结果，跳过汇总报告生成")
                return None
            
            # 1. 数据准备
            pl_ratios = [r['scores']['pl_ratio'] for r in results if 'scores' in r and 'pl_ratio' in r['scores']]
            conf_factors = [r.get('technical_quality', {}).get('factor', 1.0) for r in results if 'technical_quality' in r]
            
            summary = {
                'timestamp': datetime.now().isoformat(),
                'total_stocks': len(results),
                'by_sector': {},
                'by_recommendation': {},
                'metrics': {
                    'avg_pl_ratio': round(float(np.mean(pl_ratios)), 2) if pl_ratios else 0.0,
                    'avg_confidence': round(float(np.mean(conf_factors)), 3) if conf_factors else 1.0,
                    'high_confidence_count': sum(1 for r in results if r.get('technical_quality', {}).get('level') == 'high'),
                }
            }
            
            for r in results:
                summary['by_sector'][r.get('sector', '未知')] = summary['by_sector'].get(r.get('sector', '未知'), 0) + 1
                summary['by_recommendation'][r.get('recommendation', '未知')] = summary['by_recommendation'].get(r.get('recommendation', '未知'), 0) + 1
            
            # 2. 创建子图（明确类型声明）
            fig = make_subplots(
                rows=2, cols=2,
                subplot_titles=['板块分布', '建议分布', '盈亏比分布', '置信度分布'],
                specs=[
                    [{'type': 'pie'}, {'type': 'pie'}],      # domain 类型
                    [{'type': 'histogram'}, {'type': 'histogram'}]  # xy 类型
                ],
                vertical_spacing=0.12,
                horizontal_spacing=0.1
            )
            
            # 2.1 板块分布饼图 (1,1) ✅ 使用 trace 自带文本，不额外加 annotation
            fig.add_trace(go.Pie(
                labels=list(summary['by_sector'].keys()),
                values=list(summary['by_sector'].values()),
                name='板块',
                textinfo='label+percent',
                textposition='auto',
                insidetextfont=dict(size=10),
                hovertemplate='<b>%{label}</b><br>数量：%{value}<extra></extra>'
            ), row=1, col=1)
            
            # 2.2 建议分布饼图 (1,2) ✅ 同上
            color_map = {'强烈推荐': '#2ca02c', '推荐': '#1f77b4', '观望': '#ff7f0e', '谨慎': '#d62728'}
            fig.add_trace(go.Pie(
                labels=list(summary['by_recommendation'].keys()),
                values=list(summary['by_recommendation'].values()),
                marker_colors=[color_map.get(k, '#7f7f7f') for k in summary['by_recommendation'].keys()],
                name='建议',
                textinfo='label+percent',
                insidetextfont=dict(size=10),
                hovertemplate='<b>%{label}</b><br>数量：%{value}<extra></extra>'
            ), row=1, col=2)
            
            # 2.3 盈亏比直方图 (2,1) ✅ xy 类型支持 add_vline
            if pl_ratios:
                fig.add_trace(go.Histogram(
                    x=pl_ratios, name='盈亏比', marker_color='#1f77b4', nbinsx=20,
                    hovertemplate='<b>盈亏比</b><br>%{x:.1f}x<extra></extra>'
                ), row=2, col=1)
                
                # 安全添加参考线（带降级）
                try:
                    fig.add_vline(
                        x=2.0, line_dash='dash', line_color='blue',
                        annotation_text='阈值', annotation_position='top right',
                        row=2, col=1
                    )
                except Exception:
                    fig.add_annotation(
                        x=2.0, y=0.95, text='阈值', showarrow=False,
                        bgcolor='lightblue', font=dict(size=9),
                        xref='x', yref='paper', row=2, col=1
                    )
            
            # 2.4 置信度直方图 (2,2) ✅ 同上
            if conf_factors:
                fig.add_trace(go.Histogram(
                    x=conf_factors, name='置信度', marker_color='#2ca02c', nbinsx=20,
                    hovertemplate='<b>置信度</b><br>%{x:.3f}<extra></extra>'
                ), row=2, col=2)
                
                try:
                    fig.add_vline(
                        x=1.0, line_dash='dash', line_color='gray',
                        annotation_text='中性', annotation_position='top right',
                        row=2, col=2
                    )
                except Exception:
                    fig.add_annotation(
                        x=1.0, y=0.95, text='中性', showarrow=False,
                        bgcolor='lightgray', font=dict(size=9),
                        xref='x', yref='paper', row=2, col=2
                    )
            
            # 3. 统一布局
            fig.update_layout(
                title=f"📊 AiStock 计算汇总报告 ({datetime.now().strftime('%Y-%m-%d')})",
                height=850,
                showlegend=False,
                hovermode='closest',
                template='plotly_white',
                margin=dict(l=40, r=40, t=60, b=50)
            )
            
            # 4. 全局底部指标卡片 ✅ 去掉 row/col，使用 paper 坐标
            fig.add_annotation(
                x=0.5, y=-0.04,
                text=f"标的数: {summary['total_stocks']} | 平均盈亏比: {summary['metrics']['avg_pl_ratio']:.2f}x | 高置信度: {summary['metrics']['high_confidence_count']} 只",
                showarrow=False, bgcolor='rgba(240,240,240,0.9)', font=dict(size=11),
                xref='paper', yref='paper'  # ✅ 不传 row/col
            )
            
            # 5. 导出
            report_path = output_dir / f"summary_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html"
            fig.write_html(str(report_path), include_plotlyjs='cdn', full_html=True)
            
            json_path = output_dir / f"summary_{datetime.now().strftime('%Y%m%d')}.json"
            with open(json_path, 'w', encoding='utf-8') as f:
                json.dump(summary, f, ensure_ascii=False, indent=2, default=str)
            
            self.logger.info(f"✅ 汇总报告已生成: {report_path.name}")
            return str(report_path)
            
        except Exception as e:
            self.logger.warning(f"⚠️ 生成汇总报告异常: {e}", exc_info=True)
            return None
    
    def _cleanup(self):
        """优雅关闭所有服务资源"""
        self.logger.info("🧹 清理服务资源...")
        
        for name, svc in self.services.items():
            if not svc:
                continue
            try:
                if hasattr(svc, 'close'):
                    svc.close()
                elif hasattr(svc, 'stop_watcher'):  # ConfigService
                    svc.stop_watcher()
            except Exception as e:
                self.logger.debug(f"清理 {name} 失败: {e}")
        
        # 清理可视化缓存（可选）
        if self.services.get('viz') and hasattr(self.services['viz'], 'clear_cache'):
            try:
                self.services['viz'].clear_cache()
                self.logger.debug("✅ 可视化缓存已清理")
            except:
                pass
        
        self.logger.info("✅ 资源清理完成")

# ==================== 入口函数 ====================
def main():
    args = parse_args()
    runner = DynamicPriceRunner(args)
    runner.run()


if __name__ == '__main__':
    main()