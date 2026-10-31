"""Controlled Spark comparisons: four Python kernels + native MLlib baseline.

All kernels use the same exact two-pass partition/union/count strategy. Raw
customers never collect to the driver. Native MLlib is an engineering reference,
not a fifth algorithm or a language-controlled kernel comparison.
"""
import argparse,hashlib,json,math,os,platform,random,resource,time,traceback
from pathlib import Path
from collections import Counter
from pyspark import StorageLevel,TaskContext
from pyspark.sql import SparkSession,functions as F
from pyspark.ml.fpm import PrefixSpan
from 算法内核 import ALGORITHMS,mine,threshold,trie_build,trie_matches

ROOT=Path(__file__).resolve().parent.parent
METHODS=list(ALGORITHMS)+['MLlib']

def write(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    temporary=path.with_suffix(path.suffix+'.写入中')
    temporary.write_text(json.dumps(value,ensure_ascii=False,indent=2),encoding='utf-8')
    temporary.replace(path)

def digest(patterns):
    data=json.dumps([[list(pattern),count] for pattern,count in sorted(patterns.items())],ensure_ascii=False,separators=(',',':')).encode()
    return hashlib.sha256(data).hexdigest()

def local_patterns(rows,algorithm,support,maximum):
    loaded=time.perf_counter()
    sequences=[row.sequence for row in rows]
    load_seconds=time.perf_counter()-loaded
    started=time.perf_counter();cpu=time.process_time()
    patterns,details=mine(algorithm,sequences,support,maximum)
    elapsed=time.perf_counter()-started;cpu_elapsed=time.process_time()-cpu
    # Materialize result rows before measuring the high-water RSS.
    prepared=[('pattern',pattern) for pattern in patterns]
    details.update({'partition':TaskContext.get().partitionId(),'process_id':os.getpid(),
        'load_seconds':load_seconds,'kernel_seconds':elapsed,'kernel_cpu_seconds':cpu_elapsed,
        'peak_python_rss_bytes':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024})
    yield ('summary',json.dumps(details))
    yield from prepared

def count_partition(rows,trie):
    counts=Counter()
    for row in rows:counts.update(trie_matches(row.sequence,trie))
    yield from counts.items()

def partition_mine(frame,algorithm,support,maximum,partitions,maximum_candidates):
    local=frame.select('sequence').rdd.mapPartitions(lambda rows:local_patterns(rows,algorithm,support,maximum))
    local.persist(StorageLevel.MEMORY_AND_DISK)
    candidates=None;broadcast=None
    started=time.perf_counter()
    try:
        summaries=[json.loads(x[1]) for x in local.filter(lambda x:x[0]=='summary').collect()]
        candidates=local.filter(lambda x:x[0]=='pattern').map(lambda x:x[1]).distinct(partitions).persist(StorageLevel.MEMORY_AND_DISK)
        number=candidates.count()
        if number>maximum_candidates:raise RuntimeError(f'Candidate union {number} exceeds explicit driver catalogue limit {maximum_candidates}')
        patterns=sorted(candidates.collect())
        local_phase=time.perf_counter()-started
        broadcast=frame.sparkSession.sparkContext.broadcast(trie_build(patterns))
        verification_started=time.perf_counter()
        counts=frame.select('sequence').rdd.mapPartitions(lambda rows:count_partition(rows,broadcast.value)).reduceByKey(lambda x,y:x+y,partitions).collect()
        minimum=threshold(support,sum(r['customers'] for r in summaries))
        result={patterns[index]:count for index,count in counts if count>=minimum}
        verify_seconds=time.perf_counter()-verification_started
        metrics={'local_and_union_seconds':local_phase,'global_count_seconds':verify_seconds,
            'candidate_union':number,'partition_metrics':sorted(summaries,key=lambda r:r['partition']),
            'kernel_seconds_sum':sum(r['kernel_seconds'] for r in summaries),
            'kernel_seconds_max':max(r['kernel_seconds'] for r in summaries),
            'kernel_cpu_seconds_sum':sum(r['kernel_cpu_seconds'] for r in summaries),
            'peak_single_python_worker_bytes':max(r['peak_python_rss_bytes'] for r in summaries)}
        return result,metrics
    finally:
        if broadcast is not None:broadcast.destroy()
        if candidates is not None:candidates.unpersist(blocking=True)
        local.unpersist(blocking=True)

def native_mine(frame,support,maximum):
    output=PrefixSpan(minSupport=support,maxPatternLength=maximum,maxLocalProjDBSize=200000).findFrequentSequentialPatterns(frame.select('sequence'))
    rows=output.filter(F.forall('sequence',lambda step:F.size(step)==1)).collect()
    return {tuple(step[0] for step in row.sequence):row.freq for row in rows}, {'native_language_note':'MLlib internally also explores multi-item itemsets; output is filtered to singleton steps',
        'peak_single_python_worker_bytes':None,'kernel_seconds_sum':None,'kernel_seconds_max':None}

def scenario_frame(spark,scenario,partitions):
    name='零售分钟' if scenario['dataset']=='retail' else '服装日级'
    source=ROOT/'数据'/'分布式仓库'/'运行批次'/name/'序列'/'顾客序列'
    frame=spark.read.parquet(str(source)).filter("period=0 and split='discovery'").select('customer','sequence')
    if scenario.get('fraction',100)<100:
        selection=F.pmod(F.conv(F.substring(F.sha2(F.concat(F.lit('benchmark-v1:'),F.col('customer')),256),1,8),16,10).cast('long'),100)
        frame=frame.filter(selection<scenario['fraction'])
    frame=frame.repartition(partitions,'customer').persist(StorageLevel.MEMORY_AND_DISK)
    descriptor=frame.agg(F.count('*').alias('customers'),F.sum(F.size('sequence')).alias('baskets'),
        F.sum(F.aggregate('sequence',F.lit(0),lambda n,b:n+F.size(b))).alias('item_occurrences')).first().asDict()
    descriptor['source']=str(source)
    return frame,descriptor

def scenarios(phase):
    common=[{'name':'零售全量','dataset':'retail','fraction':100,'support':.05,'maximum':3,'repeats':3},
            {'name':'服装全量','dataset':'fashion','fraction':100,'support':.05,'maximum':3,'repeats':3}]
    if phase=='pilot':
        return [dict(common[0],repeats=1),dict(common[1],name='服装试跑',fraction=10,repeats=1)]
    return common+[
        {'name':'服装十分之一','dataset':'fashion','fraction':10,'support':.05,'maximum':3,'repeats':3},
        {'name':'服装二分之一','dataset':'fashion','fraction':50,'support':.05,'maximum':3,'repeats':3},
        {'name':'服装低阈值','dataset':'fashion','fraction':100,'support':.02,'maximum':3,'repeats':1},
        {'name':'服装高阈值','dataset':'fashion','fraction':100,'support':.10,'maximum':3,'repeats':1},
        {'name':'服装两步','dataset':'fashion','fraction':100,'support':.05,'maximum':2,'repeats':1}]

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--phase',choices=['pilot','formal'],default='formal')
    parser.add_argument('--partitions',type=int,default=4);parser.add_argument('--only',default='')
    args=parser.parse_args();folder=ROOT/'结果'/'算法比较'/('试跑' if args.phase=='pilot' else '正式')
    program_hash={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in [Path(__file__),Path(__file__).with_name('算法内核.py')]}
    protocol={'phase':args.phase,'seed':20261101,'partitions':args.partitions,'maximum_driver_candidates':250000,
        'pattern_language':'singleton steps, strict later baskets, unlimited gaps; all lengths 1..maximum',
        'algorithms':METHODS,'scenarios':scenarios(args.phase),'source_sha256':program_hash,
        'timing':'cached input; total includes local discovery, candidate union, exact global support and cleanup; file output excluded',
        'memory':'maximum Linux high-water RSS of one freshly started Python local-mining worker, including input materialization; not JVM/system peak',
        'native_comparison':'different implementation and distributed strategy; engineering reference only'}
    if (folder/'实验协议.json').exists():
        old=json.loads((folder/'实验协议.json').read_text(encoding='utf-8'))
        if old!=protocol:raise RuntimeError('Protocol/source changed: use a new result directory, never mix benchmark versions')
    write(folder/'实验协议.json',protocol)
    spark=(SparkSession.builder.appName('序列算法比较-'+args.phase)
        .config('spark.sql.shuffle.partitions',args.partitions).config('spark.sql.session.timeZone','UTC')
        .config('spark.sql.adaptive.enabled','false').config('spark.python.worker.reuse','false').getOrCreate())
    spark.sparkContext.setLogLevel('ERROR')
    environment={'application_id':spark.sparkContext.applicationId,'master':spark.sparkContext.master,'spark':spark.version,
        'python':platform.python_version(),'platform':platform.platform(),'java':spark._jvm.java.lang.System.getProperty('java.version'),
        'logical_cpus_visible':os.cpu_count(),'physical_memory_visible_bytes':os.sysconf('SC_PAGE_SIZE')*os.sysconf('SC_PHYS_PAGES'),
        'worker_reuse':False,'partitions':args.partitions}
    write(folder/('环境-'+spark.sparkContext.applicationId+'.json'),environment)
    try:
        warm=spark.createDataFrame([(str(i),[['A','B'],['B','C'],['A','C']]) for i in range(16)],['customer','sequence']).repartition(args.partitions,'customer').cache()
        warm.count()
        expected=None
        for method in METHODS:
            result,_=native_mine(warm,.2,3) if method=='MLlib' else partition_mine(warm,method,.2,3,args.partitions,250000)
            if expected is None:expected=result
            else:assert result==expected,'Warmup output disagreement'
        warm.unpersist(blocking=True)
        for scenario in protocol['scenarios']:
            if args.only and scenario['name'] not in args.only.split(','):continue
            frame,descriptor=scenario_frame(spark,scenario,args.partitions)
            expected=None
            # Resume only frozen protocol/results. Cache preparation and warmup are repeated.
            for file in (folder/'原始记录').glob(scenario['name']+'_*_第1次.json') if (folder/'原始记录').exists() else []:
                record=json.loads(file.read_text(encoding='utf-8'))
                if record.get('status')=='complete':
                    saved=json.loads((folder/record['patterns_file']).read_text(encoding='utf-8'))
                    expected={tuple(x[0]):x[1] for x in saved};break
            base=list(METHODS);random.Random(20261101+len(scenario['name'])).shuffle(base)
            for repeat in range(1,scenario['repeats']+1):
                offset=((repeat-1)*2)%len(base);order=base[offset:]+base[:offset]
                for position,method in enumerate(order):
                    filename=f'{scenario["name"]}_{method}_第{repeat}次.json';target=folder/'原始记录'/filename
                    if target.exists() and json.loads(target.read_text(encoding='utf-8')).get('status')=='complete':continue
                    spark.sparkContext.setJobGroup(filename,filename)
                    print(json.dumps({'start':filename,'customers':descriptor['customers']},ensure_ascii=False),flush=True)
                    began=time.perf_counter()
                    try:
                        output,metrics=native_mine(frame,scenario['support'],scenario['maximum']) if method=='MLlib' else partition_mine(frame,method,scenario['support'],scenario['maximum'],args.partitions,250000)
                        elapsed=time.perf_counter()-began
                        if expected is None:expected=output
                        if output!=expected:
                            difference=[{'pattern':list(p),'expected':expected.get(p),'actual':output.get(p)} for p in set(expected)|set(output) if expected.get(p)!=output.get(p)]
                            write(folder/'不一致.json',difference)
                            raise AssertionError(f'Pattern/support mismatch: {len(difference)}')
                        pattern_name=f'完整模式/{scenario["name"]}_{method}.json'
                        if repeat==1:write(folder/pattern_name,[[list(p),n] for p,n in sorted(output.items())])
                        record={'status':'complete','scenario':scenario,'method':method,'repeat':repeat,'order_position':position,
                            'application_id':spark.sparkContext.applicationId,'input':descriptor,'wall_seconds':elapsed,
                            'patterns':len(output),'counts_by_length':dict(Counter(len(p) for p in output)),
                            'result_sha256':digest(output),'exactly_equal_to_other_methods':True,'patterns_file':pattern_name,**metrics}
                        write(target,record)
                        print(json.dumps({'done':filename,'seconds':round(elapsed,3),'patterns':len(output),'worker_peak_MiB':round(metrics['peak_single_python_worker_bytes']/1024**2,1) if metrics['peak_single_python_worker_bytes'] else None},ensure_ascii=False),flush=True)
                    except Exception as error:
                        write(target,{'status':'failed','scenario':scenario,'method':method,'repeat':repeat,'elapsed_seconds':time.perf_counter()-began,'error':repr(error),'traceback':traceback.format_exc()})
                        raise
            frame.unpersist(blocking=True)
    finally:spark.stop()

if __name__=='__main__':main()
