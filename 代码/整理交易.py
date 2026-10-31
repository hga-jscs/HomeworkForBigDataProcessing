from 公共设置 import ROOT, save_json, discovery
import duckdb, time, platform, sys, json
import psutil

def main():
    start = time.perf_counter()
    con = duckdb.connect(str(ROOT / '数据' / '交易仓库.duckdb'))
    con.execute("SET threads=4; SET memory_limit='2GB'; SET preserve_insertion_order=false")
    con.execute("SET temp_directory=?", [str(ROOT / '临时文件' / '数据库溢写')])
    con.execute('CREATE OR REPLACE TABLE raw AS SELECT * FROM read_csv(?, all_varchar=true)', [str(ROOT / '数据' / '原始交易.csv')])
    con.execute('''CREATE OR REPLACE TABLE typed AS SELECT invoice, upper(trim(stock)) stock,
        description, try_cast(quantity AS DOUBLE) quantity, try_cast(time AS TIMESTAMP) time,
        try_cast(price AS DOUBLE) price, try_cast(customer AS BIGINT) customer, country FROM raw''')
    checks = [
        ('原始明细', 'true'),
        ('顾客和时间有效', 'customer IS NOT NULL AND time IS NOT NULL'),
        ('非撤销且数量为正', "customer IS NOT NULL AND time IS NOT NULL AND NOT starts_with(upper(invoice),'C') AND quantity>0"),
        ('单价为正', "customer IS NOT NULL AND time IS NOT NULL AND NOT starts_with(upper(invoice),'C') AND quantity>0 AND price>0"),
        ('标准商品编码', "customer IS NOT NULL AND time IS NOT NULL AND NOT starts_with(upper(invoice),'C') AND quantity>0 AND price>0 AND regexp_full_match(stock, '[0-9]{5}[A-Z]{0,2}')")]
    counts = [{'stage':label, 'rows':con.execute('SELECT count(*) FROM typed WHERE '+condition).fetchone()[0]} for label,condition in checks]
    con.execute('CREATE OR REPLACE TABLE clean AS SELECT DISTINCT * FROM typed WHERE '+checks[-1][1])
    counts.append({'stage':'完整字段去重', 'rows':con.execute('SELECT count(*) FROM clean').fetchone()[0]})
    export = (ROOT / '数据' / '分区交易').as_posix().replace("'", "''")
    con.execute(f"COPY (SELECT *, year(time) AS event_year, month(time) AS event_month FROM clean) TO '{export}' (FORMAT PARQUET, PARTITION_BY(event_year,event_month), OVERWRITE_OR_IGNORE)")
    con.execute('''CREATE OR REPLACE TABLE baskets AS SELECT customer, time, year(time) AS event_year,
        list(DISTINCT stock ORDER BY stock) items, count(DISTINCT invoice) invoices
        FROM clean WHERE month(time) BETWEEN 1 AND 11 AND year(time) IN (2010,2011)
        GROUP BY customer,time''')
    con.execute('''CREATE OR REPLACE TABLE cohort AS SELECT customer FROM
        (SELECT customer,event_year,count(*) n FROM baskets GROUP BY customer,event_year)
        GROUP BY customer HAVING count(*)=2 AND min(n)>=2''')
    rows = con.execute('''SELECT b.customer,b.event_year,b.time,b.items FROM baskets b JOIN cohort c USING(customer)
        ORDER BY b.customer,b.event_year,b.time''').fetchall()
    customers = {}
    for customer,year,timestamp,items in rows:
        entry = customers.setdefault(str(customer), {'split':'discovery' if discovery(customer) else 'evaluation', '2010':[], '2011':[]})
        entry[str(year)].append({'time':timestamp.isoformat(), 'items':items})
    save_json('顾客序列.json', customers, folder='数据')
    descriptions = dict(con.execute('SELECT stock, mode(description) FROM clean GROUP BY stock').fetchall())
    save_json('商品说明.json', descriptions, folder='数据')
    period_rows = con.execute('''SELECT year(time),count(*),count(DISTINCT customer),count(DISTINCT invoice),count(DISTINCT stock)
        FROM clean WHERE month(time) BETWEEN 1 AND 11 AND year(time) IN (2010,2011) GROUP BY 1 ORDER BY 1''').fetchall()
    summary = {'cleaning':counts, 'period_rows':[dict(zip(['year','rows','customers','invoices','products'],r)) for r in period_rows],
        'customers_paired':len(customers), 'discovery':sum(v['split']=='discovery' for v in customers.values()),
        'evaluation':sum(v['split']=='evaluation' for v in customers.values()),
        'multiple_invoice_ties':con.execute('SELECT count(*) FROM baskets WHERE invoices>1').fetchone()[0],
        'all_baskets':con.execute('SELECT count(*) FROM baskets').fetchone()[0],
        'paired_baskets':len(rows), 'seconds':time.perf_counter()-start,
        'process_peak_working_set_bytes':psutil.Process().memory_info().peak_wset,
        'memory_limit':'2GB','threads':4,'duckdb':duckdb.__version__}
    save_json('数据整理.json', summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2), flush=True)
    con.close()

if __name__ == '__main__':
    main()
