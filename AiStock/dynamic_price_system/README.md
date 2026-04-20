## 资产配置 + 回测 + 监测

* ✅ 基于三维动态价格引擎 | ✅ 配置驱动 + 模块化设计 | ✅ 生产级操作流程

### 一、资产配置：从评分到组合构建

#### 1.1 配置逻辑框架

三维评分 → 标的筛选 → 权重分配 → 组合生成
    ↓           ↓           ↓           ↓
技术/基本面/宏观  盈亏比+评分阈值  板块约束+风险预算  再平衡规则

#### 1.2 配置策略示例 (config/dynamic_price/portfolio_config.yaml)

``` yaml
# ==================== 组合配置 ====================
portfolio:
  initial_capital: 1000000        # 初始资金
  max_position_single: 0.15       # 单标的上限 15%
  max_position_sector: 0.30       # 单板块上限 30%
  min_pl_ratio: 2.0               # 最低盈亏比阈值
  min_fundamental_score: 60       # 最低基本面评分
  
# ==================== 权重分配策略 ====================
weighting:
  method: "score_weighted"        # score_weighted / equal / risk_parity
  score_weights:
    pl_ratio: 0.5                 # 盈亏比权重
    fundamental_score: 0.3        # 基本面权重
    macro_factor: 0.2             # 宏观因子权重
  
# ==================== 再平衡规则 ====================
rebalance:
  frequency: "weekly"             # daily/weekly/monthly
  threshold: 0.15                 # 权重偏离 15% 触发再平衡
  max_turnover: 0.30              # 单次调仓最大换手率 30%
  
# ==================== 风控规则 ====================
risk_control:
  stop_loss: -0.15                # 止损阈值 -15%
  take_profit: 0.30               # 止盈阈值 +30%
  max_drawdown: -0.20             # 组合最大回撤 -20%
  daily_loss_limit: -0.05         # 单日亏损限制 -5%

```

#### 1.3 资产配置代码示例 (scripts/allocate.py)

#### 1.4 运行资产配置

```bash

# 执行资产配置（生成 target_weights.json）
python scripts/allocate.py

# 输出示例:
📋 目标组合权重:
  • 600938 中国海油: 12.3% | 板块:油气开采 | 盈亏比:3.2x
  • 601899 紫金矿业: 11.8% | 板块:黄金 | 盈亏比:2.9x
  • 300750 宁德时代: 10.5% | 板块:新能源 | 盈亏比:2.5x
  ...
✅ 配置已保存: /path/to/AiStock/output/target_weights.json

```

### 二、回测验证：策略历史表现分析

#### 2.1 回测框架设计 (dynamic_price_system/run_backtest.py)

#### 2.2 回测执行脚本 (scripts/backtest.py)

#### 2.3 运行回测

```bash

# 执行 1 年回测（示例）
python scripts/backtest.py \
  --start 2025-01-01 \
  --end 2025-12-31 \
  --stocks 600938 601899 300750 600406 \
  --output output/backtest_2025.json

# 输出示例:
📊 回测结果:
  • total_return: 0.2341
  • annual_return: 0.2341
  • volatility: 0.1823
  • sharpe_ratio: 1.2842
  • max_drawdown: -0.1256
  • win_rate: 0.5834
  • total_trades: 47
  • benchmark_return: 0.1873
  • alpha: 0.0468

✅ 结果已保存: output/backtest_2025.json

```

### 三、实时监测：组合跟踪与风控预警

#### 3.1 监测仪表板 (scripts/monitor.py)

#### 3.2 定时监测配置（Cron 示例）

```bash
# 编辑 crontab: crontab -e

# 每日 9:30 开盘后监测（预警检查）
30 9 * * 1-5 cd /path/to/AiStock && python scripts/monitor.py >> logs/monitor.log 2>&1

# 每日 15:30 收盘后监测（净值更新 + 日报生成）
30 15 * * 1-5 cd /path/to/AiStock && python scripts/monitor.py --report daily >> logs/monitor.log 2>&1

# 每周五 16:00 生成周度回测报告
0 16 * * 5 cd /path/to/AiStock && python scripts/backtest.py --start $(date -d 'last-week' +%Y-%m-%d) --end $(date +%Y-%m-%d) >> logs/backtest.log 2>&1
```

#### 3.3 预警集成示例（钉钉机器人utils/alert_utils.py）

### 四、完整工作流：每日自动化流程

``` mermaid

graph TD
    A[09:00 宏观数据更新] --> B[09:30 动态价格计算]
    B --> C[10:00 资产配置生成]
    C --> D[10:30 交易信号输出]
    D --> E[14:00 盘中监测预警]
    E --> F[15:30 收盘净值更新]
    F --> G[16:00 日报/周报生成]
    G --> H[17:00 数据归档备份]

```

#### 自动化脚本 (scripts/daily_pipeline.sh)

```bash

#!/bin/bash
# AiStock 每日自动化流程

set -e  # 遇错即停

LOG_DIR="logs/daily"
mkdir -p $LOG_DIR

echo "🚀 启动每日流程 $(date)"

# 1. 宏观数据更新
echo "📥 更新宏观数据..."
python scripts/update_macro.py >> $LOG_DIR/macro.log 2>&1

# 2. 动态价格计算
echo "🧮 计算动态价格..."
python dynamic_price_system/main.py --mode paper >> $LOG_DIR/calc.log 2>&1

# 3. 资产配置生成
echo "⚖️ 生成资产配置..."
python scripts/allocate.py >> $LOG_DIR/allocate.log 2>&1

# 4. 交易信号输出（对接实盘系统）
echo "📤 输出交易信号..."
python scripts/generate_signals.py >> $LOG_DIR/signals.log 2>&1

# 5. 监测预警（盘中执行）
if [[ $(date +%H) -ge 9 && $(date +%H) -le 15 ]]; then
    echo "📡 执行盘中监测..."
    python scripts/monitor.py >> $LOG_DIR/monitor.log 2>&1
fi

# 6. 收盘后处理
if [[ $(date +%H) -ge 15 ]]; then
    echo "📊 生成收盘报告..."
    python scripts/generate_report.py --type daily >> $LOG_DIR/report.log 2>&1
    
    echo "💾 数据归档..."
    python scripts/archive_data.py >> $LOG_DIR/archive.log 2>&1
fi

echo "✅ 每日流程完成 $(date)"

```

### 六、最佳实践建议

#### ✅ 资产配置

* 动态调整：每周根据最新宏观数据重新计算权重，避免静态配置失效
* 分散约束：单板块≤30% + 单标的≤15%，防止过度集中
* 评分门槛：盈亏比<2.0 或 基本面<50 的标的自动排除

#### ✅ 回测验证

* 样本外测试：用 2023 年数据训练参数，2024 年数据验证效果
* 成本敏感性：测试佣金从万 2~万 5 对收益的影响
* 极端行情：单独回测 2022 年 4 月/10 月等波动期表现

#### ✅ 实时监测

* 多级预警：黄色（关注）→ 橙色（减仓）→ 红色（止损）
* 自动熔断：单日亏损>5% 时暂停新开仓
* 日志审计：所有调仓/预警操作记录到数据库，支持追溯

### 七、 实盘交易对接

> ✅ **架构原则**：适配器模式解耦券商 | 风控前置拦截 | 幂等防重复 | 干跑模拟优先 | 全链路可追溯  
> ⚠️ **合规提示**：实盘模块仅作为技术对接框架，实际接入需符合证监会/券商合规要求，建议先在模拟盘验证 ≥3 个月。


#### 实盘安全红线清单（必须遵守）

| 环节 | 安全机制 | 验证方法 |
|------|---------|---------|
| **资金安全** | `dry_run: true` 默认开启 | 启动日志必须显示 `🧪 [DRY-RUN]` |
| **防重复下单** | `client_order_id` 幂等 + UUID | 同一信号多次触发只生成1笔委托 |
| **前置风控** | 仓位/集中度/单日亏损/熔断 | 拦截日志必须记录 `🛑 风控拦截` |
| **异常处理** | 网络重试 ≤3 次 + 超时撤单 | 模拟断网测试订单状态机 |
| **数据同步** | 每日收盘 `sync_positions()` | 本地持仓 vs 券商持仓差异 < 0.1% |
| **操作留痕** | 订单流水 CSV/DB + Webhook 告警 | 每笔委托可追溯策略版本+时间戳 |

---

#### 上线前验证 checklist

- [ ] 模拟盘连续运行 ≥30 个交易日，无风控拦截误杀
- [ ] 断网重连后订单状态自动恢复，无重复委托
- [ ] 单日亏损达到 `-5%` 时自动停止交易
- [ ] 个股权重达到 `15%` 时禁止继续买入
- [ ] 订单超时 `300s` 未成交自动撤单
- [ ] 日志完整记录：策略信号→风控检查→券商回报→本地同步
- [ ] `dry_run: false` 切换实盘前，双人复核配置与权限

  **终极建议**：
> 
> 🔹 **先干跑，后实盘**：`dry_run: true` 验证逻辑，确认无误后再切换
> 🔹 **小资金试水**：首次实盘资金 ≤ 总资金 10%，观察 2 周再放大
> 🔹 **人工 oversight**：实盘初期保留“人工确认下单”开关，避免黑盒自动交易
> 🔹 **合规优先**：对接券商前确认 API 使用协议，保留完整审计日志
> 
> 🔁 **核心口诀**：
> > “风控前置拦截，幂等防重复，干跑验逻辑，实盘小步走”
