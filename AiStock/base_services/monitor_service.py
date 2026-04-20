# monitor_service.py
import logging
import asyncio
from datetime import datetime
from typing import Dict, List, Optional
from pathlib import Path

from base_services.config_service import ConfigService
from data_services.data_loading_service import DataLoadingService
from dynamic_price_system.portfolio.tracker import PortfolioTracker
from visualization.services.visualization_service import VisualizationService
from utils.alert_utils import send_dingtalk_alert, send_email_digest

logger = logging.getLogger(__name__)

class MonitorService:
    def __init__(self, config: ConfigService):
        self.config = config
        self.cfg = config.get('monitor', {})
        self.dashboard_cfg = self.cfg.get('dashboard', {})
        self.alert_cfg = self.cfg.get('alerts', {})
        self.health_cfg = self.cfg.get('health_checks', {})
        
        # 依赖注入
        self.loader = DataLoadingService(config)
        self.portfolio = PortfolioTracker(initial_capital=config.get('portfolio.initial_capital', 1_000_000))
        self.viz = VisualizationService()
        
        # 运行时状态
        self._circuit_breaker_active = False
        self._last_alert_time = {}
        self._health_status = {}
        
    async def run_monitoring_cycle(self, mode: str = "intraday"):
        """主监控循环（支持盘中/盘后/夜间模式）"""
        try:
            # 1. 数据刷新
            market_prices = await self._fetch_latest_prices()
            self.portfolio.update_prices(market_prices)
            
            # 2. 风控检查
            alerts = self._check_risk_alerts(market_prices)
            if alerts:
                await self._dispatch_alerts(alerts)
                
            # 3. 熔断判断
            if self._check_circuit_breaker():
                logger.critical("🚨 触发组合熔断，已暂停自动调仓")
                return {"status": "circuit_breaker", "alerts": alerts}
                
            # 4. 仪表盘更新
            if self.dashboard_cfg.get('auto_save_snapshot'):
                snapshot = self._generate_dashboard_snapshot()
                self._save_snapshot(snapshot)
                
            # 5. 健康检查
            health = await self._run_health_checks()
            self._health_status.update(health)
            
            return {"status": "ok", "alerts": alerts, "health": health}
            
        except Exception as e:
            logger.error(f"❌ 监控循环异常: {e}", exc_info=True)
            return {"status": "error", "message": str(e)}
    
    def _check_risk_alerts(self, prices: Dict[str, float]) -> List[Dict]:
        """检查价格/组合/集中度预警"""
        alerts = []
        portfolio_value = self.portfolio.get_portfolio_value()
        positions = self.portfolio.get_positions()
        
        # 标的级预警
        for code, pos in positions.items():
            current = prices.get(code, 0)
            cost = pos['cost']
            weight = pos['market_value'] / portfolio_value if portfolio_value > 0 else 0
            
            # 涨跌阈值
            pnl_pct = (current - cost) / cost
            if pnl_pct < self.alert_cfg['price']['drop_threshold']:
                alerts.append({"type": "price_drop", "code": code, "pct": pnl_pct})
            if weight > self.alert_cfg['portfolio']['concentration_alert']:
                alerts.append({"type": "concentration", "code": code, "weight": weight})
                
        # 组合级预警
        daily_pnl = self.portfolio.calculate_daily_pnl()
        if daily_pnl < self.alert_cfg['portfolio']['daily_loss_limit']:
            alerts.append({"type": "daily_loss", "value": daily_pnl})
            
        return alerts
    
    def _check_circuit_breaker(self) -> bool:
        """检查是否触发熔断"""
        if not self.alert_cfg['circuit_breaker']['enabled']:
            return False
            
        drawdown = self.portfolio.calculate_max_drawdown()
        threshold = self.alert_cfg['circuit_breaker']['threshold']
        
        if drawdown <= threshold and not self._circuit_breaker_active:
            self._circuit_breaker_active = True
            self._breaker_start_time = datetime.now()
            logger.critical(f" 熔断触发: 回撤 {drawdown:.2%} ≤ {threshold:.0%}")
            return True
            
        if self._circuit_breaker_active:
            cooldown = self.alert_cfg['circuit_breaker']['cooldown_minutes']
            elapsed = (datetime.now() - self._breaker_start_time).total_seconds() / 60
            if elapsed >= cooldown:
                self._circuit_breaker_active = False
                logger.info("🟢 熔断冷却结束，恢复监控")
            return True  # 冷却期内持续返回 True
            
        return False
    
    async def _dispatch_alerts(self, alerts: List[Dict]):
        """告警路由与频率抑制"""
        for alert in alerts:
            key = f"{alert['type']}_{alert.get('code', 'portfolio')}"
            now = datetime.now()
            
            # 频率抑制（防告警风暴）
            last = self._last_alert_time.get(key)
            freq = self.alert_cfg['notifications']['dingtalk'].get('frequency', 'realtime')
            if freq == 'realtime' or not last or (now - last).total_seconds() > 300:
                await send_dingtalk_alert(self.cfg['notifications']['dingtalk']['webhook'], alert)
                self._last_alert_time[key] = now
                
    async def _run_health_checks(self) -> Dict:
        """系统健康巡检"""
        checks = {}
        # 示例：数据新鲜度检查
        last_update = self.loader.get_last_update_time()
        delay = (datetime.now() - last_update).total_seconds()
        checks['data_freshness'] = delay < self.health_cfg['data_freshness']
        
        # 可扩展：API延迟、DB连接、缓存命中率等
        return checks
    
    def _generate_dashboard_snapshot(self) -> Dict:
        """生成可视化看板数据（供 VisualizationService 渲染）"""
        return {
            'nav_curve': self.portfolio.get_nav_history(),
            'position_pie': self.portfolio.get_sector_weights(),
            'risk_gauges': {
                'drawdown': self.portfolio.calculate_max_drawdown(),
                'daily_pnl': self.portfolio.calculate_daily_pnl(),
                'sharpe_rolling': self.portfolio.calculate_rolling_sharpe()
            },
            'alert_log': self._last_alert_time,
            'health': self._health_status
        }