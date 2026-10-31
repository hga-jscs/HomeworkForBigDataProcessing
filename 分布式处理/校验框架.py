"""Independent semantics checks and cross-engine regression on real retail data."""
import csv, itertools, json, random, sys
from collections import Counter
from pathlib import Path
from pyspark.sql import SparkSession, functions as F
from pyspark.ml.fpm import PrefixSpan
from 数据适配 import fashion, ARTICLE_COLUMNS
from 模式分析 import make_trie, matches, statistics

ROOT = Path(__file__).resolve().parent.parent

def brute(sequence, maximum=3):
    found = set()
    for length in range(1,maximum+1):
        for positions in itertools.combinations(range(len(sequence)),length):
            found.update(itertools.product(*(sequence[p] for p in positions)))
    return found

def checks(spark):
    result = {}
    rng = random.Random(20261031)
    sequences = [[sorted(rng.sample(['A','B','C','D'],rng.randint(1,3)))
                  for _ in range(rng.randint(1,5))] for _ in range(40)]
    counts = Counter(p for seq in sequences for p in brute(seq))
    expected = {p:n for p,n in counts.items() if n >= 8}
    df = spark.createDataFrame([(s,) for s in sequences],['sequence']).repartition(4)
    native = PrefixSpan(minSupport=.2,maxPatternLength=3,maxLocalProjDBSize=2000).findFrequentSequentialPatterns(df)
    actual = {tuple(step[0] for step in r.sequence):r.freq for r in native.collect() if all(len(x)==1 for x in r.sequence)}
    assert actual == expected, 'MLlib singleton-step semantics differ from exhaustive enumeration'
    all_patterns = [(str(i),p) for i,p in enumerate(sorted(counts))]
    trie = make_trie(all_patterns)
    for sequence in sequences:
        assert matches(sequence,trie) == {i for i,p in all_patterns if p in brute(sequence)}
    assert matches([['A','B']],make_trie([('AB',('A','B'))])) == set()
    assert matches([['A'],['A']],make_trie([('AA',('A','A'))])) == {'AA'}
    result['exhaustive_patterns_checked'] = len(actual)
    result['independent_trie_sequence_cases'] = len(sequences)+2

    fixture = ROOT/'临时文件'/'适配校验'
    fixture.mkdir(parents=True,exist_ok=True)
    articles = fixture/'商品.csv'
    with articles.open('w',encoding='utf-8',newline='') as file:
        writer = csv.DictWriter(file,fieldnames=ARTICLE_COLUMNS); writer.writeheader()
        writer.writerows([{'article_id':'0100000001','product_type_no':'1','product_type_name':'A'},
                         {'article_id':'0100000002','product_type_no':'2','product_type_name':'B'}])
    transaction_file = fixture/'交易.csv'
    customer = 'a'*64
    rows = [('2019-01-01',customer,'0100000001','.1','1'),
            ('2019-01-01',customer,'0100000001','.1','1'),
            ('2019-01-01',customer,'0100000002','.2','1'),
            ('2019-01-02',customer,'0100000002','.2','2'),
            ('bad-date',customer,'0100000001','.1','1'),
            ('2019-01-01',customer,'0100000009','.1','1')]
    rng.shuffle(rows)
    with transaction_file.open('w',encoding='utf-8',newline='') as file:
        writer=csv.writer(file);writer.writerow(['t_dat','customer_id','article_id','price','sales_channel_id']);writer.writerows(rows)
    config = {'transactions':str(transaction_file),'articles':str(articles),'granularity':'day','item_level':'product_type'}
    judged,clean,_ = fashion(spark,config)
    quality={r.quality:r['count'] for r in judged.groupBy('quality').count().collect()}
    assert quality == {'accepted':4,'invalid_customer_or_date':1,'unmatched_article':1}
    assert clean.count()==4, 'Identical purchase units must not be discarded'
    def make_sequence(frame):
        return [sorted(r.items) for r in frame.groupBy('event_time').agg(F.collect_set('item').alias('items')).orderBy('event_time').collect()]
    first = make_sequence(clean.repartition(1))
    second = make_sequence(clean.orderBy(F.rand(17)).repartition(4))
    assert first == second == [['type:1','type:2'],['type:2']]
    assert matches(first,make_trie([('forward',('type:1','type:2')),('reverse',('type:2','type:1'))])) == {'forward'}
    result['fashion_contract'] = {'rows_preserved':4,'days':2,'invalid_isolated':2,'repartition_order_invariant':True}

    # Real-data equivalence is bounded to the existing, explicitly counted 1548-customer reference.
    warehouse = ROOT/'数据'/'分布式仓库'/'运行批次'/'零售分钟'
    reference = json.loads((ROOT/'数据'/'顾客序列.json').read_text(encoding='utf-8'))
    actual_sequences = spark.read.parquet(str(warehouse/'序列'/'顾客序列'))
    assert actual_sequences.count() == 2*len(reference) == 3096
    for row in actual_sequences.collect():
        expected_events = reference[row.customer][str(2010+row.period)]
        assert row.split == reference[row.customer]['split']
        assert [sorted(x.items) for x in row.events] == [sorted(x['items']) for x in expected_events]
        assert [x.event_time.isoformat() for x in row.events] == [x['time'] for x in expected_events]
    sys.path.insert(0,str(ROOT/'代码'))
    from 序列算法 import mine_sequences
    discovery = [[x['items'] for x in v['2010']] for v in reference.values() if v['split']=='discovery']
    # Retained prefix-projection implementation is independent of Spark MLlib.
    baseline = mine_sequences(discovery,.05,3)
    spark_patterns = spark.read.parquet(str(warehouse/'模式'/'发现模式'))
    patterns = {tuple(r.pattern):r.freq for r in spark_patterns.collect()}
    assert patterns == baseline
    records=json.loads((warehouse/'变化'/'完整统计.json').read_text(encoding='utf-8'))
    old_records=json.loads((ROOT/'结果'/'跨年变化.json').read_text(encoding='utf-8'))
    old = {tuple(r['pattern']):r for r in old_records}
    for record in records:
        previous = old[tuple(record['pattern'])]
        assert record['count0']==previous['count2010'] and record['count1']==previous['count2011']
        assert abs(record['p']-previous['p']) < 1e-12
    # BY differs because 5% and 2% thresholds define different test families.
    result['retail_real_data']={'customer_period_sequences':3096,'patterns_and_supports':len(patterns),
                              'paired_counts_and_pvalues':len(records),'by_family_note':'5% family has 1048 tests; old 2% family has 46740'}
    # Spark timestamps are stored correctly, but naive Python datetime conversion
    # in an earlier launcher displayed UTC instants in the host's +08 zone. Audit
    # the stored columns and correct only the human-readable manifest fields.
    from 作业 import read_json,write_json
    corrections=[]
    for run in ('零售分钟','服装日级','零售日级'):
        base=ROOT/'数据'/'分布式仓库'/'运行批次'/run
        if not (base/'清洗'/'_完成.json').exists():continue
        stored=spark.read.parquet(str(base/'清洗'/'交易'))
        correct=stored.agg(F.min('event_time').cast('string').alias('first_date'),
                          F.max('event_time').cast('string').alias('last_date')).first().asDict()
        manifest=read_json(spark,str(base/'清洗'/'_完成.json'))
        before={k:manifest['metrics'][k] for k in correct}
        if before!=correct:
            corrections.append({'run':run,'original_host_display':before,'verified_utc_display':correct})
            manifest['metrics'].update(correct)
            manifest['timestamp_display_audit']='corrected against stored Parquet in UTC; transactions, cohorts, statistics and timings unchanged'
            write_json(spark,str(base/'清洗'/'_完成.json'),manifest)
    result['timestamp_display_audit']=corrections
    numerical=[]
    for run in ('零售分钟','服装日级','零售日级'):
        base=ROOT/'数据'/'分布式仓库'/'运行批次'/run
        if not (base/'变化'/'_完成.json').exists():continue
        records=read_json(spark,str(base/'变化'/'完整统计.json'))
        pairs=[(r['pattern_id'],r['pattern']) for r in records]
        sufficient=[(r['pattern_id'],tuple(r[k] for k in ['count0','count1','discordant0','discordant1'])) for r in records]
        fixed=statistics(pairs,sufficient,records[0]['customers'])
        assert sum(r['q_by']<=.05 for r in fixed)==sum(r['q_by']<=.05 for r in records)
        assert all(__import__('math').isfinite(r['log10_p']) for r in fixed)
        if any('log10_p' not in r for r in records):
            spark.createDataFrame(fixed).coalesce(4).write.mode('overwrite').parquet(str(base/'变化'/'模式差异'))
            write_json(spark,str(base/'变化'/'完整统计.json'),fixed)
            marker=read_json(spark,str(base/'变化'/'_完成.json'))
            marker['metrics']['top_changes']=sorted([r for r in fixed if r['q_by']<=.05],key=lambda r:r['log10_q_by'])[:12]
            marker['numerical_audit']='Added log-space exact binomial tails and BY correction from saved sufficient statistics; cohort, counts, decisions and original stage timing unchanged'
            write_json(spark,str(base/'变化'/'_完成.json'),marker)
        numerical.append({'run':run,'patterns':len(fixed),'ordinary_p_underflows':sum(r['p_underflow'] for r in fixed),
                          'all_log_p_finite':True,'decisions_unchanged':True})
    result['numerical_stability']=numerical
    path = ROOT/'结果'/'分布式校验.json'
    path.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(result,ensure_ascii=False),flush=True)
    return result

if __name__ == '__main__':
    spark = SparkSession.builder.appName('事件序列独立校验').config('spark.sql.session.timeZone','UTC').config('spark.sql.shuffle.partitions',4).getOrCreate()
    spark.sparkContext.setLogLevel('ERROR')
    try: checks(spark)
    finally: spark.stop()
