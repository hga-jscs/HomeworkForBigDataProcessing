"""Audit frozen experiment evidence and summarize repeated measurements."""
import hashlib,json,statistics
from collections import Counter
from pathlib import Path

ROOT=Path(__file__).resolve().parent.parent
FOLDER=ROOT/'结果'/'算法比较'/'正式'

def read(path):return json.loads(path.read_text(encoding='utf-8'))
def sha(path):
    digest=hashlib.sha256()
    with path.open('rb') as handle:
        for block in iter(lambda:handle.read(1024*1024),b''):digest.update(block)
    return digest.hexdigest()
def write(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(value,ensure_ascii=False,indent=2),encoding='utf-8')
def spread(values):
    return {'median':statistics.median(values),'minimum':min(values),'maximum':max(values),'values':values}

def application_metrics(application):
    directory=ROOT/'结果'/'算法比较'/'事件日志'/('eventlog_v2_'+application)
    result={'application_id':application,'tasks':0,'failed_tasks':0,'executor_tasks':{},
            'shuffle_write_bytes':0,'shuffle_read_bytes':0,'disk_spill_bytes':0,
            'application_finished':False,'scope':'all application tasks, including warmup and input preparation'}
    for file in sorted(directory.glob('events_*')):
        with file.open(encoding='utf-8') as handle:
            for line in handle:
                event=json.loads(line)
                if event.get('Event')=='SparkListenerApplicationEnd':result['application_finished']=True
                if event.get('Event')!='SparkListenerTaskEnd':continue
                info=event['Task Info'];metrics=event.get('Task Metrics',{})
                result['tasks']+=1
                if event.get('Task End Reason',{}).get('Reason')!='Success':result['failed_tasks']+=1
                executor=info.get('Executor ID','unknown')
                result['executor_tasks'][executor]=result['executor_tasks'].get(executor,0)+1
                result['shuffle_write_bytes']+=metrics.get('Shuffle Write Metrics',{}).get('Shuffle Bytes Written',0)
                reads=metrics.get('Shuffle Read Metrics',{})
                result['shuffle_read_bytes']+=reads.get('Remote Bytes Read',0)+reads.get('Local Bytes Read',0)
                result['disk_spill_bytes']+=metrics.get('Disk Bytes Spilled',0)
    assert result['application_finished'],f'Application has not ended: {application}'
    assert len(result['executor_tasks'])>=2,'Need evidence from both executors'
    return result

def main():
    protocol=read(FOLDER/'实验协议.json');records=[];summary={};artifacts=[]
    for name,expected in protocol['source_sha256'].items():
        assert sha(ROOT/'算法比较'/name)==expected,f'Benchmark source changed: {name}'
    for scenario in protocol['scenarios']:
        expected_patterns=None;candidate_union=None;methods={};descriptor=None
        for method in protocol['algorithms']:
            runs=[]
            for repeat in range(1,scenario['repeats']+1):
                record_file=FOLDER/'原始记录'/f'{scenario["name"]}_{method}_第{repeat}次.json'
                row=read(record_file)
                assert row['status']=='complete',str(record_file)
                assert row['scenario']==scenario and row['method']==method and row['repeat']==repeat
                assert row['exactly_equal_to_other_methods']
                descriptor=descriptor or row['input']
                assert descriptor==row['input']
                runs.append(row);records.append(row)
                artifacts.append({'file':str(record_file.relative_to(ROOT)),'sha256':sha(record_file)})
            pattern_file=FOLDER/runs[0]['patterns_file'];patterns=read(pattern_file)
            packed=json.dumps(patterns,ensure_ascii=False,separators=(',',':')).encode()
            fingerprint=hashlib.sha256(packed).hexdigest()
            assert all(row['result_sha256']==fingerprint for row in runs),'Repeat output changed'
            assert len(patterns)==len({tuple(p) for p,count in patterns})
            assert all(row['patterns']==len(patterns) for row in runs)
            counts_by_length=dict(Counter(str(len(p)) for p,count in patterns))
            assert all(row['counts_by_length']==counts_by_length for row in runs)
            if expected_patterns is None:expected_patterns=patterns
            else:assert patterns==expected_patterns,f'Pattern/support difference: {scenario["name"]}/{method}'
            if method!='MLlib':
                for row in runs:
                    if candidate_union is None:candidate_union=row['candidate_union']
                    assert row['candidate_union']==candidate_union,'Partition candidates must be identical'
                    assert sum(r['customers'] for r in row['partition_metrics'])==descriptor['customers']
            metrics={'repeats':len(runs),'wall_seconds':spread([r['wall_seconds'] for r in runs]),
                     'patterns':len(patterns),'counts_by_length':counts_by_length,'result_sha256':fingerprint}
            for field in ['kernel_seconds_max','kernel_seconds_sum','kernel_cpu_seconds_sum',
                          'peak_single_python_worker_bytes','local_and_union_seconds','global_count_seconds']:
                metrics[field]=spread([r[field] for r in runs]) if method!='MLlib' else None
            metrics['first_run_partition_metrics']=runs[0].get('partition_metrics')
            methods[method]=metrics
            artifacts.append({'file':str(pattern_file.relative_to(ROOT)),'sha256':sha(pattern_file)})
        summary[scenario['name']]={'configuration':scenario,'input':descriptor,'methods':methods,
            'patterns':len(expected_patterns),'counts_by_length':counts_by_length,
            'candidate_union':candidate_union,'candidate_inflation':candidate_union/len(expected_patterns),
            'all_outputs_exactly_equal':True}
    expected_runs=sum(s['repeats'] for s in protocol['scenarios'])*len(protocol['algorithms'])
    assert len(records)==expected_runs
    applications=sorted({r['application_id'] for r in records})
    input_files=[]
    for dataset in ['零售分钟','服装日级']:
        source=ROOT/'数据'/'分布式仓库'/'运行批次'/dataset/'序列'/'顾客序列'/'period=0'/'split=discovery'
        files=sorted(source.glob('*.parquet'))
        assert files,f'No input Parquet files: {source}'
        input_files.extend({'file':str(file.relative_to(ROOT)),'bytes':file.stat().st_size,'sha256':sha(file)} for file in files)
    result={'complete_runs':len(records),'scenarios':summary,'protocol':protocol,
            'correctness':read(ROOT/'结果'/'算法正确性.json'),
            'environments':[read(FOLDER/('环境-'+app+'.json')) for app in applications],
            'event_metrics':[application_metrics(app) for app in applications],
            'input_files':input_files,'artifacts':artifacts,
            'interpretation':'Medians and ranges are descriptive (three repetitions); native MLlib is an engineering reference. No cluster-wide memory peak or multi-host scalability measured.'}
    write(ROOT/'结果'/'算法比较汇总.json',result)
    lines=['# 四种序列算法的实际比较','',f'正式测量 {len(records)} 次；所有场景下完整模式和支持数逐项一致。','',
           '| 场景 | 顾客 | 模式 | GSP 秒 | PrefixSpan 秒 | SPADE 秒 | SPAM 秒 | MLlib 秒 |',
           '|---|---:|---:|---:|---:|---:|---:|---:|']
    for name,data in summary.items():
        times=' | '.join(f'{data["methods"][method]["wall_seconds"]["median"]:.3f}' for method in protocol['algorithms'])
        lines.append(f'| {name} | {data["input"]["customers"]:,} | {data["patterns"]:,} | {times} |')
    lines+=['','主实验及规模实验取 3 次中位数；2%、10% 阈值及两步长度为单次探索。',
            '四个 Python 内核共用相同 Spark 分区与全局精确计数流程。MLlib 使用 JVM 原生实现及自身分布式策略，作为工程参考。',
            '内存指标为每次运行中局部挖掘阶段单个 Python 工作进程的最大 RSS（Linux 高水位），不含 JVM，不是集群总内存。']
    (ROOT/'结果'/'算法比较摘要.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    print(json.dumps({'complete_runs':len(records),'all_equal':True,'scenarios':{name:{'customers':r['input']['customers'],'patterns':r['patterns'],'median_seconds':{m:round(v['wall_seconds']['median'],3) for m,v in r['methods'].items()}} for name,r in summary.items()}},ensure_ascii=False))

if __name__=='__main__':main()
