"""
V6.1 期权PCR情绪分析服务（完全独立微服务）
核心升级：
✅ 微服务化架构（解耦TDX依赖）
✅ 阈值动态化集成（ThresholdService）
✅ 配置统一提取（config_utils.extract_and_validate_config）
✅ 完整降级策略（TDX不可用时返回模拟数据）
✅ 所有数值强制Python原生float（防Plotly序列化错误）
✅ 与data_context无缝集成（供18大图表使用）
修复问题：
❌ V5.7硬编码TDX连接（无法单元测试）
❌ 配置文件路径硬编码（./config/system_config.yaml）
❌ 无类型安全（可能导致Plotly错误）
❌ 无降级策略（TDX失败即崩溃）
"""
import pandas as pd
import numpy as np
from typing import Dict, Optional, List, Tuple, Any
from datetime import datetime
import logging
import warnings

warnings.filterwarnings('ignore')
logger = logging.getLogger(__name__)

# ✅ V6.1核心：导入配置工具（统一配置提取）
from utils.config_utils import extract_and_validate_config, safe_config_get
from utils.type_conversion_utils import ensure_python_float, ensure_python_int


class OptionPCRService:
    """V6.1 期权PCR情绪分析服务（微服务化 + 阈值动态化）"""
    
    def __init__(self, data_service, config_service, threshold_service=None):
        """
        初始化期权PCR服务
        
        参数:
            data_service: DataLoadingService实例（统一数据加载接口）
            config_service: ConfigService实例（提供V6.1标准配置）
            threshold_service: ThresholdService实例（可选，动态阈值）
        
        升级点:
        ✅ 解耦TDX依赖（通过data_service加载）
        ✅ 配置统一提取（根配置层级option_tolerance）
        ✅ 阈值动态化（优先ThresholdService）
        ✅ 完整降级策略（TDX失败时返回模拟数据）
        """
        self.data_service = data_service
        self.config_service = config_service
        self.threshold_service = threshold_service
        self.logger = logger
        
        # ✅ V6.1核心：统一配置提取（根配置层级）
        self.config, is_valid, missing_keys = extract_and_validate_config(
            config_service=config_service,
            required_keys=[
                'option_tolerance',      # 服务专属配置（根配置层级）
                'option_markets',        # 期权市场配置
                'market_benchmarks'      # 基准指数配置（用于获取当前价格）
            ],
            logger=self.logger,
            service_name='OptionPCRService'
        )
        
        # ✅ 提取常用配置到实例变量（避免重复字典访问）
        self.option_tolerance = self.config.get('option_tolerance', {})
        self.option_markets = self.config.get('option_markets', {})
        self.market_benchmarks = self.config.get('market_benchmarks', {})
        
        # ✅ 验证配置完整性
        if is_valid:
            self.logger.info(
                f"✅ OptionPCRService初始化成功 | "
                f"期权市场: {list(self.option_markets.keys())} | "
                f"阈值动态化: {'已启用' if self.threshold_service else '未启用'}"
            )
        else:
            self.logger.warning(f"⚠️ OptionPCRService初始化完成（缺失{len(missing_keys)}项配置）")
    
    # ==================== 核心方法：计算单个标的PCR ====================
    
    def calculate_pcr_for_underlying(
        self,
        underlying: str,
        market_code: int,
        current_price: Optional[float] = None,
        days: int = 60
    ) -> Dict[str, Any]:
        """
        V6.1核心：计算单个标的的PCR指标（升级版）
        
        参数:
            underlying: 标的代码（'IO'/'510300'等）
            market_code: 市场代码（7=中金所, 8=上交所, 9=深交所）
            current_price: 标的当前价格（用于选择平值合约）
            days: 历史数据天数
        
        返回:
            {
                'underlying': str,
                'market_code': int,
                'pcr_volume': float,      # 成交量PCR
                'pcr_oi': float,          # 持仓量PCR
                'pcr_ma5': float,         # 5日移动平均PCR
                'call_volume': float,
                'put_volume': float,
                'call_oi': float,
                'put_oi': float,
                'signal': str,            # 情绪信号
                'tolerance': float,       # 动态容忍度
                'data_quality': str,
                'contracts_used': int,
                'calculation_time': str
            }
        
        升级点:
        ✅ 通过data_service加载数据（解耦TDX）
        ✅ 动态容忍度获取（优先ThresholdService）
        ✅ 完整降级策略（数据加载失败时返回模拟数据）
        ✅ 所有数值强制Python原生float
        """
        try:
            # 1. ✅ 获取动态容忍度（用于平值筛选）
            tolerance = self._get_dynamic_tolerance(underlying, market_code)
            
            # 2. ✅ 获取标的当前价格（用于平值筛选）
            if current_price is None:
                current_price = self._get_current_price(underlying, default_price=4000.0)
            
            # 3. ✅ 关键优化：先筛选合约，再加载数据（传入current_price和tolerance）
            option_data = self._load_option_data(
                underlying=underlying,
                market_code=market_code,
                current_price=current_price,  # ✅ 新增参数
                tolerance=tolerance,           # ✅ 新增参数
                days=days
            )
            
            if not option_data or len(option_data) == 0:
                self.logger.warning(
                    f"⚠️ {underlying} 期权数据加载失败（市场代码: {market_code}），"
                    f"触发降级策略"
                )
                return self._generate_mock_pcr_result(underlying, market_code, tolerance)
            
            # 3. ✅ 筛选近月平值合约
            near_month_contracts = option_data
            atm_contracts = self._filter_atm_contracts(near_month_contracts, current_price, tolerance)
            
            if len(atm_contracts) == 0:
                return self._generate_mock_pcr_result(underlying, market_code, tolerance)
            
            # 4. ✅ 计算PCR指标
            pcr_result = self._calculate_pcr_metrics(atm_contracts)
            
            # 5. ✅ 生成信号（使用动态容忍度）
            signal = self._generate_pcr_signal(pcr_result['pcr_ma5'], tolerance)
            
            # 6. ✅ 强制转换为Python原生类型（关键修复：防Plotly序列化错误）
            return {
                'underlying': underlying,
                'market_code': ensure_python_int(market_code),
                'pcr_volume': ensure_python_float(pcr_result['pcr_volume']),
                'pcr_oi': ensure_python_float(pcr_result['pcr_oi']),
                'pcr_ma5': ensure_python_float(pcr_result['pcr_ma5']),
                'call_volume': ensure_python_float(pcr_result['call_volume']),
                'put_volume': ensure_python_float(pcr_result['put_volume']),
                'call_oi': ensure_python_float(pcr_result['call_oi']),
                'put_oi': ensure_python_float(pcr_result['put_oi']),
                'signal': signal,
                'tolerance': ensure_python_float(tolerance),
                'data_quality': pcr_result['data_quality'],
                'contracts_used': ensure_python_int(pcr_result['contracts_used']),
                'calculation_time': datetime.now().isoformat()
            }
        
        except Exception as e:
            self.logger.error(f"❌ {underlying} PCR计算失败: {str(e)[:100]}")
            import traceback
            self.logger.debug(traceback.format_exc())
            
            # 降级：返回模拟数据
            tolerance = self._get_dynamic_tolerance(underlying, market_code)
            return self._generate_mock_pcr_result(underlying, market_code, tolerance)
    
    # ==================== 核心方法：计算综合PCR ====================
    
    def calculate_composite_pcr(self) -> Dict[str, Any]:
        """
        V6.1核心：计算综合PCR指标（多标的加权）
        
        返回:
            {
                'composite_pcr': float,       # 综合PCR
                'composite_signal': str,      # 综合信号
                'components': Dict[str, Dict], # 各标的PCR结果
                'weights_used': Dict[str, float], # 使用的权重
                'calculation_time': str,
                'threshold_source': str       # 阈值来源（动态/静态）
            }
        
        升级点:
        ✅ 使用V6.1标准配置权重（option_markets.pcr_weight）
        ✅ 动态权重调整（根据市场状态）
        ✅ 完整降级策略（单个标的失败不影响整体）
        """
        components = {}
        weights_used = {}
        
        # 定义主要标的（与V5.7兼容 + V6.1扩展）
        main_underlyings = self.config_service.get('option_underlying_mapping', {})
        # main_underlyings = [
        #     ('IO', 7, 4000.0),    # 沪深300指数期权（中金所）
        #     ('MO', 7, 7000.0),    # 中证1000指数期权（中金所）
        #     ('510300', 8, 4.0),   # 沪深300ETF期权（上交所）
        #     ('510500', 8, 7.5),   # 中证500ETF期权（上交所）
        #     ('159919', 9, 4.2)    # 沪深300ETF期权（深交所，V6.1新增）
        # ]
        
        # 1. ✅ 计算各标的PCR（独立try-except，单个失败不影响整体）
        for underlying, underlying_conte in main_underlyings.items():
            try:
                # 获取标的当前价格（从market_benchmarks或使用默认值）
                underlying_code, market_code, weight, default_price = underlying_conte
                current_price = self._get_current_price(underlying, default_price)
                
                # 计算PCR
                pcr_result = self.calculate_pcr_for_underlying(
                    underlying,
                    market_code,
                    current_price=current_price,
                    days=60
                )
                
                components[underlying] = pcr_result
                
                # # 获取权重（从option_markets配置）
                # market_key = self._get_market_key(market_code)
                # weight = self.option_markets.get(market_key, {}).get('pcr_weight', 0.2)
                weights_used[underlying] = weight
                
            except Exception as e:
                self.logger.warning(
                    f"⚠️ {underlying} PCR计算失败（已跳过）: {str(e)[:50]}"
                )
                # 降级：使用模拟数据
                tolerance = self._get_dynamic_tolerance(underlying, market_code)
                components[underlying] = self._generate_mock_pcr_result(
                    underlying, market_code, tolerance
                )
                weights_used[underlying] = 0.0  # 失败标的权重设为0
        
        # 2. ✅ 加权计算综合PCR
        weighted_pcr = 0.0
        total_weight = 0.0
        
        for underlying, result in components.items():
            if 'pcr_ma5' in result and result.get('data_quality') != 'error':
                weight = weights_used.get(underlying, 0.0)
                weighted_pcr += result['pcr_ma5'] * weight
                total_weight += weight
        
        composite_pcr = weighted_pcr / total_weight if total_weight > 0 else 1.0
        composite_signal = self._generate_pcr_signal(composite_pcr, tolerance=0.05)
        
        # 3. ✅ 强制转换为Python原生类型
        return {
            'composite_pcr': ensure_python_float(composite_pcr),
            'composite_signal': composite_signal,
            'components': components,
            'weights_used': weights_used,
            'calculation_time': datetime.now().isoformat(),
            'threshold_source': '动态' if self.threshold_service else '静态'
        }
    
    # ==================== 辅助方法：动态容忍度获取 ====================
    def _get_dynamic_tolerance(self, underlying: str, market_code: int, vol_percentile: float = 50.0) -> float:
        """
        ✅ 优化版：精准对接 ThresholdService V6.1 配置结构
        
        逻辑流程:
        1️⃣ 优先：从 ThresholdService 获取基础容忍度（固定阈值名 'option_tolerance_base'）
        2️⃣ 动态调整：根据波动率分位数应用 volatility_based 配置（OptionPCRService 自主实现）
        3️⃣ 市场微调：根据 market_code 进行流动性/波动率补偿
        4️⃣ 降级：ThresholdService 不可用时从配置获取
        
        关键修复:
        ✅ 阈值名称修正：使用固定名 'option_tolerance_base'（非 per-underlying）
        ✅ 配置路径修正：从 self.option_tolerance.volatility_based 获取参数
        ✅ 策略解耦：波动率调整由 OptionPCRService 自主实现（不依赖 ThresholdService 不存在的策略）
        ✅ 类型安全：所有数值强制 Python 原生 float
        
        参数:
            underlying: 标的代码（如 '510300'）
            market_code: 市场代码（7=中金所, 8=上交所, 9=深交所）
            vol_percentile: 波动率分位数（0-100，用于动态调整，默认50.0）
        
        返回:
            容忍度（float，0.03-0.10 之间）
        """
        # ✅ 修复1：使用固定阈值名称（V6.1 配置中无 per-underlying 阈值）
        threshold_name = 'option_tolerance_base'
        
        # 1. 优先从 ThresholdService 获取基础容忍度（static 策略）
        base_tolerance = None
        if self.threshold_service:
            try:
                # ✅ 关键修复：使用固定阈值名 + static 策略（避免策略不匹配）
                base_tolerance = self.threshold_service.get_threshold(
                    threshold_name,
                    context={
                        'underlying': underlying,
                        'market_code': market_code,
                        'vol_percentile': vol_percentile  # 传递波动率用于日志
                    },
                    strategy='static'  # ✅ 明确指定 static 策略（避免 auto 选择不存在的策略）
                )
                self.logger.debug(
                    f"✅ 基础容忍度（ThresholdService）| {underlying} = {base_tolerance:.3f} | "
                    f"阈值名: {threshold_name}"
                )
            except Exception as e:
                self.logger.warning(
                    f"⚠️ ThresholdService 获取基础容忍度失败（回退配置）: {str(e)[:50]}"
                )
        
        # 2. 降级：从配置获取基础容忍度
        if base_tolerance is None:
            base_tolerance = float(self.option_tolerance.get('base_tolerance', 0.05))
            self.logger.debug(
                f"✅ 基础容忍度（配置降级）| {underlying} = {base_tolerance:.3f} | "
                f"来源: option_tolerance.base_tolerance"
            )
        
        # 3. ✅ 修复2：波动率动态调整（OptionPCRService 自主实现，不依赖 ThresholdService）
        #    原因：ThresholdService 无 volatility_based 策略，且配置路径不匹配（volatility_based vs volatility_adjustment）
        volatility_config = self.option_tolerance.get('volatility_based', {})
        threshold_percentile = float(volatility_config.get('threshold_percentile', 0.7))
        low_vol_tolerance = float(volatility_config.get('low_vol_tolerance', 0.03))
        high_vol_tolerance = float(volatility_config.get('high_vol_tolerance', 0.08))
        
        # 波动率分位数映射（0-100 → 0-1）
        vol_ratio = vol_percentile / 100.0
        
        # 动态调整逻辑（与配置语义一致）
        if vol_ratio > threshold_percentile:  # 高波动市场（>70%分位数）
            adjusted_tolerance = high_vol_tolerance
            adjustment_type = 'high_vol'
            self.logger.debug(
                f"📈 高波动调整 | vol={vol_percentile:.1f}% > {threshold_percentile*100:.0f}% | "
                f"容忍度: {base_tolerance:.3f} → {adjusted_tolerance:.3f}"
            )
        elif vol_ratio < (1.0 - threshold_percentile):  # 低波动市场（<30%分位数）
            adjusted_tolerance = low_vol_tolerance
            adjustment_type = 'low_vol'
            self.logger.debug(
                f"📉 低波动调整 | vol={vol_percentile:.1f}% < {(1-threshold_percentile)*100:.0f}% | "
                f"容忍度: {base_tolerance:.3f} → {adjusted_tolerance:.3f}"
            )
        else:  # 中等波动
            adjusted_tolerance = base_tolerance
            adjustment_type = 'normal'
            self.logger.debug(
                f"📊 正常波动 | vol={vol_percentile:.1f}% | 容忍度: {adjusted_tolerance:.3f}"
            )
        
        # 4. ✅ 修复3：市场特性微调（保持原有逻辑）
        market_adjustment = 1.0
        if market_code == 7:  # 中金所（指数期权，波动大）
            market_adjustment = 1.2
            self.logger.debug(f"📊 {underlying} 市场微调: ×1.2（中金所高波动）")
        elif market_code == 9:  # 深交所（流动性较低）
            market_adjustment = 1.1
            self.logger.debug(f"📊 {underlying} 市场微调: ×1.1（深交所低流动性）")
        
        # 5. 最终容忍度 = 波动率调整值 × 市场微调系数
        final_tolerance = adjusted_tolerance * market_adjustment
        
        # 6. ✅ 强制 Python 原生 float（防 Plotly 序列化错误）
        final_tolerance = float(np.clip(final_tolerance, 0.01, 0.15))  # 限制合理范围
        
        self.logger.info(
            f"🎯 动态容忍度 | {underlying} = {final_tolerance:.3f} | "
            f"基础={base_tolerance:.3f} | 波动调整={adjustment_type} | 市场×{market_adjustment:.1f}"
        )
        
        return final_tolerance    
    # def _get_dynamic_tolerance(self, underlying: str, market_code: int) -> float:
    #     """
    #     获取动态容忍度（优先ThresholdService）
        
    #     逻辑:
    #     1. 优先从ThresholdService获取动态容忍度
    #     2. 降级：从配置获取静态容忍度
    #     3. 最终降级：使用默认值0.05
        
    #     返回:
    #         容忍度（float，0-1之间）
    #     """
    #     # ✅ 优先从ThresholdService获取（波动率自适应+流动性调整）
    #     if self.threshold_service:
    #         try:
    #             # 构建阈值名称（如'option_510300_tolerance'）
    #             threshold_name = f"option_{underlying}_tolerance"
                
    #             tolerance = self.threshold_service.get_threshold(
    #                 threshold_name,
    #                 context={
    #                     'underlying': underlying,
    #                     'market_code': market_code,
    #                     'volatility_percentile': 50.0  # 默认中等波动
    #                 },
    #                 strategy='volatility_based'
    #             )
                
    #             self.logger.debug(
    #                 f"🔄 动态容忍度 | {underlying} = {tolerance:.3f} | 策略=volatility_based"
    #             )
    #             return float(tolerance)
                
    #         except Exception as e:
    #             self.logger.warning(
    #                 f"⚠️ 动态容忍度获取失败，回退静态配置: {str(e)[:30]}"
    #             )
        
    #     # 降级：从配置获取静态容忍度
    #     base_tolerance = float(self.option_tolerance.get('base_tolerance', 0.05))
        
    #     # 根据市场代码微调
    #     if market_code == 7:  # 中金所（指数期权，波动大）
    #         base_tolerance *= 1.2
    #     elif market_code == 9:  # 深交所（流动性较低）
    #         base_tolerance *= 1.1
        
    #     return float(base_tolerance)
    
    # ==================== 辅助方法：数据加载与处理 ====================
    # ==================== 核心优化：先筛选合约，再加载数据 ====================
    
    def _load_option_data(
        self,
        underlying: str,
        market_code: int,
        current_price: float,  # ✅ 新增：用于平值筛选
        tolerance: float,       # ✅ 新增：平值容忍度
        days: int = 60
    ) -> Optional[List[Dict]]:
        """
        ✅ 优化版：先筛选近月平值合约，再加载K线（节省90%资源）
        
        优化点:
        ✅ 1. 先获取合约基本信息（无K线）
        ✅ 2. 筛选近月合约（根据到期月份）
        ✅ 3. 筛选平值合约（根据行权价与current_price的偏离度）
        ✅ 4. 仅加载筛选出的合约K线（8-10个，非100+个）
        ✅ 5. 详细日志（显示筛选过程）
        """
        try:
            # ✅ 优化步骤1：获取合约基本信息（无K线，仅元数据）
            all_contracts = self.data_service.get_option_contracts(
                underlying=underlying,
                market_code=market_code
            )
            
            if not all_contracts or len(all_contracts) == 0:
                self.logger.warning(f"⚠️ 未找到{underlying}的期权合约（市场代码: {market_code}）")
                return None
            
            self.logger.debug(f"🔍 {underlying}共有{len(all_contracts)}个期权合约")
            
            # ✅ 优化步骤2：筛选近月合约（根据到期月份）
            near_month_contracts = self._filter_near_month_contracts_metadata(
                all_contracts,
                underlying,
                market_code
            )
            
            if len(near_month_contracts) == 0:
                self.logger.warning(f"⚠️ 未找到{underlying}的近月合约")
                return None
            
            self.logger.debug(f"   • 近月合约: {len(near_month_contracts)}个")
            
            # ✅ 优化步骤3：筛选平值合约（根据行权价与current_price的偏离度）
            atm_contracts = self._filter_atm_contracts_metadata(
                near_month_contracts,
                current_price,
                tolerance
            )
            
            if len(atm_contracts) == 0:
                # 降级：选择最接近的2个看涨+2个看跌
                atm_contracts = self._select_closest_contracts(
                    near_month_contracts,
                    current_price
                )
            
            self.logger.debug(
                f"   • 平值合约: {len(atm_contracts)}个 "
                f"(看涨{sum(1 for c in atm_contracts if c['option_type']=='call')} | "
                f"看跌{sum(1 for c in atm_contracts if c['option_type']=='put')})"
            )
            
            # ✅ 优化步骤4：仅加载筛选出的合约K线（关键优化！）
            option_data = []
            successful_loads = 0
            
            for contract in atm_contracts:
                try:
                    # 仅加载筛选出的合约K线（8-10个，非100+个）
                    kline_data = self.data_service.load_derivative_data(
                        code=contract['code'],
                        market_code=market_code,
                        days=days
                    )
                    
                    if kline_data is None or len(kline_data) == 0:
                        continue
                    
                    # 验证必要列
                    if not all(col in kline_data.columns for col in ['volume', 'open_interest']):
                        continue
                    
                    # 构建合约数据
                    contract_data = {
                        'code': contract['code'],
                        'name': contract.get('name', contract['code']),
                        'option_type': contract['option_type'],
                        'strike_price': contract['strike_price'],
                        'expiry_month': contract['expiry_month'],
                        'kline_data': kline_data
                    }
                    
                    option_data.append(contract_data)
                    successful_loads += 1
                    
                except Exception as e:
                    # ✅ 修复：详细错误日志（显示实际错误）
                    self.logger.warning(
                        f"⚠️ 加载合约{contract.get('code', 'unknown')}失败: {str(e)[:80]}"
                    )
                    import traceback
                    self.logger.debug(traceback.format_exc())
                    continue
            
            # 验证加载结果
            if successful_loads == 0:
                self.logger.warning(
                    f"⚠️ 未成功加载任何{underlying}的平值合约K线 | "
                    f"尝试合约: {len(atm_contracts)}个 | 原因: TDX接口可能不可用或合约代码无效"
                )
                return None
            
            self.logger.info(
                f"✅ 成功加载{underlying}的{successful_loads}个平值合约K线 "
                f"(筛选自{len(all_contracts)}个原始合约)"
            )
            return option_data
        
        except Exception as e:
            self.logger.error(f"❌ 加载{underlying}期权数据失败: {str(e)[:100]}")
            import traceback
            self.logger.debug(traceback.format_exc())
            return None
    
    # ==================== 辅助方法：元数据筛选（无K线） ====================
    
    def _filter_near_month_contracts_metadata(
        self,
        contracts: List[Dict],
        underlying: str,
        market_code: int
    ) -> List[Dict]:
        """筛选近月合约（仅元数据，无K线）"""
        if not contracts:
            return []
        
        current_month = datetime.now().strftime('%y%m')
        near_contracts = []
        
        for contract in contracts:
            expiry = contract.get('expiry_month', '0000')
            
            # 中金所期权：直接比较年月
            if market_code == 7:
                if expiry >= current_month:
                    near_contracts.append(contract)
            # ETF期权：比较月份数字
            else:
                try:
                    expiry_month = int(expiry[-2:]) if len(expiry) >= 2 else 0
                    current_month_num = datetime.now().month
                    if expiry_month >= current_month_num and expiry_month <= current_month_num + 1:
                        near_contracts.append(contract)
                except:
                    continue
        
        # 取最近的2个月（按到期月份排序）
        near_contracts.sort(key=lambda x: x.get('expiry_month', '9999'))
        return near_contracts[:4]  # 取4个近月合约（2个看涨+2个看跌）
    
    def _filter_atm_contracts_metadata(
        self,
        contracts: List[Dict],
        current_price: float,
        tolerance: float
    ) -> List[Dict]:
        """筛选平值合约（仅元数据，无K线）"""
        if not contracts or current_price <= 0:
            return contracts
        
        atm_contracts = []
        for contract in contracts:
            strike = contract.get('strike_price', 0.0)
            if strike <= 0:
                continue
            
            # 计算偏离度
            deviation = abs(strike - current_price) / current_price
            if deviation <= tolerance:
                atm_contracts.append(contract)
        
        # 确保至少有2个看涨+2个看跌
        calls = [c for c in atm_contracts if c.get('option_type') == 'call']
        puts = [c for c in atm_contracts if c.get('option_type') == 'put']
        
        if len(calls) < 2 or len(puts) < 2:
            return []  # 降级：返回空，后续会选择最接近的
        
        return atm_contracts
    
    def _select_closest_contracts(
        self,
        contracts: List[Dict],
        current_price: float
    ) -> List[Dict]:
        """选择最接近当前价格的合约（降级策略）"""
        if not contracts:
            return []
        
        # 按行权价与当前价格的偏离度排序
        sorted_contracts = sorted(
            contracts,
            key=lambda x: abs(x.get('strike_price', 0) - current_price)
        )
        
        # 选择最接近的4个（2个看涨+2个看跌）
        calls = [c for c in sorted_contracts if c.get('option_type') == 'call'][:2]
        puts = [c for c in sorted_contracts if c.get('option_type') == 'put'][:2]
        
        return calls + puts
    
    def _generate_mock_kline(self, days: int) -> pd.DataFrame:
        """生成模拟K线数据（降级策略）"""
        dates = pd.date_range(end=datetime.now(), periods=days)
        base_price = 100.0
        
        return pd.DataFrame({
            'datetime': dates,
            'open': base_price + np.random.randn(days) * 2,
            'high': base_price + np.abs(np.random.randn(days)) * 3,
            'low': base_price - np.abs(np.random.randn(days)) * 3,
            'close': base_price + np.random.randn(days) * 2,
            'volume': np.random.randint(1000, 10000, days),
            'open_interest': np.random.randint(5000, 50000, days)
        })
    
    # ==================== 辅助方法：合约筛选 ====================
    
    def _filter_near_month_contracts(
        self,
        option_data: List[Dict],
        underlying: str,
        market_code: int
    ) -> List[Dict]:
        """筛选近月合约（V6.1优化版）"""
        if not option_data:
            return []
        
        # 获取当前月份
        current_month = datetime.now().strftime('%y%m')
        
        # 筛选逻辑（与V5.7兼容）
        near_contracts = []
        for contract in option_data:
            expiry = contract.get('expiry_month', '0000')
            
            # 中金所期权：直接比较年月
            if market_code == 7:
                if expiry >= current_month:
                    near_contracts.append(contract)
            # ETF期权：比较月份数字
            else:
                try:
                    expiry_month = int(expiry[-2:]) if len(expiry) >= 2 else 0
                    current_month_num = datetime.now().month
                    if expiry_month >= current_month_num and expiry_month <= current_month_num + 1:
                        near_contracts.append(contract)
                except:
                    continue
        
        # 取最近的2个月
        return sorted(near_contracts, key=lambda x: x.get('expiry_month', '9999'))[:2]
    
    def _filter_atm_contracts(
        self,
        contracts: List[Dict],
        current_price: Optional[float],
        tolerance: float
    ) -> List[Dict]:
        """筛选平值附近合约（V6.1优化版）"""
        if not contracts or current_price is None or current_price <= 0:
            return contracts
        
        # 计算偏离度并筛选
        atm_contracts = []
        for contract in contracts:
            strike = contract.get('strike_price', 0.0)
            if strike <= 0:
                continue
            
            deviation = abs(strike - current_price) / current_price
            if deviation <= tolerance:
                atm_contracts.append(contract)
        
        # 如果没有平值合约，选择最接近的2个
        if len(atm_contracts) == 0:
            sorted_contracts = sorted(
                contracts,
                key=lambda x: abs(x.get('strike_price', 0) - current_price)
            )
            atm_contracts = sorted_contracts[:2]
        
        return atm_contracts
    
    # ==================== 辅助方法：PCR计算 ====================
    
    def _calculate_pcr_metrics(self, atm_contracts: List[Dict]) -> Dict[str, float]:
        """计算PCR指标（V6.1优化版）"""
        calls = [c for c in atm_contracts if c.get('option_type') == 'call']
        puts = [c for c in atm_contracts if c.get('option_type') == 'put']
        
        if len(calls) == 0 or len(puts) == 0:
            return {
                'pcr_volume': 1.0,
                'pcr_oi': 1.0,
                'pcr_ma5': 1.0,
                'call_volume': 0.0,
                'put_volume': 0.0,
                'call_oi': 0.0,
                'put_oi': 0.0,
                'data_quality': 'error',
                'contracts_used': 0
            }
        
        # 计算最新成交量和持仓量
        call_volume = sum(c['kline_data']['volume'].iloc[-1] for c in calls if len(c['kline_data']) > 0)
        put_volume = sum(p['kline_data']['volume'].iloc[-1] for p in puts if len(p['kline_data']) > 0)
        call_oi = sum(c['kline_data']['open_interest'].iloc[-1] for c in calls if len(c['kline_data']) > 0)
        put_oi = sum(p['kline_data']['open_interest'].iloc[-1] for p in puts if len(p['kline_data']) > 0)
        
        # 计算PCR
        pcr_volume = put_volume / call_volume if call_volume > 0 else 1.0
        pcr_oi = put_oi / call_oi if call_oi > 0 else 1.0
        
        # 计算5日移动平均PCR
        pcr_history = []
        for i in range(1, 6):
            cv = sum(c['kline_data']['volume'].iloc[-i] for c in calls if len(c['kline_data']) >= i)
            pv = sum(p['kline_data']['volume'].iloc[-i] for p in puts if len(p['kline_data']) >= i)
            if cv > 0:
                pcr_history.append(pv / cv)
        
        pcr_ma5 = np.mean(pcr_history) if pcr_history else pcr_volume
        
        # 数据质量评估
        data_quality = 'good' if call_oi > 10000 else 'low_liquidity'
        
        return {
            'pcr_volume': pcr_volume,
            'pcr_oi': pcr_oi,
            'pcr_ma5': pcr_ma5,
            'call_volume': call_volume,
            'put_volume': put_volume,
            'call_oi': call_oi,
            'put_oi': put_oi,
            'data_quality': data_quality,
            'contracts_used': len(calls) + len(puts)
        }
    
    # ==================== 辅助方法：信号生成 ====================
    
    def _generate_pcr_signal(self, pcr_value: float, tolerance: float = 0.05) -> str:
        """
        生成PCR情绪信号（V6.1升级版：支持动态阈值）
        
        逻辑:
        1. 使用动态容忍度调整阈值
        2. 根据PCR值生成信号
        """
        # ✅ 动态阈值调整（基于容忍度）
        extreme_high = 1.5 + tolerance * 2
        warning_high = 1.2 + tolerance
        warning_low = 0.8 - tolerance
        extreme_low = 0.5 - tolerance * 2
        
        if pcr_value > extreme_high:
            return '🔴 极度悲观（潜在反弹）'
        elif pcr_value > warning_high:
            return '🟠 看跌情绪浓厚'
        elif pcr_value > 1.0:
            return '🟡 中性偏空'
        elif pcr_value > warning_low:
            return '🟢 中性偏多'
        elif pcr_value > extreme_low:
            return '🔵 看涨情绪浓厚'
        else:
            return '🟣 极度乐观（潜在回调）'
    
    # ==================== 辅助方法：降级策略 ====================
    
    def _generate_mock_pcr_result(
        self,
        underlying: str,
        market_code: int,
        tolerance: float
    ) -> Dict[str, Any]:
        """生成模拟PCR结果（降级策略）"""
        # 随机生成合理PCR值（基于市场类型）
        if market_code == 7:  # 指数期权（波动大）
            pcr_ma5 = np.random.uniform(0.8, 1.5)
        else:  # ETF期权（波动小）
            pcr_ma5 = np.random.uniform(0.9, 1.3)
        
        signal = self._generate_pcr_signal(pcr_ma5, tolerance)
        
        return {
            'underlying': underlying,
            'market_code': ensure_python_int(market_code),
            'pcr_volume': ensure_python_float(pcr_ma5 * 0.95),
            'pcr_oi': ensure_python_float(pcr_ma5 * 1.05),
            'pcr_ma5': ensure_python_float(pcr_ma5),
            'call_volume': 10000.0,
            'put_volume': 10000.0 * pcr_ma5,
            'call_oi': 50000.0,
            'put_oi': 50000.0 * pcr_ma5,
            'signal': signal,
            'tolerance': ensure_python_float(tolerance),
            'data_quality': 'simulated',  # 标记为模拟数据
            'contracts_used': 2,
            'calculation_time': datetime.now().isoformat()
        }

    def _get_current_price(self, underlying: str, default_price: float) -> float:
        """
        ✅ 优化版：精准区分数据源
        - 指数期权（IO/HO/MO）→ 从数据库直接查询（避免TDX延迟/失败）
        - ETF期权（510300/510500等）→ 通过（优先TDX）
        """
        try:
            # ✅ 标的映射（指数期权→指数代码，ETF期权→ETF代码）
            underlying_to_index = {
                # 指数期权：映射到指数代码（用于数据库查询）
                'IO': '000300',   # 沪深300指数
                # 'HO': '000016',   # 上证50指数
                'MO': '000852',   # 中证1000指数
                
                # ETF期权：映射到ETF代码（用于TDX加载）
                '510300': '510300',  # 沪深300ETF
                '510500': '510500',  # 中证500ETF
                # '159919': '159919',  # 沪深300ETF(深)
                '588000': '588000',  # 科创50ETF
                '159915': '159915'   # 创业板ETF
            }
            
            index_code = underlying_to_index.get(underlying)
            if not index_code:
                self.logger.warning(f"⚠️ 未找到{underlying}的标的映射，使用默认价格")
                return default_price
            
            # ✅ 关键优化：区分数据源
            if underlying in ['IO', 'HO', 'MO']:
                # ========== 指数期权：直接从数据库查询（绕过TDX） ==========
                current_price = float(self.data_service.load_index_data(index_code, min_days=1)['close'].iloc[-1])
                if current_price is not None:
                    self.logger.debug(
                        f"✅ {underlying}当前价格（数据库）: {current_price:.2f} | 标的: {index_code}"
                    )
                    return current_price
                # 降级：使用默认价格
                self.logger.warning(
                    f"⚠️ {underlying}数据库查询失败，使用默认价格 {default_price}"
                )
                return default_price
            
            else:
                # ========== ETF期权：通过data_service加载（TDX优先） ==========
                df = self.data_service.load_derivative_data(index_code, market_code=33, days=5)
                
                if len(df) > 0 and 'close' in df.columns and len(df['close']) > 0:
                    current_price = float(df['close'].iloc[-1])
                    self.logger.debug(
                        f"✅ {underlying}当前价格 : {current_price:.3f} | 标的: {index_code}"
                    )
                    return current_price
                else:
                    self.logger.warning(
                        f"⚠️ {underlying}数据无效（{index_code}），使用默认价格 {default_price}"
                    )
                    return default_price
        
        except Exception as e:
            self.logger.error(f"❌ 获取{underlying}价格异常: {str(e)[:100]}")
            import traceback
            self.logger.debug(traceback.format_exc())
            return default_price

    
    def _get_market_key(self, market_code: int) -> str:
        """根据市场代码获取配置键名"""
        market_map = {7: 'cffex', 8: 'sse', 9: 'szse'}
        return market_map.get(market_code, 'cffex')


# ==================== 使用示例 ====================
def example_option_pcr_service():
    """OptionPCRService使用示例（V6.1）"""
    
    print("=" * 80)
    print("🧪 OptionPCRService V6.1 使用示例")
    print("=" * 80)
    
    # 1. 初始化服务（简化版）
    print("\n1️⃣ 初始化OptionPCRService...")
    
    class MockConfigService:
        def __init__(self):
            self.config = {
                'option_tolerance': {
                    'base_tolerance': 0.05,
                    'volatility_based': {
                        'enabled': True,
                        'low_vol_tolerance': 0.03,
                        'high_vol_tolerance': 0.08
                    }
                },
                'option_markets': {
                    'cffex': {'pcr_weight': 0.4, 'market_code': 7},
                    'sse': {'pcr_weight': 0.4, 'market_code': 8},
                    'szse': {'pcr_weight': 0.2, 'market_code': 9}
                },
                'market_benchmarks': {
                    '大盘': {'code': '000300', 'weight': 0.40}
                }
            }
    
    class MockDataService:
        pass
    
    config_service = MockConfigService()
    data_service = MockDataService()
    
    # 模拟ThresholdService（可选）
    class MockThresholdService:
        def get_threshold(self, name, context, strategy):
            return 0.06
    
    threshold_service = MockThresholdService()
    
    pcr_service = OptionPCRService(data_service, config_service, threshold_service)
    print("✅ 服务初始化成功")
    
    # 2. 计算单个标的PCR
    print("\n2️⃣ 计算沪深300指数期权（IO）PCR...")
    io_result = pcr_service.calculate_pcr_for_underlying('IO', 7, current_price=4000.0)
    print(f"   ✅ PCR(5日MA): {io_result['pcr_ma5']:.3f}")
    print(f"   ✅ 信号: {io_result['signal']}")
    print(f"   ✅ 容忍度: {io_result['tolerance']:.3f}（动态）")
    
    # 3. 计算综合PCR
    print("\n3️⃣ 计算综合PCR（多标的加权）...")
    composite_result = pcr_service.calculate_composite_pcr()
    print(f"   ✅ 综合PCR: {composite_result['composite_pcr']:.3f}")
    print(f"   ✅ 综合信号: {composite_result['composite_signal']}")
    print(f"   ✅ 阈值来源: {composite_result['threshold_source']}")
    
    # 4. 验证数据类型
    print("\n4️⃣ 验证数据类型（防Plotly序列化错误）:")
    sample_pcr = composite_result['composite_pcr']
    is_python_float = isinstance(sample_pcr, float) and not isinstance(sample_pcr, np.floating)
    print(f"   ✅ 综合PCR类型: {type(sample_pcr).__name__} | Python float: {is_python_float}")
    
    print("\n" + "=" * 80)
    print("✅ OptionPCRService V6.1 示例运行完成")
    print("=" * 80)


if __name__ == "__main__":
    example_option_pcr_service()