#!/usr/bin/env python3
"""
AiStock V10 — 子系统包 (Subsystems)

所有子系统均继承 SubsystemBase, 通过 ServiceContainer 注入共享服务。

已注册子系统:
  - market_state: 市场状态量化子系统
"""
from __future__ import annotations

from base_service.service_container import SubsystemBase

__all__ = ["SubsystemBase"]
