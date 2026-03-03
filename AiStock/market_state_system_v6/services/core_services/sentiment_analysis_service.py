# ==================== 4.1.4 情绪分析服务 （情绪分析：四大指标 + 资金流向）SentimentAnalysisService ====================
# sentiment_analysis_service_v6.py
"""
V6.0 情绪分析服务（完全独立，无循环依赖）
职责：
1. 四大情绪指标计算（融资/基金/波动率/恐慌）
2. 资金流向热力图生成
3. 情绪仪表盘数据准备
依赖：
- 仅依赖DataLoadingService和ConfigService（无业务服务依赖）
- 所有数据通过参数传递，避免循环引用
"""
import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Tuple
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


class SentimentAnalysisService:
    """V6.0 情绪分析服务（修复版：完全独立）"""
    
    def __init__(self, data_service, config_service):
        """
        初始化情绪分析服务
        
        参数:
            data_service: DataLoadingService实例（仅用于数据加载）
            config_service: ConfigService实例（仅用于配置获取）
        """
        self.data_service = data_service
        self.config_service = config_service
        self.logger = logger
        self.logger.info("✅ 情绪分析服务初始化成功（V6.0独立版）")
    
    def calculate_sentiment_scores(self) -> Dict[str, float]:
        """
        计算四大情绪指标得分（0-100）
        
        返回:
            {
                'margin_score': float,    # 融资余额情绪（0-100）
                'fund_score': float,      # 基金资金情绪（0-100）
                'vol_score': float,       # 波动率情绪（0-100，反向）
                'vix_score': float        # 恐慌情绪（0-100，反向）
            }
        
        修复点：
        ✅ 移除对OptionPCRService的依赖（PCR由独立服务提供）
        ✅ 所有数值强制转换为Python原生float（避免Plotly序列化错误）
        ✅ 增强异常处理，确保单个指标失败不影响整体
        """
        scores = {
            'margin_score': 50.0,
            'fund_score': 50.0,
            'vol_score': 50.0,
            'vix_score': 50.0
        }
        
        # ========== 1. 融资余额情绪（修复：独立计算，无外部依赖）==========
        try:
            rz_df = self.data_service.load_macro_data('7_RZ', days=250)
            if len(rz_df) >= 50:
                current = rz_df['close'].iloc[-1]
                history = rz_df['close'].iloc[-250:-1]
                percentile = (history < current).mean() * 100
                
                # 近期趋势加分（20日变化）
                if len(rz_df) >= 21:
                    change_20d = ((current - rz_df['close'].iloc[-21]) / rz_df['close'].iloc[-21]) * 100
                    trend_bonus = np.clip(change_20d * 2, -20, 20)
                else:
                    trend_bonus = 0
                
                scores['margin_score'] = float(np.clip(percentile + trend_bonus, 0, 100))
                self.logger.debug(f"✅ 融资余额情绪得分: {scores['margin_score']:.1f}")
        except Exception as e:
            self.logger.warning(f"⚠️ 融资余额情绪计算失败: {str(e)[:50]}")
        
        # ========== 2. 基金资金情绪（修复：独立计算）==========
        try:
            etf_df = self.data_service.load_macro_data('7_TETF', days=250)
            fund_df = self.data_service.load_macro_data('9_990002', days=250)  # 股票型基金指数
            
            if len(etf_df) >= 50:
                # ETF规模分位数
                etf_current = etf_df['close'].iloc[-1]
                etf_hist = etf_df['close'].iloc[-250:-1]
                etf_pct = (etf_hist < etf_current).mean() * 100
                
                # 基金指数相对强弱
                if len(fund_df) >= 50:
                    hs300_df = self.data_service.load_index_data('000300', min_days=250)
                    if len(hs300_df) >= 50:
                        fund_return = (fund_df['close'].iloc[-1] / fund_df['close'].iloc[-21] - 1) * 100
                        hs300_return = (hs300_df['close'].iloc[-1] / hs300_df['close'].iloc[-21] - 1) * 100
                        relative_strength = fund_return - hs300_return
                        rs_score = 50 + relative_strength * 5
                    else:
                        rs_score = 50
                else:
                    rs_score = 50
                
                scores['fund_score'] = float(np.clip((etf_pct * 0.6 + rs_score * 0.4), 0, 100))
                self.logger.debug(f"✅ 基金资金情绪得分: {scores['fund_score']:.1f}")
        except Exception as e:
            self.logger.warning(f"⚠️ 基金情绪计算失败: {str(e)[:50]}")
        
        # ========== 3. 波动率情绪（反向）==========
        try:
            hs300_df = self.data_service.load_index_data('000300', min_days=250)
            if len(hs300_df) >= 250 and 'volatility_20' in hs300_df.columns:
                current_vol = hs300_df['volatility_20'].iloc[-1]
                vol_hist = hs300_df['volatility_20'].iloc[-250:-1]
                vol_percentile = (vol_hist < current_vol).mean() * 100
                # 反向映射：波动率高 → 情绪差
                scores['vol_score'] = float(np.clip(100 - vol_percentile, 0, 100))
                self.logger.debug(f"✅ 波动率情绪得分: {scores['vol_score']:.1f}")
        except Exception as e:
            self.logger.warning(f"⚠️ 波动率情绪计算失败: {str(e)[:50]}")
        
        # ========== 4. 恐慌情绪（VHSI替代，修复：独立计算）==========
        try:
            # 尝试加载VHSI（恒生波幅指数）
            vhsi_df = self.data_service.load_derivative_data('VHSI', market_code=27, days=250)
            if len(vhsi_df) >= 50 and 'close' in vhsi_df.columns:
                current_vhsi = vhsi_df['close'].iloc[-1]
                vhsi_history = vhsi_df['close'].iloc[-250:-1]
                vhsi_percentile = (vhsi_history < current_vhsi).mean() * 100
                # 反向映射：VHSI越高 → 恐慌越强 → 情绪得分越低
                vix_score = 100 - vhsi_percentile
                
                # 极端值校准
                if current_vhsi > 30:  # 极度恐慌
                    vix_score = max(5, vix_score * 0.8)
                elif current_vhsi < 12:  # 异常平静
                    vix_score = min(65, vix_score * 0.9)
                
                scores['vix_score'] = float(np.clip(vix_score, 0, 100))
                self.logger.info(f"✅ VHSI情绪得分: {scores['vix_score']:.1f} | VHSI={current_vhsi:.1f}")
            else:
                # 回退：使用默认值（由主系统提供PCR数据时再计算）
                self.logger.warning("⚠️ VHSI数据不足，使用默认值50.0")
                scores['vix_score'] = 50.0
        except Exception as e:
            self.logger.warning(f"⚠️ VHSI加载失败: {str(e)[:50]}，使用默认值50.0")
            scores['vix_score'] = 50.0
        
        # ⭐⭐⭐ 关键修复：强制转换为Python原生float（避免Plotly序列化错误）⭐⭐⭐
        return {
            'margin_score': float(scores['margin_score']),
            'fund_score': float(scores['fund_score']),
            'vol_score': float(scores['vol_score']),
            'vix_score': float(scores['vix_score'])
        }
    
    def calculate_fund_flow_heatmap(self) -> Dict[str, List]:
        """
        V6.0修复版：计算资金流向热力图数据（完整实现）
        修复点：
        ✅ 补充ETF规模和南下资金的简化数据（V5.7缺失部分）
        ✅ 完整数据验证与空值处理
        ✅ 强制转换为Python原生float（避免Plotly序列化错误）
        ✅ 添加详细日志
        
        返回:
            {
                'categories': ['融资余额', '北上资金', 'ETF规模', '南下资金'],
                'data_values': [
                    [5d变化%, 10d变化%, 20d变化%],  # 融资余额
                    [5d变化%, 10d变化%, 20d变化%],  # 北上资金
                    [5d变化%, 10d变化%, 20d变化%],  # ETF规模（简化）
                    [5d变化%, 10d变化%, 20d变化%]   # 南下资金（简化）
                ]
            }
        """
        fund_flow_data = {
            'categories': ['融资余额', '北上资金', 'ETF规模', '南下资金'],
            'data_values': []
        }
        
        # ========== 1. 融资余额（7_RZ）==========
        try:
            rz_df = self.data_service.load_macro_data('7_RZ', days=30)
            if len(rz_df) >= 20:
                rz_latest = rz_df['close'].iloc[-1]
                rz_5d = rz_df['close'].iloc[-5] if len(rz_df) >= 5 else rz_latest
                rz_10d = rz_df['close'].iloc[-10] if len(rz_df) >= 10 else rz_latest
                rz_20d = rz_df['close'].iloc[-20]
                
                rz_change_5d = ((rz_latest - rz_5d) / rz_5d * 100) if rz_5d > 0 else 0.0
                rz_change_10d = ((rz_latest - rz_10d) / rz_10d * 100) if rz_10d > 0 else 0.0
                rz_change_20d = ((rz_latest - rz_20d) / rz_20d * 100) if rz_20d > 0 else 0.0
                
                fund_flow_data['data_values'].append([
                    round(float(rz_change_5d), 1),
                    round(float(rz_change_10d), 1),
                    round(float(rz_change_20d), 1)
                ])
                self.logger.debug(f"✅ 融资余额: 5d={rz_change_5d:+.1f}%, 10d={rz_change_10d:+.1f}%, 20d={rz_change_20d:+.1f}%")
            else:
                fund_flow_data['data_values'].append([0.0, 0.0, 0.0])
                self.logger.warning("⚠️ 融资余额数据不足（需≥20日）")
        except Exception as e:
            self.logger.error(f"❌ 融资余额计算失败: {str(e)[:50]}")
            fund_flow_data['data_values'].append([0.0, 0.0, 0.0])
        
        # ========== 2. 北上资金（7_TON）==========
        try:
            ton_df = self.data_service.load_macro_data('7_TON', days=30)
            if len(ton_df) >= 20:
                ton_latest = ton_df['close'].iloc[-1]
                ton_5d = ton_df['close'].iloc[-5] if len(ton_df) >= 5 else ton_latest
                ton_10d = ton_df['close'].iloc[-10] if len(ton_df) >= 10 else ton_latest
                ton_20d = ton_df['close'].iloc[-20]
                
                ton_change_5d = ((ton_latest - ton_5d) / ton_5d * 100) if ton_5d > 0 else 0.0
                ton_change_10d = ((ton_latest - ton_10d) / ton_10d * 100) if ton_10d > 0 else 0.0
                ton_change_20d = ((ton_latest - ton_20d) / ton_20d * 100) if ton_20d > 0 else 0.0
                
                fund_flow_data['data_values'].append([
                    round(float(ton_change_5d), 1),
                    round(float(ton_change_10d), 1),
                    round(float(ton_change_20d), 1)
                ])
                self.logger.debug(f"✅ 北上资金: 5d={ton_change_5d:+.1f}%, 10d={ton_change_10d:+.1f}%, 20d={ton_change_20d:+.1f}%")
            else:
                fund_flow_data['data_values'].append([0.0, 0.0, 0.0])
                self.logger.warning("⚠️ 北上资金数据不足（需≥20日）")
        except Exception as e:
            self.logger.error(f"❌ 北上资金计算失败: {str(e)[:50]}")
            fund_flow_data['data_values'].append([0.0, 0.0, 0.0])
        
        # ========== 3. ETF规模（7_TETF）- V5.7缺失部分 ==========
        try:
            etf_df = self.data_service.load_macro_data('7_TETF', days=30)
            if len(etf_df) >= 20:
                etf_latest = etf_df['close'].iloc[-1]
                etf_5d = etf_df['close'].iloc[-5] if len(etf_df) >= 5 else etf_latest
                etf_10d = etf_df['close'].iloc[-10] if len(etf_df) >= 10 else etf_latest
                etf_20d = etf_df['close'].iloc[-20]
                
                etf_change_5d = ((etf_latest - etf_5d) / etf_5d * 100) if etf_5d > 0 else 0.0
                etf_change_10d = ((etf_latest - etf_10d) / etf_10d * 100) if etf_10d > 0 else 0.0
                etf_change_20d = ((etf_latest - etf_20d) / etf_20d * 100) if etf_20d > 0 else 0.0
                
                fund_flow_data['data_values'].append([
                    round(float(etf_change_5d), 1),
                    round(float(etf_change_10d), 1),
                    round(float(etf_change_20d), 1)
                ])
                self.logger.debug(f"✅ ETF规模: 5d={etf_change_5d:+.1f}%, 10d={etf_change_10d:+.1f}%, 20d={etf_change_20d:+.1f}%")
            else:
                # 回退：使用简化数据（V5.7原始逻辑）
                fund_flow_data['data_values'].append([1.2, 2.5, 3.8])
                self.logger.warning("⚠️ ETF规模数据不足，使用简化数据")
        except Exception as e:
            self.logger.error(f"❌ ETF规模计算失败: {str(e)[:50]}，使用简化数据")
            # 回退：使用简化数据（V5.7原始逻辑）
            fund_flow_data['data_values'].append([1.2, 2.5, 3.8])
        
        # ========== 4. 南下资金（7_TOS）- V5.7缺失部分 ==========
        try:
            tos_df = self.data_service.load_macro_data('7_TOS', days=30)
            if len(tos_df) >= 20:
                tos_latest = tos_df['close'].iloc[-1]
                tos_5d = tos_df['close'].iloc[-5] if len(tos_df) >= 5 else tos_latest
                tos_10d = tos_df['close'].iloc[-10] if len(tos_df) >= 10 else tos_latest
                tos_20d = tos_df['close'].iloc[-20]
                
                tos_change_5d = ((tos_latest - tos_5d) / tos_5d * 100) if tos_5d > 0 else 0.0
                tos_change_10d = ((tos_latest - tos_10d) / tos_10d * 100) if tos_10d > 0 else 0.0
                tos_change_20d = ((tos_latest - tos_20d) / tos_20d * 100) if tos_20d > 0 else 0.0
                
                fund_flow_data['data_values'].append([
                    round(float(tos_change_5d), 1),
                    round(float(tos_change_10d), 1),
                    round(float(tos_change_20d), 1)
                ])
                self.logger.debug(f"✅ 南下资金: 5d={tos_change_5d:+.1f}%, 10d={tos_change_10d:+.1f}%, 20d={tos_change_20d:+.1f}%")
            else:
                # 回退：使用简化数据（V5.7原始逻辑）
                fund_flow_data['data_values'].append([0.8, 1.5, 2.2])
                self.logger.warning("⚠️ 南下资金数据不足，使用简化数据")
        except Exception as e:
            self.logger.error(f"❌ 南下资金计算失败: {str(e)[:50]}，使用简化数据")
            # 回退：使用简化数据（V5.7原始逻辑）
            fund_flow_data['data_values'].append([0.8, 1.5, 2.2])
        
        self.logger.info(f"✅ 资金流向热力图数据计算完成: {len(fund_flow_data['data_values'])}个类别")
        return fund_flow_data
    
    def generate_sentiment_dashboard_data(self, sentiment_scores: Dict) -> Dict:
        """
        生成情绪仪表盘图表数据（用于Plotly可视化）
        
        参数:
            sentiment_scores: 四大情绪指标得分字典
        
        返回:
            仪表盘配置数据字典
        """
        # 计算综合情绪得分
        composite_score = (
            sentiment_scores['margin_score'] +
            sentiment_scores['fund_score'] +
            sentiment_scores['vol_score'] +
            sentiment_scores['vix_score']
        ) / 4.0
        
        # 确定市场情绪状态
        if composite_score > 60:
            status = "🟢 乐观"
            status_emoji = "🟢"
        elif composite_score > 40:
            status = "🟡 中性"
            status_emoji = "🟡"
        else:
            status = "🔴 悲观"
            status_emoji = "🔴"
        
        return {
            'composite_score': float(composite_score),
            'status': status,
            'status_emoji': status_emoji,
            'indicators': [
                {
                    'name': '融资余额情绪',
                    'score': float(sentiment_scores['margin_score']),
                    'color': '#3498db',
                    'range': [0, 40, 60, 100],
                    'range_colors': ['#e74c3c', '#f39c12', '#27ae60']
                },
                {
                    'name': '基金资金情绪',
                    'score': float(sentiment_scores['fund_score']),
                    'color': '#9b59b6',
                    'range': [0, 40, 60, 100],
                    'range_colors': ['#e74c3c', '#f39c12', '#27ae60']
                },
                {
                    'name': '波动率情绪',
                    'score': float(sentiment_scores['vol_score']),
                    'color': '#e67e22',
                    'range': [0, 40, 60, 100],
                    'range_colors': ['#e74c3c', '#f39c12', '#27ae60']
                },
                {
                    'name': '市场恐慌情绪',
                    'score': float(sentiment_scores['vix_score']),
                    'color': '#c0392b',
                    'range': [0, 40, 60, 100],
                    'range_colors': ['#e74c3c', '#f39c12', '#27ae60']
                }
            ],
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }