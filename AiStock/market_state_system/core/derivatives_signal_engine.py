#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
V7.0 DerivativesSignalEngine — 衍生品信号引擎（统一版）

合并 V6.1 的 CommodityEngineService + FuturesAnalysisService 为单一引擎。
两服务 >80% 代码重叠（期限结构、产业景气度、报告生成），V7 彻底消除冗余。

依赖注入：data_service / contract_manager / config(dict)
核心方法：commodity_signals / term_structure / index_futures_basis / industry_sentiment / report
"""
import logging
from datetime import datetime
from typing import Dict, List, Optional, Tuple

import pandas as pd

logger = logging.getLogger(__name__)

# 商品→九大战略方向映射
_COMMODITY_DIR: Dict[str, List[str]] = {
    "copper": ["高端制造", "供应链"], "aluminum": ["高端制造", "新能源"],
    "lithium": ["新能源", "信息技术"], "silicon": ["信息技术", "新能源"],
    "crude": ["公用事业", "供应链", "传统升级"], "rebar": ["传统升级", "供应链"],
    "gold": ["公用事业"], "soybean": ["现代农业", "生物健康", "文化消费"],
}
_NINE_DIRS = ["高端制造", "信息技术", "新能源", "生物健康", "供应链",
              "现代农业", "公用事业", "传统升级", "文化消费"]
_IDX_DESC = {"if": "沪深300股指期货（大盘蓝筹）", "ih": "上证50股指期货（超大蓝筹）",
             "ic": "中证500股指期货（中盘成长）", "im": "中证1000股指期货（小盘成长）"}
_MC2TYPE = {30: "future_sh", 29: "future_dl", 28: "future_zz", 32: "future_zz",
            66: "future_gz", 47: "future_zj"}
_NAME2KEY = {"沪铜": "copper", "沪铝": "aluminum", "碳酸锂": "lithium",
             "工业硅": "silicon", "原油": "crude", "螺纹钢": "rebar",
             "黄金": "gold", "豆粕": "soybean"}


class DerivativesSignalEngine:
    """V7 衍生品信号引擎 — 合并原 CommodityEngineService + FuturesAnalysisService"""

    def __init__(self, data_service, contract_manager=None, config: Optional[Dict] = None):
        self.data_service = data_service
        self.contract_manager = contract_manager
        self.config = config or {}
        self._smap = self.config.get("commodity_strategy_map", {})
        self._basis_thr = self.config.get("risk_thresholds", {}).get("basis", {})
        self.logger = logger
        self.logger.info(f"DerivativesSignalEngine V7.0 初始化 | 商品={len(self._smap)}")

    # ── 1. 商品期货信号（20d价格变动） ──────────────────────────────

    def calculate_commodity_signals(self) -> Dict[str, Dict]:
        """对 commodity_strategy_map 中每品种计算 20d 涨跌幅信号"""
        signals, cmap = {}, self._commodity_contracts_map()
        for code, cfg in self._smap.items():
            mc = cfg.get("market_code", 30)
            mt = cfg.get("market_type", "future_sh")
            df = self.data_service.load_derivative_data(code, mt, days=60)
            src = "main_contract"
            if df is None or len(df) < 20:
                near = cmap.get(code, {}).get("near_code")
                if near:
                    df = self.data_service.load_derivative_data(near, mc, days=60)
                    src = "near_contract"
                if df is None or len(df) < 20:
                    continue
            chg = (df["close"].iloc[-1] / df["close"].iloc[-20] - 1) * 100
            sig, score = self._gen_signal(chg, cfg.get("impact_type", "cost"),
                                          cfg.get("threshold_up", 10.0), cfg.get("threshold_down", -10.0))
            signals[code] = {
                "name": cfg.get("name", code), "price_chg_20d": float(chg),
                "signal": sig, "score": float(score), "directions": cfg.get("directions", []),
                "weight": cfg.get("weight", 0.05), "impact_type": cfg.get("impact_type", "cost"),
                "threshold_up": cfg.get("threshold_up", 10.0), "threshold_down": cfg.get("threshold_down", -10.0),
                "market_code": mc, "near_contract": cmap.get(code, {}).get("near_code", ""),
                "far_contract": cmap.get(code, {}).get("far_code", ""), "data_source": src,
            }
        self.logger.info(f"商品信号: {len(signals)}个品种")
        return signals

    # ── 2. 期限结构（近/远月价差） ──────────────────────────────

    def calculate_term_structure(self) -> Dict[str, Dict]:
        """近月/远月价差 → backwardation(供应紧张) / contango(供应充足)"""
        ts, contracts = {}, self._commodity_contracts_tuple()
        if not contracts:
            self.logger.warning("无合约配置，无法计算期限结构")
            return ts
        for key, (nc, fc, mc) in contracts.items():
            try:
                mt = _MC2TYPE.get(mc, "future_sh")
                ndf = self.data_service.load_derivative_data(nc, mt, days=20)
                fdf = self.data_service.load_derivative_data(fc, mt, days=20)
                if ndf is not None and len(ndf) > 0 and fdf is not None and len(fdf) > 0 and fdf["close"].iloc[-1] > 0:
                    np_, fp = float(ndf["close"].iloc[-1]), float(fdf["close"].iloc[-1])
                    spread = ((np_ - fp) / fp) * 100
                    struct = "backwardation" if spread > 0 else "contango"
                    nm, fm = 0, 0
                    if self.contract_manager:
                        pairs = self.contract_manager.get_commodity_contracts()
                        if key in pairs:
                            nm, fm = pairs[key].near_month, pairs[key].far_month
                    ts[key] = {"spread": round(float(spread), 2), "structure": struct,
                               "signal": "供应紧张/景气" if spread > 0 else "供应充足/疲软",
                               "near_price": np_, "far_price": fp,
                               "near_code": nc, "far_code": fc, "near_month": nm, "far_month": fm}
            except Exception as e:
                self.logger.warning(f"{key} 期限结构失败: {str(e)[:60]}")
        self.logger.info(f"期限结构: {len(ts)}/{len(contracts)}个品种")
        return ts

    # ── 3. 股指期货基差 ──────────────────────────────

    def calculate_index_futures_basis(self) -> Dict[str, Dict]:
        """IF/IH/IC/IM 基差 = futures - spot, 信号阈值取自 risk_thresholds.basis"""
        results, ic = {}, self._index_futures_contracts()
        warn, extr = self._basis_thr.get("warning", -1.5), self._basis_thr.get("extreme", -2.0)
        for key, (fcode, scode, mc) in ic.items():
            try:
                fdf = self.data_service.load_derivative_data(fcode, "future_zj", days=20)
                sdf = self.data_service.load_index_data(scode, min_days=20)
                if fdf is not None and len(fdf) > 0 and sdf is not None and len(sdf) > 0:
                    fp, sp = float(fdf["close"].iloc[-1]), float(sdf["close"].iloc[-1])
                    if sp > 0:
                        basis, bp = fp - sp, (fp - sp) / sp * 100
                        sig = ("深度贴水（极度悲观）" if bp < extr else
                               "贴水（谨慎）" if bp < warn else
                               "升水（乐观）" if bp > 0 else "平水（中性）")
                        dm = 0
                        if self.contract_manager:
                            idx_c = self.contract_manager.get_index_futures_contracts()
                            if key in idx_c:
                                dm = idx_c[key].delivery_month
                        results[key] = {"futures_price": fp, "spot_price": sp,
                                        "basis": float(basis), "basis_pct": float(bp),
                                        "signal": sig, "futures_code": fcode, "spot_code": scode,
                                        "description": _IDX_DESC.get(key, key.upper()),
                                        "delivery_month": dm, "is_main_contract": fcode.endswith("L8")}
            except Exception as e:
                self.logger.warning(f"{key} 基差失败: {str(e)[:60]}")
        self.logger.info(f"股指基差: {len(results)}/{len(ic)}个品种")
        return results

    # ── 4. 产业景气度（期限结构→9大方向） ──────────────────────────────

    def calculate_industry_sentiment(self, term_structure: Optional[Dict[str, Dict]] = None) -> Dict[str, float]:
        """backwardation → 景气(加分), contango → 疲软(减分), 加权混合到9方向"""
        if term_structure is None:
            term_structure = self.calculate_term_structure()
        sent = {d: 50.0 for d in _NINE_DIRS}
        for comm, data in term_structure.items():
            dirs = _COMMODITY_DIR.get(comm)
            if not dirs:
                continue
            s = abs(data["spread"])
            score = min(100.0, 50.0 + s * 3) if data["structure"] == "backwardation" else max(0.0, 50.0 - s * 3)
            for d in dirs:
                if d in sent:
                    sent[d] = sent[d] * 0.7 + score * 0.3
        return {k: float(v) for k, v in sent.items()}

    # ── 5. 综合报告 ──────────────────────────────

    def generate_report(self) -> Dict:
        """衍生品综合报告：商品信号 + 期限结构 + 股指基差 + 产业景气度 + 到期预警"""
        cs = self.calculate_commodity_signals()
        ts = self.calculate_term_structure()
        ib = self.calculate_index_futures_basis()
        ins = self.calculate_industry_sentiment(ts)
        ew = self.contract_manager.check_expiry_warnings() if self.contract_manager else []

        L = ["=" * 60, "  衍生品市场综合分析报告（V7.0）",
             f"  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", "=" * 60]
        if cs:
            L.append("\n[商品期货信号]")
            for c, s in cs.items():
                L.append(f"  {s['name']}({c}): {s['price_chg_20d']:+.1f}% → {s['signal']} (score={s['score']:+.2f})")
        if ts:
            bk = sum(1 for v in ts.values() if v["structure"] == "backwardation")
            L.append(f"\n[期限结构] Back={bk} Cont={len(ts)-bk}")
            for k, d in ts.items():
                L.append(f"  {k}: {d['spread']:+.1f}% ({d['signal']}) | {d['near_code']}/{d['far_code']}")
        if ib:
            L.append("\n[股指期货基差]")
            for k, d in ib.items():
                L.append(f"  {d['description']}: {d['basis_pct']:+.1f}% {d['signal']}")
        if ins:
            L.append("\n[产业景气度 TOP5]")
            for direction, score in sorted(ins.items(), key=lambda x: x[1], reverse=True)[:5]:
                st = "景气" if score > 65 else ("稳健" if score > 50 else "疲软")
                L.append(f"  {direction}: {score:.0f}分 ({st})")
        if ew:
            L.append("\n[合约到期预警]")
            for w in ew:
                L.append(f"  ⚠ {w['warning']}")
        L.append("=" * 60)
        return {"commodity_signals": cs, "term_structure": ts, "index_futures_basis": ib,
                "industry_sentiment": ins, "expiry_warnings": ew,
                "summary": "\n".join(L), "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")}

    # ── 内部辅助 ──────────────────────────────

    def _commodity_contracts_map(self) -> Dict[str, Dict]:
        """{main_code: {near_code, far_code, market_code}} — 优先动态推导，回退config"""
        if self.contract_manager:
            try:
                pairs = self.contract_manager.get_commodity_contracts()
                r = {f"{p.variety_code}L8": {"near_code": p.near_code, "far_code": p.far_code,
                                              "market_code": p.market_code} for p in pairs.values()}
                if r:
                    return r
            except Exception as e:
                self.logger.warning(f"动态推导失败: {e}")
        return {c: {"near_code": v.get("near_contract", ""), "far_code": v.get("far_contract", ""),
                     "market_code": v.get("market_code", 30)} for c, v in self._smap.items()}

    def _commodity_contracts_tuple(self) -> Dict[str, Tuple[str, str, int]]:
        """{key: (near_code, far_code, market_code)} — 优先动态推导"""
        if self.contract_manager:
            try:
                d = self.contract_manager.generate_commodity_contracts_config()
                if d:
                    return d
            except Exception:
                pass
        cm = self._commodity_contracts_map()
        r = {}
        for mc, info in cm.items():
            n, f = info.get("near_code", ""), info.get("far_code", "")
            if n and f:
                name = self._smap.get(mc, {}).get("name", "")
                key = _NAME2KEY.get(name, mc)
                r[key] = (n, f, info.get("market_code", 30))
        return r

    def _index_futures_contracts(self) -> Dict[str, Tuple[str, str, int]]:
        """{key: (futures_code, spot_code, market_code)}"""
        if self.contract_manager:
            try:
                d = self.contract_manager.generate_index_futures_config()
                if d:
                    return d
            except Exception:
                pass
        r = {}
        for key, cfg in self.config.get("index_futures_contracts", {}).items():
            variety, sc = cfg.get("variety", key.upper()), cfg.get("spot_code", "")
            if sc:
                r[key] = (f"{variety}L8", sc, cfg.get("market_code", 47))
        return r

    @staticmethod
    def _gen_signal(price_chg: float, impact_type: str, up: float, down: float) -> Tuple[str, float]:
        """cost: 涨=利空/跌=利好; benefit: 涨=利好/跌=利空"""
        if impact_type == "cost":
            if price_chg > up:      return "成本大幅上升", -0.15
            elif price_chg > up/2:  return "成本上升", -0.08
            elif price_chg < down:  return "成本大幅下降", 0.12
            elif price_chg < down/2:return "成本下降", 0.06
            else:                   return "成本稳定", 0.0
        else:
            if price_chg > up:      return "利好信号增强", 0.10
            elif price_chg > up/2:  return "利好信号", 0.05
            elif price_chg < down:  return "利空信号增强", -0.10
            elif price_chg < down/2:return "利空信号", -0.05
            else:                   return "正常", 0.0
