#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
V7.0 MarketStateClassifier：3D 市场状态分类器

三维模型:
  ┌────────────────────────────────────────────────────┐
  │           MarketStateClassifier (3D Model)          │
  ├────────────────────────────────────────────────────┤
  │  D1: Valuation Score   ← PE 百分位分析             │
  │  D2: Momentum Score    ← 均线趋势分析              │
  │  D3: Regime Score      ← MarketRegimeEngine        │
  ├────────────────────────────────────────────────────┤
  │  Composite = w1*D1 + w2*D2 + w3*D3                 │
  │  → 映射到九宫格状态                                  │
  └────────────────────────────────────────────────────┘

九宫格状态:
  战略进攻区 | 积极配置区 | 均衡持有区
  防御观望区 | 战略防御区 | 防御进攻区
  左侧布局区 | 左侧防御区 | 谨慎持有区
"""

import numpy as np
import pandas as pd
from typing import Dict, Optional, List, Tuple
import logging

logger = logging.getLogger(__name__)

# 九宫格状态名称
GRID_STATES = [
    "战略进攻区",  # 0: composite >= 80
    "积极配置区",  # 1: 65 <= composite < 80
    "均衡持有区",  # 2: 50 <= composite < 65
    "防御观望区",  # 3: 35 <= composite < 50
    "战略防御区",  # 4: composite < 20
    "防御进攻区",  # 5: 防御+动量改善
    "左侧布局区",  # 6: 估值低+体制复苏
    "左侧防御区",  # 7: 估值低+体制熊市
    "谨慎持有区",  # 8: 估值中性+体制震荡
]

# 基准指数默认权重
DEFAULT_BENCHMARK_WEIGHTS = {
    "000300": 0.40,  # 沪深300 大盘
    "000905": 0.30,  # 中证500 中盘
    "000852": 0.20,  # 中证1000 小盘
    "932000": 0.10,  # 中证2000 微盘
}


class MarketStateClassifier:
    """
    V7 3D 市场状态分类器

    将估值、动量、体制三维得分按可配置权重组合，
    映射到九宫格状态之一。
    """

    # 默认配置
    DEFAULT_CONFIG = {
        "dimensions": ["valuation", "momentum", "regime"],
        "grid": {
            "strategic_offense": 80,
            "active_allocation": 65,
            "balanced_hold": 50,
            "defensive_watch": 35,
            "strategic_defense": 20,
        },
        "thresholds": {
            "valuation_weight": 0.35,
            "momentum_weight": 0.35,
            "regime_weight": 0.30,
        },
    }

    def __init__(self, data_service, config: Dict, regime_engine):
        """
        依赖注入初始化

        参数:
            data_service: DataLoadingService 实例
            config: 系统配置字典，需包含 'market_state_classifier' 节
            regime_engine: MarketRegimeEngine 实例
        """
        self.data_service = data_service
        self.config = config.get("market_state_classifier", self.DEFAULT_CONFIG)
        self.regime_engine = regime_engine
        self.logger = logger

        # 权重
        thresholds = self.config.get("thresholds", self.DEFAULT_CONFIG["thresholds"])
        self.w_valuation = float(thresholds.get("valuation_weight", 0.35))
        self.w_momentum = float(thresholds.get("momentum_weight", 0.35))
        self.w_regime = float(thresholds.get("regime_weight", 0.30))

        # 九宫格阈值
        self.grid = self.config.get("grid", self.DEFAULT_CONFIG["grid"])

        # PE 估值百分位阈值
        self.risk_cfg = config.get("risk_thresholds", {}).get("valuation", {})
        self.pe_overvalued = self.risk_cfg.get("overvalued_pe_percentile", 75)
        self.pe_undervalued = self.risk_cfg.get("undervalued_pe_percentile", 25)

        # 基准指数权重
        self.benchmark_weights = config.get("market_benchmarks", DEFAULT_BENCHMARK_WEIGHTS)

        self.logger.info(
            f"✅ MarketStateClassifier V7 初始化 | "
            f"权重: 估值={self.w_valuation:.0%} 动量={self.w_momentum:.0%} 体制={self.w_regime:.0%}"
        )

    # ─────────────────── 公开接口 ───────────────────

    def classify(self) -> Dict:
        """
        执行 3D 市场状态分类

        返回:
            {
                'market_state': str,
                'composite_score': float,
                'valuation_score': float,
                'momentum_score': float,
                'regime_score': float,
                'regime_name': str,
                'confidence': float,
                'diagnosis': Dict
            }
        """
        # 1. 估值维度
        val_score, val_diag = self._calc_valuation_score()

        # 2. 动量维度
        mom_score, mom_diag = self._calc_momentum_score()

        # 3. 体制维度
        regime_result = self.regime_engine.detect_regime()
        regime_score, regime_diag = self._calc_regime_score(regime_result)

        # 4. 综合得分
        composite = (
            self.w_valuation * val_score
            + self.w_momentum * mom_score
            + self.w_regime * regime_score
        )

        # 5. 映射九宫格
        market_state = self._map_to_grid(composite, val_score, mom_score, regime_result)

        # 6. 置信度：三维方向一致性
        confidence = self._calc_confidence(val_score, mom_score, regime_score)

        # 7. 体制中文名
        regime_cn = self._regime_cn_name(regime_result["current_regime"])

        result = {
            "market_state": market_state,
            "composite_score": round(float(composite), 2),
            "valuation_score": round(float(val_score), 2),
            "momentum_score": round(float(mom_score), 2),
            "regime_score": round(float(regime_score), 2),
            "regime_name": regime_cn,
            "confidence": round(float(confidence), 4),
            "diagnosis": {
                "valuation": val_diag,
                "momentum": mom_diag,
                "regime": regime_diag,
            },
        }

        self.logger.info(
            f"📊 市场状态: {market_state} | "
            f"综合={composite:.1f} 估值={val_score:.1f} 动量={mom_score:.1f} 体制={regime_score:.1f} | "
            f"置信度={confidence:.2%}"
        )
        return result

    # ─────────────────── 估值维度 ───────────────────

    def _calc_valuation_score(self) -> Tuple[float, Dict]:
        """
        基于 PE 百分位计算估值得分 (0-100)

        多指数加权:
          - PE 百分位 < 25%: 高分(低估)
          - PE 百分位 > 75%: 低分(高估)
          - 线性映射
        """
        pe_codes = {
            "000300": {"name": "沪深300", "weight": 0.45},
            "000905": {"name": "中证500", "weight": 0.30},
            "000852": {"name": "中证1000", "weight": 0.25},
        }

        weighted_score = 0.0
        total_weight = 0.0
        details = {}

        for code, info in pe_codes.items():
            try:
                pe_df = self.data_service.load_pe_data(code)
                if pe_df is not None and len(pe_df) >= 250 and "pe_ttm" in pe_df.columns:
                    pe_series = pe_df["pe_ttm"].dropna()
                    current_pe = pe_series.iloc[-1]
                    # 计算历史百分位
                    percentile = float(
                        (pe_series < current_pe).sum() / len(pe_series) * 100
                    )
                    # 百分位 → 得分: 低百分位=高分, 高百分位=低分
                    score = 100 - percentile
                    weight = info["weight"]
                    weighted_score += score * weight
                    total_weight += weight
                    details[code] = {
                        "name": info["name"],
                        "pe_ttm": round(float(current_pe), 2),
                        "percentile": round(percentile, 1),
                        "score": round(score, 1),
                    }
                else:
                    details[code] = {"name": info["name"], "pe_ttm": None, "percentile": None, "score": None}
            except Exception as e:
                self.logger.warning(f"⚠️ PE 数据加载失败 {code}: {e}")
                details[code] = {"name": info["name"], "error": str(e)}

        val_score = weighted_score / total_weight if total_weight > 0 else 50.0

        diag = {
            "score": round(val_score, 1),
            "level": self._valuation_level(val_score),
            "indices": details,
        }
        return val_score, diag

    def _valuation_level(self, score: float) -> str:
        """估值水平描述"""
        if score >= 75:
            return "极度低估"
        elif score >= 60:
            return "偏低估"
        elif score >= 40:
            return "中性"
        elif score >= 25:
            return "偏高估"
        else:
            return "极度高估"

    # ─────────────────── 动量维度 ───────────────────

    def _calc_momentum_score(self) -> Tuple[float, Dict]:
        """
        基于均线趋势分析计算动量得分 (0-100)

        多指数加权，分析:
          - 价格 vs MA20 / MA60 关系
          - MA20 vs MA60 关系（金叉/死叉）
          - 短期/中期趋势强度
        """
        # 从配置中获取基准指数
        benchmark_cfg = self.benchmark_weights
        if isinstance(benchmark_cfg, dict):
            codes = {}
            for name, cfg in benchmark_cfg.items():
                if isinstance(cfg, dict) and "code" in cfg:
                    codes[cfg["code"]] = {"name": name, "weight": cfg.get("weight", 0.25)}
                elif isinstance(cfg, (int, float)):
                    # 简化格式: name → weight
                    pass
        else:
            codes = DEFAULT_BENCHMARK_WEIGHTS

        # 确保有数据
        if not codes:
            codes = DEFAULT_BENCHMARK_WEIGHTS

        weighted_score = 0.0
        total_weight = 0.0
        details = {}

        for code, info in codes.items():
            try:
                idx_df = self.data_service.load_index_data(code, min_days=120)
                if idx_df is not None and len(idx_df) >= 60 and "close" in idx_df.columns:
                    close = idx_df["close"]
                    ma20 = close.rolling(20).mean()
                    ma60 = close.rolling(60).mean()

                    latest_close = close.iloc[-1]
                    latest_ma20 = ma20.iloc[-1]
                    latest_ma60 = ma60.iloc[-1]

                    # 价格 vs MA 位置
                    above_ma20 = 1.0 if latest_close > latest_ma20 else 0.0
                    above_ma60 = 1.0 if latest_close > latest_ma60 else 0.0

                    # 金叉/死叉
                    golden_cross = 1.0 if latest_ma20 > latest_ma60 else 0.0

                    # 趋势强度: 偏离均线的程度
                    deviation_20 = (latest_close / latest_ma20 - 1) if latest_ma20 > 0 else 0
                    deviation_60 = (latest_close / latest_ma60 - 1) if latest_ma60 > 0 else 0

                    # 综合动量得分
                    score = (
                        above_ma20 * 25
                        + above_ma60 * 25
                        + golden_cross * 20
                        + min(max(deviation_20 * 500, -15), 15)
                        + min(max(deviation_60 * 300, -15), 15)
                    )
                    score = max(0, min(100, score))

                    weight = info.get("weight", 0.25)
                    weighted_score += score * weight
                    total_weight += weight

                    details[code] = {
                        "name": info.get("name", code),
                        "above_ma20": bool(above_ma20),
                        "above_ma60": bool(above_ma60),
                        "golden_cross": bool(golden_cross),
                        "deviation_20": round(float(deviation_20), 4),
                        "deviation_60": round(float(deviation_60), 4),
                        "score": round(score, 1),
                    }
                else:
                    details[code] = {"name": info.get("name", code), "score": None, "reason": "数据不足"}
            except Exception as e:
                self.logger.warning(f"⚠️ 动量计算失败 {code}: {e}")
                details[code] = {"name": info.get("name", code), "error": str(e)}

        mom_score = weighted_score / total_weight if total_weight > 0 else 50.0

        diag = {
            "score": round(mom_score, 1),
            "trend": self._momentum_trend(mom_score),
            "indices": details,
        }
        return mom_score, diag

    def _momentum_trend(self, score: float) -> str:
        """动量趋势描述"""
        if score >= 75:
            return "强上升趋势"
        elif score >= 60:
            return "温和上升"
        elif score >= 40:
            return "震荡"
        elif score >= 25:
            return "温和下降"
        else:
            return "强下降趋势"

    # ─────────────────── 体制维度 ───────────────────

    def _calc_regime_score(self, regime_result: Dict) -> Tuple[float, Dict]:
        """
        将 MarketRegimeEngine 结果转换为体制得分 (0-100)

        映射:
          - Bull → 85
          - Recovery → 65
          - Volatile → 45
          - Bear → 20
        然后用概率加权微调
        """
        regime_name = regime_result["current_regime"]
        regime_prob = regime_result["regime_probability"]
        confidence = regime_result.get("confidence", 0.5)

        # 基础分数映射
        base_scores = {
            "bull": 85.0,
            "recovery": 65.0,
            "volatile": 45.0,
            "bear": 20.0,
        }

        # 概率加权得分
        weighted_score = sum(
            base_scores.get(r, 50.0) * regime_prob.get(r, 0.0)
            for r in base_scores
        )

        # 置信度微调：低置信度向中性靠拢
        if confidence < 0.4:
            neutral_pull = 0.3 * (50.0 - weighted_score)
            weighted_score += neutral_pull

        regime_score = max(0.0, min(100.0, weighted_score))

        diag = {
            "score": round(regime_score, 1),
            "regime": regime_name,
            "regime_cn": self._regime_cn_name(regime_name),
            "probability": regime_prob,
            "confidence": round(confidence, 4),
            "volatility_20d": regime_result.get("volatility_20d"),
            "momentum_20d": regime_result.get("momentum_20d"),
        }
        return regime_score, diag

    # ─────────────────── 九宫格映射 ───────────────────

    def _map_to_grid(
        self,
        composite: float,
        val_score: float,
        mom_score: float,
        regime_result: Dict,
    ) -> str:
        """
        将综合得分映射到九宫格状态

        基础映射（5 级）+ 三维交互修正（4 级）
        """
        regime = regime_result["current_regime"]

        # 基础五级映射
        if composite >= self.grid.get("strategic_offense", 80):
            base_state = "战略进攻区"
        elif composite >= self.grid.get("active_allocation", 65):
            base_state = "积极配置区"
        elif composite >= self.grid.get("balanced_hold", 50):
            base_state = "均衡持有区"
        elif composite >= self.grid.get("defensive_watch", 35):
            base_state = "防御观望区"
        elif composite < self.grid.get("strategic_defense", 20):
            base_state = "战略防御区"
        else:
            # 20-35 之间
            base_state = "防御观望区"

        # 三维交互修正
        # 左侧布局区: 估值极低 + 体制复苏（左侧信号）
        if val_score >= 70 and regime == "recovery":
            return "左侧布局区"

        # 左侧防御区: 估值极低 + 体制熊市
        if val_score >= 70 and regime == "bear":
            return "左侧防御区"

        # 防御进攻区: 综合偏低但动量改善（防御中伺机进攻）
        if composite < 50 and mom_score >= 60 and regime in ("recovery", "bull"):
            return "防御进攻区"

        # 谨慎持有区: 估值中性 + 体制震荡
        if 40 <= val_score <= 60 and regime == "volatile":
            return "谨慎持有区"

        return base_state

    # ─────────────────── 置信度计算 ───────────────────

    def _calc_confidence(
        self,
        val_score: float,
        mom_score: float,
        regime_score: float,
    ) -> float:
        """
        基于三维方向一致性计算置信度

        三维得分越一致（同高/同低），置信度越高；
        三维得分分歧越大，置信度越低。
        """
        scores = np.array([val_score, mom_score, regime_score])

        # 方差越小 → 方向越一致 → 置信度越高
        std_dev = float(np.std(scores))

        # 标准差范围: [0, ~50]，映射到置信度 [1.0, 0.3]
        confidence = max(0.3, min(1.0, 1.0 - std_dev / 70.0))

        # 极端得分提升置信度（三维都在极端区域时更确定）
        if np.all(scores >= 70) or np.all(scores <= 30):
            confidence = min(1.0, confidence + 0.1)

        return confidence

    # ─────────────────── 工具方法 ───────────────────

    @staticmethod
    def _regime_cn_name(regime: str) -> str:
        """体制英文名 → 中文名"""
        mapping = {
            "bull": "牛市",
            "bear": "熊市",
            "volatile": "震荡市",
            "recovery": "复苏期",
        }
        return mapping.get(regime, regime)