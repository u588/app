#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
V7.0 RiskAssessmentEngine — 风险评估与期权PCR分析引擎
修复 V6.0 np.random.uniform 伪造PCR → V7.0 真实期权链持仓量驱动
模块: PCR分析 / 微盘流动性 / 风险预警 / 估值评估(PE+ERP)
"""

from __future__ import annotations
import logging
from datetime import datetime
from typing import Dict, List, Optional
import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

# ── PCR 信号阈值 ────────────────────────────────────────
_PCR_EXT_HIGH = 1.20   # 极度看空（put远超call）
_PCR_WARN_HIGH = 1.00  # 偏看空
_PCR_EXT_LOW = 0.50   # 极度看多（call远超put）
_PCR_WARN_LOW = 0.65  # 偏看多

# ── 微盘流动性阶段阈值 ─────────────────────────────────
_MICRO_NORM = 0.85     # 正常
_MICRO_WARN = 0.70    # 预警
_MICRO_MELT = 0.50    # 熔融

# ── 基差预警阈值（%） ───────────────────────────────────
_BASIS_EXT_DEEP = -2.0   # 极度贴水
_BASIS_WARN_DEEP = -1.5  # 贴水预警
_BASIS_EXT_HIGH = 1.5    # 极度升水

# ── ERP 参数 ─────────────────────────────────────────────
_DEF_BOND = 2.8        # 默认十年期国债收益率(%)
_ERP_OVER = -1.0       # ERP低于此 → 高估
_ERP_UNDER = 4.0       # ERP高于此 → 低估


class RiskAssessmentEngine:
    """V7 风险评估引擎 — PCR + 微盘流动性 + 估值 + 预警

    公共接口:
      calculate_pcr()           — 单标的PCR（真实持仓量驱动）
      calculate_composite_pcr() — 加权合成PCR
      assess_micro_liquidity()  — 微盘流动性（932000 vs 399311）
      generate_risk_alerts()    — 风险预警
      assess_valuation()        — 估值(PE百分位+ERP)
    """

    def __init__(self, data_service, contract_manager=None, config: Optional[Dict] = None):
        """依赖注入初始化。

        Args:
            data_service:      DataLoadingService 实例
            contract_manager:  ContractManager 实例（可选）
            config:            配置字典，需含 option_underlying_mapping / risk_thresholds
        """
        self.data_service = data_service
        self.contract_manager = contract_manager
        self.config = config or {}
        self.logger = logger

        # 期权标的映射: {IO: {spot_code, market_code, market_type, weight, default_price}, ...}
        self.underlying_mapping: Dict[str, Dict] = self.config.get(
            "option_underlying_mapping", self._default_underlying_mapping())

        # 风险阈值（允许配置覆盖）
        rt = self.config.get("risk_thresholds", {})
        self._peh = rt.get("pcr_extreme_high", _PCR_EXT_HIGH)
        self._pwh = rt.get("pcr_warning_high", _PCR_WARN_HIGH)
        self._pel = rt.get("pcr_extreme_low", _PCR_EXT_LOW)
        self._pwl = rt.get("pcr_warning_low", _PCR_WARN_LOW)

        self.logger.info(
            f"RiskAssessmentEngine V7 初始化 | "
            f"标的={len(self.underlying_mapping)} | "
            f"PCR阈值=[{self._pel:.2f}, {self._peh:.2f}]")

    # ── 1. 期权 PCR 分析 ──────────────────────────────────

    def calculate_pcr(self, underlying: str, market_code: int, market_type: str,
                      current_price: float, days: int = 5) -> Dict:
        """计算单标的PCR（Put-Call Ratio）。

        修复 V6 的 np.random.uniform 伪造问题：
          - 从 contract_manager 获取真实期权链
          - 用 data_service 加载每个合约的持仓量/成交量
          - ATM 动态容差过滤，排除深度虚值噪声
          - PCR = put_oi / call_oi（持仓量优先，成交量 fallback）

        Args:
            underlying:    标的代码 (IO / 510300 / ...)
            market_code:   TDX 市场代码
            market_type:   V7 市场类型字符串
            current_price: 标的当前价格
            days:          近N日数据窗口
        """
        res = {"underlying": underlying, "current_price": current_price,
               "pcr_oi": None, "pcr_volume": None, "call_oi": 0.0, "put_oi": 0.0,
               "call_vol": 0.0, "put_vol": 0.0, "atm_contracts": 0, "signal": "数据不足"}
        # 获取期权链
        group = (self.contract_manager.get_option_contracts(underlying, market_code, market_type)
                 if self.contract_manager else None)
        if group is None or (not group.call_codes and not group.put_codes):
            self.logger.warning(f"PCR: {underlying} 无期权链")
            return self._fallback_pcr(underlying, current_price)
        # ATM动态容差: ETF±2%, 指数期权±3%
        is_etf = underlying.isdigit() or underlying[0] in "15"
        tol = 0.02 if is_etf else 0.03
        p_lo, p_hi = current_price * (1 - tol), current_price * (1 + tol)
        # 汇总ATM合约持仓量/成交量
        c_oi, p_oi, c_vol, p_vol, atm_n = 0.0, 0.0, 0.0, 0.0, 0
        for codes, side in [(group.call_codes, "C"), (group.put_codes, "P")]:
            for code in codes:
                df = self.data_service.load_derivative_data(code, market_type, days=days)
                if df is None or df.empty:
                    continue
                row = df.iloc[-1]
                strike = float(row.get("close", 0))
                if p_lo <= strike <= p_hi:
                    atm_n += 1
                    oi = float(row.get("open_interest", row.get("position", 0)))
                    vol = float(row.get("volume", 0))
                    if side == "C": c_oi += oi; c_vol += vol
                    else: p_oi += oi; p_vol += vol
        # ATM无命中 → 全合约
        if atm_n == 0:
            self.logger.info(f"PCR: {underlying} ATM无命中，使用全合约")
            c_oi, p_oi, c_vol, p_vol = 0.0, 0.0, 0.0, 0.0
            for codes, side in [(group.call_codes, "C"), (group.put_codes, "P")]:
                for code in codes:
                    df = self.data_service.load_derivative_data(code, market_type, days=days)
                    if df is None or df.empty: continue
                    row = df.iloc[-1]
                    oi = float(row.get("open_interest", row.get("position", 0)))
                    vol = float(row.get("volume", 0))
                    if side == "C": c_oi += oi; c_vol += vol
                    else: p_oi += oi; p_vol += vol
            atm_n = len(group.call_codes) + len(group.put_codes)
        # PCR计算: 持仓量优先, 成交量fallback
        pcr_oi = (p_oi / c_oi) if c_oi > 0 else None
        pcr_vol = (p_vol / c_vol) if c_vol > 0 else None
        pcr_val = pcr_oi if pcr_oi is not None else pcr_vol
        res.update({"pcr_oi": round(pcr_oi, 4) if pcr_oi else None,
                    "pcr_volume": round(pcr_vol, 4) if pcr_vol else None,
                    "call_oi": c_oi, "put_oi": p_oi, "call_vol": c_vol, "put_vol": p_vol,
                    "atm_contracts": atm_n, "signal": self._pcr_signal(pcr_val)})
        return res

    def calculate_composite_pcr(self) -> Dict:
        """加权合成PCR — 跨标的加权。

        覆盖标的: IO, MO, 510300, 510500, 588000, 159915
        权重来自 option_underlying_mapping 的 weight 字段。

        Returns:
            {composite_pcr, components, signal, timestamp}
        """
        comps, w_pcr, tw = {}, 0.0, 0.0
        for und, cfg in self.underlying_mapping.items():
            mc, mt, w = cfg.get("market_code", 7), cfg.get("market_type", "option_zj"), cfg.get("weight", 0.20)
            spot = cfg.get("spot_code", und)
            price = self._fetch_spot_price(spot) or cfg.get("default_price", 0)
            if price <= 0:
                self.logger.warning(f"CompositePCR: {und} 无有效价格"); continue
            pr = self.calculate_pcr(und, mc, mt, price)
            pv = pr.get("pcr_oi") or pr.get("pcr_volume")
            comps[und] = {"pcr": pv, "weight": w, "signal": pr.get("signal", "N/A")}
            if pv is not None: w_pcr += pv * w; tw += w
        comp = (w_pcr / tw) if tw > 0 else None
        return {"composite_pcr": round(comp, 4) if comp else None,
                "components": comps, "signal": self._pcr_signal(comp),
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")}

    # ── 2. 微盘流动性评估 ────────────────────────────────

    def assess_micro_liquidity(self) -> Dict:
        """评估微盘股流动性 — 932000(中证2000) vs 399311(国证2000) 相关性。

        当两个微盘指数走势相关性下降时，表明微盘内部出现分化，
        可能预示流动性危机。阶段划分:
          - normal:        corr >= 0.85
          - early_warning: 0.70 <= corr < 0.85
          - watch:         0.50 <= corr < 0.70
          - melted:        corr < 0.50

        Returns:
            {correlation, stage, zz2000_return, gz2000_return, divergence, description}
        """
        res = {"correlation": None, "stage": "normal", "zz2000_return": None,
               "gz2000_return": None, "divergence": None, "description": "数据不足"}
        df_zz = self.data_service.load_index_data("932000", min_days=30)
        df_gz = self.data_service.load_index_data("399311", min_days=30)
        if df_zz is None or df_gz is None or len(df_zz) < 10 or len(df_gz) < 10:
            self.logger.warning("微盘流动性: 数据不足"); return res
        ml = min(len(df_zz), len(df_gz))
        r_zz = df_zz["close"].pct_change().dropna().tail(ml - 1)
        r_gz = df_gz["close"].pct_change().dropna().tail(ml - 1)
        al = min(len(r_zz), len(r_gz))
        if al < 5: return res
        corr = float(np.corrcoef(r_zz.tail(al).values, r_gz.tail(al).values)[0, 1])
        if np.isnan(corr): corr = 0.0
        ret_zz = float(df_zz["close"].iloc[-1] / df_zz["close"].iloc[0] - 1)
        ret_gz = float(df_gz["close"].iloc[-1] / df_gz["close"].iloc[0] - 1)
        div = abs(ret_zz - ret_gz) * 100
        if corr >= _MICRO_NORM:    stage, desc = "normal", "微盘流动性正常"
        elif corr >= _MICRO_WARN:  stage, desc = "early_warning", "微盘分化预警：中证2000与国证2000相关性下降"
        elif corr >= _MICRO_MELT:  stage, desc = "watch", "微盘流动性紧张：两指数显著分化"
        else:                      stage, desc = "melted", "微盘流动性熔融：极端分化，小盘风险极高"
        res.update({"correlation": round(corr, 4), "stage": stage,
                    "zz2000_return": round(ret_zz, 4), "gz2000_return": round(ret_gz, 4),
                    "divergence": round(div, 2), "description": desc})
        return res

    # ── 3. 风险预警生成 ──────────────────────────────────

    def generate_risk_alerts(self, market_state: str, pcr_value: Optional[float],
                             micro_liquidity: Dict, basis_value: Optional[float]) -> List[Dict]:
        """基于多维信号生成风险预警列表。

        Args:
            market_state:    九宫格状态名
            pcr_value:       合成PCR值
            micro_liquidity: assess_micro_liquidity() 结果
            basis_value:     基差百分比

        Returns:
            [{level, category, message, value}]  level: critical/warning/info
        """
        alerts: List[Dict] = []
        # PCR极端
        if pcr_value is not None:
            if pcr_value >= self._peh:
                alerts.append({"level": "critical", "category": "pcr_extreme",
                    "message": f"PCR极端看空({pcr_value:.2f})，市场恐慌性买入看跌期权", "value": pcr_value})
            elif pcr_value >= self._pwh:
                alerts.append({"level": "warning", "category": "pcr_high",
                    "message": f"PCR偏看空({pcr_value:.2f})，看跌持仓高于看涨", "value": pcr_value})
            if pcr_value <= self._pel:
                alerts.append({"level": "critical", "category": "pcr_extreme",
                    "message": f"PCR极端看多({pcr_value:.2f})，市场过度乐观", "value": pcr_value})
            elif pcr_value <= self._pwl:
                alerts.append({"level": "warning", "category": "pcr_low",
                    "message": f"PCR偏看多({pcr_value:.2f})，需警惕拥挤交易", "value": pcr_value})
        # 基差异常
        if basis_value is not None:
            if basis_value <= _BASIS_EXT_DEEP:
                alerts.append({"level": "critical", "category": "basis_extreme",
                    "message": f"基差深度贴水({basis_value:+.2f}%)，市场极度悲观", "value": basis_value})
            elif basis_value <= _BASIS_WARN_DEEP:
                alerts.append({"level": "warning", "category": "basis_deep",
                    "message": f"基差贴水({basis_value:+.2f}%)，市场偏悲观", "value": basis_value})
            elif basis_value >= _BASIS_EXT_HIGH:
                alerts.append({"level": "warning", "category": "basis_high",
                    "message": f"基差大幅升水({basis_value:+.2f}%)，注意套利压力", "value": basis_value})
        # 微盘流动性
        ms = micro_liquidity.get("stage", "normal")
        lvl = {"melted": "critical", "watch": "warning", "early_warning": "info"}
        if ms in lvl:
            alerts.append({"level": lvl[ms], "category": "micro_liquidity",
                "message": f"微盘流动性{ms}，相关性={micro_liquidity.get('correlation', 'N/A')}",
                "value": micro_liquidity.get("correlation")})
        # 九宫格联动
        if "防御" in market_state or "谨慎" in market_state:
            alerts.append({"level": "info", "category": "market_state",
                "message": f"市场状态为【{market_state}】，建议降低仓位", "value": market_state})
        return alerts

    # ── 4. 估值评估 ──────────────────────────────────────

    def assess_valuation(self) -> Dict:
        """估值评估 — PE百分位 + ERP(股权风险溢价)。

        PE百分位: 当前PE在历史中的分位数（低=低估，高=高估）
        ERP:     1/PE - 十年期国债收益率，衡量股票相对债券的吸引力

        Returns:
            {indices, overall_erp, overall_level, bond_yield_10y, description, timestamp}
        """
        pe_cfg = {"000300": {"name": "沪深300", "w": 0.50},
                  "000905": {"name": "中证500", "w": 0.30},
                  "000852": {"name": "中证1000", "w": 0.20}}
        by = self.config.get("bond_yield_10y", _DEF_BOND) / 100.0
        indices, w_erp, tw = {}, 0.0, 0.0
        for code, info in pe_cfg.items():
            ir = {"name": info["name"], "pe_ttm": None, "percentile": None, "erp": None, "level": "数据不足"}
            try:
                pe_df = self.data_service.load_pe_data(code)
                if pe_df is not None and len(pe_df) >= 250 and "pe_ttm" in pe_df.columns:
                    ps = pe_df["pe_ttm"].dropna()
                    if not ps.empty:
                        cpe = float(ps.iloc[-1])
                        pct = float((ps < cpe).sum() / len(ps) * 100)
                        erp = (1.0 / cpe - by) * 100 if cpe > 0 else None
                        lvl = ("极度高估" if pct >= 80 else "偏高估" if pct >= 60 else
                               "中性" if pct >= 40 else "偏低估" if pct >= 20 else "极度低估")
                        ir.update({"pe_ttm": round(cpe, 2), "percentile": round(pct, 1),
                                   "erp": round(erp, 2) if erp else None, "level": lvl})
                        if erp is not None: w_erp += erp * info["w"]; tw += info["w"]
            except Exception as e:
                self.logger.warning(f"估值评估 {code} 失败: {e}")
            indices[code] = ir
        o_erp = (w_erp / tw) if tw > 0 else None
        if o_erp is not None:
            if o_erp >= _ERP_UNDER:   ol, desc = "极度低估", f"ERP={o_erp:.2f}%，股票极具吸引力"
            elif o_erp >= 1.5:        ol, desc = "偏低估", f"ERP={o_erp:.2f}%，股票相对债券有优势"
            elif o_erp >= 0:          ol, desc = "中性", f"ERP={o_erp:.2f}%，股债吸引力相当"
            elif o_erp >= _ERP_OVER:  ol, desc = "偏高估", f"ERP={o_erp:.2f}%，债券更具吸引力"
            else:                     ol, desc = "极度高估", f"ERP={o_erp:.2f}%，股票极度高估"
        else:
            ol, desc = "数据不足", "无法计算综合ERP"
        return {"indices": indices, "overall_erp": round(o_erp, 2) if o_erp else None,
                "overall_level": ol, "bond_yield_10y": round(by * 100, 2),
                "description": desc, "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")}

    # ── 内部辅助 ─────────────────────────────────────────

    @staticmethod
    def _default_underlying_mapping() -> Dict[str, Dict]:
        """默认期权标的映射 (IO/MO/510300/510500/588000/159915)"""
        return {
            "IO": {"spot_code": "000300", "market_code": 7, "market_type": "option_zj",
                    "weight": 0.25, "default_price": 3800},
            "MO": {"spot_code": "000852", "market_code": 7, "market_type": "option_zj",
                    "weight": 0.20, "default_price": 6200},
            "510300": {"spot_code": "510300", "market_code": 8, "market_type": "option_sh",
                       "weight": 0.20, "default_price": 3.9},
            "510500": {"spot_code": "510500", "market_code": 8, "market_type": "option_sh",
                       "weight": 0.15, "default_price": 6.2},
            "588000": {"spot_code": "588000", "market_code": 8, "market_type": "option_sh",
                       "weight": 0.10, "default_price": 0.95},
            "159915": {"spot_code": "159915", "market_code": 9, "market_type": "option_sz",
                       "weight": 0.10, "default_price": 2.1},
        }

    def _fetch_spot_price(self, code: str) -> Optional[float]:
        """获取现货/指数最新价格"""
        try:
            df = self.data_service.load_index_data(code, min_days=5)
            if df is not None and not df.empty and "close" in df.columns:
                return float(df["close"].iloc[-1])
        except Exception as e:
            self.logger.debug(f"获取 {code} 价格失败: {e}")
        return None

    @staticmethod
    def _pcr_signal(pcr: Optional[float]) -> str:
        if pcr is None: return "数据不足"
        if pcr >= _PCR_EXT_HIGH: return "极度看空（恐慌性对冲）"
        if pcr >= _PCR_WARN_HIGH: return "偏看空（对冲需求增加）"
        if pcr <= _PCR_EXT_LOW: return "极度看多（过度乐观）"
        if pcr <= _PCR_WARN_LOW: return "偏看多（拥挤交易风险）"
        return "中性"

    @staticmethod
    def _fallback_pcr(underlying: str, current_price: float) -> Dict:
        """期权链缺失时回退（不伪造数据，与V6划清界限）"""
        return {"underlying": underlying, "current_price": current_price,
                "pcr_oi": None, "pcr_volume": None, "call_oi": 0.0, "put_oi": 0.0,
                "call_vol": 0.0, "put_vol": 0.0, "atm_contracts": 0,
                "signal": "数据不足（无期权链）"}
