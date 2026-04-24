##### 场景 1：全流程运行（批量分析 + 自动深度分析首推标的）

```bash
# 执行全流程：批量分析 18 只 → 筛选推荐 → 自动分析首推标的
python dynamic_price_system/main.py --phase all --export html

# 输出:
# ✅ 阶段 1 完成 | 耗时: 28.45s | 推荐: 5 只
# 🔄 全流程模式：自动选择推荐标的 600938 进行深度分析
# ✅ 阶段 2 完成 | 标的:600938 | 耗时: 3.21s
# 📁 结果查看:
#   - output/analysis_results/latest/recommended_stocks.json
#   - output/visualization/phase1/portfolio_comparison.html
#   - output/visualization/phase2/600938_price_interval.html

```

##### 场景 2：仅执行阶段 1（批量分析 + 保存）

```bash

# 仅执行批量分析，保存结果供后续使用
python dynamic_price_system/main.py --phase 1 --filter-rule conservative --save-results

# 输出:
# ✅ 阶段 1 完成 | 耗时: 25.12s | 推荐: 3 只
# 🔗 创建 latest 软链接 -> 20260416
# 📁 结果查看:
#   - output/analysis_results/20260416/batch_results.json
#   - output/analysis_results/20260416/recommended_stocks.json

```

##### 场景 3：仅执行阶段 2（单标深度分析）

```bash

# 从保存的结果中加载 600938 进行深度分析
python dynamic_price_system/main.py --phase 2 --code 600938 --charts price_interval confidence_gauge diagnostics_tree

# 或指定历史版本分析
python dynamic_price_system/main.py --phase 2 --code 600938 --version 20260415

# 输出:
# ✅ 加载批量结果:18 只标的 | 版本:20260416
# ✅ 生成 600938 深度分析: ['price_interval', 'confidence_gauge', 'diagnostics_tree']
# 📁 结果查看:
#   - output/visualization/phase2/600938_price_interval.html

```

##### 场景 4：对比分析（标的 vs 板块/推荐列表）

``` bash

# 生成 600938 与油气开采板块均值的对比分析
python dynamic_price_system/main.py --phase 2 --code 600938 --charts comparison

# 输出:
# ✅ 生成对比分析: 600938_comparison.html
# 📊 对比结论:
#   • 600938 盈亏比 2.27x vs 板块均值 1.85x ✅
#   • 600938 置信度 1.015 vs 板块均值 0.998 ✅

```

##### 定时批量分析（Cron 示例）

```bash

# 每日 16:30 执行批量分析（收盘后）
30 16 * * 1-5 cd /home/ts/app/AiStock && \
  python dynamic_price_system/main.py \
    --phase 1 \
    --mode paper \
    --filter-rule default \
    --save-results \
    --skip-viz >> logs/phase1_daily.log 2>&1

```

##### 系统筛选逻辑 --filter-rule

* 使用默认规则
python dynamic_price_system/main.py --phase 1 --filter-rule default

* 使用保守规则
python dynamic_price_system/main.py --phase 1 --filter-rule conservative

* 使用板块定制规则
python dynamic_price_system/main.py --phase 1 --filter-rule sector_custom