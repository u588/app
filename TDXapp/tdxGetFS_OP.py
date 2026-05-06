import pandas as pd
from sqlalchemy import create_engine, text
from pytdx.hq import TdxHq_API
from pytdx.crawler.base_crawler import demo_reporthook
from pytdx.crawler.history_financial_crawler import HistoryFinancialCrawler

conn = create_engine('postgresql+psycopg://sa:11111111@10.3.18.56/tdxFS')
api = TdxHq_API()
api.connect('119.147.212.81', 7709)

ls = ['gpcw20251231.zip', 'gpcw20260331.zip']
datacrawler = HistoryFinancialCrawler()
pd.set_option('display.max_columns', None)

for i in ls:
    # ======== 第1步：下载 + 解析（原逻辑不变）========
    result = datacrawler.fetch_and_parse(
        reporthook=demo_reporthook,
        filename=i,
        path_to_download="/tmp/tmpfile.zip"
    )
    dd = datacrawler.to_df(data=result)
    dd = dd[dd.columns[:582]]
    dd['report_date'] = dd['report_date'].astype(object)
    upday = dd['report_date'].iloc[0]
    dd = dd.round(2)

    # 整表写入（原逻辑不变）
    dd.to_sql(i[:12], conn, if_exists='replace')

    # ======== 第2步：批量查询已有表的最大 report_date（1次SQL替代N次）========
    stock_codes = dd.index.values.tolist()
    
    # 用 information_schema 一次性获取所有已存在的表名
    with conn.connect() as c:
        existing_tables = pd.read_sql(text("""
            SELECT table_name FROM information_schema.tables 
            WHERE table_schema = 'public'
        """), c)['table_name'].tolist()
    
    # 构建 {股票代码: 最新report_date} 的字典（只查已存在的表）
    existing_max_date = {}
    existing_stocks = [s for s in stock_codes if s in existing_tables]
    
    if existing_stocks:
        # 批量查询：用 UNION ALL 一次查出所有表的最新日期
        union_parts = []
        for code in existing_stocks:
            # 对表名做安全检查（防止SQL注入）
            safe_code = code.replace("'", "''")
            union_parts.append(
                f"SELECT '{safe_code}' AS stock_code, MAX(report_date) AS max_date FROM \"{safe_code}\""
            )
        
        # 分批执行，每批200个表（避免SQL过长）
        batch_size = 200
        for batch_start in range(0, len(union_parts), batch_size):
            batch_sql = " UNION ALL ".join(union_parts[batch_start:batch_start + batch_size])
            with conn.connect() as c:
                batch_result = pd.read_sql(text(batch_sql), c)
            for _, row in batch_result.iterrows():
                existing_max_date[row['stock_code']] = row['max_date']

    # ======== 第3步：分类——更新 / 新增 / 跳过 ========
    to_update = {}   # {股票代码: DataFrame行}
    to_insert = {}   # {股票代码: DataFrame行}
    skipped = []

    for code in stock_codes:
        row_df = dd.loc[[code]].reset_index(drop=True).set_index('report_date')  # 取单行但保持DataFrame
        if code in existing_max_date:
            if upday > existing_max_date[code]:
                to_update[code] = row_df
            else:
                skipped.append(code)
        else:
            to_insert[code] = row_df

    # ======== 第4步：批量写入更新数据 ========
    update_count = 0
    for code, row_df in to_update.items():
        row_df.copy().to_sql(code, conn, if_exists='append', index=True)
        update_count += 1
    if update_count:
        print(f"[{i}] Updated: {update_count} stocks")

    # ======== 第5步：批量写入新增数据 ========
    insert_count = 0
    for code, row_df in to_insert.items():
        row_df.copy().to_sql(code, conn, if_exists='append', index=True)
        insert_count += 1
    if insert_count:
        print(f"[{i}] New: {insert_count} stocks")

    # ======== 汇总日志 ========
    print(f"[{i}] Total: {len(stock_codes)} | Updated: {update_count} | "
          f"New: {insert_count} | Skipped: {len(skipped)}")

conn.dispose()
api.disconnect()