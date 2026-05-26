"""
AiStock V8 — 统一期权代码解析器 (Option Code Parser)

解决 TDX 三格式期权代码解析问题:
  1. 上交所ETF期权 (Market=8):  510050C6A02850
  2. 深交所ETF期权 (Market=9):  159901C6M003100A
  3. 中金所/商品期权:            HO2606-C-2400 / CU2606-C-100000

核心能力:
  - parse()          → 单合约解析 → OptionContractInfo
  - parse_batch()    → 批量解析
  - extract_call_put_codes() → 分离 Call/Put 代码用于 PCR 计算
  - 完整的月份字母映射、行权价标准化、调整合约识别
  - 当前月合约 (CCM/PCM) 识别

设计参考: TDX分析报告 — 期权代码3格式问题
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════════════
# 月份字母映射 (TDX 期权编码标准)
# ═══════════════════════════════════════════════════════════════════════════════

# Call 月份: A-L → 1-12月
CALL_MONTH_MAP: Dict[str, int] = {
    "A": 1, "B": 2, "C": 3, "D": 4,
    "E": 5, "F": 6, "G": 7, "H": 8,
    "I": 9, "J": 10, "K": 11, "L": 12,
}

# Put 月份: M-X → 1-12月
PUT_MONTH_MAP: Dict[str, int] = {
    "M": 1, "N": 2, "O": 3, "P": 4,
    "Q": 5, "R": 6, "S": 7, "T": 8,
    "U": 9, "V": 10, "W": 11, "X": 12,
}

# 反向映射: month → call/put letter
_CALL_MONTH_REVERSE: Dict[int, str] = {v: k for k, v in CALL_MONTH_MAP.items()}
_PUT_MONTH_REVERSE: Dict[int, str] = {v: k for k, v in PUT_MONTH_MAP.items()}

# 合并的月份映射 (用于灵活解码: 任何字母 → 月份 + 推断方向)
UNIFIED_MONTH_MAP: Dict[str, Tuple[int, str]] = {
    **{k: (v, "call") for k, v in CALL_MONTH_MAP.items()},
    **{k: (v, "put") for k, v in PUT_MONTH_MAP.items()},
}


# ═══════════════════════════════════════════════════════════════════════════════
# 中金所/商品期权品种表
# ═══════════════════════════════════════════════════════════════════════════════

# 中金所指数期权品种
CFFEX_VARIETIES: Dict[str, Dict[str, Any]] = {
    "IO": {"name": "沪深300股指期权", "spot_code": "000300", "market_code": 7},
    "HO": {"name": "上证50股指期权",  "spot_code": "000016", "market_code": 7},
    "MO": {"name": "中证1000股指期权", "spot_code": "000852", "market_code": 7},
}

# 商品期权品种 (按流动性排序, Top 20)
COMMODITY_VARIETIES: Dict[str, Dict[str, Any]] = {
    "CU": {"name": "沪铜期权", "exchange": "SHFE", "market_code": 6,  "strike_divisor": 1},
    "AG": {"name": "白银期权", "exchange": "SHFE", "market_code": 5,  "strike_divisor": 1},
    "I":  {"name": "铁矿石期权", "exchange": "DCE", "market_code": 4,  "strike_divisor": 1},
    "AU": {"name": "黄金期权", "exchange": "SHFE", "market_code": 6,  "strike_divisor": 1},
    "AL": {"name": "沪铝期权", "exchange": "SHFE", "market_code": 6,  "strike_divisor": 1},
    "ZN": {"name": "沪锌期权", "exchange": "SHFE", "market_code": 6,  "strike_divisor": 1},
    "PB": {"name": "沪铅期权", "exchange": "SHFE", "market_code": 6,  "strike_divisor": 1},
    "NI": {"name": "沪镍期权", "exchange": "SHFE", "market_code": 6,  "strike_divisor": 1},
    "SN": {"name": "沪锡期权", "exchange": "SHFE", "market_code": 6,  "strike_divisor": 1},
    "RB": {"name": "螺纹钢期权", "exchange": "SHFE", "market_code": 6,  "strike_divisor": 1},
    "RU": {"name": "橡胶期权", "exchange": "SHFE", "market_code": 6,  "strike_divisor": 1},
    "M":  {"name": "豆粕期权",  "exchange": "DCE", "market_code": 4,  "strike_divisor": 1},
    "Y":  {"name": "豆油期权",  "exchange": "DCE", "market_code": 4,  "strike_divisor": 1},
    "P":  {"name": "棕榈油期权", "exchange": "DCE", "market_code": 4, "strike_divisor": 1},
    "C":  {"name": "玉米期权",  "exchange": "DCE", "market_code": 4,  "strike_divisor": 1},
    "CF": {"name": "棉花期权",  "exchange": "CZCE", "market_code": 28, "strike_divisor": 1},
    "SR": {"name": "白糖期权",  "exchange": "CZCE", "market_code": 28, "strike_divisor": 1},
    "TA": {"name": "PTA期权",   "exchange": "CZCE", "market_code": 28, "strike_divisor": 1},
    "MA": {"name": "甲醇期权",  "exchange": "CZCE", "market_code": 28, "strike_divisor": 1},
    "AP": {"name": "苹果期权",  "exchange": "CZCE", "market_code": 28, "strike_divisor": 1},
}

# ETF 期权标的 → 行权价除数映射
_ETF_STRIKE_DIVISOR: Dict[str, int] = {
    # 上交所 ETF 期权
    "510050": 1000,  # 上证50ETF
    "510300": 1000,  # 沪深300ETF(沪)
    "510500": 1000,  # 中证500ETF(沪)
    "588000": 1000,  # 科创50ETF
    "588050": 1000,  # 科创50ETF易方达
    "588080": 1000,  # 科创板50ETF
    # 深交所 ETF 期权
    "159901": 1000,  # 深证100ETF
    "159915": 1000,  # 创业板ETF
    "159919": 1000,  # 沪深300ETF(深)
    "159922": 1000,  # 中证500ETF(深)
}

# 上交所ETF期权市场编号
_SH_ETF_MARKET_CODE = 8
# 深交所ETF期权市场编号
_SZ_ETF_MARKET_CODE = 9
# 中金所期权市场编号
_CFFEX_MARKET_CODE = 7


# ═══════════════════════════════════════════════════════════════════════════════
# 正则表达式 — 三种期权代码格式
# ═══════════════════════════════════════════════════════════════════════════════

# 格式1: 上交所ETF期权  → 510050C6A02850
#   underlying(6) + C/P(1) + year_digit(1) + month_letter(1) + strike_digits(4-7)
_RE_SH_ETF = re.compile(
    r"^(\d{6})"          # underlying: 6位数字
    r"([CP])"            # direction: C/P
    r"(\d)"              # year: 1位数字
    r"([A-X])"           # month: A-L(Call) / M-X(Put)
    r"(\d{4,7})$"        # strike: 4-7位数字
)

# 格式2: 深交所ETF期权  → 159901C6M003100A
#   underlying(6) + C/P(1) + year_digit(1) + month_letter(1) + strike_digits(4-7) + [A]
_RE_SZ_ETF = re.compile(
    r"^(\d{6})"          # underlying: 6位数字
    r"([CP])"            # direction: C/P
    r"(\d)"              # year: 1位数字
    r"([A-X])"           # month: A-L(Call) / M-X(Put)
    r"(\d{4,7})"         # strike: 4-7位数字
    r"(A?)$"             # adjusted: 可选 "A" 后缀
)

# 格式3: 中金所/商品期权  → HO2606-C-2400 / CU2606-C-100000
#   variety(1-3) + year_month(4) + -C/P- + strike_digits
_RE_CFFEX_COMMODITY = re.compile(
    r"^([A-Z]{1,3})"     # variety: 1-3个字母
    r"(\d{4})"           # year_month: YYMM
    r"-([CP])-"          # direction: -C- / -P-
    r"(\d+)$"            # strike: 数字串
)


# ═══════════════════════════════════════════════════════════════════════════════
# 解析结果数据类
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class OptionContractInfo:
    """期权合约解析结果

    Attributes:
        code_name:          原始合约代码
        market_code:        TDX 市场编号
        underlying:         标的代码 (ETF: 6位数字, CFFEX/商品: 品种代码)
        variety:            品种代码 (仅 CFFEX/商品期权有效, ETF期权为空)
        direction:          方向 'call' / 'put'
        delivery_year:      到期年 (4位, 如 2026)
        delivery_month:     到期月 (1-12)
        strike_price:       行权价 (已标准化, 如 2.850)
        is_adjusted:        是否为除权除息调整合约 (深交所 "A" 后缀)
        is_current_month:   是否为当月合约
        raw_strike_digits:  行权价原始数字串 (用于调试)
        parse_source:       解析来源: 'sh_etf' / 'sz_etf' / 'cffex' / 'commodity'
    """

    code_name: str
    market_code: int
    underlying: str
    variety: str
    direction: str           # 'call' | 'put'
    delivery_year: int
    delivery_month: int
    strike_price: float
    is_adjusted: bool = False
    is_current_month: bool = False
    raw_strike_digits: str = ""
    parse_source: str = ""   # 'sh_etf' | 'sz_etf' | 'cffex' | 'commodity'

    @property
    def direction_code(self) -> str:
        """方向单字母: C/P"""
        return "C" if self.direction == "call" else "P"

    @property
    def delivery_year_month(self) -> str:
        """到期年月字符串: '202601'"""
        return f"{self.delivery_year}{self.delivery_month:02d}"

    @property
    def is_call(self) -> bool:
        return self.direction == "call"

    @property
    def is_put(self) -> bool:
        return self.direction == "put"

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典 (用于序列化/日志)"""
        return {
            "code_name": self.code_name,
            "market_code": self.market_code,
            "underlying": self.underlying,
            "variety": self.variety,
            "direction": self.direction,
            "delivery_year": self.delivery_year,
            "delivery_month": self.delivery_month,
            "strike_price": self.strike_price,
            "is_adjusted": self.is_adjusted,
            "is_current_month": self.is_current_month,
            "parse_source": self.parse_source,
        }

    def __repr__(self) -> str:
        adj = " [调整]" if self.is_adjusted else ""
        ccm = " [当月]" if self.is_current_month else ""
        return (
            f"OptionContractInfo({self.code_name} → "
            f"{self.underlying} {self.direction.upper()} "
            f"{self.delivery_year}/{self.delivery_month:02d} "
            f"K={self.strike_price}{adj}{ccm})"
        )


# ═══════════════════════════════════════════════════════════════════════════════
# 统一期权代码解析器
# ═══════════════════════════════════════════════════════════════════════════════

class OptionCodeParser:
    """统一期权代码解析器

    解决 TDX 三格式期权代码的统一解析问题:
      1. 上交所 ETF 期权 (Market=8): 510050C6A02850
      2. 深交所 ETF 期权 (Market=9): 159901C6M003100A
      3. 中金所/商品期权:             HO2606-C-2400

    使用方式:
        >>> parser = OptionCodeParser()
        >>> info = parser.parse("510050C6A02850", market_code=8)
        >>> info.underlying, info.direction, info.strike_price
        ('510050', 'call', 2.85)

        >>> info = parser.parse("HO2606-C-2400", market_code=7)
        >>> info.variety, info.direction, info.strike_price
        ('HO', 'call', 2400.0)

        >>> # 批量解析
        >>> results = parser.parse_batch([
        ...     {"code_name": "510050C6A02850", "market_code": 8},
        ...     {"code_name": "159915P6M003000", "market_code": 9},
        ... ])

        >>> # 分离 Call/Put 代码
        >>> calls, puts = parser.extract_call_put_codes(parsed_list, "510050", 1)
    """

    def __init__(self, reference_year: Optional[int] = None) -> None:
        """初始化解析器

        Args:
            reference_year: 参考年份 (用于 ETF 期权 1 位年号解码),
                            默认使用当前年份
        """
        self._reference_year = reference_year or datetime.now().year
        self._current_month = datetime.now().month
        self._current_year = datetime.now().year

        # 解析统计
        self._parse_count: int = 0
        self._fail_count: int = 0

        logger.info(
            "OptionCodeParser 初始化 — 参考年份: %d, 当前月: %d",
            self._reference_year, self._current_month,
        )

    # ─── 核心解析方法 ──────────────────────────────────────────────────

    def parse(
        self,
        code_name: str,
        market_code: int,
    ) -> Optional[OptionContractInfo]:
        """解析单个期权合约代码

        根据 market_code 自动选择解析策略:
          - 8  → 上交所 ETF 期权格式
          - 9  → 深交所 ETF 期权格式
          - 7  → 中金所指数期权格式
          - 其他 → 商品期权格式 (尝试 CFFEX 格式匹配)

        Args:
            code_name:  期权合约代码
            market_code: TDX 市场编号

        Returns:
            OptionContractInfo 或 None (解析失败时)
        """
        if not code_name or not isinstance(code_name, str):
            logger.warning("OptionCodeParser.parse: 无效输入 code_name=%r", code_name)
            self._fail_count += 1
            return None

        code_name = code_name.strip().upper()
        result: Optional[OptionContractInfo] = None

        # 按 market_code 分派解析
        if market_code == _SH_ETF_MARKET_CODE:
            result = self._parse_sh_etf(code_name, market_code)
        elif market_code == _SZ_ETF_MARKET_CODE:
            result = self._parse_sz_etf(code_name, market_code)
        elif market_code == _CFFEX_MARKET_CODE:
            result = self._parse_cffex_commodity(code_name, market_code)
        else:
            # 商品期权: 尝试 CFFEX/商品格式
            result = self._parse_cffex_commodity(code_name, market_code)
            if result is None:
                # 尝试 ETF 格式 (兜底)
                result = self._parse_sh_etf(code_name, market_code)
                if result is None:
                    result = self._parse_sz_etf(code_name, market_code)

        if result is not None:
            # 标记是否为当月合约
            result.is_current_month = (
                result.delivery_year == self._current_year
                and result.delivery_month == self._current_month
            )
            self._parse_count += 1
        else:
            logger.warning("OptionCodeParser: 无法解析 code=%r market=%d", code_name, market_code)
            self._fail_count += 1

        return result

    def parse_batch(
        self,
        contracts: List[Dict[str, Any]],
    ) -> List[OptionContractInfo]:
        """批量解析期权合约代码

        Args:
            contracts: 合约字典列表, 每个字典需包含:
                       - 'code_name': 合约代码
                       - 'market_code': 市场编号
                       可选: 其他字段会被保留在 parsed_contracts 的 extra 中

        Returns:
            成功解析的 OptionContractInfo 列表 (跳过失败的)
        """
        results: List[OptionContractInfo] = []

        for contract in contracts:
            code_name = contract.get("code_name", "")
            market_code = contract.get("market_code", 0)

            info = self.parse(code_name, market_code)
            if info is not None:
                results.append(info)

        logger.info(
            "OptionCodeParser.parse_batch: 输入 %d, 成功 %d, 失败 %d",
            len(contracts), len(results), len(contracts) - len(results),
        )
        return results

    # ─── Call/Put 代码分离 (PCR 专用) ──────────────────────────────────

    def extract_call_put_codes(
        self,
        contracts: List[OptionContractInfo],
        underlying: str,
        delivery_month: Optional[int] = None,
    ) -> Tuple[List[str], List[str]]:
        """分离 Call/Put 合约代码, 用于 PCR 计算

        Args:
            contracts:      已解析的合约列表
            underlying:     标的代码筛选 (如 '510050')
            delivery_month: 到期月筛选 (None = 全部月份)

        Returns:
            (call_codes, put_codes) — 看涨/看跌合约代码列表
        """
        call_codes: List[str] = []
        put_codes: List[str] = []

        for info in contracts:
            # 标的筛选
            if info.underlying != underlying:
                continue
            # 月份筛选
            if delivery_month is not None and info.delivery_month != delivery_month:
                continue

            if info.is_call:
                call_codes.append(info.code_name)
            elif info.is_put:
                put_codes.append(info.code_name)

        logger.debug(
            "extract_call_put_codes(%s, month=%s): calls=%d, puts=%d",
            underlying, delivery_month, len(call_codes), len(put_codes),
        )
        return call_codes, put_codes

    # ─── 上交所 ETF 期权解析 ────────────────────────────────────────────

    def _parse_sh_etf(
        self,
        code_name: str,
        market_code: int,
    ) -> Optional[OptionContractInfo]:
        """解析上交所 ETF 期权代码

        格式: {underlying_6d}{C/P}{year_1d}{month_letter}{strike_digits}
        示例: 510050C6A02850
          → underlying=510050, call, 2026, 1月(A), strike=2.850
        """
        match = _RE_SH_ETF.match(code_name)
        if not match:
            return None

        underlying = match.group(1)
        dir_letter = match.group(2)
        year_digit = match.group(3)
        month_letter = match.group(4)
        strike_digits = match.group(5)

        # 方向
        direction = "call" if dir_letter == "C" else "put"

        # 年份: 1 位数字 → 4 位年份
        delivery_year = self._decode_etf_year(year_digit)

        # 月份
        delivery_month, inferred_dir = self._decode_month_letter(
            month_letter, direction,
        )

        # 行权价
        strike_price = self._decode_etf_strike(underlying, strike_digits)

        return OptionContractInfo(
            code_name=code_name,
            market_code=market_code,
            underlying=underlying,
            variety="",
            direction=direction,
            delivery_year=delivery_year,
            delivery_month=delivery_month,
            strike_price=strike_price,
            is_adjusted=False,
            raw_strike_digits=strike_digits,
            parse_source="sh_etf",
        )

    # ─── 深交所 ETF 期权解析 ────────────────────────────────────────────

    def _parse_sz_etf(
        self,
        code_name: str,
        market_code: int,
    ) -> Optional[OptionContractInfo]:
        """解析深交所 ETF 期权代码

        格式: {underlying_6d}{C/P}{year_1d}{month_letter}{strike_digits}[A]
        示例: 159901C6M003100A
          → underlying=159901, call, 2026, 1月(M), strike=3.100, adjusted=True
        """
        match = _RE_SZ_ETF.match(code_name)
        if not match:
            return None

        underlying = match.group(1)
        dir_letter = match.group(2)
        year_digit = match.group(3)
        month_letter = match.group(4)
        strike_digits = match.group(5)
        adjusted_suffix = match.group(6)

        # 方向
        direction = "call" if dir_letter == "C" else "put"

        # 年份
        delivery_year = self._decode_etf_year(year_digit)

        # 月份
        delivery_month, _ = self._decode_month_letter(month_letter, direction)

        # 行权价
        strike_price = self._decode_etf_strike(underlying, strike_digits)

        # 是否调整合约
        is_adjusted = adjusted_suffix == "A"

        return OptionContractInfo(
            code_name=code_name,
            market_code=market_code,
            underlying=underlying,
            variety="",
            direction=direction,
            delivery_year=delivery_year,
            delivery_month=delivery_month,
            strike_price=strike_price,
            is_adjusted=is_adjusted,
            raw_strike_digits=strike_digits,
            parse_source="sz_etf",
        )

    # ─── 中金所/商品期权解析 ────────────────────────────────────────────

    def _parse_cffex_commodity(
        self,
        code_name: str,
        market_code: int,
    ) -> Optional[OptionContractInfo]:
        """解析中金所/商品期权代码

        格式: {variety}{YYMM}-{C/P}-{strike}
        示例: HO2606-C-2400 → variety=HO, 2026年6月, call, strike=2400
              CU2606-C-100000 → variety=CU, 2026年6月, call, strike=100000
        """
        match = _RE_CFFEX_COMMODITY.match(code_name)
        if not match:
            return None

        variety = match.group(1)
        year_month_str = match.group(2)
        dir_letter = match.group(3)
        strike_str = match.group(4)

        # 方向
        direction = "call" if dir_letter == "C" else "put"

        # 年月: YYMM
        yy = int(year_month_str[:2])
        mm = int(year_month_str[2:])
        delivery_year = 2000 + yy
        delivery_month = mm

        # 行权价: 直接作为浮点数
        try:
            strike_price = float(strike_str)
        except ValueError:
            logger.warning("行权价解析失败: %s", strike_str)
            strike_price = 0.0

        # 判断来源: CFFEX 还是商品
        if variety in CFFEX_VARIETIES:
            underlying = variety  # CFFEX 品种本身就是标的标识
            parse_source = "cffex"
        elif variety in COMMODITY_VARIETIES:
            underlying = variety
            parse_source = "commodity"
        else:
            # 未知品种, 仍然解析但标记为 unknown
            underlying = variety
            parse_source = "commodity"
            logger.debug("未知的商品期权品种: %s (code=%s)", variety, code_name)

        return OptionContractInfo(
            code_name=code_name,
            market_code=market_code,
            underlying=underlying,
            variety=variety,
            direction=direction,
            delivery_year=delivery_year,
            delivery_month=delivery_month,
            strike_price=strike_price,
            is_adjusted=False,
            raw_strike_digits=strike_str,
            parse_source=parse_source,
        )

    # ─── 内部解码方法 ───────────────────────────────────────────────────

    @staticmethod
    def _decode_etf_year(year_digit: str) -> int:
        """解码 ETF 期权 1 位年号 → 4 位年份

        规则: 基于当前年份的十年周期
          - 若 year_digit <= 当前年份末位 → 当前十年的对应年
          - 若 year_digit >  当前年份末位 → 上一个十年的对应年

        Args:
            year_digit: 1 位数字字符串 ('0'-'9')

        Returns:
            4 位年份 (如 2026)
        """
        digit = int(year_digit)
        current_year = datetime.now().year
        decade_start = (current_year // 10) * 10

        candidate = decade_start + digit
        # 如果候选年份明显在未来太远, 回退到上一个十年
        if candidate > current_year + 5:
            candidate -= 10
        # 如果候选年份在太久以前, 推进到下一个十年
        if candidate < current_year - 5:
            candidate += 10

        return candidate

    @staticmethod
    def _decode_month_letter(
        month_letter: str,
        declared_direction: str,
    ) -> Tuple[int, str]:
        """解码月份字母 → 月份数字

        月份编码:
          Call: A(1月) ~ L(12月)
          Put:  M(1月) ~ X(12月)

        如果月份字母与声明方向不一致 (如 Call 使用了 M-X 字母),
        仍然正常解码月份, 但记录方向推断。

        Args:
            month_letter:      月份字母 (A-X)
            declared_direction: 代码中声明的方向 ('call'/'put')

        Returns:
            (month, inferred_direction)
        """
        if month_letter in CALL_MONTH_MAP:
            month = CALL_MONTH_MAP[month_letter]
            inferred = "call"
        elif month_letter in PUT_MONTH_MAP:
            month = PUT_MONTH_MAP[month_letter]
            inferred = "put"
        else:
            logger.warning("无效月份字母: %s", month_letter)
            return 1, declared_direction

        # 一致性检查: 方向与月份字母是否匹配
        if inferred != declared_direction:
            logger.debug(
                "月份字母与方向不完全一致: letter=%s inferred=%s declared=%s, "
                "使用声明方向",
                month_letter, inferred, declared_direction,
            )

        return month, inferred

    @staticmethod
    def _decode_etf_strike(underlying: str, strike_digits: str) -> float:
        """解码 ETF 期权行权价

        规则: 将数字串除以 1000 得到行权价
          - 02850 → 2.850
          - 003100 → 3.100
          - 04700 → 4.700

        Args:
            underlying:    标的代码 (用于确定除数)
            strike_digits: 行权价原始数字串

        Returns:
            行权价 (float)
        """
        try:
            raw_value = int(strike_digits)
        except ValueError:
            logger.warning("行权价数字串无效: %s", strike_digits)
            return 0.0

        divisor = _ETF_STRIKE_DIVISOR.get(underlying, 1000)
        strike = raw_value / divisor

        # 四舍五入到合理精度
        return round(strike, 3)

    # ─── 辅助方法 ───────────────────────────────────────────────────────

    @staticmethod
    def get_month_letter(month: int, direction: str) -> str:
        """获取月份对应的字母编码

        Args:
            month:     月份 (1-12)
            direction: 方向 ('call' / 'put')

        Returns:
            月份字母 (A-L for call, M-X for put)
        """
        if direction == "call":
            return _CALL_MONTH_REVERSE.get(month, "A")
        return _PUT_MONTH_REVERSE.get(month, "M")

    @staticmethod
    def build_etf_code(
        underlying: str,
        direction: str,
        year: int,
        month: int,
        strike_price: float,
        is_adjusted: bool = False,
    ) -> str:
        """构建 ETF 期权合约代码 (反向操作)

        Args:
            underlying:   标的代码 (6 位)
            direction:    方向 ('call'/'put')
            year:         到期年 (4 位)
            month:        到期月 (1-12)
            strike_price: 行权价
            is_adjusted:  是否调整合约 (深交所)

        Returns:
            合约代码字符串
        """
        dir_letter = "C" if direction == "call" else "P"
        year_digit = str(year % 10)
        month_letter = OptionCodeParser.get_month_letter(month, direction)

        divisor = _ETF_STRIKE_DIVISOR.get(underlying, 1000)
        strike_int = int(round(strike_price * divisor))
        strike_str = str(strike_int)

        code = f"{underlying}{dir_letter}{year_digit}{month_letter}{strike_str}"
        if is_adjusted:
            code += "A"

        return code

    @staticmethod
    def build_cffex_code(
        variety: str,
        year: int,
        month: int,
        direction: str,
        strike_price: float,
    ) -> str:
        """构建中金所/商品期权合约代码

        Args:
            variety:      品种代码 (如 'IO', 'CU')
            year:         到期年 (4 位)
            month:        到期月 (1-12)
            direction:    方向 ('call'/'put')
            strike_price: 行权价

        Returns:
            合约代码 (如 'IO2606-C-4000')
        """
        dir_letter = "C" if direction == "call" else "P"
        yy = year % 100
        strike_int = int(strike_price) if strike_price == int(strike_price) else strike_price
        return f"{variety}{yy:02d}{month:02d}-{dir_letter}-{strike_int}"

    @property
    def stats(self) -> Dict[str, int]:
        """解析统计"""
        return {
            "total_parsed": self._parse_count,
            "total_failed": self._fail_count,
            "success_rate": (
                self._parse_count / (self._parse_count + self._fail_count)
                if (self._parse_count + self._fail_count) > 0
                else 0.0
            ),
        }

    def __repr__(self) -> str:
        return (
            f"OptionCodeParser("
            f"parsed={self._parse_count}, "
            f"failed={self._fail_count})"
        )
