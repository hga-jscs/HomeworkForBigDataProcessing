"""Spark batch framework: clean -> sequences -> patterns -> paired change tests.

Use spark-submit; storage URIs and cluster resources are supplied externally.
Only bounded quality summaries and candidate sufficient statistics reach driver.
"""
import argparse, datetime, hashlib, json, os, platform, sys, time
from pathlib import Path
from pyspark.sql import SparkSession, functions as F
from pyspark import StorageLevel
from pyspark.ml.fpm import PrefixSpan
from 数据适配 import adapt
from 模式分析 import make_trie, partition_counts, combine, statistics

VERSION = '2026-10-31.1'

def uri_join(base, *parts):
    return base.rstrip('/') + '/' + '/'.join(parts)

def write_json(spark, uri, value):
    path = spark._jvm.org.apache.hadoop.fs.Path(uri)
    fs = path.getFileSystem(spark._jsc.hadoopConfiguration())
    fs.mkdirs(path.getParent())
    stream = fs.create(path, True)
    try: stream.write(bytearray(json.dumps(value,ensure_ascii=False,indent=2,default=str).encode('utf-8')))
    finally: stream.close()

def read_json(spark, uri):
    path = spark._jvm.org.apache.hadoop.fs.Path(uri)
    fs = path.getFileSystem(spark._jsc.hadoopConfiguration())
    if not fs.exists(path): return None
    stream = fs.open(path)
    try:
        return json.loads(spark._jvm.org.apache.commons.io.IOUtils.toString(stream,'UTF-8'))
    finally: stream.close()

def fingerprint(config):
    return hashlib.sha256(json.dumps(config,sort_keys=True,ensure_ascii=False).encode()).hexdigest()

def root_uri(config):
    run_id = config['run_id']
    if not run_id or '/' in run_id or '\\' in run_id or run_id in ('.','..'):
        raise ValueError('run_id must be a single meaningful directory name')
    root = uri_join(config['output'], '运行批次', run_id)
    for key in ('transactions','articles'):
        if key in config and config[key].rstrip('/').startswith(root):
            raise ValueError('Input files must be outside the run output')
    return root

def run_stage(spark, config, name, operation):
    root = root_uri(config)
    marker = uri_join(root, name, '_完成.json')
    previous = read_json(spark, marker)
    sig = fingerprint(config)
    if previous:
        if previous['configuration_sha256'] != sig or previous['framework_version'] != VERSION:
            raise ValueError('Existing run configuration differs: choose a new run_id')
        print(json.dumps({'stage':name,'status':'verified_manifest_skip','metrics':previous['metrics']},ensure_ascii=False),flush=True)
        return previous['metrics']
    started = time.perf_counter()
    spark.sparkContext.setJobGroup(name,config['run_id'] + ': ' + name)
    metrics = operation(spark,config,root)
    metrics['wall_seconds'] = time.perf_counter()-started
    manifest = {'framework_version':VERSION,'configuration_sha256':sig,'configuration':config,
        'application_id':spark.sparkContext.applicationId,'spark_version':spark.version,
        'python_version':platform.python_version(),'java_version':spark._jvm.java.lang.System.getProperty('java.version'),
        'master':spark.sparkContext.master,'completed_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),
        'metrics':metrics}
    write_json(spark,marker,manifest)
    print(json.dumps({'stage':name,'status':'completed','metrics':metrics},ensure_ascii=False,default=str),flush=True)
    return metrics

def clean_stage(spark, config, root):
    judged, clean, notes = adapt(spark,config)
    quality = {r.quality:r['count'] for r in judged.groupBy('quality').count().collect()}
    rejected = judged.filter("quality != 'accepted'")
    rejected.write.mode('overwrite').parquet(uri_join(root,'清洗','隔离记录'))
    clean = clean.withColumn('event_year',F.year('event_time')).withColumn('event_month',F.month('event_time'))
    buckets = int(config.get('write_buckets',1))
    clean = clean.withColumn('_bucket',F.pmod(F.xxhash64('customer'),F.lit(buckets)))
    target = uri_join(root,'清洗','交易')
    (clean.repartition(config['partitions'],'event_year','event_month','_bucket').drop('_bucket')
        .write.mode('overwrite').option('maxRecordsPerFile',1000000).partitionBy('event_year','event_month').parquet(target))
    saved = spark.read.parquet(target)
    row = saved.agg(F.count('*').alias('rows'),F.countDistinct('customer').alias('customers'),
        F.countDistinct('product').alias('products'),F.countDistinct('item').alias('items'),
        F.min('event_time').cast('string').alias('first_date'),F.max('event_time').cast('string').alias('last_date')).first().asDict()
    monthly = [r.asDict() for r in saved.groupBy('event_year','event_month').count().orderBy('event_year','event_month').collect()]
    row.update({'raw_rows':sum(quality.values()),'quality':quality,'accepted_before_dedup':quality.get('accepted',0),
        'deduplicated_rows':quality.get('accepted',0)-row['rows'],'monthly':monthly,'contract':notes})
    return row

def sequence_stage(spark, config, root):
    periods = config['periods']
    if len(periods) != 2 or periods[0][1] > periods[1][0]:
        raise ValueError('Exactly two ordered non-overlapping half-open windows are required')
    for a,b in periods:
        if a >= b: raise ValueError('Invalid window boundaries')
    transactions = spark.read.parquet(uri_join(root,'清洗','交易'))
    # Explicit partition predicates enable year pruning before exact timestamp filters.
    years = sorted(set(y for a,b in periods for y in range(int(a[:4]),int(b[:4])+1)))
    selected = transactions.filter(F.col('event_year').isin(years))
    period = F.lit(None).cast('int')
    for i,(start,end) in reversed(list(enumerate(periods))):
        period = F.when((F.col('event_time')>=F.lit(start).cast('timestamp')) &
                        (F.col('event_time')<F.lit(end).cast('timestamp')),F.lit(i)).otherwise(period)
    selected = selected.withColumn('period',period).filter('period is not null')
    if config['granularity'] == 'day': selected = selected.withColumn('event_time',F.date_trunc('day','event_time'))
    elif config['granularity'] != 'timestamp': raise ValueError('granularity must be day or timestamp')
    baskets = selected.groupBy('customer','period','event_time').agg(F.sort_array(F.collect_set('item')).alias('items'),
        F.count('*').alias('transaction_rows'),F.sum('quantity').alias('units'))
    baskets.write.mode('overwrite').partitionBy('period').parquet(uri_join(root,'序列','购物篮'))
    baskets = spark.read.parquet(uri_join(root,'序列','购物篮'))
    sizes = baskets.groupBy('customer','period').agg(F.count('*').alias('baskets'),F.max(F.size('items')).alias('max_basket_items'))
    if sizes.filter((F.col('baskets')>config['max_baskets_per_customer']) |
                    (F.col('max_basket_items')>config['max_items_per_basket'])).limit(1).count():
        raise ValueError('Oversized customer/basket encountered; increase explicit limits or define a new cohort. No silent truncation.')
    minimum = int(config.get('min_baskets',2))
    cohort = sizes.groupBy('customer').agg(F.count('*').alias('periods'),F.min('baskets').alias('minimum_baskets'))
    cohort = cohort.filter((F.col('periods')==2)&(F.col('minimum_baskets')>=minimum)).select('customer')
    cohort = cohort.withColumn('split',F.when(F.pmod(F.conv(F.substring(F.sha2(F.concat(F.lit('sequence-v1:'),F.col('customer')),256),1,8),16,10).cast('long'),10)<5,'discovery').otherwise('evaluation'))
    cohort.write.mode('overwrite').parquet(uri_join(root,'序列','顾客队列'))
    paired = baskets.join(cohort,'customer','inner')
    sequences = paired.repartition(config['partitions'],'customer').groupBy('customer','period','split').agg(
        F.sort_array(F.collect_list(F.struct('event_time','items'))).alias('events'))
    sequences = sequences.withColumn('sequence',F.transform('events',lambda x:x['items'])).withColumn('basket_count',F.size('events'))
    sequences.write.mode('overwrite').partitionBy('period','split').parquet(uri_join(root,'序列','顾客序列'))
    saved = spark.read.parquet(uri_join(root,'序列','顾客序列'))
    summary = [r.asDict() for r in saved.groupBy('period','split').agg(F.count('*').alias('customers'),
        F.sum('basket_count').alias('baskets'),F.max('basket_count').alias('max_baskets'),
        F.expr('percentile_approx(basket_count, array(0.5,0.95,0.99))').alias('basket_quantiles')).orderBy('period','split').collect()]
    quality = [r.asDict() for r in baskets.groupBy('period').agg(F.count('*').alias('all_baskets'),
        F.sum('transaction_rows').alias('transaction_rows'),F.sum(F.size('items')).alias('basket_items')).orderBy('period').collect()]
    return {'cohort_customers':cohort.count(),'sequences':sum(r['customers'] for r in summary),
        'groups':summary,'windows':quality,'granularity':config['granularity']}

def mining_stage(spark, config, root):
    sequences = spark.read.parquet(uri_join(root,'序列','顾客序列'))
    discovery = sequences.filter("period = 0 and split = 'discovery'").select('sequence').persist(StorageLevel.MEMORY_AND_DISK)
    n = discovery.count()
    if n < 1: raise ValueError('Empty discovery cohort')
    model = PrefixSpan(minSupport=config['minimum_support'],maxPatternLength=config['maximum_length'],
                       maxLocalProjDBSize=config['max_local_projection_items'])
    patterns = model.findFrequentSequentialPatterns(discovery)
    # Native PrefixSpan permits multi-item itemsets; retain exactly the baseline's
    # language of singleton steps, each at a strictly later basket.
    patterns = patterns.filter(F.forall('sequence',lambda step:F.size(step)==1))
    patterns = patterns.withColumn('pattern',F.transform('sequence',lambda step:step[0]))
    patterns = patterns.withColumn('pattern_id',F.sha2(F.to_json('pattern'),256)).withColumn('support',F.col('freq')/F.lit(n))
    target = uri_join(root,'模式','发现模式')
    patterns.write.mode('overwrite').parquet(target)
    discovery.unpersist()
    saved = spark.read.parquet(target)
    counts = {str(r.length):r['count'] for r in saved.groupBy(F.size('pattern').alias('length')).count().collect()}
    return {'discovery_customers':n,'minimum_count':__import__('math').ceil(config['minimum_support']*n),
        'pattern_counts':counts,'language':'singleton-step sequences; no same-basket ordering',
        'engine':'Spark MLlib PrefixSpan','maxLocalProjDBSize':config['max_local_projection_items']}

def change_stage(spark, config, root):
    candidates = spark.read.parquet(uri_join(root,'模式','发现模式')).filter(F.size('pattern')>=2)
    count = candidates.count()
    if count > config['max_broadcast_patterns']:
        raise ValueError(f'{count} candidates exceed bounded catalogue limit; raise discovery threshold or budget explicitly')
    patterns = [(r.pattern_id,tuple(r.pattern)) for r in candidates.select('pattern_id','pattern').collect()]
    sequences = spark.read.parquet(uri_join(root,'序列','顾客序列')).filter("split = 'evaluation'")
    earlier = sequences.filter('period = 0').select('customer',F.col('sequence').alias('sequence0'))
    later = sequences.filter('period = 1').select('customer',F.col('sequence').alias('sequence1'))
    paired = earlier.join(later,'customer').repartition(config['partitions'],'customer').persist(StorageLevel.MEMORY_AND_DISK)
    n = paired.count()
    trie = spark.sparkContext.broadcast(make_trie(patterns))
    counts = paired.rdd.mapPartitions(lambda rows:partition_counts(rows,trie.value)).reduceByKey(combine,config['partitions']).collect()
    rows = statistics(patterns,counts,n)
    trie.destroy(); paired.unpersist()
    if rows:
        spark.createDataFrame(rows).repartition(min(config['partitions'],4)).write.mode('overwrite').parquet(uri_join(root,'变化','模式差异'))
    write_json(spark,uri_join(root,'变化','完整统计.json'),rows)
    significant = [r for r in rows if r['q_by']<=.05]
    return {'evaluation_customers':n,'tested_patterns':len(rows),'significant_by':len(significant),
        'increased':sum(r['delta']>0 for r in significant),'decreased':sum(r['delta']<0 for r in significant),
        'top_changes':sorted(significant,key=lambda r:r['log10_q_by'])[:12],
        'collection_boundary':'bounded candidate catalogue and aggregated pattern counts only; no raw customers collected'}

STAGES = [('清洗',clean_stage),('序列',sequence_stage),('模式',mining_stage),('变化',change_stage)]

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--config',required=True)
    parser.add_argument('--stage',choices=['全部']+[s for s,_ in STAGES],default='全部')
    args = parser.parse_args()
    config = json.loads(Path(args.config).read_text(encoding='utf-8-sig'))
    project = str(Path(__file__).resolve().parent.parent)
    config = json.loads(json.dumps(config,ensure_ascii=False).replace('{project}',os.environ.get('SEQUENCE_PROJECT',project)))
    spark = (SparkSession.builder.appName('事件序列-'+config['run_id'])
        .config('spark.sql.session.timeZone','UTC').config('spark.sql.shuffle.partitions',str(config['partitions']))
        .config('spark.sql.adaptive.enabled','true').config('spark.sql.parquet.compression.codec','snappy')
        .config('spark.sql.files.maxPartitionBytes',str(64*1024**2)).getOrCreate())
    spark.sparkContext.setLogLevel('WARN')
    try:
        for name,operation in STAGES:
            if args.stage in ('全部',name):
                # Require committed upstream manifests, including identical configuration.
                for prerequisite,_ in STAGES[:[x[0] for x in STAGES].index(name)]:
                    marker = read_json(spark,uri_join(root_uri(config),prerequisite,'_完成.json'))
                    if marker is None or marker['configuration_sha256'] != fingerprint(config):
                        raise ValueError('Missing or inconsistent upstream stage: '+prerequisite)
                run_stage(spark,config,name,operation)
    finally: spark.stop()

if __name__ == '__main__': main()
