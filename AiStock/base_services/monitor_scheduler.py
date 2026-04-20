#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AsyncMonitorScheduler：异步监控循环调度器
职责：
  - 基于交易时段自动切换运行模式（盘前/盘中/盘后/夜间）
  - 非阻塞异步循环 + 任务超时控制
  - 熔断联动 + 优雅停机 + 信号处理
  - 周期指标采集与可观测性埋点
"""

import asyncio
import signal
import logging
import yaml
from datetime import datetime, time, timedelta
from typing import Dict, Optional, Any
from enum import Enum
from dataclasses import dataclass, field
import os

logger = logging.getLogger(__name__)


class MarketMode(Enum):
    """交易时段模式"""
    PRE_MARKET = "pre_market"       # 08:30-09:15
    INTRA_DAY = "intra_day"         # 09:15-15:00
    POST_MARKET = "post_market"     # 15:00-15:30
    NIGHTLY = "nightly"             # 15:30-08:30
    HALTED = "halted"               # 熔断/人工暂停


@dataclass
class SchedulerMetrics:
    """调度器运行指标"""
    cycles_run: int = 0
    cycles_failed: int = 0
    last_cycle_duration: float = 0.0
    last_success_time: Optional[datetime] = None
    current_mode: MarketMode = MarketMode.NIGHTLY
    breaker_active: bool = False


class AsyncMonitorScheduler:
    def __init__(
        self,
        config_path: str,
        monitor_service,
        risk_controller,
        notification_service,
        loop: Optional[asyncio.AbstractEventLoop] = None
    ):
        self.config = self._load_config(config_path)
        self.monitor = monitor_service
        self.risk = risk_controller
        self.notifier = notification_service
        self.loop = loop or asyncio.get_event_loop()
        
        self.metrics = SchedulerMetrics()
        self._stop_event = asyncio.Event()
        self._breaker_triggered_at: Optional[datetime] = None
        
        self._setup_signal_handlers()
        logger.info("✅ AsyncMonitorScheduler 初始化完成")

    def _load_config(self, path: str) -> Dict:
        with open(path, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f)

    def _setup_signal_handlers(self):
        """注册优雅停机信号"""
        for sig in (signal.SIGINT, signal.SIGTERM):
            self.loop.add_signal_handler(sig, self._request_stop)

    def _request_stop(self):
        logger.warning("🛑 收到终止信号，准备优雅停机...")
        self._stop_event.set()

    # ==================== 模式路由 ====================
    def _update_market_mode(self) -> None:
        """根据当前时间切换运行模式"""
        now = datetime.now().time()
        scheduler_cfg = self.config.get('scheduler', {})
        
        # 可配置交易时段（默认A股）
        pre_start = time.fromisoformat(scheduler_cfg.get('pre_market_start', '08:30'))
        market_open = time.fromisoformat(scheduler_cfg.get('market_open', '09:15'))
        market_close = time.fromisoformat(scheduler_cfg.get('market_close', '15:00'))
        post_end = time.fromisoformat(scheduler_cfg.get('post_market_end', '15:30'))
        
        if self.metrics.breaker_active:
            cooldown = scheduler_cfg.get('circuit_breaker_cooldown_minutes', 60)
            if self._breaker_triggered_at and \
               (datetime.now() - self._breaker_triggered_at).total_seconds() >= cooldown * 60:
                self.metrics.breaker_active = False
                self._breaker_triggered_at = None
                logger.info("🟢 熔断冷却结束，恢复监控")
            else:
                self.metrics.current_mode = MarketMode.HALTED
                return

        if pre_start <= now < market_open:
            self.metrics.current_mode = MarketMode.PRE_MARKET
        elif market_open <= now < market_close:
            self.metrics.current_mode = MarketMode.INTRA_DAY
        elif market_close <= now < post_end:
            self.metrics.current_mode = MarketMode.POST_MARKET
        else:
            self.metrics.current_mode = MarketMode.NIGHTLY

    def _get_sleep_interval(self) -> float:
        """根据模式返回休眠间隔(秒)"""
        intervals = self.config.get('intervals', {})
        mode = self.metrics.current_mode.value
        return float(intervals.get(mode, intervals.get('default', 30)))

    # ==================== 主循环 ====================
    async def start(self):
        logger.info("🚀 异步监控调度器启动 | 模式: %s", self.metrics.current_mode.value)
        try:
            while not self._stop_event.is_set():
                self._update_market_mode()
                if self.metrics.current_mode == MarketMode.HALTED:
                    await asyncio.sleep(60)
                    continue
                    
                await self._execute_mode_cycle()
                self.metrics.cycles_run += 1
                await asyncio.sleep(self._get_sleep_interval())
                
        except asyncio.CancelledError:
            logger.info("🛑 调度器循环已取消")
        except Exception as e:
            logger.error(f"❌ 调度器致命异常: {e}", exc_info=True)
        finally:
            await self._graceful_shutdown()

    async def _execute_mode_cycle(self):
        """执行当前模式对应的监控周期"""
        start = datetime.now()
        mode = self.metrics.current_mode
        
        try:
            if mode == MarketMode.INTRA_DAY:
                await self._run_intraday_cycle()
            elif mode == MarketMode.POST_MARKET:
                await self._run_post_market_cycle()
            elif mode == MarketMode.NIGHTLY:
                await self._run_nightly_cycle()
            # PRE_MARKET 通常只做轻量健康检查，可复用 intraday 或单独实现
            elif mode == MarketMode.PRE_MARKET:
                await self._run_pre_market_cycle()
                
            self.metrics.last_success_time = datetime.now()
        except Exception as e:
            self.metrics.cycles_failed += 1
            logger.error(f"⚠️ 模式 {mode.value} 周期执行失败: {e}")
        finally:
            self.metrics.last_cycle_duration = (datetime.now() - start).total_seconds()

    # ==================== 周期任务实现 ====================
    async def _run_intraday_cycle(self):
        """盘中监控周期（高频/实时）"""
        logger.debug("🔍 执行盘中监控周期")
        # 1. 刷新行情与持仓
        await asyncio.to_thread(self.monitor.update_prices_from_market)
        
        # 2. 风控检查
        alerts = await asyncio.to_thread(self.risk.check_realtime_alerts)
        if alerts:
            await self._dispatch_alerts(alerts, priority='high')
            
        # 3. 熔断判断
        if self.risk.is_circuit_breaker_triggered():
            self.metrics.breaker_active = True
            self._breaker_triggered_at = datetime.now()
            await self.notifier.send_system_alert("🚨 触发组合熔断，暂停调仓与高风险监控")
            return
            
        # 4. 仪表盘快照
        await asyncio.to_thread(self.monitor.save_dashboard_snapshot)

    async def _run_post_market_cycle(self):
        """盘后结算周期（中频）"""
        logger.debug("📊 执行盘后结算周期")
        await asyncio.to_thread(self.monitor.calculate_daily_pnl)
        await asyncio.to_thread(self.monitor.generate_settlement_report)
        await self.notifier.send_digest("📈 盘后结算完成，日报已生成")

    async def _run_nightly_cycle(self):
        """夜间批处理周期（低频/重型）"""
        logger.debug("🌙 执行夜间批处理周期")
        await asyncio.to_thread(self.monitor.run_backtest_validation)
        await asyncio.to_thread(self.monitor.archive_data)
        await asyncio.to_thread(self.monitor.clear_stale_cache)
        # 重载配置（支持热更新）
        self.config = self._load_config(self.config_path)

    async def _run_pre_market_cycle(self):
        """盘前准备周期"""
        logger.debug("🌅 执行盘前检查周期")
        await asyncio.to_thread(self.monitor.check_data_freshness)
        await asyncio.to_thread(self.risk.reset_daily_counters)
        await self.notifier.send_system_alert("✅ 盘前检查完成，系统就绪")

    # ==================== 辅助方法 ====================
    async def _dispatch_alerts(self, alerts: list, priority: str = 'normal'):
        """告警分发与频率抑制"""
        freq_cfg = self.config.get('notifications', {}).get('frequency_control', {})
        for alert in alerts:
            key = f"{alert.get('type')}_{alert.get('code', 'portfolio')}"
            now = datetime.now()
            last = self.notifier.get_last_sent_time(key)
            min_interval = freq_cfg.get(priority, 300)
            
            if not last or (now - last).total_seconds() >= min_interval:
                await self.notifier.send(alert, channel='dingtalk')
                self.notifier.record_sent_time(key, now)

    async def _graceful_shutdown(self):
        """优雅停机"""
        logger.info("🧹 执行优雅停机流程...")
        try:
            await asyncio.to_thread(self.monitor.flush_buffers)
            await self.notifier.send_system_alert("🛑 监控调度器已安全关闭")
        except Exception as e:
            logger.error(f"⚠️ 停机清理异常: {e}")
        logger.info("✅ 调度器已完全停止")

    def stop(self):
        """外部调用停止"""
        self._request_stop()