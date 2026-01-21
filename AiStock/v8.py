# %% [markdown]
# ##### 财务评分系统 V8
# 
# * ✅ 157个细分行业
# * ✅ 三级行业分类（超级行业(13) → 二级子类(29) → 细分行业(157)）
# * ✅ 行业分位数标准化 + 成长性 Winsorize 预处理
# * ✅ 3年数据窗口 + TTM + 趋势评分
# * ✅ 累计报表转单季
# * ✅ 行业特有比率（净息差、现金短债比、政府补贴等）
# 
# ##### 核心升级点
# * 数据层
#     * 69个核心字段（+20个风险/行业特有指标）
# * 指标层
#     * 157行业精细化配置，含负向指标（如不良率）
# * 计算层
#     * 新增8个行业特有比率（净息差、预收/营收等）
# * 风险层
#     * 信用减值损失率、资本支出比率等预警信号
# * 政策层
#     * EBITDA、研发费用等“新质生产力”指标强化

# %%
from sqlalchemy import create_engine
import pandas as pd
from tqdm import tqdm
import numpy as np
from typing import Dict, List, Tuple

from scipy.stats import zscore
from scipy.stats.mstats import winsorize

import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots


import warnings
warnings.filterwarnings("ignore")

# %%
engB = create_engine('postgresql+psycopg://sa:11111111@10.3.18.56/StockBas')
engF = create_engine('postgresql+psycopg://sa:11111111@10.3.18.56/tdxFS')

# %% [markdown]
# ##### 申万分类 IC1:31 IC2:134 IC3:346

# %%
# StockICRAW = pd.read_sql('akStockIC', engB)
# StockIC = StockICRAW[StockICRAW['ICSCode']=='008003']
StockIC = pd.read_sql('swStockIC', engB)

# %% [markdown]
# ##### 一、行业分类

# %% [markdown]
# * 1.1 行业细分主函数

# %%
def hierarchical_summary_with_fallback(df, upper_thresh=50, lower_thresh=10):
    results = []
    
    # 确保 IC2、IC3 无 NaN（避免分组异常）
    df = df.fillna({'IC2': '', 'IC3': ''})
    
    # --- Level 1: IC1 ---
    ic1_groups = df.groupby('IC1', sort=False)
    for ic1, group1 in ic1_groups:
        cnt1 = len(group1)
        # 默认只加 IC1
        ic1_row = {'IC1': ic1, 'IC2': '', 'IC3': '', 'count': cnt1}
        add_ic1 = True
        ic2_to_process = []

        # 尝试展开 IC2？
        if cnt1 > upper_thresh:
            ic2_subgroups = group1.groupby('IC2', sort=False)
            ic2_counts = {ic2: len(g) for ic2, g in ic2_subgroups}
            
            # 检查是否所有 IC2 子类 count >= lower_thresh
            if min(ic2_counts.values()) >= lower_thresh:
                # 所有子类都合格 → 展开 IC2
                add_ic1 = False  # 暂不添加 IC1（由子类代表）
                for ic2, cnt2 in ic2_counts.items():
                    ic2_row = {'IC1': ic1, 'IC2': ic2, 'IC3': '', 'count': cnt2}
                    results.append(ic2_row)
                    # 记录可能需要展开 IC3 的项
                    if cnt2 > upper_thresh:
                        ic2_to_process.append((ic1, ic2, group1[group1['IC2'] == ic2]))
                # 处理 IC3 展开
                for ic1_val, ic2_val, g2 in ic2_to_process:
                    ic3_subgroups = g2.groupby('IC3', sort=False)
                    ic3_counts = {ic3: len(g) for ic3, g in ic3_subgroups}
                    if min(ic3_counts.values()) >= lower_thresh:
                        # 展开 IC3，移除对应的 IC2 行（用更细粒度代替）
                        results = [r for r in results if not (r['IC1'] == ic1_val and r['IC2'] == ic2_val and r['IC3'] == '')]
                        for ic3, cnt3 in ic3_counts.items():
                            results.append({'IC1': ic1_val, 'IC2': ic2_val, 'IC3': ic3, 'count': cnt3})
                    # else: 保留 IC2 行（已添加，不处理）
        
        if add_ic1:
            results.append(ic1_row)
    
    # 构造 path 列
    def make_path(row):
        parts = [row['IC1']]
        if row['IC2']:
            parts.append(row['IC2'])
        if row['IC3']:
            parts.append(row['IC3'])
        return ' > '.join(parts)
    
    result_df = pd.DataFrame(results, columns=['IC1', 'IC2', 'IC3', 'count'])
    result_df['path'] = result_df.apply(make_path, axis=1)
    
    # 排序：按 path 层级顺序
    result_df = result_df.sort_values(
        ['IC1', 'IC2', 'IC3'],
        key=lambda col: col.where(col != '', '\0')
    ).reset_index(drop=True)
    
    # 调整列顺序
    result_df = result_df[['path', 'IC1', 'IC2', 'IC3', 'count']]
    return result_df

# %% [markdown]
# * 申万157细分行业（upper_thresh:50 lower_thresh:6）细分行业个股数大于等于6

# %%
ddf = hierarchical_summary_with_fallback(StockIC, upper_thresh=23, lower_thresh=4)

# %%
hierarchical_summary_with_fallback(StockIC, upper_thresh=23, lower_thresh=4).sort_values('IC2', ascending=True)

# %%
swIC = [[['IC1'],ddf[(ddf['IC2'] == '')]['IC1'].to_list()]] + [[['IC2'],ddf[(ddf['IC2'] != '') & (ddf['IC3'] == '')]['IC2'].to_list()]] + [[['IC3'],ddf[(ddf['IC3'] != '')]['IC3'].to_list()]]
# 定义行业列表
INDUSTRIES = swIC[0][1]+swIC[1][1]+swIC[2][1]

# %%
INDUSTRIES

# %% [markdown]
# * 1.2 分层157个细分行业 13大类29子类 AI推荐

# %%
industry_hierarchy = {
    "金融业": {
        "银行业": ["银行"],
        "保险业": ["保险Ⅱ"],
        "资本市场服务业": ["证券Ⅱ", "多元金融"]
    },
    "房地产业": {
        "房地产开发": ["住宅开发", "商业地产", "产业地产"],
        "工程建设与服务": ["房屋建设Ⅱ", "装修装饰Ⅱ", "房地产服务"]
    },
    "基础设施与交通运输": {
        "交通运营": ["航空机场", "航运港口", "铁路公路", "物流"],
        "工程建设与咨询": ["专业工程", "基础建设", "工程咨询服务Ⅱ"]
    },
    "能源与资源": {
        "化石能源与公用事业": ["煤炭", "石油石化", "燃气Ⅱ", "电力"],
        "金属与矿业": ["钢铁", "小金属", "能源金属", "贵金属", "金属新材料", "铅锌", "铜", "铝"]
    },
    "基础材料与化工": {
        "化工与农化": [
            "农化制品", "化学制品", "化学原料", "化学纤维", "橡胶",
            "合成树脂", "改性塑料", "膜材料", "其他塑料制品"
        ],
        "建材与非金属材料": [
            "非金属材料Ⅱ", "水泥", "玻璃玻纤", "装修建材", "瓷砖地板"
        ],
        "金属制品加工": ["金属制品", "磨具磨料"]
    },
    "工业制造": {
        "通用与专用设备": [
            "工程机械", "环保设备Ⅱ", "其他专用设备", "农用机械", "印刷包装机械",
            "楼宇设备", "纺织服装设备", "能源及重型设备", "其他自动化设备",
            "工控设备", "机器人", "激光设备", "仪器仪表", "其他通用设备",
            "制冷空调设备", "机床工具", "电机Ⅱ", "风电设备", "其他电源设备Ⅱ"
        ],
        "交通运输设备": [
            "轨交设备Ⅱ", "乘用车", "商用车", "摩托车及其他", "汽车服务",
            "其他汽车零部件", "底盘与发动机系统", "汽车电子电气系统",
            "车身附件及饰件", "轮胎轮毂"
        ]
    },
    "环保服务": {
        "环保工程与运营": [
            "固废治理", "大气治理", "水务及水治理", "综合环境治理"
        ]
    },
    "TMT科技": {
        "半导体与电子元器件": [
            "半导体材料", "半导体设备", "数字芯片设计", "模拟芯片设计",
            "集成电路制造", "集成电路封测", "印制电路板", "被动元件",
            "LED", "光学元件", "面板", "分立器件", "电子化学品Ⅱ", "其他电子Ⅱ"
        ],
        "消费电子与新能源硬件": [
            "品牌消费电子", "消费电子零部件及组装", "电池",
            "光伏加工设备", "光伏电池组件", "光伏辅材", "硅料硅片", "逆变器"
        ],
        "软件与IT服务": [
            "IT服务Ⅲ", "其他计算机设备", "安防设备",
            "垂直应用软件", "横向通用软件"
        ],
        "通信设备与电网自动化": [
            "通信服务", "其他通信设备", "通信线缆及配套",
            "通信终端及配件", "通信网络设备及器件",
            "电工仪器仪表", "电网自动化设备", "线缆部件及其他",
            "输变电设备", "配电设备"
        ]
    },
    "大消费": {
        "必需消费品": [
            "休闲食品", "白酒Ⅱ", "调味发酵品Ⅱ", "非白酒",
            "食品加工", "饮料乳品", "造纸", "包装印刷", "农林牧渔"
        ],
        "可选消费品": [
            "家用电器", "服装家纺", "纺织制造", "饰品",
            "文娱用品", "其他家居用品", "卫浴制品",
            "定制家居", "成品家居"
        ],
        "传媒与社会服务": [
            "社会服务", "出版", "广告营销", "影视院线",
            "数字媒体", "游戏Ⅱ", "电视广播Ⅱ"
        ]
    },
    "医药健康": {
        "制药与生物技术": ["中药Ⅲ", "化学制剂", "原料药", "生物制品"],
        "医疗器械与服务": [
            "医疗服务", "医药商业", "体外诊断", "医疗耗材", "医疗设备"
        ]
    },
    "国防军工": {
        "国防装备整机与系统": ["地面兵装Ⅱ", "航天装备Ⅱ", "航海装备Ⅱ", "航空装备Ⅱ"],
        "军工电子与配套": ["军工电子Ⅲ"]
    },
    "生活服务与零售": {
        "零售与商贸": ["商贸零售"],
        "个人护理与美容": ["美容护理"]
    },
    "其他": {
        "综合类企业": ["综合"]
    }
}

# %% [markdown]
# * 1.3 构建映射
#   * 构建反向映射：细分行业 → (一级, 二级)

# %%
industry_to_levels = {}
for super_ind, sub_dict in industry_hierarchy.items():
    for sub_ind, inds in sub_dict.items():
        for ind in inds:
            industry_to_levels[ind] = (super_ind, sub_ind)
print(f"✅ 已加载 {len(industry_to_levels)} 个细分行业")

# %%
INDUSTRIES

# %%
set(INDUSTRIES)-set(industry_to_levels.keys())  

# %%
set(list(industry_to_levels.keys())) - set(INDUSTRIES)

# %% [markdown]
# ##### 二、 权重体系

# %% [markdown]
# * 2.1 维度基础权重

# %%
DIMENSION_NAMES = [
    "Profitability", "CashFlow", "Solvency", 
    "Efficiency", "Growth", "EquityStructure", "Size"
]

SUPER_INDUSTRY_WEIGHTS = {
    "金融业": {"Profitability":0.25,"CashFlow":0.10,"Solvency":0.40,"Efficiency":0.05,"Growth":0.10,"EquityStructure":0.05,"Size":0.05},
    "房地产业": {"Profitability":0.10,"CashFlow":0.25,"Solvency":0.40,"Efficiency":0.05,"Growth":0.05,"EquityStructure":0.05,"Size":0.10},
    "基础设施与交通运输": {"Profitability":0.20,"CashFlow":0.25,"Solvency":0.25,"Efficiency":0.10,"Growth":0.05,"EquityStructure":0.05,"Size":0.10},
    "能源与资源": {"Profitability":0.30,"CashFlow":0.20,"Solvency":0.20,"Efficiency":0.05,"Growth":0.10,"EquityStructure":0.05,"Size":0.10},
    "基础材料与化工": {"Profitability":0.25,"CashFlow":0.20,"Solvency":0.20,"Efficiency":0.15,"Growth":0.10,"EquityStructure":0.05,"Size":0.05},
    "工业制造": {"Profitability":0.25,"CashFlow":0.20,"Solvency":0.15,"Efficiency":0.15,"Growth":0.15,"EquityStructure":0.05,"Size":0.05},
    "环保服务": {"Profitability":0.20,"CashFlow":0.30,"Solvency":0.25,"Efficiency":0.10,"Growth":0.10,"EquityStructure":0.05,"Size":0.00},
    "TMT科技": {"Profitability":0.20,"CashFlow":0.15,"Solvency":0.10,"Efficiency":0.15,"Growth":0.30,"EquityStructure":0.05,"Size":0.05},
    "大消费": {"Profitability":0.33,"CashFlow":0.24,"Solvency":0.10,"Efficiency":0.10,"Growth":0.14,"EquityStructure":0.05,"Size":0.04},
    "医药健康": {"Profitability":0.20,"CashFlow":0.20,"Solvency":0.15,"Efficiency":0.10,"Growth":0.25,"EquityStructure":0.05,"Size":0.05},
    "国防军工": {"Profitability":0.25,"CashFlow":0.20,"Solvency":0.15,"Efficiency":0.10,"Growth":0.20,"EquityStructure":0.05,"Size":0.05},
    "生活服务与零售": {"Profitability":0.25,"CashFlow":0.25,"Solvency":0.15,"Efficiency":0.10,"Growth":0.15,"EquityStructure":0.05,"Size":0.05},
    "其他": {"Profitability":0.20,"CashFlow":0.20,"Solvency":0.20,"Efficiency":0.10,"Growth":0.15,"EquityStructure":0.05,"Size":0.10}
}

SUB_INDUSTRY_WEIGHTS = {
    "房地产开发": {"Solvency":0.45,"CashFlow":0.30,"Profitability":0.05},
    "工程建设与服务": {"CashFlow":0.30,"Solvency":0.35},
    "半导体与电子元器件": {"Growth":0.35,"Profitability":0.15},
    "软件与IT服务": {"CashFlow":0.25,"Growth":0.25},
    "必需消费品": {"Profitability":0.35,"CashFlow":0.30,"Growth":0.05},
    "可选消费品": {"CashFlow":0.28,"Solvency":0.15},
    "制药与生物技术": {"Growth":0.30,"Profitability":0.15},
    "国防装备整机与系统": {"Growth":0.22,"CashFlow":0.22},
    "化石能源与公用事业": {"CashFlow":0.25,"Profitability":0.35},
    "环保工程与运营": {"CashFlow":0.35,"Solvency":0.30},
    "资本市场服务业": {"Profitability":0.30,"Growth":0.25}
}



# %% [markdown]
# * 2.1.1  宏观因子
# * 2.1.1.1 宏观因子映射表  宏观因子对维度的敏感性（2026版）

# %%
MACRO_SENSITIVITY = {
    "GDP增速": {
        "Growth": 0.8,
        "Profitability": 0.5,
        "CashFlow": 0.3
    },
    "PPI同比": {
        "Profitability": 0.7,   # PPI↑ → 工业品涨价 → 毛利↑
        "Growth": 0.4
    },
    "社融增速": {
        "Solvency": -0.7,       # 社融↑ → 流动性改善 → 偿债压力↓
        "Growth": 0.6
    },
    "10年期国债收益率": {
        "Solvency": -0.5,       # 利率↑ → 折现成本↑ → 偿债能力↓
        "Profitability": -0.3
    },
    "出口增速": {
        "Growth": 0.9,          # 出口链直接受益
        "CashFlow": 0.6
    },
    "制造业PMI": {
        "Efficiency": 0.7,      # PMI↑ → 产能利用率↑ → 周转率↑
        "Growth": 0.5
    }
}


# %% [markdown]
# * 2.1.1.2 最新宏观数据  # 2026年1月最新宏观数据 Latest_macro日更新

# %%
LATEST_MACRO = {
    "GDP增速": 0.048,
    "CPI同比": 0.009,
    "PPI同比": -0.012,
    "社融增速": 0.092,
    "M2增速": 0.085,
    "10年期国债收益率": 0.028,
    "出口增速": 0.068,
    "制造业PMI": 50.2
}

# 5年基准线（2020–2024均值）
MACRO_BASELINES = {
    "GDP增速": 0.052,
    "CPI同比": 0.018,
    "PPI同比": 0.005,
    "社融增速": 0.105,
    "M2增速": 0.098,
    "10年期国债收益率": 0.031,
    "出口增速": 0.035,
    "制造业PMI": 49.8
}

# %% [markdown]
# * 2.1.2 政策
# * 2.1.2.1 政策阶段规则

# %%
POLICY_PHASES = {
    # ========== 1. 房地产政策 ==========
    "房地产": {
        "风险暴露期（2021-2022）": {
            "Solvency": +0.08,   # 偿债能力权重大幅提高
            "CashFlow": +0.05,
            "Profitability": -0.05
        },
        "保交楼攻坚期（2023-2024Q2）": {
            "Solvency": +0.06,
            "CashFlow": +0.04,
            "Growth": -0.03
        },
        "需求复苏初期（2024Q3-2025Q4）": {
            "Solvency": +0.04,   # 偿债压力缓解
            "Growth": +0.03,     # 销售回暖
            "CashFlow": +0.02
        },
        "市场企稳期（2026+）": {
            "Profitability": +0.03,  # 盈利修复
            "Growth": +0.02,
            "Solvency": +0.02
        }
    },
    
    # ========== 2. 新质生产力 ==========
    "新质生产力": {
        "技术攻关期（2020-2023）": {
            "Growth": +0.06,     # 研发投入驱动
            "R&D_efficiency": +0.04,  # 研发效率权重
            "Profitability": -0.02   # 短期盈利承压
        },
        "产业化加速期（2024-2025）": {
            "Growth": +0.04,
            "Efficiency": +0.03,  # 产能爬坡
            "Profitability": +0.02  # 规模效应显现
        },
        "全球竞争力期（2026+）": {
            "Profitability": +0.04,
            "CashFlow": +0.03,
            "Growth": +0.02
        }
    },
    
    # ========== 3. 消费政策 ==========
    "消费": {
        "疫情恢复期（2023）": {
            "Growth": +0.05,     # 补偿性消费
            "CashFlow": +0.03
        },
        "服务消费主导期（2024-2025）": {
            "Growth": +0.03,     # 文旅/医疗/教育升级
            "Profitability": +0.02
        },
        "国货潮升级期（2026+）": {
            "Profitability": +0.04,  # 品牌溢价提升
            "Growth": +0.02
        }
    },
    
    # ========== 4. 地方债务 ==========
    "地方债务": {
        "风险累积期（2020-2023）": {
            "Solvency": +0.05,   # 城投相关行业
            "CashFlow": +0.03
        },
        "风险化解期（2024-2025）": {
            "Solvency": +0.04,   # 特殊再融资债券置换
            "CashFlow": +0.02
        },
        "财政可持续期（2026+）": {
            "Solvency": +0.02,
            "Growth": +0.03      # 财政空间释放
        }
    },
    
    # ========== 5. 出口与贸易 ==========
    "出口": {
        "传统出口承压期（2022-2023）": {
            "Growth": -0.03,
            "CashFlow": -0.02
        },
        "结构升级期（2024-2025）": {
            "Growth": +0.05,     # “新三样”出口爆发
            "CashFlow": +0.03
        },
        "全球份额提升期（2026+）": {
            "Profitability": +0.04,  # 高附加值产品
            "Growth": +0.03
        }
    },
    
    # ========== 6. 金融监管 ==========
    "金融": {
        "防风险优先期（2023-2024）": {
            "Solvency": +0.07,   # 银行资本充足率
            "Profitability": -0.03  # 净息差收窄
        },
        "支持实体经济期（2025-2026）": {
            "Solvency": +0.05,
            "Growth": +0.03      # 信贷支持制造业
        }
    },
    
    # ========== 7. 能源转型 ==========
    "能源转型": {
        "双碳目标推进期（2021-2023）": {
            "Solvency": +0.04,   # 传统能源去杠杆
            "Growth": -0.02
        },
        "新型电力系统建设期（2024-2025）": {
            "Growth": +0.05,     # 光伏/风电/储能
            "CashFlow": +0.03
        },
        "能源安全强化期（2026+）": {
            "Profitability": +0.03,  # 传统能源盈利修复
            "Solvency": +0.02
        }
    },
    
    # ========== 8. 医药健康 ==========
    "医药健康": {
        "集采深化期（2021-2023）": {
            "Profitability": -0.05,  # 药品价格下降
            "Growth": -0.02
        },
        "创新药突破期（2024-2025）": {
            "Growth": +0.1,     # 创新药出海 +0.06
            # "R&D_efficiency": +0.04 # R&D_efficiency 是新增维度，可映射到 Growth
        },
        "医疗新基建期（2026+）": {
            "Growth": +0.04,     # 医院/设备扩容
            "CashFlow": +0.02
        }
    },
    
    # ========== 9. 国防军工 ==========
    "国防军工": {
        "装备现代化加速期（2023-2025）": {
            "Growth": +0.06,     # 军费稳定增长
            "CashFlow": +0.04    # 预收款模式
        },
        "军民融合深化期（2026+）": {
            "Profitability": +0.03,  # 民品业务贡献
            "Growth": +0.03
        }
    },
    
    # ========== 10. 数字经济 ==========
    "数字经济": {
        "基础设施建设期（2022-2023）": {
            "Growth": +0.05,     # 东数西算/5G
            "Solvency": -0.02    # 高资本开支
        },
        "AI应用爆发期（2024-2025）": {
            "Growth": +0.06,     # 大模型商业化
            "Profitability": +0.03
        },
        "数据要素市场化期（2026+）": {
            "Profitability": +0.04,  # 数据资产入表
            "CashFlow": +0.02
        }
    }
}


# %% [markdown]
# * 2.1.2.2 行业-政策映射表

# %%
INDUSTRY_POLICY_MAPPING = {
    # 房地产链
    "住宅开发": "房地产",
    "商业地产": "房地产",
    "房屋建设Ⅱ": "房地产",
    "装修装饰Ⅱ": "房地产",
    "水泥": "房地产",
    "家电": "房地产",
    
    # 新质生产力
    "半导体设备": "新质生产力",
    "集成电路制造": "新质生产力",
    "光伏电池组件": "新质生产力",
    "电池": "新质生产力",
    "机器人": "新质生产力",
    
    # 消费
    "白酒Ⅱ": "消费",
    "食品加工": "消费",
    "影视院线": "消费",
    "游戏Ⅱ": "消费",
    
    # 出口链
    "品牌消费电子": "出口",
    "通信设备": "出口",
    "乘用车": "出口",  # 新能源车
    
    # 国防军工
    "航天装备Ⅱ": "国防军工",
    "军工电子Ⅲ": "国防军工",
    
    # 金融
    "银行": "金融",
    "保险Ⅱ": "金融",
    
    # 能源
    "煤炭": "能源转型",
    "电力": "能源转型",
    "光伏辅材": "能源转型",
    
    # 医药
    "生物制品": "医药健康",
    "医疗设备": "医药健康",
    
    # 数字经济
    "云计算": "数字经济",  # 注：隐含在IT服务
    "AI芯片": "数字经济"   # 注：隐含在半导体
}

# %% [markdown]
# * 2.1.2.3 当前政策阶段标签（2026年1月）current_policy_phases 日更新

# %%
CURRENT_POLICY_PHASES = {
    "房地产": "需求复苏初期（2024Q3-2025Q4）",
    "新质生产力": "产业化加速期（2024-2025）",
    "消费": "服务消费主导期（2024-2025）",
    "金融": "支持实体经济期（2025-2026）"
}

# %% [markdown]
# * 2.1.3 产业链
# * 2.1.3.1 商品-行业映射

# %%
COMMODITY_TO_UPSTREAM = { # 商品-上游行业映射
    "煤炭": ["煤炭"],
    "石油": ["石油石化"],
    "铁矿石": ["钢铁"],
    "铜": ["铜"],
    "铝": ["铝"],
    "铅锌": ["铅锌"],
    "锂": ["能源金属"],
    "钴": ["能源金属"],
    "镍": ["能源金属"],
    "硅料": ["硅料硅片"],
    "纯碱": ["化学制品"],
    "PX": ["化学制品"],
    "MDI": ["化学制品"],
    "TDI": ["化学制品"],
    "PVC": ["化学制品"],
    "涤纶": ["化学纤维"],
    "锦纶": ["化学纤维"],
    "氨纶": ["化学纤维"],
    "天然橡胶": ["橡胶"],
    "合成橡胶": ["橡胶"],
    "玻璃": ["玻璃玻纤"],
    "水泥": ["水泥"],
    "石膏板": ["装修建材"],
    "瓷砖": ["瓷砖地板"]
}

# 下游行业-商品映射
DOWNSTREAM_COMMODITY_MAPPING = {
    # 能源与资源
    "电力": ["煤炭", "石油"],
    "钢铁": ["铁矿石", "煤炭"],
    "化工与农化": ["石油", "煤炭", "纯碱", "PX"],
    "化学纤维": ["PX", "涤纶", "锦纶", "氨纶"],
    "橡胶": ["天然橡胶", "合成橡胶"],
    
    # 基础材料
    "玻璃玻纤": ["纯碱", "玻璃"],
    "水泥": ["水泥"],
    "装修建材": ["石膏板", "瓷砖"],
    "瓷砖地板": ["瓷砖"],
    
    # 工业制造
    "电机Ⅱ": ["铜"],
    "电线电缆": ["铜"],  # 注：电线电缆在"通信线缆及配套"
    "家用电器": ["铜", "铝"],
    "乘用车": ["钢铁", "铝", "橡胶", "锂", "钴", "镍"],
    "商用车": ["钢铁", "铝", "橡胶", "锂", "钴", "镍"],
    "轮胎轮毂": ["天然橡胶", "合成橡胶"],
    
    # TMT科技
    "半导体材料": ["硅料"],
    "光伏电池组件": ["硅料"],
    "逆变器": ["硅料"],
    "电池": ["锂", "钴", "镍"],
    
    # 大消费
    "食品加工": ["农产品"],  # 农产品价格通过CPI间接反映
    "调味发酵品Ⅱ": ["农产品"],
    "白酒Ⅱ": ["农产品"],
    "服装家纺": ["涤纶", "锦纶", "氨纶"],
    "纺织制造": ["涤纶", "锦纶", "氨纶"]
}

# %% [markdown]
# * 2.1.3.2 产业链关联矩阵
#   *  ("下游行业1", 强度, "描述")

# %%
INDUSTRY_LINKAGE_V2 = {
    # ========== 能源与资源 ==========
    "煤炭": {
        "downstream": [
            ("电力", 0.9, "煤炭"),
            ("钢铁", 0.8, "煤炭")
        ],
        "commodity": "煤炭"
    },
    "石油石化": {
        "downstream": [
            ("化学制品", 0.9, "石油"),
            ("化学纤维", 0.8, "石油"),
            ("橡胶", 0.7, "石油")
        ],
        "commodity": "石油"
    },
    "钢铁": {
        "downstream": [
            ("工程机械", 0.8, "钢铁"),
            ("轨交设备Ⅱ", 0.8, "钢铁"),
            ("乘用车", 0.7, "钢铁"),
            ("商用车", 0.7, "钢铁"),
            ("房屋建设Ⅱ", 0.6, "钢铁")
        ],
        "commodity": "铁矿石"
    },
    "铜": {
        "downstream": [
            ("电机Ⅱ", 0.9, "铜"),
            ("通信线缆及配套", 0.9, "铜"),
            ("家用电器", 0.7, "铜")
        ],
        "commodity": "铜"
    },
    "铝": {
        "downstream": [
            ("乘用车", 0.8, "铝"),
            ("商用车", 0.8, "铝"),
            ("家电", 0.7, "铝")
        ],
        "commodity": "铝"
    },
    "铅锌": {
        "downstream": [
            ("电池", 0.8, "铅锌")
        ],
        "commodity": "铅锌"
    },
    "能源金属": {
        "downstream": [
            ("电池", 0.95, "锂"),
            ("电池", 0.85, "钴"),
            ("电池", 0.8, "镍")
        ],
        "commodity": "锂"  # 主要监测锂价
    },
    
    # ========== 基础材料与化工 ==========
    "化学制品": {
        "downstream": [
            ("农化制品", 0.8, "PX"),
            ("化学制剂", 0.7, "MDI"),
            ("原料药", 0.7, "TDI"),
            ("电子化学品Ⅱ", 0.6, "PVC")
        ],
        "commodity": "PX"
    },
    "化学纤维": {
        "downstream": [
            ("服装家纺", 0.9, "涤纶"),
            ("纺织制造", 0.9, "锦纶")
        ],
        "commodity": "涤纶"
    },
    "橡胶": {
        "downstream": [
            ("轮胎轮毂", 0.95, "天然橡胶"),
            ("其他汽车零部件", 0.7, "合成橡胶")
        ],
        "commodity": "天然橡胶"
    },
    "玻璃玻纤": {
        "downstream": [
            ("装修建材", 0.8, "玻璃"),
            ("光伏辅材", 0.9, "玻璃")
        ],
        "commodity": "玻璃"
    },
    "水泥": {
        "downstream": [
            ("房屋建设Ⅱ", 0.9, "水泥"),
            ("专业工程", 0.8, "水泥")
        ],
        "commodity": "水泥"
    },
    "装修建材": {
        "downstream": [
            ("装修装饰Ⅱ", 0.9, "石膏板"),
            ("定制家居", 0.7, "石膏板")
        ],
        "commodity": "石膏板"
    },
    "瓷砖地板": {
        "downstream": [
            ("装修装饰Ⅱ", 0.8, "瓷砖")
        ],
        "commodity": "瓷砖"
    },
    
    # ========== TMT科技 ==========
    "硅料硅片": {
        "downstream": [
            ("光伏电池组件", 0.95, "硅料"),
            ("逆变器", 0.3, "硅料")
        ],
        "commodity": "硅料"
    },
    "半导体材料": {
        "downstream": [
            ("集成电路制造", 0.95, "硅料")
        ],
        "commodity": "硅料"
    },
    
    # ========== 大消费 ==========
    "农林牧渔": {
        "downstream": [
            ("食品加工", 0.9, "农产品"),
            ("调味发酵品Ⅱ", 0.8, "农产品"),
            ("白酒Ⅱ", 0.7, "农产品")
        ]
        # 农产品无直接商品价格，通过CPI监测
    },
    "服装家纺": {
        "upstream": [
            ("化学纤维", 0.9, "涤纶")
        ]
    },
    "纺织制造": {
        "upstream": [
            ("化学纤维", 0.9, "锦纶")
        ]
    }
}

# %%
INDUSTRY_LINKAGE_V2.values()

# %%
sum(len(inner) for inner in INDUSTRY_LINKAGE_V2.values())

# %% [markdown]
# * 2.1.3.3 2025年商品价格基准（单位：元/吨）

# %%
COMMODITY_BASELINES = {
    "煤炭": 850,
    "石油": 5500,      # 原油价格×7.3
    "铁矿石": 950,
    "铜": 70000,
    "铝": 20000,
    "铅锌": 22000,
    "锂": 100000,      # 电池级碳酸锂
    "钴": 280000,
    "镍": 140000,
    "硅料": 60000,
    "纯碱": 2200,
    "PX": 8500,
    "MDI": 18000,
    "TDI": 15000,
    "PVC": 6500,
    "涤纶": 7500,
    "锦纶": 12000,
    "氨纶": 35000,
    "天然橡胶": 13000,
    "合成橡胶": 15000,
    "玻璃": 2000,
    "水泥": 400,
    "石膏板": 8,
    "瓷砖": 45
}

# 事件触发阈值（价格变动幅度）
EVENT_THRESHOLDS = {
    "原材料价格变动": 0.20,  # 20%变动触发
    "产能扩张": 0.30,       # 30%产能增长触发
    "技术突破": 0.15        # 技术指标提升15%触发
}

# %% [markdown]
# * 2.1.3.4 产业链相关辅助函数

# %%
def get_downstream_by_commodity(commodity: str) -> List[str]:
    """获取某商品的所有直接下游行业"""
    downstream = []
    for upstream, info in INDUSTRY_LINKAGE_V2.items():
        if "downstream" in info:
            for industry, strength, comm in info["downstream"]:
                if comm == commodity:
                    downstream.append(industry)
    return list(set(downstream))  # 去重

def get_linkage_strength(industry: str, commodity: str) -> float:
    """获取行业与商品的关联强度"""
    for upstream, info in INDUSTRY_LINKAGE_V2.items():
        if "downstream" in info:
            for down, strength, comm in info["downstream"]:
                if down == industry and comm == commodity:
                    return strength
    # 未找到精确匹配，返回默认强度
    return 0.5

class LinkageEventDetector:
    def __init__(self):
        self.baselines = COMMODITY_BASELINES
        self.thresholds = EVENT_THRESHOLDS
    
    def detect_events(self, current_prices: Dict[str, float]) -> List[Dict]:
        """检测产业链事件"""
        events = []
        
        for commodity, current_price in current_prices.items():
            if commodity in self.baselines:
                baseline = self.baselines[commodity]
                magnitude = (current_price - baseline) / baseline
                
                if abs(magnitude) >= self.thresholds["原材料价格变动"]:
                    events.append({
                        "type": "原材料价格变动",
                        "commodity": commodity,
                        "magnitude": magnitude,
                        "baseline": baseline,
                        "current": current_price
                    })
        
        return events
    
def calculate_linkage_adjustment(industry: str, events: List[Dict]) -> Dict[str, float]:
    """计算产业链事件对行业的权重调整"""
    adjustment = {dim: 0.0 for dim in ["Profitability", "CashFlow", "Solvency", 
                                    "Efficiency", "Growth", "EquityStructure", "Size"]}
    
    for event in events:
        if event["type"] == "原材料价格变动":
            commodity = event["commodity"]
            magnitude = event["magnitude"]
            
            # 检查是否为上游行业
            if industry in COMMODITY_TO_UPSTREAM.get(commodity, []):
                # 上游行业：价格上涨利好
                adjustment["Profitability"] += 0.05 * magnitude
                adjustment["Growth"] += 0.02 * magnitude
            
            # 检查是否为下游行业
            elif industry in get_downstream_by_commodity(commodity):
                # 下游行业：价格上涨利空
                strength = get_linkage_strength(industry, commodity)
                adjustment["Profitability"] -= 0.04 * strength * abs(magnitude)
                adjustment["CashFlow"] -= 0.03 * strength * abs(magnitude)
    
    return adjustment    

# %% [markdown]
# * 2.1.3.5 产业链相关示例

# %%
current_prices = {      # 当前商品价格（2026年1月）
    "硅料": 43000,      # -28.3%
    "锂": 65000,        # -35.0%
    "铜": 72000,        # +2.9% (未触发)
    "铝": 19500,        # -2.5% (未触发)
    "PX": 7200,         # -15.3% (未触发)
    "涤纶": 6400        # -14.7% (未触发)
}

# 初始化事件检测器
detector = LinkageEventDetector()
events = detector.detect_events(current_prices)

print("检测到的产业链事件:")
for event in events:
    print(f"- {event['commodity']}价格变动: {event['magnitude']:+.1%}")

# 计算各行业权重调整
industries_to_check = ["硅料硅片", "光伏电池组件", "能源金属", "电池", "化学制品", "服装家纺"]

for industry in industries_to_check:
    adj = calculate_linkage_adjustment(industry, events)
    total_adj = sum(abs(v) for v in adj.values())
    if total_adj > 0.001:
        print(f"\n{industry} 权重调整:")
        for dim, value in adj.items():
            if abs(value) > 0.001:
                print(f"  {dim}: {value:+.3f}")

# %% [markdown]
# * 2.2 维度内指标权重
# * 2.2.1全局默认指标权重（适用于大多数行业）

# %%
DEFAULT_INDICATORS = {
    "Profitability": [
        ("col202", False, 0.4, "销售毛利率"),
        ("col194", False, 0.3, "营业利润率"),  # 新增
        ("col199", False, 0.2, "销售净利率"),
        ("profit_quality", False, 0.1, "盈利质量（现金流/利润）")  # 新增
    ],
    "CashFlow": [
        ("col107", True, 0.5, "经营现金流TTM"),
        ("col228", True, 0.3, "经营现金流/净利润TTM"),
        ("col229", False, 0.2, "全部资产现金回收率")  # 新增
    ],
    "Solvency": [
        ("col210", False, 0.5, "资产负债率"),
        ("credit_impairment_ratio", False, -0.3, "信用减值损失率（负向）"),  # 新增
        ("col8", False, 0.2, "货币资金")
    ],
    "Efficiency": [
        ("col175", True, 0.5, "总资产周转率TTM"),
        ("col172", True, 0.3, "应收周转率TTM"),
        ("col173", True, 0.2, "存货周转率TTM")
    ],
    "Growth": [
        ("col183", False, 0.4, "营业收入增长率"),
        ("col184", False, 0.4, "净利润增长率"),
        ("col187", False, 0.2, "总资产增长率")
    ],
    "EquityStructure": [
        ("col243", False, 0.5, "第一大股东持股"),
        ("col238", False, 0.3, "总股本"),
        ("col242", False, 0.2, "股东人数")
    ],
    "Size": [
        ("col502", True, 0.6, "营业总收入TTM"),
        ("col40", False, 0.3, "资产总计"),
        ("col238", False, 0.1, "总股本")
    ]
}

# %% [markdown]
# * 2.2.2 维度内二级子类通用指标权重

# %%
DIMENSION_INDICATORS_BASE = {}

for super_ind, sub_dict in industry_hierarchy.items():
    for sub_ind, industries in sub_dict.items():
        overrides = {}
        if super_ind == "金融业":
            if sub_ind == "银行业":
                overrides = {
                    "Profitability": [("col281", False, 0.6, "加权净资产收益率"), ("col197", False, 0.3, "净资产收益率"), ("col199", False, 0.1, "销售净利率")],
                    "CashFlow": [("col8", False, 0.7, "货币资金"), ("col9", False, 0.2, "交易性金融资产"), ("col133", False, 0.1, "期末现金余额")],
                    "Solvency": [("col72", False, 0.5, "所有者权益合计"), ("col40", False, 0.3, "资产总计"), ("col63", False, 0.2, "负债合计")],
                    "Efficiency": [("col74", True, 0.9, "营业收入TTM"), ("col40", False, 0.1, "资产总计")],
                    "Size": [("col40", False, 0.6, "资产总计"), ("col74", True, 0.3, "营业收入TTM"), ("col72", False, 0.1, "所有者权益合计")]
                }
            elif sub_ind == "保险业":
                overrides = {
                    "CashFlow": [("col565", True, 0.6, "保费现金流入TTM"), ("col107", True, 0.3, "经营现金流TTM"), ("col133", False, 0.1, "期末现金余额")],
                    "Solvency": [("col72", False, 0.5, "所有者权益合计"), ("col40", False, 0.3, "资产总计"), ("col419", False, 0.2, "保险合同准备金")],
                    "Efficiency": [("col74", True, 0.9, "营业收入TTM"), ("col40", False, 0.1, "资产总计")],
                    "Size": [("col40", False, 0.6, "资产总计"), ("col74", True, 0.3, "营业收入TTM"), ("col72", False, 0.1, "所有者权益合计")]
                }
            else:  # 资本市场服务业
                overrides = {
                    "Profitability": [("col197", False, 0.5, "净资产收益率"), ("col83", False, 0.3, "投资收益"), ("col199", False, 0.2, "销售净利率")],
                    "CashFlow": [("col107", True, 0.6, "经营现金流TTM"), ("col133", False, 0.4, "期末现金余额")],
                    "Solvency": [("col210", False, 0.6, "资产负债率"), ("col8", False, 0.4, "货币资金")],
                    "Efficiency": [("col175", True, 0.7, "总资产周转率TTM"), ("col172", True, 0.3, "应收周转率TTM")],
                    "Size": [("col74", True, 0.7, "营业收入TTM"), ("col40", False, 0.3, "资产总计")]
                }

        elif super_ind == "房地产业":
            if sub_ind == "房地产开发":
                overrides = {
                    "Profitability": [("col202", False, 0.6, "销售毛利率（核心）"), ("col199", False, 0.3, "销售净利率"), ("col197", False, 0.1, "净资产收益率")],
                    "CashFlow": [("col107", True, 0.5, "经营现金流TTM"), ("col219", False, 0.3, "每股经营性现金流"), ("col223", True, 0.2, "经营现金流/营收TTM")],
                    "Solvency": [("col8", False, 0.4, "货币资金"), ("col41", False, 0.3, "短期借款"), ("col52", False, 0.3, "一年内到期非流动负债")],
                    "Efficiency": [("col173", True, 0.6, "存货周转率TTM"), ("col175", True, 0.3, "总资产周转率TTM"), ("col172", True, 0.1, "应收周转率TTM")],
                    "Size": [("col40", False, 0.6, "资产总计"), ("col74", True, 0.3, "营业收入TTM"), ("col17", False, 0.1, "存货")]
                }
            else:  # 工程建设与服务
                overrides = {
                    "Profitability": [("col199", False, 0.6, "销售净利率"), ("col202", False, 0.3, "销售毛利率"), ("col197", False, 0.1, "净资产收益率")],
                    "CashFlow": [("col107", True, 0.5, "经营现金流TTM"), ("col223", True, 0.3, "经营现金流/营收TTM"), ("col228", True, 0.2, "经营现金流/净利润TTM")],
                    "Solvency": [("col21", False, 0.5, "流动资产合计"), ("col54", False, 0.5, "流动负债合计")],
                    "Efficiency": [("col172", True, 0.6, "应收周转率TTM"), ("col175", True, 0.3, "总资产周转率TTM"), ("col173", True, 0.1, "存货周转率TTM")],
                    "Size": [("col40", False, 0.6, "资产总计"), ("col74", True, 0.3, "营业收入TTM"), ("col21", False, 0.1, "流动资产合计")]
                }

        elif super_ind == "TMT科技":
            if sub_ind == "半导体与电子元器件":
                overrides = {
                    "Profitability": [("col202", False, 0.5, "销售毛利率（技术壁垒）"), ("col199", False, 0.3, "销售净利率"), ("col197", False, 0.2, "净资产收益率")],
                    "Growth": [("col304", True, 0.4, "研发费用TTM"), ("col183", False, 0.4, "营业收入增长率"), ("col184", False, 0.2, "净利润增长率")],
                    "Size": [("col74", True, 0.6, "营业收入TTM"), ("col40", False, 0.3, "资产总计"), ("col238", False, 0.1, "总股本")]
                }
            elif sub_ind == "软件与IT服务":
                overrides = {
                    "Profitability": [("col202", False, 0.6, "销售毛利率（轻资产高毛利）"), ("col199", False, 0.3, "销售净利率"), ("col197", False, 0.1, "净资产收益率")],
                    "Solvency": [("col210", False, 0.7, "资产负债率"), ("col8", False, 0.2, "货币资金"), ("col63", False, 0.1, "负债合计")],
                    "Efficiency": [("col175", True, 0.7, "总资产周转率TTM"), ("col172", True, 0.2, "应收周转率TTM"), ("col179", True, 0.1, "流动资产周转率TTM")],
                    "Growth": [("col183", False, 0.5, "营业收入增长率"), ("col304", True, 0.3, "研发费用TTM"), ("col184", False, 0.2, "净利润增长率")],
                    "Size": [("col74", True, 0.7, "营业收入TTM"), ("col40", False, 0.2, "资产总计"), ("col238", False, 0.1, "总股本")]
                }
            else:
                overrides = {
                    "Growth": [("col183", False, 0.4, "营业收入增长率"), ("col184", False, 0.4, "净利润增长率"), ("col304", True, 0.2, "研发费用TTM")],
                    "Size": [("col74", True, 0.6, "营业收入TTM"), ("col40", False, 0.3, "资产总计"), ("col238", False, 0.1, "总股本")]
                }

        elif super_ind == "大消费":
            overrides = {
                "Profitability": [("col281", False, 0.4, "加权净资产收益率"), ("col202", False, 0.4, "销售毛利率"), ("col199", False, 0.2, "销售净利率")],
                "CashFlow": [("col107", True, 0.5, "经营现金流TTM"), ("col228", True, 0.3, "经营现金流/净利润TTM"), ("col219" if "必需消费品" in sub_ind else "col223", False, 0.2, "每股经营性现金流" if "必需消费品" in sub_ind else "经营现金流/营收TTM")],
                "Solvency": [("col210", False, 0.6, "资产负债率"), ("col8", False, 0.3, "货币资金"), ("col63", False, 0.1, "负债合计")],
                "Efficiency": [("col175", True, 0.6, "总资产周转率TTM"), ("col172", True, 0.3, "应收周转率TTM"), ("col179", True, 0.1, "流动资产周转率TTM")],
                "Growth": [("col183", False, 0.5, "营业收入增长率"), ("col184", False, 0.3, "净利润增长率"), ("col185", False, 0.2, "净资产增长率")],
                "Size": [("col74", True, 0.7, "营业收入TTM"), ("col40", False, 0.2, "资产总计"), ("col238", False, 0.1, "总股本")]
            }

        elif super_ind == "环保服务":
            overrides = {
                "Profitability": [("col199", False, 0.6, "销售净利率"), ("col202", False, 0.4, "销售毛利率")],
                "CashFlow": [("col107", True, 0.5, "经营现金流TTM"), ("col223", True, 0.3, "经营现金流/营收TTM"), ("col88", True, 0.2, "政府补贴")],
                "Solvency": [("col21", False, 0.5, "流动资产合计"), ("col54", False, 0.5, "流动负债合计")],
                "Efficiency": [("col172", True, 0.6, "应收周转率TTM"), ("col175", True, 0.4, "总资产周转率TTM")],
                "Size": [("col74", True, 0.6, "营业收入TTM"), ("col40", False, 0.4, "资产总计")]
            }

        # 其他行业使用默认模板，无需 overrides

        DIMENSION_INDICATORS_BASE[sub_ind] = overrides

# %% [markdown]
# * 2.2.3 维度内细分行业指标权重

# %%
FULL_OVERRIDE_INDUSTRIES = {
    # ========== 金融业 ==========
    "银行": {
        "Profitability": [
            ("nim_approx", False, 0.4, "净息差（近似）"),
            ("npl_approx", False, -0.3, "不良率（负向）"),
            ("col281", False, 0.3, "加权净资产收益率")
        ],
        "CashFlow": [
            ("col8", False, 0.7, "货币资金（流动性）"),
            ("col133", False, 0.3, "期末现金余额")
        ],
        "Solvency": [
            ("col72", False, 0.5, "所有者权益合计（资本充足）"),
            ("col40", False, 0.3, "资产总计"),
            ("col63", False, 0.2, "负债合计")
        ],
        "Efficiency": [
            ("col502", True, 0.6, "营业总收入TTM"),
            ("col40", False, 0.4, "资产总计")
        ],
        "Growth": [
            ("col183", False, 0.6, "营业收入增长率"),
            ("col184", False, 0.4, "净利润增长率")
        ],
        "EquityStructure": [
            ("col243", False, 0.5, "第一大股东持股"),
            ("col238", False, 0.3, "总股本"),
            ("col242", False, 0.2, "股东人数")
        ],
        "Size": [
            ("col40", False, 0.7, "资产总计"),
            ("col502", True, 0.3, "营业总收入TTM")
        ]
    },
    "保险Ⅱ": {
        "Profitability": [
            ("col197", False, 0.5, "净资产收益率"),
            ("col281", False, 0.3, "加权净资产收益率"),
            ("col199", False, 0.2, "销售净利率")
        ],
        "CashFlow": [
            ("col565", True, 0.6, "保费现金流入TTM"),
            ("col107", True, 0.4, "经营现金流TTM")
        ],
        "Solvency": [
            ("col72", False, 0.5, "所有者权益合计"),
            ("col419", False, 0.3, "保险合同准备金"),
            ("col40", False, 0.2, "资产总计")
        ],
        "Efficiency": [
            ("col502", True, 0.7, "营业总收入TTM"),
            ("col40", False, 0.3, "资产总计")
        ],
        "Growth": [
            ("col183", False, 0.6, "营业收入增长率"),
            ("col184", False, 0.4, "净利润增长率")
        ],
        "EquityStructure": [
            ("col243", False, 0.5, "第一大股东持股"),
            ("col238", False, 0.3, "总股本"),
            ("col242", False, 0.2, "股东人数")
        ],
        "Size": [
            ("col40", False, 0.7, "资产总计"),
            ("col502", True, 0.3, "营业总收入TTM")
        ]
    },
    "证券Ⅱ": {
        "Profitability": [
            ("col83", False, 0.5, "投资收益（自营+投行）"),
            ("col197", False, 0.3, "净资产收益率"),
            ("col199", False, 0.2, "销售净利率")
        ],
        "CashFlow": [
            ("col107", True, 0.6, "经营现金流TTM"),
            ("col133", False, 0.4, "期末现金余额")
        ],
        "Solvency": [
            ("col210", False, 0.6, "资产负债率"),
            ("col8", False, 0.4, "货币资金")
        ],
        "Efficiency": [
            ("col175", True, 0.7, "总资产周转率TTM"),
            ("col172", True, 0.3, "应收周转率TTM")
        ],
        "Growth": [
            ("col183", False, 0.5, "营业收入增长率"),
            ("col184", False, 0.5, "净利润增长率")
        ],
        "EquityStructure": [
            ("col243", False, 0.5, "第一大股东持股"),
            ("col238", False, 0.3, "总股本"),
            ("col242", False, 0.2, "股东人数")
        ],
        "Size": [
            ("col502", True, 0.7, "营业总收入TTM"),
            ("col40", False, 0.3, "资产总计")
        ]
    },
    "多元金融": {
        "Profitability": [
            ("col83", False, 0.5, "投资收益（自营+投行）"),
            ("col197", False, 0.3, "净资产收益率"),
            ("col199", False, 0.2, "销售净利率")
        ],
        "CashFlow": [
            ("col107", True, 0.6, "经营现金流TTM"),
            ("col133", False, 0.4, "期末现金余额")
        ],
        "Solvency": [
            ("col210", False, 0.6, "资产负债率"),
            ("col8", False, 0.4, "货币资金")
        ],
        "Efficiency": [
            ("col175", True, 0.7, "总资产周转率TTM"),
            ("col172", True, 0.3, "应收周转率TTM")
        ],
        "Growth": [
            ("col183", False, 0.5, "营业收入增长率"),
            ("col184", False, 0.5, "净利润增长率")
        ],
        "EquityStructure": [
            ("col243", False, 0.5, "第一大股东持股"),
            ("col238", False, 0.3, "总股本"),
            ("col242", False, 0.2, "股东人数")
        ],
        "Size": [
            ("col502", True, 0.7, "营业总收入TTM"),
            ("col40", False, 0.3, "资产总计")
        ]
    },

    # ========== 房地产业 ==========
    "住宅开发": {
        "Profitability": [
            ("col202", False, 0.6, "销售毛利率"),
            ("col199", False, 0.3, "销售净利率"),
            ("pre_sales_ratio", False, 0.1, "预收/营收（渠道强势度）")
    ],
        "CashFlow": [
            ("col107", True, 0.5, "经营现金流TTM"),
            ("col223", True, 0.3, "经营现金流/营收TTM"),
            ("col219", False, 0.2, "每股经营性现金流")
        ],
        "Solvency": [
            ("cash_short_debt_ratio", False, 0.7, "现金短债比"),
            ("col210", False, 0.3, "资产负债率")
        ],
        "Efficiency": [
            ("col173", True, 0.8, "存货周转率TTM（去化速度）"),
            ("payables_turnover", True, 0.2, "应付账款周转率TTM")  # 新增
        ],
        "Growth": [
            ("col183", False, 0.6, "营业收入增长率"),
            ("col184", False, 0.4, "净利润增长率")
        ],
        "EquityStructure": [
            ("col243", False, 0.5, "第一大股东持股"),
            ("col238", False, 0.3, "总股本"),
            ("col242", False, 0.2, "股东人数")
        ],
        "Size": [
            ("col40", False, 0.6, "资产总计"),
            ("col502", True, 0.4, "营业总收入TTM")
        ]
    },
    "商业地产": {
        "Profitability": [
            ("col202", False, 0.6, "销售毛利率"),
            ("col199", False, 0.3, "销售净利率"),
            ("pre_sales_ratio", False, 0.1, "预收/营收（渠道强势度）")
        ],
        "CashFlow": [
            ("col107", True, 0.5, "经营现金流TTM"),
            ("col223", True, 0.3, "经营现金流/营收TTM"),
            ("col219", False, 0.2, "每股经营性现金流")
        ],
        "Solvency": [
            ("cash_short_debt_ratio", False, 0.7, "现金短债比"),
            ("col210", False, 0.3, "资产负债率")
        ],
        "Efficiency": [
            ("col173", True, 0.8, "存货周转率TTM（去化速度）"),
            ("payables_turnover", True, 0.2, "应付账款周转率TTM")  # 新增
        ],
        "Growth": [
            ("col183", False, 0.6, "营业收入增长率"),
            ("col184", False, 0.4, "净利润增长率")
        ],
        "EquityStructure": [
            ("col243", False, 0.5, "第一大股东持股"),
            ("col238", False, 0.3, "总股本"),
            ("col242", False, 0.2, "股东人数")
        ],
        "Size": [
            ("col40", False, 0.6, "资产总计"),
            ("col502", True, 0.4, "营业总收入TTM")
        ]
    },
    "产业地产": {
        "Profitability": [
            ("col202", False, 0.6, "销售毛利率"),
            ("col199", False, 0.3, "销售净利率"),
            ("pre_sales_ratio", False, 0.1, "预收/营收（渠道强势度）")
        ],
        "CashFlow": [
            ("col107", True, 0.5, "经营现金流TTM"),
            ("col223", True, 0.3, "经营现金流/营收TTM"),
            ("col219", False, 0.2, "每股经营性现金流")
        ],
        "Solvency": [
            ("cash_short_debt_ratio", False, 0.7, "现金短债比"),
            ("col210", False, 0.3, "资产负债率")
        ],
        "Efficiency": [
            ("col173", True, 0.8, "存货周转率TTM（去化速度）"),
            ("payables_turnover", True, 0.2, "应付账款周转率TTM")  # 新增
        ],
        "Growth": [
            ("col183", False, 0.6, "营业收入增长率"),
            ("col184", False, 0.4, "净利润增长率")
        ],
        "EquityStructure": [
            ("col243", False, 0.5, "第一大股东持股"),
            ("col238", False, 0.3, "总股本"),
            ("col242", False, 0.2, "股东人数")
        ],
        "Size": [
            ("col40", False, 0.6, "资产总计"),
            ("col502", True, 0.4, "营业总收入TTM")
        ]
    },
    "房屋建设Ⅱ": {
        "Profitability": [
            ("col199", False, 0.7, "销售净利率"),
            ("col202", False, 0.3, "销售毛利率")
        ],
        "CashFlow": [
            ("col107", True, 0.5, "经营现金流TTM"),
            ("col223", True, 0.3, "经营现金流/营收TTM"),
            ("col228", True, 0.2, "经营现金流/净利润TTM")
        ],
        "Solvency": [
            ("col21", False, 0.5, "流动资产合计"),
            ("col54", False, 0.5, "流动负债合计（流动比率）")
        ],
        "Efficiency": [
            ("col172", True, 0.7, "应收周转率TTM（回款能力）"),
            ("col175", True, 0.3, "总资产周转率TTM")
        ],
        "Growth": [
            ("col183", False, 0.6, "营业收入增长率"),
            ("col184", False, 0.4, "净利润增长率")
        ],
        "EquityStructure": [
            ("col243", False, 0.5, "第一大股东持股"),
            ("col238", False, 0.3, "总股本"),
            ("col242", False, 0.2, "股东人数")
        ],
        "Size": [
            ("col40", False, 0.6, "资产总计"),
            ("col502", True, 0.4, "营业总收入TTM")
        ]
    },
    "装修装饰Ⅱ": {
        "Profitability": [
            ("col199", False, 0.7, "销售净利率"),
            ("col202", False, 0.3, "销售毛利率")
        ],
        "CashFlow": [
            ("col107", True, 0.5, "经营现金流TTM"),
            ("col223", True, 0.3, "经营现金流/营收TTM"),
            ("col228", True, 0.2, "经营现金流/净利润TTM")
        ],
        "Solvency": [
            ("col21", False, 0.5, "流动资产合计"),
            ("col54", False, 0.5, "流动负债合计（流动比率）")
        ],
        "Efficiency": [
            ("col172", True, 0.7, "应收周转率TTM（回款能力）"),
            ("col175", True, 0.3, "总资产周转率TTM")
        ],
        "Growth": [
            ("col183", False, 0.6, "营业收入增长率"),
            ("col184", False, 0.4, "净利润增长率")
        ],
        "EquityStructure": [
            ("col243", False, 0.5, "第一大股东持股"),
            ("col238", False, 0.3, "总股本"),
            ("col242", False, 0.2, "股东人数")
        ],
        "Size": [
            ("col40", False, 0.6, "资产总计"),
            ("col502", True, 0.4, "营业总收入TTM")
        ]
    },
    "房地产服务": {
        "Profitability": [
            ("col199", False, 0.7, "销售净利率"),
            ("col202", False, 0.3, "销售毛利率")
        ],
        "CashFlow": [
            ("col107", True, 0.5, "经营现金流TTM"),
            ("col223", True, 0.3, "经营现金流/营收TTM"),
            ("col228", True, 0.2, "经营现金流/净利润TTM")
        ],
        "Solvency": [
            ("col21", False, 0.5, "流动资产合计"),
            ("col54", False, 0.5, "流动负债合计（流动比率）")
        ],
        "Efficiency": [
            ("col172", True, 0.7, "应收周转率TTM（回款能力）"),
            ("col175", True, 0.3, "总资产周转率TTM")
        ],
        "Growth": [
            ("col183", False, 0.6, "营业收入增长率"),
            ("col184", False, 0.4, "净利润增长率")
        ],
        "EquityStructure": [
            ("col243", False, 0.5, "第一大股东持股"),
            ("col238", False, 0.3, "总股本"),
            ("col242", False, 0.2, "股东人数")
        ],
        "Size": [
            ("col40", False, 0.6, "资产总计"),
            ("col502", True, 0.4, "营业总收入TTM")
        ]
    },

    # ========== 环保服务 ==========
    "固废治理": {
        "Profitability": [
            ("col199", False, 0.6, "销售净利率（低毛利行业）"),
            ("col202", False, 0.4, "销售毛利率")
        ],
        "CashFlow": [
            ("col107", True, 0.5, "经营现金流TTM"),
            ("col88", True, 0.3, "营业外收入TTM（政府补贴）"),
            ("col223", True, 0.2, "经营现金流/营收TTM")
        ],
        "Solvency": [
            ("col21", False, 0.5, "流动资产合计"),
            ("col54", False, 0.5, "流动负债合计")
        ],
        "Efficiency": [
            ("col172", True, 0.7, "应收周转率TTM（政府回款慢）"),
            ("col175", True, 0.3, "总资产周转率TTM")
        ],
        "Growth": [
            ("col183", False, 0.6, "营业收入增长率"),
            ("col184", False, 0.4, "净利润增长率")
        ],
        "EquityStructure": [
            ("col243", False, 0.5, "第一大股东持股"),
            ("col238", False, 0.3, "总股本"),
            ("col242", False, 0.2, "股东人数")
        ],
        "Size": [
            ("col502", True, 0.7, "营业总收入TTM"),
            ("col40", False, 0.3, "资产总计")
        ]
    },
    "大气治理": {
        "Profitability": [
            ("col199", False, 0.6, "销售净利率（低毛利行业）"),
            ("col202", False, 0.4, "销售毛利率")
        ],
        "CashFlow": [
            ("col107", True, 0.5, "经营现金流TTM"),
            ("col88", True, 0.3, "营业外收入TTM（政府补贴）"),
            ("col223", True, 0.2, "经营现金流/营收TTM")
        ],
        "Solvency": [
            ("col21", False, 0.5, "流动资产合计"),
            ("col54", False, 0.5, "流动负债合计")
        ],
        "Efficiency": [
            ("col172", True, 0.7, "应收周转率TTM（政府回款慢）"),
            ("col175", True, 0.3, "总资产周转率TTM")
        ],
        "Growth": [
            ("col183", False, 0.6, "营业收入增长率"),
            ("col184", False, 0.4, "净利润增长率")
        ],
        "EquityStructure": [
            ("col243", False, 0.5, "第一大股东持股"),
            ("col238", False, 0.3, "总股本"),
            ("col242", False, 0.2, "股东人数")
        ],
        "Size": [
            ("col502", True, 0.7, "营业总收入TTM"),
            ("col40", False, 0.3, "资产总计")
        ]
    },
    "水务及水治理": {
        "Profitability": [
            ("col199", False, 0.6, "销售净利率（低毛利行业）"),
            ("col202", False, 0.4, "销售毛利率")
        ],
        "CashFlow": [
            ("col107", True, 0.5, "经营现金流TTM"),
            ("col88", True, 0.3, "营业外收入TTM（政府补贴）"),
            ("col223", True, 0.2, "经营现金流/营收TTM")
        ],
        "Solvency": [
            ("col21", False, 0.5, "流动资产合计"),
            ("col54", False, 0.5, "流动负债合计")
        ],
        "Efficiency": [
            ("col172", True, 0.7, "应收周转率TTM（政府回款慢）"),
            ("col175", True, 0.3, "总资产周转率TTM")
        ],
        "Growth": [
            ("col183", False, 0.6, "营业收入增长率"),
            ("col184", False, 0.4, "净利润增长率")
        ],
        "EquityStructure": [
            ("col243", False, 0.5, "第一大股东持股"),
            ("col238", False, 0.3, "总股本"),
            ("col242", False, 0.2, "股东人数")
        ],
        "Size": [
            ("col502", True, 0.7, "营业总收入TTM"),
            ("col40", False, 0.3, "资产总计")
        ]
    },
    "综合环境治理": {
        "Profitability": [
            ("col199", False, 0.6, "销售净利率（低毛利行业）"),
            ("col202", False, 0.4, "销售毛利率")
        ],
        "CashFlow": [
            ("col107", True, 0.5, "经营现金流TTM"),
            ("col88", True, 0.3, "营业外收入TTM（政府补贴）"),
            ("col223", True, 0.2, "经营现金流/营收TTM")
        ],
        "Solvency": [
            ("col21", False, 0.5, "流动资产合计"),
            ("col54", False, 0.5, "流动负债合计")
        ],
        "Efficiency": [
            ("col172", True, 0.7, "应收周转率TTM（政府回款慢）"),
            ("col175", True, 0.3, "总资产周转率TTM")
        ],
        "Growth": [
            ("col183", False, 0.6, "营业收入增长率"),
            ("col184", False, 0.4, "净利润增长率")
        ],
        "EquityStructure": [
            ("col243", False, 0.5, "第一大股东持股"),
            ("col238", False, 0.3, "总股本"),
            ("col242", False, 0.2, "股东人数")
        ],
        "Size": [
            ("col502", True, 0.7, "营业总收入TTM"),
            ("col40", False, 0.3, "资产总计")
        ]
    },

    # ========== TMT科技 ==========
    "半导体材料": {
        "Profitability": [
            ("col202", False, 0.5, "销售毛利率"),
            ("col208", True, 0.3, "EBITDA TTM"),
            ("col199", False, 0.2, "销售净利率")
        ],
        "CashFlow": [
            ("col107", True, 0.6, "经营现金流TTM"),
            ("col228", True, 0.4, "经营现金流/净利润TTM")
        ],
        "Solvency": [
            ("capex_ratio", False, -0.4, "资本支出/折旧（负向）"),
            ("col210", False, 0.6, "资产负债率")
        ],
        "Efficiency": [
            ("col175", True, 0.7, "总资产周转率TTM"),
            ("col172", True, 0.3, "应收周转率TTM")
        ],
        "Growth": [
            ("col304", True, 0.5, "研发费用TTM（创新投入）"),
            ("col183", False, 0.3, "营业收入增长率"),
            ("col184", False, 0.2, "净利润增长率")
        ],
        "EquityStructure": [
            ("col243", False, 0.5, "第一大股东持股"),
            ("col238", False, 0.3, "总股本"),
            ("col242", False, 0.2, "股东人数")
        ],
        "Size": [
            ("col502", True, 0.7, "营业总收入TTM"),
            ("col40", False, 0.3, "资产总计")
        ]
    },
    "半导体设备": {
        "Profitability": [
            ("col202", False, 0.5, "销售毛利率"),
            ("col208", True, 0.3, "EBITDA TTM"),
            ("col199", False, 0.2, "销售净利率")
        ],
        "CashFlow": [
            ("col107", True, 0.6, "经营现金流TTM"),
            ("col228", True, 0.4, "经营现金流/净利润TTM")
        ],
        "Solvency": [
            ("capex_ratio", False, -0.4, "资本支出/折旧（负向）"),
            ("col210", False, 0.6, "资产负债率")
        ],
        "Efficiency": [
            ("col175", True, 0.7, "总资产周转率TTM"),
            ("col172", True, 0.3, "应收周转率TTM")
        ],
        "Growth": [
            ("col304", True, 0.5, "研发费用TTM（创新投入）"),
            ("col183", False, 0.3, "营业收入增长率"),
            ("col184", False, 0.2, "净利润增长率")
        ],
        "EquityStructure": [
            ("col243", False, 0.5, "第一大股东持股"),
            ("col238", False, 0.3, "总股本"),
            ("col242", False, 0.2, "股东人数")
        ],
        "Size": [
            ("col502", True, 0.7, "营业总收入TTM"),
            ("col40", False, 0.3, "资产总计")
        ]
    },
    "数字芯片设计": {
        "Profitability": [
            ("col202", False, 0.6, "销售毛利率（技术壁垒）"),
            ("col199", False, 0.4, "销售净利率")
        ],
        "CashFlow": [
            ("col107", True, 0.6, "经营现金流TTM"),
            ("col228", True, 0.4, "经营现金流/净利润TTM")
        ],
        "Solvency": [
            ("col210", False, 0.7, "资产负债率"),
            ("col8", False, 0.3, "货币资金")
        ],
        "Efficiency": [
            ("col175", True, 0.7, "总资产周转率TTM"),
            ("col172", True, 0.3, "应收周转率TTM")
        ],
        "Growth": [
            ("col304", True, 0.5, "研发费用TTM（创新投入）"),
            ("col183", False, 0.3, "营业收入增长率"),
            ("col184", False, 0.2, "净利润增长率")
        ],
        "EquityStructure": [
            ("col243", False, 0.5, "第一大股东持股"),
            ("col238", False, 0.3, "总股本"),
            ("col242", False, 0.2, "股东人数")
        ],
        "Size": [
            ("col502", True, 0.7, "营业总收入TTM"),
            ("col40", False, 0.3, "资产总计")
        ]
    },
    "模拟芯片设计": {
        "Profitability": [
            ("col202", False, 0.6, "销售毛利率（技术壁垒）"),
            ("col199", False, 0.4, "销售净利率")
        ],
        "CashFlow": [
            ("col107", True, 0.6, "经营现金流TTM"),
            ("col228", True, 0.4, "经营现金流/净利润TTM")
        ],
        "Solvency": [
            ("col210", False, 0.7, "资产负债率"),
            ("col8", False, 0.3, "货币资金")
        ],
        "Efficiency": [
            ("col175", True, 0.7, "总资产周转率TTM"),
            ("col172", True, 0.3, "应收周转率TTM")
        ],
        "Growth": [
            ("col304", True, 0.5, "研发费用TTM（创新投入）"),
            ("col183", False, 0.3, "营业收入增长率"),
            ("col184", False, 0.2, "净利润增长率")
        ],
        "EquityStructure": [
            ("col243", False, 0.5, "第一大股东持股"),
            ("col238", False, 0.3, "总股本"),
            ("col242", False, 0.2, "股东人数")
        ],
        "Size": [
            ("col502", True, 0.7, "营业总收入TTM"),
            ("col40", False, 0.3, "资产总计")
        ]
    },
    "集成电路制造": {
        "Profitability": [
            ("col202", False, 0.5, "销售毛利率"),
            ("col208", True, 0.3, "EBITDA TTM"),
            ("col199", False, 0.2, "销售净利率")
        ],
        "CashFlow": [
            ("col107", True, 0.6, "经营现金流TTM"),
            ("col228", True, 0.4, "经营现金流/净利润TTM")
        ],
        "Solvency": [
            ("capex_ratio", False, -0.4, "资本支出/折旧（负向）"),
            ("col210", False, 0.6, "资产负债率")
        ],
        "Efficiency": [
            ("col175", True, 0.7, "总资产周转率TTM"),
            ("col172", True, 0.3, "应收周转率TTM")
        ],
        "Growth": [
            ("col304", True, 0.5, "研发费用TTM（创新投入）"),
            ("col183", False, 0.3, "营业收入增长率"),
            ("col184", False, 0.2, "净利润增长率")
        ],
        "EquityStructure": [
            ("col243", False, 0.5, "第一大股东持股"),
            ("col238", False, 0.3, "总股本"),
            ("col242", False, 0.2, "股东人数")
        ],
        "Size": [
            ("col502", True, 0.7, "营业总收入TTM"),
            ("col40", False, 0.3, "资产总计")
        ]
    },
    "集成电路封测": {
        "Profitability": [
            ("col202", False, 0.6, "销售毛利率（技术壁垒）"),
            ("col199", False, 0.4, "销售净利率")
        ],
        "CashFlow": [
            ("col107", True, 0.6, "经营现金流TTM"),
            ("col228", True, 0.4, "经营现金流/净利润TTM")
        ],
        "Solvency": [
            ("col210", False, 0.7, "资产负债率"),
            ("col8", False, 0.3, "货币资金")
        ],
        "Efficiency": [
            ("col175", True, 0.7, "总资产周转率TTM"),
            ("col172", True, 0.3, "应收周转率TTM")
        ],
        "Growth": [
            ("col304", True, 0.5, "研发费用TTM（创新投入）"),
            ("col183", False, 0.3, "营业收入增长率"),
            ("col184", False, 0.2, "净利润增长率")
        ],
        "EquityStructure": [
            ("col243", False, 0.5, "第一大股东持股"),
            ("col238", False, 0.3, "总股本"),
            ("col242", False, 0.2, "股东人数")
        ],
        "Size": [
            ("col502", True, 0.7, "营业总收入TTM"),
            ("col40", False, 0.3, "资产总计")
        ]
    },
    "光伏电池组件": {
        "Profitability": [
            ("col202", False, 0.8, "销售毛利率（价格战核心）"),
            ("col199", False, 0.2, "销售净利率")
        ],
        "CashFlow": [
            ("col107", True, 0.6, "经营现金流TTM"),
            ("col228", True, 0.4, "经营现金流/净利润TTM")
        ],
        "Solvency": [
            ("col8", False, 0.4, "货币资金"),
            ("col41", False, 0.3, "短期借款"),
            ("col52", False, 0.3, "一年内到期非流动负债")
        ],
        "Efficiency": [
            ("col173", True, 0.7, "存货周转率TTM（去库存）"),
            ("col175", True, 0.3, "总资产周转率TTM")
        ],
        "Growth": [
            ("col183", False, 0.6, "营业收入增长率"),
            ("col184", False, 0.4, "净利润增长率")
        ],
        "EquityStructure": [
            ("col243", False, 0.5, "第一大股东持股"),
            ("col238", False, 0.3, "总股本"),
            ("col242", False, 0.2, "股东人数")
        ],
        "Size": [
            ("col502", True, 0.7, "营业总收入TTM"),
            ("col40", False, 0.3, "资产总计")
        ]
    },
    "硅料硅片": {
        "Profitability": [
            ("col202", False, 0.8, "销售毛利率（价格战核心）"),
            ("col199", False, 0.2, "销售净利率")
        ],
        "CashFlow": [
            ("col107", True, 0.6, "经营现金流TTM"),
            ("col228", True, 0.4, "经营现金流/净利润TTM")
        ],
        "Solvency": [
            ("col8", False, 0.4, "货币资金"),
            ("col41", False, 0.3, "短期借款"),
            ("col52", False, 0.3, "一年内到期非流动负债")
        ],
        "Efficiency": [
            ("col173", True, 0.8, "存货周转率TTM"),
            ("col175", True, 0.2, "总资产周转率TTM")
        ],
        "Growth": [
            ("col183", False, 0.6, "营业收入增长率"),
            ("col184", False, 0.4, "净利润增长率")
        ],
        "EquityStructure": [
            ("col243", False, 0.5, "第一大股东持股"),
            ("col238", False, 0.3, "总股本"),
            ("col242", False, 0.2, "股东人数")
        ],
        "Size": [
            ("col502", True, 0.7, "营业总收入TTM"),
            ("col40", False, 0.3, "资产总计")
        ]
    },
    "光伏辅材": {
        "Profitability": [
            ("col202", False, 0.8, "销售毛利率（价格战核心）"),
            ("col199", False, 0.2, "销售净利率")
        ],
        "CashFlow": [
            ("col107", True, 0.6, "经营现金流TTM"),
            ("col228", True, 0.4, "经营现金流/净利润TTM")
        ],
        "Solvency": [
            ("col8", False, 0.4, "货币资金"),
            ("col41", False, 0.3, "短期借款"),
            ("col52", False, 0.3, "一年内到期非流动负债")
        ],
        "Efficiency": [
            ("col173", True, 0.7, "存货周转率TTM（去库存）"),
            ("col175", True, 0.3, "总资产周转率TTM")
        ],
        "Growth": [
            ("col183", False, 0.6, "营业收入增长率"),
            ("col184", False, 0.4, "净利润增长率")
        ],
        "EquityStructure": [
            ("col243", False, 0.5, "第一大股东持股"),
            ("col238", False, 0.3, "总股本"),
            ("col242", False, 0.2, "股东人数")
        ],
        "Size": [
            ("col502", True, 0.7, "营业总收入TTM"),
            ("col40", False, 0.3, "资产总计")
        ]
    },
    "逆变器": {
        "Profitability": [
            ("col202", False, 0.8, "销售毛利率（价格战核心）"),
            ("col199", False, 0.2, "销售净利率")
        ],
        "CashFlow": [
            ("col107", True, 0.6, "经营现金流TTM"),
            ("col228", True, 0.4, "经营现金流/净利润TTM")
        ],
        "Solvency": [
            ("col8", False, 0.4, "货币资金"),
            ("col41", False, 0.3, "短期借款"),
            ("col52", False, 0.3, "一年内到期非流动负债")
        ],
        "Efficiency": [
            ("col173", True, 0.7, "存货周转率TTM（去库存）"),
            ("col175", True, 0.3, "总资产周转率TTM")
        ],
        "Growth": [
            ("col183", False, 0.6, "营业收入增长率"),
            ("col184", False, 0.4, "净利润增长率")
        ],
        "EquityStructure": [
            ("col243", False, 0.5, "第一大股东持股"),
            ("col238", False, 0.3, "总股本"),
            ("col242", False, 0.2, "股东人数")
        ],
        "Size": [
            ("col502", True, 0.7, "营业总收入TTM"),
            ("col40", False, 0.3, "资产总计")
        ]
    },
    "品牌消费电子": {
        "Profitability": [
            ("col202", False, 0.6, "销售毛利率（品牌溢价）"),
            ("col199", False, 0.4, "销售净利率")
        ],
        "CashFlow": [
            ("col107", True, 0.6, "经营现金流TTM"),
            ("col223", True, 0.4, "经营现金流/营收TTM")
        ],
        "Solvency": [
            ("col210", False, 0.7, "资产负债率"),
            ("col8", False, 0.3, "货币资金")
        ],
        "Efficiency": [
            ("col175", True, 0.7, "总资产周转率TTM"),
            ("col172", True, 0.3, "应收周转率TTM")
        ],
        "Growth": [
            ("col183", False, 0.5, "营业收入增长率"),
            ("col184", False, 0.5, "净利润增长率")
        ],
        "EquityStructure": [
            ("col243", False, 0.5, "第一大股东持股"),
            ("col238", False, 0.3, "总股本"),
            ("col242", False, 0.2, "股东人数")
        ],
        "Size": [
            ("col502", True, 0.7, "营业总收入TTM"),
            ("col40", False, 0.3, "资产总计")
        ]
    },

    # ========== 大消费 ==========
    "白酒Ⅱ": {
        "Profitability": [
            ("col281", False, 0.4, "加权净资产收益率"),
            ("col202", False, 0.3, "销售毛利率（>70%）"),
            ("col45", False, 0.1, "预收款项（渠道打款）"),
            ("sales_expense_ratio", False, -0.2, "销售费用率（负向）")            
        ],
        "CashFlow": [
            ("col45", False, 0.6, "预收款项（先款后货）"),
            ("col107", True, 0.3, "经营现金流TTM"),
            ("col219", False, 0.1, "每股经营性现金流")
        ],
        "Solvency": [
            ("col210", False, 0.7, "资产负债率"),
            ("col8", False, 0.3, "货币资金")
        ],
        "Efficiency": [
            ("col175", True, 0.7, "总资产周转率TTM"),
            ("col172", True, 0.3, "应收周转率TTM")
        ],
        "Growth": [
            ("col183", False, 0.6, "营业收入增长率"),
            ("col184", False, 0.4, "净利润增长率")
        ],
        "EquityStructure": [
            ("col243", False, 0.5, "第一大股东持股"),
            ("col238", False, 0.3, "总股本"),
            ("col242", False, 0.2, "股东人数")
        ],
        "Size": [
            ("col502", True, 0.7, "营业总收入TTM"),
            ("col40", False, 0.3, "资产总计")
        ]
    },
    "农林牧渔": {
        "Profitability": [
            ("col202", False, 0.7, "销售毛利率（周期位置指示）"),
            ("col31", False, 0.2, "生产性生物资产（生猪/果树）"),
            ("col17", False, 0.1, "存货（活畜/农产品）")
        ],
        "CashFlow": [
            ("col107", True, 0.7, "经营现金流TTM"),
            ("col228", True, 0.3, "经营现金流/净利润TTM")
        ],
        "Solvency": [
            ("col210", False, 0.7, "资产负债率"),
            ("col8", False, 0.3, "货币资金")
        ],
        "Efficiency": [
            ("col175", True, 0.6, "总资产周转率TTM"),
            ("col173", True, 0.4, "存货周转率TTM")
        ],
        "Growth": [
            ("col183", False, 0.6, "营业收入增长率"),
            ("col184", False, 0.4, "净利润增长率")
        ],
        "EquityStructure": [
            ("col243", False, 0.5, "第一大股东持股"),
            ("col238", False, 0.3, "总股本"),
            ("col242", False, 0.2, "股东人数")
        ],
        "Size": [
            ("col40", False, 0.6, "资产总计（含生物资产）"),
            ("col502", True, 0.4, "营业总收入TTM")
        ]
    },

    # ========== 国防军工 ==========
    "地面兵装Ⅱ": {
        "Profitability": [
            ("col199", False, 0.6, "销售净利率（成本加成定价）"),
            ("col202", False, 0.4, "销售毛利率")
        ],
        "CashFlow": [
            ("col45", False, 0.5, "预收款项（军品订单）"),
            ("col107", True, 0.5, "经营现金流TTM")
        ],
        "Solvency": [
            ("col210", False, 0.7, "资产负债率"),
            ("col8", False, 0.3, "货币资金")
        ],
        "Efficiency": [
            ("col175", True, 0.7, "总资产周转率TTM"),
            ("col172", True, 0.3, "应收周转率TTM")
        ],
        "Growth": [
            ("col183", False, 0.5, "营业收入增长率"),
            ("col184", False, 0.5, "净利润增长率")
        ],
        "EquityStructure": [
            ("col243", False, 0.5, "第一大股东持股"),
            ("col238", False, 0.3, "总股本"),
            ("col242", False, 0.2, "股东人数")
        ],
        "Size": [
            ("col40", False, 0.6, "资产总计"),
            ("col502", True, 0.4, "营业总收入TTM")
        ]
    },
    "航天装备Ⅱ": {
        "Profitability": [
            ("col199", False, 0.6, "销售净利率（成本加成定价）"),
            ("col202", False, 0.4, "销售毛利率")
        ],
        "CashFlow": [
            ("col45", False, 0.5, "预收款项（军品订单）"),
            ("col107", True, 0.5, "经营现金流TTM")
        ],
        "Solvency": [
            ("col210", False, 0.7, "资产负债率"),
            ("col8", False, 0.3, "货币资金")
        ],
        "Efficiency": [
            ("col175", True, 0.7, "总资产周转率TTM"),
            ("col172", True, 0.3, "应收周转率TTM")
        ],
        "Growth": [
            ("col183", False, 0.5, "营业收入增长率"),
            ("col184", False, 0.5, "净利润增长率")
        ],
        "EquityStructure": [
            ("col243", False, 0.5, "第一大股东持股"),
            ("col238", False, 0.3, "总股本"),
            ("col242", False, 0.2, "股东人数")
        ],
        "Size": [
            ("col40", False, 0.6, "资产总计"),
            ("col502", True, 0.4, "营业总收入TTM")
        ]
    },
    "航海装备Ⅱ": {
        "Profitability": [
            ("col199", False, 0.6, "销售净利率（成本加成定价）"),
            ("col202", False, 0.4, "销售毛利率")
        ],
        "CashFlow": [
            ("col45", False, 0.5, "预收款项（军品订单）"),
            ("col107", True, 0.5, "经营现金流TTM")
        ],
        "Solvency": [
            ("col210", False, 0.7, "资产负债率"),
            ("col8", False, 0.3, "货币资金")
        ],
        "Efficiency": [
            ("col175", True, 0.7, "总资产周转率TTM"),
            ("col172", True, 0.3, "应收周转率TTM")
        ],
        "Growth": [
            ("col183", False, 0.5, "营业收入增长率"),
            ("col184", False, 0.5, "净利润增长率")
        ],
        "EquityStructure": [
            ("col243", False, 0.5, "第一大股东持股"),
            ("col238", False, 0.3, "总股本"),
            ("col242", False, 0.2, "股东人数")
        ],
        "Size": [
            ("col40", False, 0.6, "资产总计"),
            ("col502", True, 0.4, "营业总收入TTM")
        ]
    },
    "航空装备Ⅱ": {
        "Profitability": [
            ("col199", False, 0.6, "销售净利率（成本加成定价）"),
            ("col202", False, 0.4, "销售毛利率")
        ],
        "CashFlow": [
            ("col45", False, 0.5, "预收款项（军品订单）"),
            ("col107", True, 0.5, "经营现金流TTM")
        ],
        "Solvency": [
            ("col210", False, 0.7, "资产负债率"),
            ("col8", False, 0.3, "货币资金")
        ],
        "Efficiency": [
            ("col175", True, 0.7, "总资产周转率TTM"),
            ("col172", True, 0.3, "应收周转率TTM")
        ],
        "Growth": [
            ("col183", False, 0.5, "营业收入增长率"),
            ("col184", False, 0.5, "净利润增长率")
        ],
        "EquityStructure": [
            ("col243", False, 0.5, "第一大股东持股"),
            ("col238", False, 0.3, "总股本"),
            ("col242", False, 0.2, "股东人数")
        ],
        "Size": [
            ("col40", False, 0.6, "资产总计"),
            ("col502", True, 0.4, "营业总收入TTM")
        ]
    },
    "军工电子Ⅲ": {
        "Profitability": [
            ("col199", False, 0.6, "销售净利率（成本加成定价）"),
            ("col202", False, 0.4, "销售毛利率")
        ],
        "CashFlow": [
            ("col45", False, 0.5, "预收款项（军品订单）"),
            ("col107", True, 0.5, "经营现金流TTM")
        ],
        "Solvency": [
            ("col210", False, 0.7, "资产负债率"),
            ("col8", False, 0.3, "货币资金")
        ],
        "Efficiency": [
            ("col175", True, 0.7, "总资产周转率TTM"),
            ("col172", True, 0.3, "应收周转率TTM")
        ],
        "Growth": [
            ("col183", False, 0.5, "营业收入增长率"),
            ("col184", False, 0.5, "净利润增长率")
        ],
        "EquityStructure": [
            ("col243", False, 0.5, "第一大股东持股"),
            ("col238", False, 0.3, "总股本"),
            ("col242", False, 0.2, "股东人数")
        ],
        "Size": [
            ("col40", False, 0.6, "资产总计"),
            ("col502", True, 0.4, "营业总收入TTM")
        ]
    },

    # ========== 工业制造 ==========
    "乘用车": {
        "Profitability": [
            ("col199", False, 0.7, "销售净利率（价格战）"),
            ("col202", False, 0.3, "销售毛利率")
        ],
        "CashFlow": [
            ("col107", True, 0.6, "经营现金流TTM"),
            ("col223", True, 0.4, "经营现金流/营收TTM")
        ],
        "Solvency": [
            ("col8", False, 0.5, "货币资金"),
            ("col41", False, 0.3, "短期借款"),
            ("col52", False, 0.2, "一年内到期非流动负债")
        ],
        "Efficiency": [
            ("col173", True, 0.6, "存货周转率TTM（去库存）"),
            ("col172", True, 0.4, "应收周转率TTM（经销商回款）")
        ],
        "Growth": [
            ("col183", False, 0.6, "营业收入增长率"),
            ("col184", False, 0.4, "净利润增长率")
        ],
        "EquityStructure": [
            ("col243", False, 0.5, "第一大股东持股"),
            ("col238", False, 0.3, "总股本"),
            ("col242", False, 0.2, "股东人数")
        ],
        "Size": [
            ("col502", True, 0.7, "营业总收入TTM"),
            ("col40", False, 0.3, "资产总计")
        ]
    },
    "机器人": {
        "Profitability": [
            ("col202", False, 0.6, "销售毛利率"),
            ("col199", False, 0.4, "销售净利率")
        ],
        "CashFlow": [
            ("col107", True, 0.7, "经营现金流TTM"),
            ("col228", True, 0.3, "经营现金流/净利润TTM")
        ],
        "Solvency": [
            ("col210", False, 0.7, "资产负债率"),
            ("col8", False, 0.3, "货币资金")
        ],
        "Efficiency": [
            ("col175", True, 0.7, "总资产周转率TTM"),
            ("col172", True, 0.3, "应收周转率TTM")
        ],
        "Growth": [
            ("col304", True, 0.6, "研发费用TTM（技术投入）"),
            ("col183", False, 0.3, "营业收入增长率"),
            ("col184", False, 0.1, "净利润增长率")
        ],
        "EquityStructure": [
            ("col243", False, 0.5, "第一大股东持股"),
            ("col238", False, 0.3, "总股本"),
            ("col242", False, 0.2, "股东人数")
        ],
        "Size": [
            ("col502", True, 0.7, "营业总收入TTM"),
            ("col40", False, 0.3, "资产总计")
        ]
    },
    "电池": {
        "Profitability": [
            ("col202", False, 0.6, "销售毛利率"),
            ("col199", False, 0.4, "销售净利率")
        ],
        "CashFlow": [
            ("col107", True, 0.7, "经营现金流TTM"),
            ("col228", True, 0.3, "经营现金流/净利润TTM")
        ],
        "Solvency": [
            ("col210", False, 0.7, "资产负债率"),
            ("col8", False, 0.3, "货币资金")
        ],
        "Efficiency": [
            ("col172", True, 0.6, "应收周转率TTM（绑定大客户）"),
            ("col177", True, 0.3, "应收周转天数TTM"),
            ("col11", False, 0.1, "应收账款（绝对值）")
        ],
        "Growth": [
            ("col183", False, 0.6, "营业收入增长率"),
            ("col184", False, 0.4, "净利润增长率")
        ],
        "EquityStructure": [
            ("col243", False, 0.5, "第一大股东持股"),
            ("col238", False, 0.3, "总股本"),
            ("col242", False, 0.2, "股东人数")
        ],
        "Size": [
            ("col502", True, 0.7, "营业总收入TTM"),
            ("col40", False, 0.3, "资产总计")
        ]
    }
}

# %% [markdown]
# *  2.2.5 维度内可调细分行业指标权重

# %%


# %% [markdown]
# * 2.3 权重主函数
# * 2.3.1 维度权重主函数

# %%
def get_final_weights_v9(industry: str) -> Dict[str, float]:
    """V9版：宏观+政策+产业链三重动态权重"""
    # 1. 基础权重 + 子类微调
    super_ind, sub_ind = industry_to_levels[industry]
    weights = SUPER_INDUSTRY_WEIGHTS[super_ind].copy()
    if sub_ind in SUB_INDUSTRY_WEIGHTS:
        weights.update(SUB_INDUSTRY_WEIGHTS[sub_ind])
    
    # 2. 宏观因子调整
    for macro_name, value in LATEST_MACRO.items():
        if macro_name in MACRO_SENSITIVITY:
            baseline = MACRO_BASELINES.get(macro_name, 0)
            deviation = (value - baseline) / (abs(baseline) + 1e-8)
            sensitivity = MACRO_SENSITIVITY[macro_name]
            for dim, sens in sensitivity.items():
                if dim in weights:
                    adjustment = sens * deviation * 0.02
                    weights[dim] += adjustment
    
    # 3. 政策阶段调整
    policy_theme = INDUSTRY_POLICY_MAPPING.get(industry, "default")
    current_phase = CURRENT_POLICY_PHASES.get(policy_theme)
    if current_phase and policy_theme in POLICY_PHASES:
        phase_adjust = POLICY_PHASES[policy_theme][current_phase]
        for dim, adj in phase_adjust.items():
            if dim in weights:
                weights[dim] += adj
    
    # 4. 产业链协同调整（示例：光伏硅料跌价）
    if industry == "光伏电池组件":
        # 假设当前事件：硅料价格下跌
        weights["Profitability"] += 0.04
        weights["CashFlow"] += 0.03
    elif industry == "硅料硅片":
        weights["Profitability"] -= 0.05
        weights["Solvency"] += 0.02
    
    # 5. 归一化 & 边界检查
    total = sum(weights.values())
    if abs(total - 1.0) > 1e-6:
        weights = {k: max(0.01, min(0.9, v / total)) for k, v in weights.items()}
    
    # 重新归一化
    total = sum(weights.values())
    return {k: v / total for k, v in weights.items()}

# %%
event_detector = LinkageEventDetector()

def get_final_weights_v9_enhanced(industry: str, current_prices: Dict[str, float] = None) -> Dict[str, float]:
    """V9增强版权重计算（含产业链协同）"""
    # 1. 基础权重（宏观+政策）
    weights = get_final_weights_v9(industry)
    
    # 2. 产业链协同调整
    if current_prices is not None:
        detector = LinkageEventDetector()
        events = detector.detect_events(current_prices)
        linkage_adj = calculate_linkage_adjustment(industry, events)
        
        for dim, adj in linkage_adj.items():
            if dim in weights:
                weights[dim] += adj
    
    # 3. 归一化
    total = sum(weights.values())
    if abs(total - 1.0) > 1e-6:
        weights = {k: max(0.01, min(0.9, v / total)) for k, v in weights.items()}
        total = sum(weights.values())
        weights = {k: v / total for k, v in weights.items()}
    
    return weights

# %% [markdown]
# * 2.3.2 维度内指标权重主函数

# %%
def get_indicators(industry: str) -> Dict[str, List[Tuple[str, bool, float, str]]]:
    # 维度内个指标权重
    # 1. 全量覆盖行业优先
    if industry in FULL_OVERRIDE_INDUSTRIES:
        return FULL_OVERRIDE_INDUSTRIES[industry]

    # 2. 获取所属二级子类
    if industry not in industry_to_levels:
        raise ValueError(f"Unknown industry: {industry}")
    super_ind, sub_ind = industry_to_levels[industry]

    # 3. 合并：默认模板 + 二级子类覆盖
    base = dict(DEFAULT_INDICATORS)
    if sub_ind in DIMENSION_INDICATORS_BASE:
        for dim, cols in DIMENSION_INDICATORS_BASE[sub_ind].items():
            base[dim] = cols
    return base

# %%
# # 产业链事件类型与影响规则
# LINKAGE_EVENT_RULES = {
#     "原材料价格变动": {
#         "上游行业": {
#             "Profitability": lambda strength, magnitude: 0.05 * strength * magnitude,
#             "Growth": lambda strength, magnitude: 0.02 * strength * magnitude
#         },
#         "下游行业": {
#             "Profitability": lambda strength, magnitude: -0.04 * strength * magnitude,
#             "CashFlow": lambda strength, magnitude: -0.03 * strength * magnitude
#         }
#     },
#     "技术突破": {
#         "技术方": {
#             "Growth": lambda strength, magnitude: 0.06 * strength * magnitude,
#             "R&D_efficiency": lambda strength, magnitude: 0.04 * strength * magnitude
#         },
#         "应用方": {
#             "Efficiency": lambda strength, magnitude: 0.03 * strength * magnitude,
#             "Cost": lambda strength, magnitude: -0.02 * strength * magnitude
#         }
#     },
#     "产能扩张": {
#         "扩张方": {
#             "Solvency": lambda strength, magnitude: -0.03 * strength * magnitude,
#             "Growth": lambda strength, magnitude: 0.04 * strength * magnitude
#         },
#         "配套方": {
#             "Growth": lambda strength, magnitude: 0.03 * strength * magnitude
#         }
#     },
#     "政策扶持": {
#         "受益行业": {
#             "CashFlow": lambda strength, magnitude: 0.03 * strength * magnitude,
#             "Growth": lambda strength, magnitude: 0.04 * strength * magnitude
#         }
#     }
# }

# %% [markdown]
# * 2.3.3 维度内指标权重函数

# %%
def get_indicators(industry: str) -> Dict[str, List[Tuple[str, bool, float, str]]]:
    # 维度内个指标权重
    # 1. 全量覆盖行业优先
    if industry in FULL_OVERRIDE_INDUSTRIES:
        return FULL_OVERRIDE_INDUSTRIES[industry]

    # 2. 获取所属二级子类
    if industry not in industry_to_levels:
        raise ValueError(f"Unknown industry: {industry}")
    super_ind, sub_ind = industry_to_levels[industry]

    # 3. 合并：默认模板 + 二级子类覆盖
    base = dict(DEFAULT_INDICATORS)
    if sub_ind in DIMENSION_INDICATORS_BASE:
        for dim, cols in DIMENSION_INDICATORS_BASE[sub_ind].items():
            base[dim] = cols
    return base

# %% [markdown]
# ##### 三、 工具函数（含行业分位数标准化）

# %%
def calculate_industry_ratios(df: pd.DataFrame) -> pd.DataFrame:
    """计算V8新增的行业特有比率"""
    df = df.copy()
    
    # 1. 银行：不良率近似
    if 'col517' in df.columns and 'col404' in df.columns:
        total_loans = df['col404'] + df.get('col411', 0)
        df['npl_approx'] = df['col517'] / (total_loans + 1e-8)
    else:
        df['npl_approx'] = np.nan
        
    # 2. 净息差（同v7）
    if 'col506' in df.columns and 'col509' in df.columns:
        earning_assets = df['col40'] - df['col8']
        df['nim_approx'] = (df['col506'] - df['col509']) / (earning_assets + 1e-8)
    else:
        df['nim_approx'] = np.nan
        
    # 3. 房企：预收/营收
    if 'col45' in df.columns and 'col74' in df.columns:
        df['pre_sales_ratio'] = df['col45'] / (df['col74'] + 1e-8)
    else:
        df['pre_sales_ratio'] = np.nan
        
    # 4. 应付账款周转率
    if 'col75' in df.columns and 'col295' in df.columns:
        df['payables_turnover'] = df['col75'] / (df['col295'] + 1e-8)
    else:
        df['payables_turnover'] = np.nan
        
    # 5. 资本支出比率
    if 'col224' in df.columns:
        df['capex_ratio'] = df['col224']
    else:
        df['capex_ratio'] = np.nan
        
    # 6. 销售费用率
    if 'col77' in df.columns and 'col74' in df.columns:
        df['sales_expense_ratio'] = df['col77'] / (df['col74'] + 1e-8)
    else:
        df['sales_expense_ratio'] = np.nan
        
    # 7. 盈利质量
    if 'col107' in df.columns and 'col95' in df.columns:
        df['profit_quality'] = df['col107'] / (df['col95'] + 1e-8)
    else:
        df['profit_quality'] = np.nan
        
    # 8. 信用减值损失率
    if 'col517' in df.columns and 'col74' in df.columns:
        df['credit_impairment_ratio'] = df['col517'] / (df['col74'] + 1e-8)
    else:
        df['credit_impairment_ratio'] = np.nan
    # 9. 房企/建筑：现金短债比
    df['cash_short_debt_ratio'] = df['col8'] / (df['col41'] + df['col52'] + 1e-8)
        
    # 10. 通用：经营现金流/净利润
    df['ocf_to_netprofit'] = df['col107'] / (df['col95'] + 1e-8)
    
    # 11. 存货周转天数（补充）
    if 'col173' in df.columns:
        df['inventory_days'] = 365 / (df['col173'] + 1e-8)
    else:
        df['inventory_days'] = np.nan        

        
    return df

def parse_report_type(report_date: str) -> str:
    """解析财报类型"""
    if report_date.endswith('1231'):
        return 'annual'
    elif report_date.endswith('0630'):
        return 'half_year'
    elif report_date.endswith('0930'):
        return 'q3'
    elif report_date.endswith('0331'):
        return 'q1'
    else:
        raise ValueError(f"Unknown report date format: {report_date}")

def convert_cumulative_to_single(df: pd.DataFrame) -> pd.DataFrame:
    """
    将累计报表转换为单季值（支持年报/半年报/季报混合）
    修复：确保每种财报类型只取最新一条，避免维度不匹配
    """
    df = df.copy()
    df['report_date'] = df['report_date'].astype(str)
    # 解析财报类型
    def parse_report_type(report_date):
        s = str(report_date)
        if s.endswith('1231'):
            return 'annual'
        elif s.endswith('0630'):
            return 'half_year'
        elif s.endswith('0930'):
            return 'q3'
        elif s.endswith('0331'):
            return 'q1'
        else:
            return 'unknown'
    
    df['report_type'] = df['report_date'].apply(parse_report_type)
    df = df[df['report_type'] != 'unknown'].copy()
    
    flow_cols = ['col88', 'col77','col75','col136','col137','col208','col74','col95','col107','col206','col207','col304','col565']
    
    all_single_rows = []
    
    for stock, group in df.groupby('stock_code'):
        # 按年份分组
        group['year'] = group['report_date'].astype(str).str[:4]
        for year, year_group in group.groupby('year'):
            # 对每种财报类型，只保留最新的一条（防止重复）
            year_group = year_group.sort_values('report_date')
            deduped = year_group.drop_duplicates(subset=['report_type'], keep='last')
            
            # 转为字典：type -> values
            type_to_vals = {}
            for _, row in deduped.iterrows():
                vals = np.array([row[col] if col in row and pd.notna(row[col]) else np.nan for col in flow_cols])
                type_to_vals[row['report_type']] = vals
            
            # 初始化季度值
            q1 = q2 = q3 = q4 = np.full(len(flow_cols), np.nan)
            
            has_q1 = 'q1' in type_to_vals
            has_h1 = 'half_year' in type_to_vals
            has_q3 = 'q3' in type_to_vals
            has_annual = 'annual' in type_to_vals
            
            val_q1 = type_to_vals.get('q1', np.full(len(flow_cols), np.nan))
            val_h1 = type_to_vals.get('half_year', np.full(len(flow_cols), np.nan))
            val_q3 = type_to_vals.get('q3', np.full(len(flow_cols), np.nan))
            val_annual = type_to_vals.get('annual', np.full(len(flow_cols), np.nan))
            
            # 计算单季值
            if has_q1:
                q1 = val_q1
            if has_h1 and has_q1:
                q2 = val_h1 - val_q1
            elif has_h1:
                q2 = val_h1 / 2  # 无Q1时平分
            if has_q3 and has_h1:
                q3 = val_q3 - val_h1
            elif has_q3 and has_q1:
                q3 = (val_q3 - val_q1) / 2
            if has_annual and has_q3:
                q4 = val_annual - val_q3
            elif has_annual and has_h1:
                q4 = (val_annual - val_h1) / 2
            elif has_annual:
                q4 = val_annual / 4  # 极端情况：只有年报
            
            # 保存结果
            for q, date_suffix in [(q1, '0331'), (q2, '0630'), (q3, '0930'), (q4, '1231')]:
                if not np.all(np.isnan(q)):
                    row_data = {
                        'stock_code': stock,
                        'report_date': f"{year}{date_suffix}",
                        'is_imputed': not (
                            (date_suffix == '0331' and has_q1) or
                            (date_suffix == '0630' and has_h1 and has_q1) or
                            (date_suffix == '0930' and has_q3 and has_h1) or
                            (date_suffix == '1231' and has_annual and has_q3)
                        )
                    }
                    for i, col in enumerate(flow_cols):
                        row_data[f"{col}_single"] = q[i]
                    all_single_rows.append(row_data)
    
    # 合并回原数据
    if not all_single_rows:
        # 若无有效数据，返回原df并添加空列
        for col in flow_cols:
            df[f"{col}_single"] = np.nan
        return df
        
    single_df = pd.DataFrame(all_single_rows)
    df = df.merge(single_df, on=['stock_code', 'report_date'], how='left')
    return df

def calculate_ttm_from_single(df: pd.DataFrame, col_name: str) -> pd.Series:
    """
    从单季值计算TTM（向量化实现）
    
    Args:
        df: DataFrame with columns ['stock_code', 'report_date', f"{col_name}_single"]
        col_name: e.g., 'col74'
    
    Returns:
        pd.Series: TTM values with same index as df
    """
    single_col = f"{col_name}_single"
    if single_col not in df.columns:
        return pd.Series(np.nan, index=df.index)
    
    # 确保按股票和日期排序
    df_sorted = df[['stock_code', 'report_date', single_col]].copy()
    df_sorted = df_sorted.sort_values(['stock_code', 'report_date']).reset_index(drop=True)
    
    # 按股票分组，计算滚动4期和（即TTM）
    ttm_series = (
        df_sorted.groupby('stock_code')[single_col]
        .rolling(window=4, min_periods=1)
        .sum()
        .reset_index(level=0, drop=True)  # 去掉groupby的索引层级
    )
    
    # 将结果对齐回原df的索引顺序
    df_sorted['ttm_temp'] = ttm_series.values
    result = df_sorted.set_index(['stock_code', 'report_date'])['ttm_temp']
    
    # 重建原始索引顺序
    original_index = df.set_index(['stock_code', 'report_date']).index
    aligned_ttm = result.reindex(original_index).values
    
    return pd.Series(aligned_ttm, index=df.index)


def winsorize_series(series: pd.Series, limits=(0.01, 0.99)) -> pd.Series:
    """Winsorize 处理（1%–99%）"""
    series = series.copy()
    series = series.replace([np.inf, -np.inf], np.nan)
    valid = series.notna()
    if valid.sum() == 0:
        return series
    lower, upper = np.nanquantile(series[valid], limits)
    series[valid] = np.clip(series[valid], lower, upper)
    return series

def calculate_cagr(series: pd.Series, periods: int = 3) -> float:
    """计算复合年均增长率（CAGR）"""
    if len(series) < 2:
        return np.nan
    start, end = series.iloc[0], series.iloc[-1]
    if start <= 0 or end <= 0:
        return np.nan
    years = min(periods, len(series) - 1)
    return (end / start) ** (1 / years) - 1 if years > 0 else np.nan

def normalize_by_industry(series: pd.Series, industry_series: pd.Series, 
                         winsorize_first: bool = False) -> pd.Series:
    """
    按细分行业分位数标准化（0-1）
    可选先在行业内Winsorize
    """
    result = pd.Series(0.5, index=series.index)
    for industry in industry_series.unique():
        mask = (industry_series == industry)
        vals = series[mask].copy()
        if winsorize_first:
            vals = winsorize_series(vals, limits=(0.01, 0.99))
        # 行业分位数（0-1）
        ranks = vals.rank(pct=True, method='min')
        result[mask] = ranks.fillna(0.5)
    return result

# %% [markdown]
# ##### 四、 评分引擎升级（支持趋势 + Winsorize）

# %%
class FinancialScoringEngine:
    def __init__(self, df: pd.DataFrame):
        self.df = df.copy()
        self._validate_and_preprocess()
        
    def _validate_and_preprocess(self):
        required = ['stock_code', 'industry', 'report_date']
        assert all(col in self.df.columns for col in required), "缺少必要列"
        assert self.df['industry'].isin(industry_to_levels.keys()).all(), "存在未定义行业"
        self.df['report_date'] = pd.to_datetime(self.df['report_date'])
        self.df = self.df.sort_values(['stock_code', 'report_date'])
        
        # # 确保包含64个核心字段（缺失则置NaN）
        # for col in USED_COLS:
        #     if col not in self.df.columns:
        #         self.df[col] = np.nan
       
        # 1. 累计转单季
        self.df = convert_cumulative_to_single(self.df)
        
        # 2. 计算TTM（从单季值）
        ttm_cols = ['col88', 'col77','col75','col136','col137','col208','col74','col95','col107','col206','col207','col304','col565']
        for col in ttm_cols:
            if f"{col}_single" in self.df.columns:
                self.df[f"{col}_ttm"] = calculate_ttm_from_single(self.df, col)
        
        # 3. 计算行业特有比率
        self.df = calculate_industry_ratios(self.df)
        
        self.df['subclass'] = self.df['industry'].map(lambda x: industry_to_levels[x][1])
    
    def _calculate_raw_score(self, row: pd.Series) -> pd.Series:
        industry = row['industry']
        indicators = get_indicators(industry)
        scores = {}
        for dim in DIMENSION_NAMES:
            cols = indicators.get(dim, [])
            weighted_sum = 0.0
            total_weight = 0.0
            for col, is_ttm, weight, _ in cols:
                if col.startswith('col') and col not in row.index:
                    continue
                if col not in row.index:  # 如 nim_approx, cash_short_debt_ratio
                    continue
                val = row[f"{col}_ttm"] if is_ttm and f"{col}_ttm" in row.index else row[col]
                if pd.notna(val):
                    weighted_sum += val * weight
                    total_weight += weight
            scores[dim] = weighted_sum / total_weight if total_weight > 0 else np.nan
        return pd.Series(scores)
    
    def _calculate_trend_score(self, stock_df: pd.DataFrame) -> float:
        """计算3年财务健康度趋势分（0-1）"""
        if len(stock_df) < 3:
            return 0.5
        
        # 选取关键指标趋势
        metrics = []
        # 偿债能力趋势（越高越好）
        if 'cash_short_debt_ratio' in stock_df.columns:
            cagr_solvency = calculate_cagr(stock_df['cash_short_debt_ratio'].dropna())
            metrics.append(cagr_solvency if pd.notna(cagr_solvency) else 0)
        else:
            cagr_solvency = calculate_cagr(stock_df['col210'].dropna())  # 资产负债率越低越好
            metrics.append(-cagr_solvency if pd.notna(cagr_solvency) else 0)
        
        # 盈利能力趋势
        cagr_profit = calculate_cagr(stock_df['col202'].dropna())
        metrics.append(cagr_profit if pd.notna(cagr_profit) else 0)
        
        # 现金流趋势
        cagr_cash = calculate_cagr(stock_df['col107'].dropna())
        metrics.append(cagr_cash if pd.notna(cagr_cash) else 0)
        
        avg_trend = np.nanmean(metrics)
        # 转为0-1分（-20% → 0, +20% → 1）
        trend_score = np.clip((avg_trend + 0.2) / 0.4, 0, 1)
        return trend_score
    
    def run(self) -> pd.DataFrame:
        # 获取最新报告期
        latest = self.df.groupby('stock_code').tail(1).reset_index(drop=True)
        
        # 计算原始维度分
        raw_scores = []
        for _, row in latest.iterrows():
            scores = self._calculate_raw_score(row)
            record = scores.to_dict()
            record.update({
                'stock_code': row['stock_code'],
                'industry': row['industry'],
                'subclass': row['subclass'],
                # 'StockName': row['StockName']
            })
            raw_scores.append(record)
            
        result = pd.DataFrame(raw_scores)
        if result.empty:
            return pd.DataFrame()
   
       # 核心升级：行业分位数标准化
        for dim in DIMENSION_NAMES:
            if dim == "Growth":
                # 成长性：先Winsorize + 行业分位数
                result[f"{dim}_norm"] = normalize_by_industry(
                    result[dim], result['industry'], winsorize_first=True
                )
            else:
                # 其他维度：直接行业分位数
                result[f"{dim}_norm"] = normalize_by_industry(
                    result[dim], result['industry'], winsorize_first=False
                )
        
        # 加权打分
        final_rows = []
        for subclass, sub_df in result.groupby('subclass'):
            sub_df = sub_df.copy()
            weights = get_final_weights_v9_enhanced(sub_df['industry'].iloc[0])
            for dim in DIMENSION_NAMES:
                sub_df[f"{dim}_weighted"] = sub_df[f"{dim}_norm"] * weights[dim]
            sub_df['total_score'] = sub_df[[f"{d}_weighted" for d in DIMENSION_NAMES]].sum(axis=1)
            final_rows.append(sub_df)            
            
        scores_df = pd.concat(final_rows, ignore_index=True)
        
        # 计算趋势分并融合
        trend_scores = []
        for stock, group in self.df.groupby('stock_code'):
            trend = self._calculate_trend_score(group)
            trend_scores.append({'stock_code': stock, 'trend_score': trend})
            
        trend_df = pd.DataFrame(trend_scores)
        final_result = scores_df.merge(trend_df, on='stock_code', how='left')
        
        # 最终得分 = 基础分 * 0.8 + 趋势分 * 0.2
        final_result['final_score'] = (
            final_result['total_score'] * 0.8 + 
            final_result['trend_score'] * 0.2
        )
        
        return final_result

# %% [markdown]
# #### 五、 数据预处理

# %% [markdown]
# * 5.1 核心字段扩充到69个

# %%
USED_COLS = [
    'col8',    # 货币资金
    'col9',    # 交易性金融资产
    'col11',   # 应收账款
    'col17',   # 存货
    'col21',   # 流动资产合计
    'col31',   # 生产性生物资产
    'col40',   # 资产总计
    'col41',   # 短期借款
    'col45',   # 预收款项
    'col52',   # 一年内到期的非流动负债
    'col54',   # 流动负债合计
    'col63',   # 负债合计
    'col68',   # 未分配利润 【新增】
    'col72',   # 所有者权益（或股东权益）合计
    'col74',   # 营业收入
    'col75',   # 营业成本
    'col77',   # 销售费用 【新增】
    'col83',   # 投资收益（券商自营业务）
    'col88',   # 营业外收入（环保企业政府补贴）
    'col95',   # 净利润
    'col107',  # 经营活动产生的现金流量净额
    'col133',  # 期末现金及现金等价物余额
    'col136',  # 固定资产折旧、油气资产折耗、生产性生物资产折旧 【新增】
    'col137',  # 无形资产摊销 【新增】
    'col172',  # 应收帐款周转率(非金融类指标)
    'col173',  # 存货周转率(非金融类指标)
    'col175',  # 总资产周转率(非金融类指标)
    'col177',  # 应收帐款周转天数(非金融类指标)
    'col179',  # 流动资产周转率(非金融类指标)
    'col183',  # 营业收入增长率(%)
    'col184',  # 净利润增长率(%)
    'col185',  # 净资产增长率(%)
    'col187',  # 总资产增长率(%)
    'col193',  # 成本费用利润率(%) 【新增】
    'col194',  # 营业利润率(非金融类指标) 【新增】
    'col197',  # 净资产收益率
    'col199',  # 销售净利率(%)
    'col201',  # 净利润率(非金融类指标) 【新增】
    'col202',  # 销售毛利率(%)(非金融类指标)
    'col203',  # 三费比重(非金融类指标) 【新增】
    'col206',  # 扣除非经常性损益后的净利润
    'col207',  # 息税前利润(EBIT)
    'col208',  # 息税折旧摊销前利润(EBITDA) 【新增】
    'col209',  # EBITDA/营业总收入(%)(非金融类指标) 【新增】
    'col210',  # 资产负债率(%)
    'col213',  # 存货比率(非金融类指标)
    'col219',  # 每股经营性现金流
    'col223',  # 经营活动产生的现金流量净额/营业收入
    'col224',  # 资本支出/折旧和摊销 【新增】
    'col228',  # 经营活动现金净流量与净利润比率
    'col229',  # 全部资产现金回收率 【新增】
    'col238',  # 总股本
    'col242',  # 股东人数(户)
    'col243',  # 第一大股东的持股数量
    'col268',  # 一般风险准备(金融类) 【新增】
    'col281',  # 加权净资产收益率(每股指标)
    'col294',  # 每股净资产（业绩快报） 【新增】
    'col295',  # 应付票据及应付账款 【新增】
    'col296',  # 应收票据及应收账款 【新增】
    'col304',  # 研发费用
    'col305',  # 利息费用(财务费用)
    'col401',  # 专项储备(万元) 【新增】
    'col404',  # 发放贷款及垫款(万元) 【新增】
    'col411',  # 发放贷款及垫款(万元)(非流动资产科目) 【新增】
    'col419',  # 保险合同准备金(万元)
    # 'col502',  # 营业总收入(万元) 与 col74 重复，保留 col74
    'col506',  # 利息收入(万元)
    'col509',  # 利息支出(万元)
    'col517',  # 信用减值损失(万元) 【新增】
    'col565'   # 收到原保险合同保费取得的现金(万元)
]

# %%
len(USED_COLS)

# %% [markdown]
# * 5.2 近3年财报合成
#     * 自动生成报告期[20230331 - 20251231]

# %%
report_dates = []
for year in range(2023, 2026):
    report_dates.extend([
        f"{year}0331", f"{year}0630", f"{year}0930", f"{year}1231"
    ])

# %%
dfFSRAW = pd.DataFrame()
for code in tqdm(report_dates[:-1]):
    dfFS_tmp = pd.read_sql(f"gpcw{code}", engF)
    dfFSRAW = pd.concat([dfFSRAW, dfFS_tmp], ignore_index=True)


# %%
dfFS = dfFSRAW[['code','report_date'] + USED_COLS].copy()

# %% [markdown]
# * 5.2 映射'industry', 生成合并集

# %%
mapping_dfs = []
for i in range(3):
    for j in swIC[i][1]:
        mask = StockIC[swIC[i][0][0]] == j
        temp_df = StockIC[mask][['StockCode', 'StockName']].copy()
        temp_df['ICLevel'] = swIC[i][0][0]
        temp_df['industry'] = j
        mapping_dfs.append(temp_df)

# 合并所有映射
full_mapping = pd.concat(mapping_dfs, ignore_index=True)

# 一次性映射
dfFS = dfFS.merge(
    full_mapping[['StockCode', 'StockName', 'ICLevel', 'industry']],
    left_on='code', 
    right_on='StockCode', 
    how='left'
)

# %% [markdown]
# * 5.3 数据处理
#   * 'code'列改名
#   * 有（万元）的列转成（元）
# 

# %%
dfFS.rename(columns={'code': 'stock_code'}, inplace=True)
# 1. 万元 → 元 转换
WANYUAN_COLS = [
    'col401', 'col404', 'col411', 'col419',
    'col506', 'col509', 'col517', 'col565'
]

for col in WANYUAN_COLS:
    if col in dfFS.columns:
        # 转换为元（万元 × 10,000）
        dfFS[col] = dfFS[col] * 10000
        # 处理异常值（如负的信用减值损失）


# %% [markdown]
# * 5.4 回存数据库

# %%
dfFS.to_sql('dfFS', engF,if_exists='replace', index=False)

# %% [markdown]
# ===================== 数据预处理 END

# %% [markdown]
# ##### 六、 评分

# %%
dfFS = pd.read_sql('dfFS', engF)

# %%
engine = FinancialScoringEngine(dfFS.dropna(subset=['industry']))
scores = engine.run()

print("✅ 评分完成！")

# %%
df_final = scores.merge(StockIC[['StockCode', 'StockName']],left_on='stock_code',right_on='StockCode', how='left')
df_final['rank_in_industry'] = df_final.groupby('industry')['total_score'].rank(ascending=False, method='min')

# %% [markdown]
# ##### 七、可视化模块
# * 7.1 一级行业

# %%
def visualize_financial_scores(scores_df: pd.DataFrame, industry_hierarchy: dict):
    """
    全面可视化财务评分结果（V2 - 增强版）
    
    Args:
        scores_df: 评分引擎输出结果，需包含：
            - stock_code, industry, subclass
            - Profitability_norm, CashFlow_norm, ..., Size_norm
            - final_score, trend_score
        industry_hierarchy: 行业分类字典
    """
    
    # 构建一级行业映射
    industry_to_super = {}
    for super_ind, sub_dict in industry_hierarchy.items():
        for sub_ind, inds in sub_dict.items():
            for ind in inds:
                industry_to_super[ind] = super_ind
    scores_df['super_industry'] = scores_df['industry'].map(industry_to_super)
    
    # 确保数值列
    score_cols = [f"{dim}_norm" for dim in 
                  ["Profitability", "CashFlow", "Solvency", "Efficiency", "Growth", "EquityStructure", "Size"]]
    for col in score_cols + ['final_score', 'trend_score']:
        scores_df[col] = pd.to_numeric(scores_df[col], errors='coerce')
    
    # 过滤有效数据
    valid_df = scores_df.dropna(subset=['final_score']).copy()

    all_superclasses = sorted(valid_df['super_industry'].unique())
    n_superclasses = len(all_superclasses)
    
    # ==================== 🔥 新增：一级行业个股数量统计 ====================
    industry_count = valid_df.groupby('super_industry').size().reset_index(name='count')
    industry_count = industry_count.sort_values('count', ascending=False)
    
    # 获取行业颜色（与箱线图一致）
    color_map = dict(zip(
        industry_count['super_industry'],
        px.colors.qualitative.Bold[:len(industry_count)]
    ))
    
    fig_pie = px.pie(
        industry_count,
        values='count',
        names='super_industry',
        title=f"各一级行业覆盖个股数量分布（共 {n_superclasses} 个大类）",
        # hover_data=['count'],
        labels={'super_industry': '一级行业', 'count': '公司数量'},
        color='super_industry',
        color_discrete_map=color_map,
        height=500
    )
    fig_pie.update_traces(textposition='inside', textinfo='percent+label')
        
    # ==================== 1. 行业评分分布（箱线图） ====================
    fig1 = px.box(
        valid_df,
        x="super_industry",
        y="final_score",
        color="super_industry",
        title="各超级行业财务评分分布",
        hover_data=['stock_code', 'StockName'],
        labels={"final_score": "综合财务评分", "super_industry": "超级行业","stock_code":"股票代码", "StockName":"股票名称"},
        height=500,
        color_discrete_sequence=px.colors.qualitative.Bold
    )
    fig1.update_layout(showlegend=False, xaxis_tickangle=-45)
    
    # ==================== 2. Top 20 公司排名 ====================
    top20 = valid_df.nlargest(20, 'final_score')
    fig2 = px.bar(
        top20,
        x="final_score",
        y="stock_code",
        color="super_industry",
        orientation='h',
        title="财务健康度 Top 20 公司",
        hover_data=['StockName'],
        labels={"super_industry": "超级行业","final_score": "综合评分", "stock_code": "股票代码", "StockName":"股票名称"},
        height=600,
        color_discrete_sequence=px.colors.qualitative.Set2
    )
    fig2.update_yaxes(categoryorder='total ascending')
    
    # ==================== 3. 7维度雷达图（示例：第一名） ====================
    if not top20.empty:
        top_stock = top20.iloc[0]
        radar_data = {
            "维度": ["盈利能力", "现金流质量", "偿债能力", "运行效率", "成长性", "股权结构", "体量"],
            "得分": [
                top_stock["Profitability_norm"],
                top_stock["CashFlow_norm"],
                top_stock["Solvency_norm"],
                top_stock["Efficiency_norm"],
                top_stock["Growth_norm"],
                top_stock["EquityStructure_norm"],
                top_stock["Size_norm"]
            ]
        }
        radar_df = pd.DataFrame(radar_data)
        
        fig3 = px.line_polar(
            radar_df,
            r="得分",
            theta="维度",
            line_close=True,
            title=f"排名第一公司 ({top_stock['stock_code']}:{top_stock['StockName']}) 7维度雷达图",
            range_r=[0, 1]
        )
        fig3.update_traces(fill='toself', fillcolor="rgba(0,0,255,0.2)")
    else:
        fig3 = go.Figure().add_annotation(text="无数据", showarrow=False)
    
    # ==================== 4. 财务健康度 vs 趋势分 ====================
    counts = valid_df['super_industry'].value_counts()
    valid_df['super_with_count'] = valid_df['super_industry'].map(lambda x: f"{x} (n={counts[x]})")    
    ordered_categories = valid_df['super_with_count'].value_counts().index.tolist()
    fig4 = px.scatter(
        valid_df,
        x="final_score",
        y="trend_score",
        color="super_with_count",
        color_discrete_map=color_map,
        category_orders={'super_with_count':ordered_categories},        
        hover_data=["industry", "stock_code", "StockName"],
        title="财务健康度 vs 3年趋势分",
        labels={
            "final_score": "当前财务健康度",
            "trend_score": "3年趋势分 (0-1)",
            "super_with_count": "超级行业",
            "industry": "细分行业",
            "stock_code": "股票代码",
            "StockName": "股票名称"
        },
        height=500,
        color_discrete_sequence=px.colors.qualitative.Bold
    )
    # 添加参考线
    fig4.add_shape(type="line", x0=0.7, x1=0.7, y0=0, y1=1, line=dict(color="red", width=2, dash="dash"))
    fig4.add_shape(type="line", x0=0, x1=1, y0=0.6, y1=0.6, line=dict(color="green", width=2, dash="dash"))
    fig4.add_annotation(x=0.72, y=0.95, text="健康阈值", showarrow=False, font=dict(color="red", size=12))
    fig4.add_annotation(x=0.95, y=0.62, text="趋势改善", showarrow=False, font=dict(color="green", size=12))
    
    # ==================== 5. 行业平均分对比 ====================
    industry_avg = valid_df.groupby('super_industry')['final_score'].mean().reset_index()
    industry_avg['count'] = valid_df.groupby('super_industry').size().reset_index(name = 'count')['count']
    industry_avg = industry_avg.sort_values('final_score', ascending=False)
    
    fig5 = px.bar(
        industry_avg,
        x="final_score",
        y="super_industry",
        orientation='h',
        title="各超级行业平均财务评分",
        hover_data='count',
        labels={"final_score": "平均评分", "super_industry": "超级行业", "count":'公司数量'},
        height=500,
        color_discrete_sequence=['#636EFA']
    )
    fig5.update_yaxes(categoryorder='total ascending')
    
    # ==================== 🔥 6. 新增：一级行业3年趋势分布 ====================
    fig6 = px.box(
        valid_df,
        x="super_industry",
        y="trend_score",
        color="super_industry",
        title="各超级行业3年财务健康度趋势分布",
        hover_data=['stock_code', 'StockName'],
        labels={"trend_score": "3年趋势得分 (0-1)", "super_industry": "超级行业"},
        height=500,
        color_discrete_sequence=px.colors.qualitative.Bold
    )
    fig6.update_layout(showlegend=False, xaxis_tickangle=-45)
    
    # ==================== 🔥 7. 新增：趋势方向热力图 ====================
    # 定义趋势方向
    valid_df['trend_direction'] = valid_df['trend_score'].apply(
        lambda x: '显著改善' if x >= 0.7 else ('改善' if x >= 0.55 else 
                ('持平' if x >= 0.45 else ('恶化' if x >= 0.3 else '显著恶化')))
    )
    
    # 统计比例
    heatmap_data = valid_df.groupby(['super_industry', 'trend_direction']).size().reset_index(name='count')
    total_per_industry = valid_df.groupby('super_industry').size().reset_index(name='total')
    heatmap_data = heatmap_data.merge(total_per_industry, on='super_industry')
    heatmap_data['percentage'] = heatmap_data['count'] / heatmap_data['total']
    
    # 构建透视表
    order = ['显著恶化', '恶化', '持平', '改善', '显著改善']
    pivot = heatmap_data.pivot(index='super_industry', columns='trend_direction', values='percentage').fillna(0)
    pivot = pivot.reindex(columns=order, fill_value=0)
    
    fig7 = px.imshow(
        pivot.values,
        labels=dict(x="趋势方向", y="超级行业", color="比例"),
        x=order,
        y=pivot.index.tolist(),
        color_continuous_scale='RdYlGn',
        aspect="auto",
        title="各超级行业财务健康度趋势方向分布",
        height=500
    )
    fig7.update_xaxes(side="top")
    
    # ==================== 🔥 8. 增强版综合仪表盘 ====================
    fig_dashboard = make_subplots(
        rows=5, cols=2,
        subplot_titles=(
            "行业评分分布", "行业个股数量分布",  # ← 新增位置
            "Top 20 公司", "健康度 vs 趋势",
            "行业平均分", "3年趋势分布",
            "趋势方向热力图", "Top 1 雷达图",
            "", ""
        ),
        specs=[
            [{"type": "box"}, {"type": "pie"}],      # ← 新增饼图
            [{"type": "bar"}, {"type": "scatter"}],
            [{"type": "bar"}, {"type": "box"}],
            [{"type": "heatmap"}, {"type": "polar"}],
            [{"type": "xy"}, {"type": "xy"}]
        ],
        vertical_spacing=0.05,
        horizontal_spacing=0.05,
        row_heights=[0.2, 0.2, 0.2, 0.25, 0.15]
    )
    
    # 添加子图（注意新布局）
    for trace in fig1.data:
        fig_dashboard.add_trace(trace, row=1, col=1)
    for trace in fig_pie.data:  # ← 新增饼图
        fig_dashboard.add_trace(trace, row=1, col=2)
    for trace in fig2.data:
        fig_dashboard.add_trace(trace, row=2, col=1)
    for trace in fig4.data:
        fig_dashboard.add_trace(trace, row=2, col=2)
    for trace in fig5.data:
        fig_dashboard.add_trace(trace, row=3, col=1)
    for trace in fig6.data:
        fig_dashboard.add_trace(trace, row=3, col=2)
    fig_dashboard.add_trace(
        go.Heatmap(
            z=pivot.values,
            x=order,
            y=pivot.index.tolist(),
            colorscale='RdYlGn'
        ), 
        row=4, col=1
    )
    for trace in fig3.data:
        fig_dashboard.add_trace(trace, row=4, col=2)
    
    fig_dashboard.update_layout(
        height=2000,  # 增加高度以容纳新行
        title_text="A股上市公司财务健康度全景分析（含行业覆盖度）",
        title_x=0.5,
        showlegend=False
    )
    
    # 更新热力图坐标轴
    fig_dashboard.update_xaxes(tickangle=45, row=3, col=2)
    fig_dashboard.update_yaxes(tickangle=0, row=3, col=2)
    
    # 显示所有图表
    fig_pie.show()
    fig1.show()
    fig2.show()
    fig3.show()
    fig4.show()
    fig5.show()
    fig6.show()  # 新增趋势分布
    fig7.show()  # 新增趋势热力图
    fig_dashboard.show()
    
    return {
        "industry_count": fig_pie,  # ← 新增返回
        "distribution": fig1,
        "top20": fig2,
        "radar": fig3,
        "scatter": fig4,
        "industry_avg": fig5,
        "trend_distribution": fig6,
        "trend_heatmap": fig7,
        "dashboard": fig_dashboard
    }

# %% [markdown]
# * 7.2 二级子行业

# %%
def visualize_financial_scores_by_subclass(scores_df: pd.DataFrame):
    """
    按二级子类全面可视化财务评分结果（V2 - 增强版）
    
    Args:
        scores_df: 评分引擎输出结果，需包含：
            - stock_code, industry, subclass
            - Profitability_norm, CashFlow_norm, ..., Size_norm
            - final_score, trend_score
    """
    # 确保数值列
    score_cols = [f"{dim}_norm" for dim in 
                  ["Profitability", "CashFlow", "Solvency", "Efficiency", "Growth", "EquityStructure", "Size"]]
    for col in score_cols + ['final_score', 'trend_score']:
        scores_df[col] = pd.to_numeric(scores_df[col], errors='coerce')
    
    # 过滤有效数据
    valid_df = scores_df.dropna(subset=['final_score']).copy()
    # 获取所有二级子类
    all_subclasses = sorted(valid_df['subclass'].unique())
    n_subclasses = len(all_subclasses)
    
    # ==================== 🔥 新增：二级子类个股数量统计 ====================
    subclass_count = valid_df.groupby('subclass').size().reset_index(name='count')
    subclass_count = subclass_count.sort_values('count', ascending=False)
    
    # 创建颜色映射（与箱线图一致）
    color_sequence = px.colors.qualitative.Pastel
    color_map = {}
    for i, subclass in enumerate(subclass_count['subclass']):
        color_map[subclass] = color_sequence[i % len(color_sequence)]
    
    # 创建饼图
    fig_pie = px.pie(
        subclass_count,
        values='count',
        names='subclass',
        title=f"各二级子类覆盖个股数量分布（共 {n_subclasses} 个子类）",
        # hover_data=['count'],
        labels={'subclass': '二级子类', 'count': '公司数量'},
        color='subclass',
        color_discrete_map=color_map,
        height=500  # 增加高度以容纳更多标签
    )
    
    # 优化标签：仅显示占比 > 3% 的标签
    fig_pie.update_traces(
        textposition='inside',
        textinfo='percent+label',
        insidetextorientation='radial',
        textfont_size=9
    )    
    
    # ==================== 1. 二级子类评分分布（箱线图） ====================
    fig1 = px.box(
        valid_df,
        x="subclass",
        y="final_score",
        color="subclass",
        title="各二级子类财务评分分布",
        hover_data=['stock_code', 'StockName'],
        labels={"final_score": "综合财务评分", "subclass": "二级子类","stock_code":"股票代码", "StockName":"股票名称"},
        height=600,
        color_discrete_sequence=px.colors.qualitative.Pastel
    )
    fig1.update_layout(showlegend=False, xaxis_tickangle=-45)
    
    # ==================== 2. Top 20 公司排名（按二级子类着色） ====================
    top20 = valid_df.nlargest(20, 'final_score')
    fig2 = px.bar(
        top20,
        x="final_score",
        y="stock_code",
        color="subclass",
        orientation='h',
        title="财务健康度 Top 20 公司（按二级子类着色）",
        hover_data=['StockName'],
        labels={"final_score": "综合评分", "stock_code": "股票代码", "subclass": "二级子类", "StockName":"股票名称"},
        height=700,
        color_discrete_sequence=px.colors.qualitative.Set3
    )
    fig2.update_yaxes(categoryorder='total ascending')
    
    # ==================== 3. 7维度雷达图（示例：第一名） ====================
    if not top20.empty:
        top_stock = top20.iloc[0]
        radar_data = {
            "维度": ["盈利能力", "现金流质量", "偿债能力", "运行效率", "成长性", "股权结构", "体量"],
            "得分": [
                top_stock["Profitability_norm"],
                top_stock["CashFlow_norm"],
                top_stock["Solvency_norm"],
                top_stock["Efficiency_norm"],
                top_stock["Growth_norm"],
                top_stock["EquityStructure_norm"],
                top_stock["Size_norm"]
            ]
        }
        radar_df = pd.DataFrame(radar_data)
        
        fig3 = px.line_polar(
            radar_df,
            r="得分",
            theta="维度",
            line_close=True,
            title=f"排名第一公司 ({top_stock['stock_code']}:{top_stock['StockName']}) 7维度雷达图<br>"
                  f"<sub>所属二级子类: {top_stock['subclass']}</sub>",
            range_r=[0, 1]
        )
        fig3.update_traces(fill='toself', fillcolor="rgba(128,0,128,0.2)")
    else:
        fig3 = go.Figure().add_annotation(text="无数据", showarrow=False)
    
    # ==================== 4. 财务健康度 vs 趋势分（按二级子类着色） ====================
    counts = valid_df['subclass'].value_counts()
    valid_df['subclass_with_count'] = valid_df['subclass'].map(lambda x: f"{x} (n={counts[x]})")    
    ordered_categories = valid_df['subclass_with_count'].value_counts().index.tolist()
    fig4 = px.scatter(
        valid_df,
        x="final_score",
        y="trend_score",
        color="subclass_with_count",
        color_discrete_map=color_map,
        category_orders={'subclass_with_count':ordered_categories},
        hover_data=["industry", "stock_code", "StockName"],
        title="财务健康度 vs 3年趋势分（按二级子类着色）",
        labels={
            "final_score": "当前财务健康度",
            "trend_score": "3年趋势分 (0-1)",
            "subclass_with_count": "二级子类",
            "industry": "细分行业",
            "stock_code": "股票代码",
            "StockName": "股票名称"
        },
        height=600,
        color_discrete_sequence=px.colors.qualitative.Pastel
    )
    # 添加参考线
    fig4.add_shape(type="line", x0=0.7, x1=0.7, y0=0, y1=1, line=dict(color="red", width=2, dash="dash"))
    fig4.add_shape(type="line", x0=0, x1=1, y0=0.6, y1=0.6, line=dict(color="green", width=2, dash="dash"))
    fig4.add_annotation(x=0.72, y=0.95, text="健康阈值", showarrow=False, font=dict(color="red", size=12))
    fig4.add_annotation(x=0.95, y=0.62, text="趋势改善", showarrow=False, font=dict(color="green", size=12))
    
    # ==================== 5. 二级子类平均分对比 ====================
    subclass_avg = valid_df.groupby('subclass')['final_score'].mean().reset_index()
    subclass_avg['count'] = valid_df.groupby('subclass').size().reset_index(name = 'count')['count']
    subclass_avg = subclass_avg.sort_values('final_score', ascending=False)
    
    fig5 = px.bar(
        subclass_avg,
        x="final_score",
        y="subclass",
        orientation='h',
        title="各二级子类平均财务评分",
        hover_data='count',
        labels={"final_score": "平均评分", "subclass": "二级子类", "count":'公司数量'},
        height=800,
        color_discrete_sequence=['#AB63FA']
    )
    fig5.update_yaxes(categoryorder='total ascending')
    
    # ==================== 🔥 6. 新增：二级子类3年趋势分布 ====================
    fig6 = px.box(
        valid_df,
        x="subclass",
        y="trend_score",
        color="subclass",
        title="各二级子类3年财务健康度趋势分布",
        labels={"trend_score": "3年趋势得分 (0-1)", "subclass": "二级子类"},
        height=600,
        color_discrete_sequence=px.colors.qualitative.Pastel
    )
    fig6.update_layout(showlegend=False, xaxis_tickangle=-45)
    
    # ==================== 🔥 7. 新增：趋势方向热力图（按二级子类） ====================
    # 定义趋势方向
    valid_df['trend_direction'] = valid_df['trend_score'].apply(
        lambda x: '显著改善' if x >= 0.7 else ('改善' if x >= 0.55 else 
                ('持平' if x >= 0.45 else ('恶化' if x >= 0.3 else '显著恶化')))
    )
    
    # 统计比例
    heatmap_data = valid_df.groupby(['subclass', 'trend_direction']).size().reset_index(name='count')
    total_per_subclass = valid_df.groupby('subclass').size().reset_index(name='total')
    heatmap_data = heatmap_data.merge(total_per_subclass, on='subclass')
    heatmap_data['percentage'] = heatmap_data['count'] / heatmap_data['total']
    
    # 构建透视表
    order = ['显著恶化', '恶化', '持平', '改善', '显著改善']
    pivot = heatmap_data.pivot(index='subclass', columns='trend_direction', values='percentage').fillna(0)
    pivot = pivot.reindex(columns=order, fill_value=0)
    
    fig7 = px.imshow(
        pivot.values,
        labels=dict(x="趋势方向", y="二级子类", color="比例"),
        x=order,
        y=pivot.index.tolist(),
        color_continuous_scale='RdYlGn',
        aspect="auto",
        title="各二级子类财务健康度趋势方向分布",
        height=800
    )
    fig7.update_xaxes(side="top")
    

    # ==================== 🔥 更新综合仪表盘（5×2 布局） ====================
    dashboard_height = max(2000, n_subclasses * 40)  # 动态高度
    
    fig_dashboard = make_subplots(
        rows=5, cols=2,
        subplot_titles=(
            "二级子类评分分布", "子类个股数量分布",  # ← 新增位置
            "Top 20 公司", "健康度 vs 趋势",
            "子类平均分", "3年趋势分布",
            "趋势方向热力图", "Top 1 雷达图",
            "", ""
        ),
        specs=[
            [{"type": "box"}, {"type": "pie"}],      # ← 新增饼图
            [{"type": "bar"}, {"type": "scatter"}],
            [{"type": "bar"}, {"type": "box"}],
            [{"type": "heatmap"}, {"type": "polar"}],
            [{"type": "xy"}, {"type": "xy"}]
        ],
        vertical_spacing=0.04,
        horizontal_spacing=0.04,
        row_heights=[0.2, 0.2, 0.2, 0.25, 0.15]
    )
    
    # 添加子图（注意新布局）
    for trace in fig1.data:
        fig_dashboard.add_trace(trace, row=1, col=1)
    for trace in fig_pie.data:  # ← 新增饼图
        fig_dashboard.add_trace(trace, row=1, col=2)
    for trace in fig2.data:
        fig_dashboard.add_trace(trace, row=2, col=1)
    for trace in fig4.data:
        fig_dashboard.add_trace(trace, row=2, col=2)
    for trace in fig5.data:
        fig_dashboard.add_trace(trace, row=3, col=1)
    for trace in fig6.data:
        fig_dashboard.add_trace(trace, row=3, col=2)
    fig_dashboard.add_trace(
        go.Heatmap(
            z=pivot.values,
            x=order,
            y=pivot.index.tolist(),
            colorscale='RdYlGn'
        ), 
        row=4, col=1
    )
    for trace in fig3.data:
        fig_dashboard.add_trace(trace, row=4, col=2)
    
    fig_dashboard.update_layout(
        height=dashboard_height,
        title_text="A股上市公司财务健康度全景分析（按二级子类 + 样本覆盖度）",
        title_x=0.5,
        showlegend=False,
        font=dict(size=9)
    )
    
    # 显示所有图表
    fig_pie.show()  # ← 新增显示
    fig1.show()
    fig2.show()
    fig3.show()
    fig4.show()
    fig5.show()
    fig6.show()
    fig7.show()
    fig_dashboard.show()
    
    return {
        "subclass_count": fig_pie,  # ← 新增返回
        "distribution": fig1,
        "top20": fig2,
        "radar": fig3,
        "scatter": fig4,
        "subclass_avg": fig5,
        "trend_distribution": fig6,
        "trend_heatmap": fig7,
        "dashboard": fig_dashboard
    }



# %% [markdown]
# * 7.3 157细分行业

# %%
def visualize_financial_scores_by_industry(scores_df: pd.DataFrame):
    """
    按157个细分行业全面可视化财务评分结果
    
    Args:
        scores_df: 评分引擎输出结果，需包含：
            - stock_code, industry, subclass
            - Profitability_norm, CashFlow_norm, ..., Size_norm
            - final_score, trend_score
    """
    # 确保数值列
    score_cols = [f"{dim}_norm" for dim in 
                  ["Profitability", "CashFlow", "Solvency", "Efficiency", "Growth", "EquityStructure", "Size"]]
    for col in score_cols + ['final_score', 'trend_score']:
        scores_df[col] = pd.to_numeric(scores_df[col], errors='coerce')
    
    # 过滤有效数据
    valid_df = scores_df.dropna(subset=['final_score']).copy()
    
    # 获取所有细分行业
    all_industries = sorted(valid_df['industry'].unique())
    n_industries = len(all_industries)
    
    # ==================== 1. 细分行业评分分布（箱线图） ====================
    fig1 = px.box(
        valid_df,
        x="industry",
        y="final_score",
        color="industry",
        title=f"157个细分行业财务评分分布（共 {n_industries} 个行业）",
        hover_data=['stock_code', 'StockName'],
        labels={"final_score": "综合财务评分", "industry": "细分行业","stock_code":"股票代码", "StockName":"股票名称"},
        height=600,  
        color_discrete_sequence=px.colors.qualitative.Dark24 * 7  # 扩展色系
    )
    fig1.update_yaxes(fixedrange=True)
    fig1.update_xaxes(fixedrange=False)
    fig1.update_layout(
        dragmode='pan',
        showlegend=False,
        xaxis=dict(
            tickmode='array',
            tickvals=all_industries,
            ticktext=all_industries,
            tickangle=-45,
            tickfont=dict(size=7)
        )
    )
    
    # ==================== 🔥 新增：细分行业个股数量饼图 ====================
    industry_count = valid_df.groupby('industry').size().reset_index(name='count')
    industry_count = industry_count.sort_values('count', ascending=False)
    
    # 创建颜色映射
    color_sequence = px.colors.qualitative.Dark24 * 7
    color_map = {}
    for i, industry in enumerate(industry_count['industry']):
        color_map[industry] = color_sequence[i % len(color_sequence)]
    
    fig_pie = px.pie(
        industry_count,
        values='count',
        names='industry',
        title=f"157个细分行业覆盖个股数量分布（共 {n_industries} 个行业）",
        # hover_data=['count'],
        labels={'industry': '细分行业', 'count': '公司数量'},
        color='industry',
        color_discrete_map=color_map,
        height=600
    )
    fig_pie.update_traces(
        textposition='inside',
        textinfo='percent+label',
        insidetextorientation='radial',
        textfont_size=6  # 小字体适应更多标签
    )
    
    # ==================== 2. Top 20 公司排名 ====================
    top20 = valid_df.nlargest(20, 'final_score')
    fig2 = px.bar(
        top20,
        x="final_score",
        y="stock_code",
        color="industry",
        orientation='h',
        title="财务健康度 Top 20 公司（按细分行业着色）",
        hover_data=['StockName'],
        labels={"final_score": "综合评分", "stock_code": "股票代码", "industry": "细分行业", "StockName":"股票名称"},
        height=600,
        color_discrete_sequence=px.colors.qualitative.Set3 * 5
    )
    fig2.update_yaxes(categoryorder='total ascending')
    
    # ==================== 3. 7维度雷达图（Top 1） ====================
    if not top20.empty:
        top_stock = top20.iloc[0]
        radar_data = {
            "维度": ["盈利能力", "现金流质量", "偿债能力", "运行效率", "成长性", "股权结构", "体量"],
            "得分": [
                top_stock["Profitability_norm"],
                top_stock["CashFlow_norm"],
                top_stock["Solvency_norm"],
                top_stock["Efficiency_norm"],
                top_stock["Growth_norm"],
                top_stock["EquityStructure_norm"],
                top_stock["Size_norm"]
            ]
        }
        radar_df = pd.DataFrame(radar_data)
        fig3 = px.line_polar(
            radar_df,
            r="得分",
            theta="维度",
            line_close=True,
            title=f"Top 1 公司 ({top_stock['stock_code']})<br><sub>细分行业: {top_stock['industry']}</sub>",
            range_r=[0, 1]
        )
        fig3.update_traces(fill='toself', fillcolor="rgba(0,0,139,0.2)")
    else:
        fig3 = go.Figure().add_annotation(text="无数据", showarrow=False)
    
    # ==================== 4. 健康度 vs 趋势分 ====================
    counts = valid_df['industry'].value_counts()
    valid_df['industry_with_count'] = valid_df['industry'].map(lambda x: f"{x} (n={counts[x]})")    
    ordered_categories = valid_df['industry_with_count'].value_counts().index.tolist()    
    fig4 = px.scatter(
        valid_df,
        x="final_score",
        y="trend_score",
        color="industry_with_count",
        category_orders={'industry_with_count':ordered_categories},
        hover_data=["stock_code", "StockName"],
        title="财务健康度 vs 3年趋势分（按细分行业着色）",
        labels={
            "final_score": "当前财务健康度",
            "trend_score": "3年趋势分 (0-1)",
            "industry_with_count": "细分行业",
            "stock_code": "股票代码",
            "StockName": "股票名称"
        },
        height=600,
        color_discrete_sequence=px.colors.qualitative.Dark24 * 7
    )
    fig4.add_shape(type="line", x0=0.7, x1=0.7, y0=0, y1=1, line=dict(color="red", width=2, dash="dash"))
    fig4.add_shape(type="line", x0=0, x1=1, y0=0.6, y1=0.6, line=dict(color="green", width=2, dash="dash"))
    fig4.add_annotation(x=0.72, y=0.95, text="健康阈值", font=dict(color="red", size=10))
    fig4.add_annotation(x=0.95, y=0.62, text="趋势改善", font=dict(color="green", size=10))
    
    # ==================== 5. 细分行业平均分对比 ====================
    industry_avg = valid_df.groupby('industry')['final_score'].mean().reindex(all_industries).reset_index()
    industry_avg['count'] = valid_df.groupby('industry').size().reset_index(name = 'count')['count']
    fig5 = px.bar(
        industry_avg,
        x="final_score",
        y="industry",
        orientation='h',
        title="各细分行业平均财务评分",
        hover_data='count',
        labels={"final_score": "平均评分", "industry": "细分行业", "count":'公司数量'},
        height=800,
        # height=max(800, n_industries * 15),
        color_discrete_sequence=['#1f77b4']
    )
    fig5.update_xaxes(fixedrange=True),
    fig5.update_yaxes(
        categoryorder='array',
        categoryarray=all_industries,
        tickfont=dict(size=7),
        fixedrange=False,
    )
    fig5.update_layout(dragmode='pan')
    # ==================== 6. 3年趋势分布 ====================
    fig6 = px.box(
        valid_df,
        x="industry",
        y="trend_score",
        color="industry",
        title="各细分行业3年财务健康度趋势分布",
        labels={"trend_score": "3年趋势得分 (0-1)", "industry": "细分行业"},
        # height=max(600, n_industries * 15),
        height=600,
        color_discrete_sequence=px.colors.qualitative.Dark24 * 7
    )
    fig6.update_yaxes(fixedrange=True),
    fig6.update_xaxes(fixedrange=False)
    fig6.update_layout(
        dragmode='pan',
        showlegend=False,
        xaxis=dict(
            tickmode='array',
            tickvals=all_industries,
            ticktext=all_industries,
            tickangle=-45,
            tickfont=dict(size=7)
        )
    )
    
    # ==================== 7. 趋势方向热力图 ====================
    valid_df['trend_direction'] = valid_df['trend_score'].apply(
        lambda x: '显著改善' if x >= 0.7 else ('改善' if x >= 0.55 else 
                ('持平' if x >= 0.45 else ('恶化' if x >= 0.3 else '显著恶化')))
    )
    
    heatmap_data = valid_df.groupby(['industry', 'trend_direction']).size().reset_index(name='count')
    total_per_industry = valid_df.groupby('industry').size().reset_index(name='total')
    heatmap_data = heatmap_data.merge(total_per_industry, on='industry')
    heatmap_data['percentage'] = heatmap_data['count'] / heatmap_data['total']
    
    order = ['显著恶化', '恶化', '持平', '改善', '显著改善']
    pivot = heatmap_data.pivot(index='industry', columns='trend_direction', values='percentage').fillna(0)
    pivot = pivot.reindex(index=all_industries, columns=order, fill_value=0)
    
    # heatmap_height = max(800, n_industries * 20)
    heatmap_height = 600
    fig7 = px.imshow(
        pivot.values,
        labels=dict(x="趋势方向", y="细分行业", color="比例"),
        x=order,
        y=pivot.index.tolist(),
        color_continuous_scale='RdYlGn',
        aspect="auto",
        title=f"各细分行业财务健康度趋势方向分布（共 {n_industries} 个行业）",
        height=heatmap_height
    )
    fig7.update_xaxes(side="top", tickangle=0,fixedrange=True)
    fig7.update_yaxes(tickfont=dict(size=8), fixedrange=False)
    fig7.update_layout(dragmode='pan')
    
    # ==================== 8. 综合仪表盘（6×2 布局） ====================
    dashboard_height = max(2000, n_industries * 25)
    
    fig_dashboard = make_subplots(
        rows=6, cols=2,
        subplot_titles=(
            "细分行业评分分布", "行业个股数量分布",
            "Top 20 公司", "健康度 vs 趋势",
            "行业平均分", "3年趋势分布",
            "趋势方向热力图", "Top 1 雷达图",
            "", "",
            "", ""
        ),
        specs=[
            [{"type": "box"}, {"type": "pie"}],
            [{"type": "bar"}, {"type": "scatter"}],
            [{"type": "bar"}, {"type": "box"}],
            [{"type": "heatmap"}, {"type": "polar"}],
            [{"type": "xy"}, {"type": "xy"}],
            [{"type": "xy"}, {"type": "xy"}]
        ],
        vertical_spacing=0.03,
        horizontal_spacing=0.03,
        row_heights=[0.18, 0.18, 0.18, 0.22, 0.12, 0.12]
    )
    
    # 添加子图
    for trace in fig1.data:
        fig_dashboard.add_trace(trace, row=1, col=1)
    for trace in fig_pie.data:
        fig_dashboard.add_trace(trace, row=1, col=2)
    for trace in fig2.data:
        fig_dashboard.add_trace(trace, row=2, col=1)
    for trace in fig4.data:
        fig_dashboard.add_trace(trace, row=2, col=2)
    for trace in fig5.data:
        fig_dashboard.add_trace(trace, row=3, col=1)
    for trace in fig6.data:
        fig_dashboard.add_trace(trace, row=3, col=2)
    fig_dashboard.add_trace(
        go.Heatmap(
            z=pivot.values,
            x=order,
            y=pivot.index.tolist(),
            colorscale='RdYlGn'
        ), 
        row=4, col=1
    )
    for trace in fig3.data:
        fig_dashboard.add_trace(trace, row=4, col=2)
    
    fig_dashboard.update_layout(
        height=dashboard_height,
        title_text="A股上市公司财务健康度全景分析（157个细分行业）",
        title_x=0.5,
        showlegend=False,
        font=dict(size=8)
    )
    fig_dashboard.update_xaxes(tickangle=45, row=4, col=2, tickfont=dict(size=7))
    fig_dashboard.update_yaxes(tickfont=dict(size=7), row=4, col=2)
    
    # 显示所有图表
    fig_pie.show()
    fig1.show(config={'scrollZoom': True})
    fig2.show()
    fig3.show()
    fig4.show()
    fig5.show(config={'scrollZoom': True})
    fig6.show(config={'scrollZoom': True})
    fig7.show(config={'scrollZoom': True})
    fig_dashboard.show()
    
    return {
        "industry_count": fig_pie,
        "distribution": fig1,
        "top20": fig2,
        "radar": fig3,
        "scatter": fig4,
        "industry_avg": fig5,
        "trend_distribution": fig6,
        "trend_heatmap": fig7,
        "dashboard": fig_dashboard
    }

# %% [markdown]
# * 7.4 含动画

# %%
def visualize_financial_scores_with_time_animation(scores_df: pd.DataFrame, full_data: pd.DataFrame):
    """
    全面可视化财务评分结果（含时间趋势动画）
    
    Args:
        scores_df: 最新一期评分结果（用于静态图）
        full_data: 多期原始数据（用于计算时间序列）
    """
    # === 静态图部分（同前）===
    score_cols = [f"{dim}_norm" for dim in 
                  ["Profitability", "CashFlow", "Solvency", "Efficiency", "Growth", "EquityStructure", "Size"]]
    for col in score_cols + ['final_score', 'trend_score']:
        scores_df[col] = pd.to_numeric(scores_df[col], errors='coerce')
    valid_df = scores_df.dropna(subset=['final_score']).copy()
    
    # 1. 二级子类评分分布
    fig1 = px.box(
        valid_df,
        x="subclass",
        y="final_score",
        color="subclass",
        title="各二级子类财务评分分布（最新期）",
        labels={"final_score": "综合财务评分", "subclass": "二级子类"},
        height=600
    )
    fig1.update_layout(showlegend=False, xaxis_tickangle=-45)
    
    # 2. Top 20 公司
    top20 = valid_df.nlargest(20, 'final_score')
    fig2 = px.bar(
        top20,
        x="final_score",
        y="stock_code",
        color="subclass",
        orientation='h',
        title="财务健康度 Top 20 公司（最新期）",
        height=700
    )
    fig2.update_yaxes(categoryorder='total ascending')
    
    # === 时间趋势动画部分 ===
    # 准备时间序列数据
    time_series = []
    for (stock, subclass), group in full_data.groupby(['stock_code', 'subclass']):
        if len(group) < 2:
            continue
        # 按时间排序
        group = group.sort_values('report_date')
        # 计算每期的最终得分（简化：用基础分代替）
        group['time_score'] = (
            group['Profitability_norm'] * 0.25 +
            group['CashFlow_norm'] * 0.20 +
            group['Solvency_norm'] * 0.20 +
            group['Efficiency_norm'] * 0.15 +
            group['Growth_norm'] * 0.15 +
            group['EquityStructure_norm'] * 0.05
        )
        for _, row in group.iterrows():
            time_series.append({
                'stock_code': stock,
                'subclass': subclass,
                'report_date': row['report_date'],
                'time_score': row['time_score']
            })
    
    time_df = pd.DataFrame(time_series)
    if time_df.empty:
        print("⚠️ 无足够时间序列数据，跳过动画")
        return {
            "distribution": fig1,
            "top20": fig2,
            "animation": None
        }
    
    # 转换日期为字符串（Plotly动画要求）
    time_df['date_str'] = pd.to_datetime(time_df['report_date']).dt.strftime('%Y-%m')
    
    # 3. 时间趋势动画：二级子类平均分
    subclass_time = time_df.groupby(['subclass', 'date_str'])['time_score'].mean().reset_index()
    subclass_time = subclass_time.sort_values('date_str')
    
    fig3 = px.line(
        subclass_time,
        x="date_str",
        y="time_score",
        color="subclass",
        title="各二级子类平均财务评分时间趋势",
        labels={
            "time_score": "平均财务评分",
            "date_str": "报告期",
            "subclass": "二级子类"
        },
        height=600
    )
    
    # 4. 动态 Top 10 榜单动画
    # 获取每个时间点的Top 10
    top10_over_time = []
    for date, date_group in time_df.groupby('date_str'):
        top10 = date_group.nlargest(10, 'time_score')
        for _, row in top10.iterrows():
            top10_over_time.append({
                'date_str': date,
                'stock_code': row['stock_code'],
                'subclass': row['subclass'],
                'time_score': row['time_score']
            })
    
    top10_df = pd.DataFrame(top10_over_time)
    if not top10_df.empty:
        fig4 = px.bar(
            top10_df,
            x="time_score",
            y="stock_code",
            color="subclass",
            animation_frame="date_str",
            animation_group="stock_code",
            orientation='h',
            range_x=[0, 1],
            title="财务健康度 Top 10 公司动态榜单",
            labels={"time_score": "财务评分", "stock_code": "股票代码"},
            height=700
        )
        fig4.layout.updatemenus[0].buttons[0].args[1]['frame']['duration'] = 1000
        fig4.layout.updatemenus[0].buttons[0].args[1]['transition']['duration'] = 500
    else:
        fig4 = go.Figure().add_annotation(text="无Top 10数据", showarrow=False)
    
    # 显示图表
    fig1.show()
    fig2.show()
    fig3.show()
    fig4.show()
    
    return {
        "distribution": fig1,
        "top20": fig2,
        "time_trend": fig3,
        "dynamic_top10": fig4
    }

    
    # # 可视化
    # figures = visualize_financial_scores_with_time_animation(latest_df, full_df)
    # print("✅ 含时间动画的可视化完成！")

# %%
ordered_categories=df_final['super_industry'].value_counts().sort_values(ascending=False).index.tolist()

# %% [markdown]
# ##### 八 、图示分析

# %%
figures = visualize_financial_scores(df_final, industry_hierarchy)

# %%
figures = visualize_financial_scores_by_subclass(df_final)

# %%
figures = visualize_financial_scores_by_industry(df_final)

# %% [markdown]
# ##### 结果图示

# %%
# 6. 可视化1：各行业健康度分布（Box Plot）
fig_box = px.box(
    df_final,
    x='industry',
    y='total_score',
    color='industry',
    title='各行业公司财务健康度分布（0=最差, 1=最优）',
    labels={'total_score': '财务健康度评分', 'industry': '行业','stock_code':'代码','StockName':'名称'},
    hover_data=['stock_code', 'StockName'],  # 👈 关键：添加悬停信息    
    height=600
)
fig_box.update_layout(xaxis_tickangle=-45)
fig_box.show()

# %%
# 7. 可视化2：行业平均健康度排名（Bar Chart）
industry_avg = df_final.groupby('industry')['total_score'].mean().sort_values(ascending=False).reset_index()

fig_bar = px.bar(
    industry_avg,
    x='industry',
    y='total_score',
    title='行业平均财务健康度排名',
    labels={'total_score': '平均健康度评分', 'industry': '行业'},
    color='total_score',
    color_continuous_scale='RdYlGn'
)
fig_bar.update_layout(xaxis_tickangle=-45, height=600)
fig_bar.show()

# %%
# 8. 输出每个行业 Top 5
print("\n" + "="*80)
print("🏆 各行业财务健康度 Top 5 公司")
print("="*80)

all_top5 = []

for industry in INDUSTRIES:
    df_ind = df_final[df_final['industry'] == industry]
    if not df_ind.empty:
        top5 = df_ind.nsmallest(5, 'rank_in_industry')
        top5_display = top5[['stock_code','StockName', 'total_score', 'rank_in_industry']].copy()
        top5_display['industry'] = industry
        all_top5.append(top5_display)
        
        print(f"\n【{industry}】Top 5:")
        for _, row in top5_display.iterrows():
            print(f"  {int(row['rank_in_industry'])}. {row['stock_code']} {row['StockName']} (评分: {row['total_score']:.3f})")
    else:
        print(f"\n【{industry}】无数据")

# 合并所有Top5
df_all_top5 = pd.concat(all_top5, ignore_index=True) if all_top5 else pd.DataFrame()

# %%
# 9. 可视化3：Top 公司展示（Bubble Chart）
if not df_all_top5.empty:
    # 限制展示前30家（避免图表过载）
    df_top30 = df_all_top5.head(30)
    
    fig_bubble = px.scatter(
        df_top30,
        x='industry',
        y='rank_in_industry',
        size='total_score',
        color='total_score',
        hover_name='stock_code',
        hover_data='StockName',
        title='各行业Top公司健康度评分（气泡大小=评分）',
        labels={'StockName':'名称', 'rank_in_industry': '行业排名', 'total_score': '健康度评分'},
        color_continuous_scale='RdYlGn',
        height=700
    )
    fig_bubble.update_yaxes(autorange="reversed")  # 排名1在顶部
    fig_bubble.update_layout(xaxis_tickangle=-45)
    fig_bubble.show()

# %%

# %%
df_final[(df_final['final_score']>=0.85) & (df_final['total_score']>=0.85)]

# %%
industry_to_levels['LED']

# %%
SUPER_INDUSTRY_WEIGHTS['TMT科技']

# %%
SUB_INDUSTRY_WEIGHTS['半导体与电子元器件']

# %%
get_indicators('银行')

