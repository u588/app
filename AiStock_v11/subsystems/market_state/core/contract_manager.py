#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AiStock V10 — 动态合约代码推导引擎 (ContractManager)

V9 → V10 升级改进:
  1. **移除所有硬编码字典**: COMMODITY_DELIVERY_MONTHS, VARIETY_MARKET_CODE,
     VARIETY_MARKET_TYPE, VARIETY_NAMES, OPTION_UNDERLYING_CONFIG, INDEX_FUTURES_CONFIG
     全部从 ConfigService (YAML) 动态加载
  2. 构造函数接受 ConfigService (通过 ServiceContainer 注入)
  3. 保留: ContractInfo, FuturesContractPair, IndexFuturesContract, OptionContractGroup 数据类
  4. 保留: 动态合约推导逻辑, code/code_name 双码制
  5. 保留: L8/L9 后缀处理 (NOT M0/M1), _parse_contract_code 带 L0-L9 正则
  6. xlsx 代码表加载保留

核心职责:
  - 从 ConfigService 加载品种/交割月/市场映射 (V10: 零硬编码)
  - 从 xlsx 加载完整合约代码表 (code/code_name/market_code/category 映射)
  - 基于当前日期动态推导商品期货近月/远月合约代码
  - 基于当前日期动态推导股指期货当月/下季月合约代码
  - 基于当前日期动态推导期权近月/远月合约组
  - 提供 code ↔ code_name 双向查找

依赖:
  - ConfigService (V10: YAML配置唯一数据源)
  - openpyxl (读取 xlsx 代码表)
  - pandas
"""

from __future__ import annotations

import os
import re
import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from collections import defaultdict

import pandas as pd

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════
#  数据结构定义
# ═══════════════════════════════════════════════════════════════════════

@dataclass
class ContractInfo:
    """单个合约的完整信息（从代码表解析而来）。

    V10: 区分 code (TDX接口用) 和 code_name (显示/解析用)

    Attributes:
        code:           TDX 内部合约代码 (用于 API 调用), 如 HO8Q0438, 10009633
        code_name:      合约显示名称 (用于解析), 如 HO2602-P-2650, 510050C3A02700
        market_code:    TDX 市场代码整数, 如 7, 8, 9, 28, 29, 30, 47, 66
        market_type:    市场类型字符串, 如 future_sh, option_zj
        market_name:    市场中文名, 如 中金所期权
        category:       类别 (3=期货, 8=股票, 10=宏观, 12=期权)
        variety:        品种代码, 如 CU, IO
        delivery_year:  交割年, 如 2026 (0=非交割合约)
        delivery_month: 交割月, 如 6 (0=非交割合约)
    """
    code: str
    code_name: str
    market_code: int
    market_type: str
    market_name: str
    category: int
    variety: str
    delivery_year: int
    delivery_month: int


@dataclass
class FuturesContractPair:
    """商品期货近月/远月合约对。

    Attributes:
        variety_key:  品种英文键名, 如 copper
        variety_code: 品种 TDX 代码, 如 CU
        near_code:    近月合约 code (TDX内部码)
        far_code:     远月合约 code (TDX内部码)
        market_code:  TDX 市场代码整数
        market_type:  市场类型字符串, 如 future_sh
        near_year:    近月交割年
        near_month:   近月交割月
        far_year:     远月交割年
        far_month:    远月交割月
    """
    variety_key: str
    variety_code: str
    near_code: str
    far_code: str
    market_code: int
    market_type: str
    near_year: int
    near_month: int
    far_year: int
    far_month: int


@dataclass
class IndexFuturesContract:
    """股指期货合约信息。

    Attributes:
        key:                品种英文键名, 如 if
        variety_code:       品种 TDX 代码, 如 IF
        futures_code:       当月合约 code
        next_quarter_code:  下季月合约 code
        spot_code:          现货指数代码, 如 000300
        market_code:        TDX 市场代码整数
        market_type:        市场类型字符串
        delivery_year:      交割年
        delivery_month:     交割月
    """
    key: str
    variety_code: str
    futures_code: str
    next_quarter_code: str
    spot_code: str
    market_code: int
    market_type: str
    delivery_year: int
    delivery_month: int


@dataclass
class OptionContractGroup:
    """期权合约组（某标的某月的全部行权价合约）。

    V10: call_codes / put_codes 使用 TDX 内部码 (code 列),
    code_names 使用显示码 (code_name 列).

    Attributes:
        underlying:     标的代码, 如 IO 或 510300
        market_code:    TDX 市场代码整数
        market_type:    市场类型字符串
        delivery_year:  交割年
        delivery_month: 交割月
        contracts:      命中的 ContractInfo 列表
        call_codes:     看涨合约 code 列表 (TDX内部码)
        put_codes:      看跌合约 code 列表 (TDX内部码)
        call_code_names: 看涨合约 code_name 列表 (显示码)
        put_code_names:  看跌合约 code_name 列表 (显示码)
    """
    underlying: str
    market_code: int
    market_type: str
    delivery_year: int
    delivery_month: int
    contracts: List[ContractInfo] = field(default_factory=list)
    call_codes: List[str] = field(default_factory=list)
    put_codes: List[str] = field(default_factory=list)
    call_code_names: List[str] = field(default_factory=list)
    put_code_names: List[str] = field(default_factory=list)


# ═══════════════════════════════════════════════════════════════════════
#  默认值 (仅当 ConfigService 不可用时的回退)
# ═══════════════════════════════════════════════════════════════════════

_DEFAULT_ROLLOVER_DAY: int = 15
_DEFAULT_EXPIRY_WARNING_DAYS: int = 5
_DEFAULT_QUARTER_MONTHS: List[int] = [3, 6, 9, 12]


# ═══════════════════════════════════════════════════════════════════════
#  ContractManager V10
# ═══════════════════════════════════════════════════════════════════════

class ContractManager:
    """V10 合约管理器: 基于日期动态推导合约代码, 全配置驱动。

    V10 核心设计原则:
    - **YAML 配置为唯一数据源**: codes.yaml 提供 delivery_months / variety_market / option_underlyings
    - **零硬编码**: 所有品种/交割月/市场映射从 ConfigService 加载
    - **xlsx 代码表补充**: xlsx 提供 code/code_name 双码映射
    - **code/code_name 双码制**: TDX API 用 code, OptionCodeParser 用 code_name
    - **自动滚动**: 合约到期后自动切换到下月
    - **L8/L9 后缀**: 主连=L8, 加权=L9 (非 M0/M1)

    公共接口:
    - get_commodity_contracts()        — 获取商品期货近月/远月合约对
    - get_index_futures_contracts()    — 获取股指期货当月/下季月合约
    - get_option_contracts()           — 获取期权近月合约组
    - get_option_near_month()          — 获取期权近月交割月份
    - get_contract_code()              — 获取品种合约代码
    - lookup_code_by_code_name()       — code_name → code 反查
    - lookup_code_name_by_code()       — code → code_name 反查
    - check_expiry_warnings()          — 检查即将到期合约
    - generate_full_config_updates()   — 生成动态配置更新
    - get_contract_summary()           — 获取合约推导摘要
    - update()                         — 刷新合约映射
    """

    def __init__(
        self,
        config: Any = None,
        code_table_path: Optional[str] = None,
        reference_date: Optional[datetime] = None,
        rollover_day: Optional[int] = None,
        expiry_warning_days: Optional[int] = None,
        option_code_parser: Optional[Any] = None,
    ) -> None:
        """初始化合约管理器。

        V10: config 参数接受 ConfigService 实例, 所有映射从 YAML 加载。

        Args:
            config:              ConfigService 实例 (V10 必需)
            code_table_path:     TDX 代码表 xlsx 路径
            reference_date:      参考日期, 默认今天
            rollover_day:        每月第 N 天后视为需切换下月合约
            expiry_warning_days: 到期提醒天数
            option_code_parser:  OptionCodeParser 实例 (可选)
        """
        self._config = config
        self._logger = logger
        self._parser = option_code_parser

        self.reference_date = reference_date or datetime.now()
        self.code_table_path = code_table_path

        # 从 ConfigService 加载配置 (V10 核心)
        self._load_config()

        # 覆盖参数优先级高于配置
        if rollover_day is not None:
            self.rollover_day = rollover_day
        if expiry_warning_days is not None:
            self.expiry_warning_days = expiry_warning_days

        # TDX 代码表数据
        self._code_table: Dict[str, ContractInfo] = {}
        self._code_name_to_code: Dict[str, str] = {}
        self._code_to_code_name: Dict[str, str] = {}
        self._variety_codes: Dict[str, List[ContractInfo]] = defaultdict(list)
        self._option_by_underlying: Dict[str, List[ContractInfo]] = defaultdict(list)
        self._option_by_market: Dict[int, List[ContractInfo]] = defaultdict(list)

        # 缓存推导结果
        self._commodity_cache: Dict[str, FuturesContractPair] = {}
        self._index_cache: Dict[str, IndexFuturesContract] = {}
        self._option_cache: Dict[str, OptionContractGroup] = {}

        # 加载 xlsx 代码表
        if code_table_path and os.path.exists(code_table_path):
            self._load_code_table(code_table_path)

        self._logger.info(
            "ContractManager V10 初始化完成 | "
            "参考日期: %s | "
            "交割月品种: %d | 品种市场映射: %d | "
            "已加载 %d 个合约 | 期货品种: %d | 期权标的: %d",
            self.reference_date.strftime('%Y-%m-%d'),
            len(self._commodity_delivery_months),
            len(self._variety_market),
            len(self._code_table),
            len(self._variety_codes),
            len(self._option_by_underlying),
        )

    # ──────────────────────────────────────────────────────────────
    #  配置加载 — V10: 全部从 ConfigService (YAML)
    # ──────────────────────────────────────────────────────────────

    def _load_config(self) -> None:
        """从 ConfigService 加载所有品种/交割月/市场映射。

        V10: 所有原 V9 硬编码字典全部从 YAML 读取。
        ConfigService 键映射:
          - codes.commodity_delivery_months  → COMMODITY_DELIVERY_MONTHS
          - codes.variety_market             → VARIETY_MARKET_CODE + VARIETY_MARKET_TYPE + VARIETY_NAMES
          - codes.index_futures              → INDEX_FUTURES_CONFIG
          - codes.option_underlyings         → OPTION_UNDERLYING_CONFIG
          - codes.index_futures.quarter_months → INDEX_FUTURES_QUARTER_MONTHS
          - codes.contract_rollover          → rollover_day / expiry_warning_days
        """
        if self._config is not None:
            # 商品期货交割月份
            raw_delivery = self._config.get("codes.commodity_delivery_months", {})
            self._commodity_delivery_months: Dict[str, List[int]] = {}
            for variety, months in raw_delivery.items():
                self._commodity_delivery_months[variety.upper()] = [int(m) for m in months]

            # 品种 → 市场映射 (从 variety_market 构建)
            raw_variety_market = self._config.get("codes.variety_market", {})
            self._variety_market: Dict[str, Dict[str, Any]] = {}
            self._variety_market_code: Dict[str, int] = {}
            self._variety_market_type: Dict[str, str] = {}
            self._variety_names: Dict[str, str] = {}

            for variety, info in raw_variety_market.items():
                v = variety.upper()
                self._variety_market[v] = info
                self._variety_market_code[v] = int(info.get("market_code", 0))
                self._variety_market_type[v] = info.get("market_type", "")
                self._variety_names[v] = info.get("name", v)

            # 股指期货配置
            raw_index_futures = self._config.get("codes.index_futures", {})
            self._index_futures_config: Dict[str, Dict[str, Any]] = {}
            for variety, info in raw_index_futures.items():
                if variety == "quarter_months":
                    continue
                v = variety.upper()
                self._index_futures_config[v] = info

            # 季月
            self._quarter_months: List[int] = raw_index_futures.get(
                "quarter_months", _DEFAULT_QUARTER_MONTHS
            )

            # 期权标的配置
            self._option_underlying_config: Dict[str, Dict[str, Any]] = {}
            raw_option_underlyings = self._config.get("codes.option_underlyings", {})
            for underlying, info in raw_option_underlyings.items():
                self._option_underlying_config[underlying.upper()] = info

            # 合约滚动配置
            rollover_cfg = self._config.get("codes.contract_rollover", {})
            self.rollover_day: int = rollover_cfg.get("rollover_day", _DEFAULT_ROLLOVER_DAY)
            self.expiry_warning_days: int = rollover_cfg.get("expiry_warning_days", _DEFAULT_EXPIRY_WARNING_DAYS)
        else:
            # 无 ConfigService 时使用空默认值 (生产环境不应走此分支)
            self._logger.warning("ContractManager: 未提供 ConfigService, 使用空默认值")
            self._commodity_delivery_months = {}
            self._variety_market = {}
            self._variety_market_code = {}
            self._variety_market_type = {}
            self._variety_names = {}
            self._index_futures_config = {}
            self._quarter_months = _DEFAULT_QUARTER_MONTHS
            self._option_underlying_config = {}
            self.rollover_day = _DEFAULT_ROLLOVER_DAY
            self.expiry_warning_days = _DEFAULT_EXPIRY_WARNING_DAYS

    def reload_config(self) -> None:
        """热重载配置 (由 ConfigService 变更回调触发)"""
        self._load_config()
        self._commodity_cache.clear()
        self._index_cache.clear()
        self._option_cache.clear()
        self._logger.info("ContractManager V10 配置热重载完成")

    # ──────────────────────────────────────────────────────────────
    #  代码表加载 — xlsx 为补充数据源
    # ──────────────────────────────────────────────────────────────

    def _load_code_table(self, path: str) -> None:
        """从 xlsx 加载 TDX 代码表。

        xlsx 列说明:
          - code:        TDX 内部码 (用于 API 调用)
          - code_name:   合约显示名称 (用于解析)
          - market_code: TDX 市场代码
          - market_name: 市场中文名
          - category:    类别 (3=期货, 8=股票, 10=宏观, 12=期权)
        """
        try:
            df = pd.read_excel(path)
            if df.empty:
                self._logger.warning("代码表为空: %s", path)
                return

            for _, row in df.iterrows():
                code = str(row.get("code", "")).strip()
                code_name = str(row.get("code_name", "")).strip()
                market_code = int(row.get("market_code", 0)) if pd.notna(row.get("market_code")) else 0
                market_name = str(row.get("market_name", "")).strip() if pd.notna(row.get("market_name")) else ""
                category = int(row.get("category", 0)) if pd.notna(row.get("category")) else 0

                if not code:
                    continue

                variety, delivery_year, delivery_month = self._parse_contract_code(
                    code, code_name, category,
                )
                market_type = self._infer_market_type(variety, market_code, category)

                info = ContractInfo(
                    code=code,
                    code_name=code_name,
                    market_code=market_code,
                    market_type=market_type,
                    market_name=market_name,
                    category=category,
                    variety=variety,
                    delivery_year=delivery_year,
                    delivery_month=delivery_month,
                )

                self._code_table[code] = info
                if code_name:
                    self._code_name_to_code[code_name] = code
                self._code_to_code_name[code] = code_name

                if category == 3 and delivery_month > 0:
                    self._variety_codes[variety].append(info)
                elif category == 12:
                    self._option_by_underlying[variety].append(info)
                    self._option_by_market[market_code].append(info)

            self._logger.info(
                "代码表加载完成 | 总合约: %d | 期货品种: %d | 期权标的: %d | code_name→code映射: %d",
                len(self._code_table), len(self._variety_codes),
                len(self._option_by_underlying), len(self._code_name_to_code),
            )

        except Exception as exc:
            self._logger.error("代码表加载失败: %s", exc)

    # ──────────────────────────────────────────────────────────────
    #  code / code_name 双向查询
    # ──────────────────────────────────────────────────────────────

    def lookup_code_by_code_name(self, code_name: str) -> Optional[str]:
        """code_name (显示码) → code (TDX内部码)"""
        return self._code_name_to_code.get(code_name)

    def lookup_code_name_by_code(self, code: str) -> Optional[str]:
        """code (TDX内部码) → code_name (显示码)"""
        return self._code_to_code_name.get(code)

    def get_contract_info(self, code: str) -> Optional[ContractInfo]:
        """通过 code 查找完整合约信息"""
        return self._code_table.get(code)

    # ──────────────────────────────────────────────────────────────
    #  market_type 推断
    # ──────────────────────────────────────────────────────────────

    def _infer_market_type(self, variety: str, market_code: int, category: int) -> str:
        """根据品种代码 / market_code / category 推断 market_type。

        V10: 使用从 YAML 加载的 _variety_market_type 映射。
        """
        if category == 3:  # 期货
            mt = self._variety_market_type.get(variety)
            if mt:
                return mt

        if category == 12:  # 期权
            if variety in ('IO', 'HO', 'MO'):
                return 'option_zj'
            # 按市场代码精确归属
            market_code_to_option_type = {
                8: 'option_sh',
                9: 'option_sz',
                4: 'option_czce',
                5: 'option_dce',
                6: 'option_shfe',
                67: 'option_gz',
            }
            opt_type = market_code_to_option_type.get(market_code)
            if opt_type:
                return opt_type
            # 兜底: 从期货品种映射推导
            mt = self._variety_market_type.get(variety, '')
            if mt.startswith('future_'):
                return mt.replace('future_', 'option_')
            return 'option_sh'

        # 回退: 按 market_code
        market_code_to_type = {
            30: 'future_sh', 29: 'future_dl', 28: 'future_zj',
            66: 'future_gz', 47: 'future_zj',
            7: 'option_zj', 8: 'option_sh', 9: 'option_sz',
            4: 'option_czce', 5: 'option_dce', 6: 'option_shfe', 67: 'option_gz',
            12: 'index_intl', 46: 'gold_sh', 62: 'index_csi', 102: 'index_cni',
        }
        return market_code_to_type.get(market_code, 'future_sh')

    # ──────────────────────────────────────────────────────────────
    #  合约代码解析
    # ──────────────────────────────────────────────────────────────

    def _parse_contract_code(
        self, code: str, code_name: str, category: int,
    ) -> Tuple[str, int, int]:
        """解析合约代码, 提取品种 / 交割年 / 交割月。

        期货: code = 品种+YYMM (如 CU2606, IFL8)
        期权: code 是 TDX 内部编码, 需从 code_name 解析

        Returns:
            (variety, delivery_year, delivery_month)
        """
        code_upper = code.upper().strip()

        if category == 3:  # 期货
            # TDX 连续合约后缀规范:
            # L0=当月连续, L1=下月连续, L2=下季, L3=隔季, L8=主连, L9=加权
            # 注: M0/M1 不存在于 tdxAPICode180.xlsx, 属旧版错误写法
            m_cont = re.match(r'^([A-Z]+)L(\d)$', code_upper)
            if m_cont:
                return m_cont.group(1), 0, 0

            # 普通合约: CU2606, M2603
            match = re.match(r'^([A-Z]+)(\d{3,4})$', code_upper)
            if match:
                variety = match.group(1)
                num = match.group(2)
                if len(num) == 4:  # YYMM
                    return variety, 2000 + int(num[:2]), int(num[2:])
                elif len(num) == 3:  # YMM
                    return variety, 2000 + int(num[0]) + 20, int(num[-2:])

            # 兜底: 从 code_name 提取
            if code_name:
                match = re.search(r'(\d{4})', code_name)
                if match:
                    num = match.group(1)
                    return code_upper.rstrip('0123456789'), 2000 + int(num[:2]), int(num[2:4])

            return code_upper, 0, 0

        elif category == 12:  # 期权
            if code_name:
                # 中金所/商品期权: HO2602-P-2650, CU2606-C-100000
                match = re.match(r'^([A-Z]+)(\d{4})', code_name)
                if match:
                    variety = match.group(1)
                    yy = int(match.group(2)[:2])
                    mm = int(match.group(2)[2:4])
                    return variety, 2000 + yy, mm

                # ETF期权: 510050C3A02700, 159901C6M002700A
                match = re.match(r'^(\d{6})([CP])(\d)([A-X])', code_name)
                if match:
                    underlying = match.group(1)
                    dir_letter = match.group(2)
                    year_digit = int(match.group(3))
                    month_letter = match.group(4)

                    current_year = datetime.now().year
                    decade_start = (current_year // 10) * 10
                    delivery_year = decade_start + year_digit
                    if delivery_year > current_year + 5:
                        delivery_year -= 10
                    if delivery_year < current_year - 5:
                        delivery_year += 10

                    call_month_map = {
                        "A": 1, "B": 2, "C": 3, "D": 4,
                        "E": 5, "F": 6, "G": 7, "H": 8,
                        "I": 9, "J": 10, "K": 11, "L": 12,
                    }
                    put_month_map = {
                        "M": 1, "N": 2, "O": 3, "P": 4,
                        "Q": 5, "R": 6, "S": 7, "T": 8,
                        "U": 9, "V": 10, "W": 11, "X": 12,
                    }

                    if dir_letter == 'C' and month_letter in call_month_map:
                        delivery_month = call_month_map[month_letter]
                    elif dir_letter == 'P' and month_letter in put_month_map:
                        delivery_month = put_month_map[month_letter]
                    elif month_letter in call_month_map:
                        delivery_month = call_month_map[month_letter]
                    elif month_letter in put_month_map:
                        delivery_month = put_month_map[month_letter]
                    else:
                        delivery_month = 0

                    return underlying, delivery_year, delivery_month

                # 兜底: 只提取6位数字标的
                match = re.match(r'^(\d{6})', code_name)
                if match:
                    underlying = match.group(1)
                    return underlying, 0, 0

            return code_upper, 0, 0

        return code_upper, 0, 0

    # ──────────────────────────────────────────────────────────────
    #  核心: 动态合约推导
    # ──────────────────────────────────────────────────────────────

    def _get_next_delivery_month(
        self, variety: str, ref_date: datetime, skip_months: int = 0,
    ) -> Tuple[int, int]:
        """获取品种从 ref_date 起第 skip_months+1 个交割月。"""
        delivery_months = self._commodity_delivery_months.get(
            variety, list(range(1, 13)),
        )

        current_year = ref_date.year
        current_month = ref_date.month
        current_day = ref_date.day

        is_rollover = current_day >= self.rollover_day

        found_count = 0
        search_year = current_year
        search_month = current_month

        if not is_rollover and current_month in delivery_months:
            if skip_months == 0:
                return search_year, current_month
            found_count += 1

        for _ in range(36):
            search_month += 1
            if search_month > 12:
                search_month = 1
                search_year += 1

            if search_month in delivery_months:
                if found_count == skip_months:
                    return search_year, search_month
                found_count += 1

        return current_year, current_month

    def get_commodity_contracts(
        self, variety_key: str = "", variety_code: str = "",
    ) -> Optional[FuturesContractPair]:
        """获取商品期货近月/远月合约对。

        Args:
            variety_key:  品种英文键名, 如 copper
            variety_code: 品种 TDX 代码, 如 CU (二选一)

        Returns:
            FuturesContractPair 或 None
        """
        if not variety_code and variety_key:
            # 从监控品种配置反查
            for v, info in self._variety_market.items():
                if v == variety_key.upper():
                    variety_code = v
                    break

        if not variety_code:
            return None

        cache_key = variety_code
        if cache_key in self._commodity_cache:
            return self._commodity_cache[cache_key]

        # 获取市场信息
        market_info = self._variety_market.get(variety_code, {})
        market_code = self._variety_market_code.get(variety_code, 0)
        market_type = self._variety_market_type.get(variety_code, "future_sh")

        # 推导近月和远月
        near_year, near_month = self._get_next_delivery_month(
            variety_code, self.reference_date, skip_months=0,
        )
        far_year, far_month = self._get_next_delivery_month(
            variety_code, self.reference_date, skip_months=1,
        )

        # 构建合约代码
        near_code = f"{variety_code}{near_year % 100:02d}{near_month:02d}"
        far_code = f"{variety_code}{far_year % 100:02d}{far_month:02d}"

        # 检查 xlsx 中是否有对应的 TDX 内部码
        near_info = self._code_table.get(near_code)
        far_info = self._code_table.get(far_code)
        if near_info:
            near_code = near_info.code
        if far_info:
            far_code = far_info.code

        pair = FuturesContractPair(
            variety_key=variety_key or variety_code.lower(),
            variety_code=variety_code,
            near_code=near_code,
            far_code=far_code,
            market_code=market_code,
            market_type=market_type,
            near_year=near_year,
            near_month=near_month,
            far_year=far_year,
            far_month=far_month,
        )

        self._commodity_cache[cache_key] = pair
        return pair

    def get_index_futures_contracts(
        self, key: str = "",
    ) -> Optional[IndexFuturesContract]:
        """获取股指期货当月/下季月合约。

        Args:
            key: 品种英文键名, 如 'if' (小写) 或 'IF' (大写)

        Returns:
            IndexFuturesContract 或 None
        """
        key_upper = key.upper()
        if key_upper in self._index_cache:
            return self._index_cache[key_upper]

        config = self._index_futures_config.get(key_upper)
        if not config:
            return None

        variety_code = key_upper
        spot_code = config.get("spot_code", "")
        continuous_suffix = config.get("continuous_suffix", "L8")

        # 获取市场信息
        market_code = self._variety_market_code.get(variety_code, 47)
        market_type = self._variety_market_type.get(variety_code, "future_zj")

        # 当月合约 = 品种 + 主连后缀 (L8)
        futures_code = f"{variety_code}{continuous_suffix}"

        # 下季月推导
        ref_date = self.reference_date
        current_month = ref_date.month
        next_quarter_month = None
        for qm in self._quarter_months:
            if qm > current_month:
                next_quarter_month = qm
                break
        if next_quarter_month is None:
            next_quarter_month = self._quarter_months[0]

        delivery_year = ref_date.year
        if next_quarter_month <= current_month:
            delivery_year += 1

        next_quarter_code = f"{variety_code}{delivery_year % 100:02d}{next_quarter_month:02d}"

        # 检查 xlsx 中的 TDX 内部码
        futures_info = self._code_table.get(futures_code)
        if futures_info:
            futures_code = futures_info.code
        nq_info = self._code_table.get(f"{variety_code}{delivery_year % 100:02d}{next_quarter_month:02d}")
        if nq_info:
            next_quarter_code = nq_info.code

        contract = IndexFuturesContract(
            key=key.lower(),
            variety_code=variety_code,
            futures_code=futures_code,
            next_quarter_code=next_quarter_code,
            spot_code=spot_code,
            market_code=market_code,
            market_type=market_type,
            delivery_year=delivery_year,
            delivery_month=next_quarter_month,
        )

        self._index_cache[key_upper] = contract
        return contract

    def get_option_contracts(
        self, underlying: str, month_offset: int = 0,
    ) -> Optional[OptionContractGroup]:
        """获取期权近月合约组。

        Args:
            underlying:    标的代码, 如 IO, 510050
            month_offset:  月偏移 (0=近月, 1=远月)

        Returns:
            OptionContractGroup 或 None
        """
        cache_key = f"{underlying}_{month_offset}"
        if cache_key in self._option_cache:
            return self._option_cache[cache_key]

        config = self._option_underlying_config.get(underlying.upper())
        if not config:
            return None

        market_code = int(config.get("market_code", 0))
        market_type = config.get("market_type", "option_zj")

        # 推导近月交割月
        delivery_year, delivery_month = self._get_option_near_month_year(
            underlying, self.reference_date, month_offset,
        )

        # 从 xlsx 代码表筛选
        contracts = []
        call_codes = []
        put_codes = []
        call_code_names = []
        put_code_names = []

        option_list = self._option_by_underlying.get(underlying.upper(), [])
        for info in option_list:
            if info.delivery_year == delivery_year and info.delivery_month == delivery_month:
                contracts.append(info)
                code_name = info.code_name
                # 判断 Call/Put
                if self._parser is not None:
                    parsed = self._parser.parse(code_name, market_code)
                    if parsed is not None:
                        if parsed.is_call:
                            call_codes.append(info.code)
                            call_code_names.append(info.code_name)
                        elif parsed.is_put:
                            put_codes.append(info.code)
                            put_code_names.append(info.code_name)
                else:
                    # 简单判断: code_name 中含 -C- 为看涨, -P- 为看跌
                    if "-C-" in code_name or (len(code_name) > 7 and code_name[7] == "C"):
                        call_codes.append(info.code)
                        call_code_names.append(info.code_name)
                    elif "-P-" in code_name or (len(code_name) > 7 and code_name[7] == "P"):
                        put_codes.append(info.code)
                        put_code_names.append(info.code_name)

        group = OptionContractGroup(
            underlying=underlying.upper(),
            market_code=market_code,
            market_type=market_type,
            delivery_year=delivery_year,
            delivery_month=delivery_month,
            contracts=contracts,
            call_codes=call_codes,
            put_codes=put_codes,
            call_code_names=call_code_names,
            put_code_names=put_code_names,
        )

        self._option_cache[cache_key] = group
        return group

    def get_option_near_month(self, ref_date: Optional[datetime] = None) -> int:
        """获取期权近月交割月份。

        Args:
            ref_date: 参考日期, 默认使用 reference_date

        Returns:
            交割月份 (1-12)
        """
        d = ref_date or self.reference_date
        if d.day < self.rollover_day:
            return d.month
        else:
            return d.month + 1 if d.month < 12 else 1

    def _get_option_near_month_year(
        self, underlying: str, ref_date: datetime, month_offset: int = 0,
    ) -> Tuple[int, int]:
        """推导期权近月/远月交割年月。"""
        near_month = self.get_option_near_month(ref_date)
        near_year = ref_date.year
        if near_month < ref_date.month:
            near_year += 1

        target_month = near_month + month_offset
        target_year = near_year
        while target_month > 12:
            target_month -= 12
            target_year += 1

        return target_year, target_month

    def get_contract_code(
        self, variety: str, month_offset: int = 0,
    ) -> str:
        """获取品种合约代码 (DerivativesSignalEngine 用)。

        V10: 默认后缀 L8 (主连), 不是 M0。

        Args:
            variety:      品种代码, 如 CU, IF
            month_offset: 月偏移 (0=主连L8, 1=加权L9)

        Returns:
            合约代码字符串
        """
        # 优先从 xlsx 代码表查找
        suffix = "L8" if month_offset == 0 else "L9"
        code = f"{variety.upper()}{suffix}"

        info = self._code_table.get(code)
        if info:
            return info.code

        return code

    # ──────────────────────────────────────────────────────────────
    #  到期预警 & 配置更新
    # ──────────────────────────────────────────────────────────────

    def check_expiry_warnings(self) -> List[Dict[str, Any]]:
        """检查即将到期合约, 返回预警列表。"""
        warnings = []
        today = datetime.now()

        for key, pair in self._commodity_cache.items():
            expiry = datetime(pair.near_year, pair.near_month, self.rollover_day)
            days_left = (expiry - today).days
            if 0 < days_left <= self.expiry_warning_days:
                warnings.append({
                    "type": "commodity",
                    "variety": pair.variety_code,
                    "near_code": pair.near_code,
                    "expiry_date": expiry.strftime("%Y-%m-%d"),
                    "days_left": days_left,
                })

        for key, contract in self._index_cache.items():
            expiry = datetime(contract.delivery_year, contract.delivery_month, self.rollover_day)
            days_left = (expiry - today).days
            if 0 < days_left <= self.expiry_warning_days:
                warnings.append({
                    "type": "index_futures",
                    "variety": contract.variety_code,
                    "futures_code": contract.futures_code,
                    "expiry_date": expiry.strftime("%Y-%m-%d"),
                    "days_left": days_left,
                })

        return warnings

    def generate_full_config_updates(self) -> Dict[str, Any]:
        """生成动态配置更新 (供系统其他模块消费)。"""
        updates = {
            "commodity_contracts": {},
            "index_futures_contracts": {},
            "expiry_warnings": self.check_expiry_warnings(),
            "timestamp": datetime.now().isoformat(),
        }

        for key, pair in self._commodity_cache.items():
            updates["commodity_contracts"][key] = {
                "near_code": pair.near_code,
                "far_code": pair.far_code,
                "near_year": pair.near_year,
                "near_month": pair.near_month,
                "far_year": pair.far_year,
                "far_month": pair.far_month,
            }

        for key, contract in self._index_cache.items():
            updates["index_futures_contracts"][key] = {
                "futures_code": contract.futures_code,
                "next_quarter_code": contract.next_quarter_code,
                "delivery_year": contract.delivery_year,
                "delivery_month": contract.delivery_month,
            }

        return updates

    def get_contract_summary(self) -> Dict[str, Any]:
        """获取合约推导摘要"""
        return {
            "reference_date": self.reference_date.strftime("%Y-%m-%d"),
            "rollover_day": self.rollover_day,
            "commodity_delivery_varieties": len(self._commodity_delivery_months),
            "variety_market_mappings": len(self._variety_market),
            "option_underlyings": len(self._option_underlying_config),
            "index_futures": len(self._index_futures_config),
            "code_table_size": len(self._code_table),
            "cached_commodity_pairs": len(self._commodity_cache),
            "cached_index_contracts": len(self._index_cache),
            "cached_option_groups": len(self._option_cache),
        }

    def update(self, reference_date: Optional[datetime] = None) -> None:
        """刷新合约映射 (日期变更或配置变更后调用)。"""
        if reference_date:
            self.reference_date = reference_date
        self._commodity_cache.clear()
        self._index_cache.clear()
        self._option_cache.clear()
        self._logger.info(
            "ContractManager 合约映射已刷新 | 参考日期: %s",
            self.reference_date.strftime("%Y-%m-%d"),
        )
