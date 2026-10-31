from 公共设置 import ROOT, save_json
import json, sys, collections, datetime
from pathlib import Path
import duckdb

WAREHOUSE=ROOT/'数据'/'分布式仓库'/'运行批次'

def read(path): return json.loads(path.read_text(encoding='utf-8'))

def event_metrics(application):
    directory=ROOT/'结果'/'Spark事件'/('eventlog_v2_'+application)
    result={'application_id':application,'tasks':0,'failed_tasks':0,'executor_tasks':{},
            'input_bytes':0,'shuffle_read_bytes':0,'shuffle_write_bytes':0,
            'disk_spill_bytes':0,'memory_spill_bytes':0,'executor_cpu_seconds':0.0}
    for path in sorted(directory.glob('events_*')):
        with path.open(encoding='utf-8') as file:
            for line in file:
                e=json.loads(line)
                if e.get('Event')=='SparkListenerTaskEnd':
                    result['tasks']+=1
                    key=e['Task Info']['Executor ID']
                    result['executor_tasks'][key]=result['executor_tasks'].get(key,0)+1
                    result['failed_tasks']+=int(e.get('Task End Reason',{}).get('Reason')!='Success')
                    m=e.get('Task Metrics',{})
                    result['input_bytes']+=m.get('Input Metrics',{}).get('Bytes Read',0)
                    sr=m.get('Shuffle Read Metrics',{})
                    result['shuffle_read_bytes']+=sr.get('Remote Bytes Read',0)+sr.get('Local Bytes Read',0)
                    result['shuffle_write_bytes']+=m.get('Shuffle Write Metrics',{}).get('Shuffle Bytes Written',0)
                    result['disk_spill_bytes']+=m.get('Disk Bytes Spilled',0)
                    result['memory_spill_bytes']+=m.get('Memory Bytes Spilled',0)
                    result['executor_cpu_seconds']+=m.get('Executor CPU Time',0)/1e9
    return result

def contains(sequence,pattern):
    index=0
    for basket in sequence:
        if pattern[index] in basket:
            index+=1
            if index==len(pattern): return True
    return False

def granularity():
    sys.path.insert(0,str(ROOT/'分布式处理'))
    from 模式分析 import make_trie,matches
    customers=read(ROOT/'数据'/'顾客序列.json')
    patterns=read(WAREHOUSE/'零售分钟'/'变化'/'完整统计.json')
    trie=make_trie([(i,r['pattern']) for i,r in enumerate(patterns)])
    counts=[[0,0] for _ in patterns]; old_baskets=[0,0]; new_baskets=[0,0]; n=0
    for data in customers.values():
        if data['split']!='evaluation':continue
        n+=1
        for period,year in enumerate(['2010','2011']):
            days={}
            for event in data[year]: days.setdefault(event['time'][:10],set()).update(event['items'])
            old_baskets[period]+=len(data[year]);new_baskets[period]+=len(days)
            sequence=[sorted(v) for k,v in sorted(days.items())]
            for index in matches(sequence,trie): counts[index][period]+=1
    rows=[]
    for pattern,(a,b) in zip(patterns,counts):
        assert a<=pattern['count0'] and b<=pattern['count1']
        rows.append({'pattern':pattern['pattern'],'minute0':pattern['count0'],'day0':a,
                     'minute1':pattern['count1'],'day1':b})
    result={'fixed_evaluation_customers':n,'fixed_candidate_patterns':len(patterns),
        'minute_baskets':old_baskets,'day_baskets':new_baskets,
        'patterns_with_reduced_support0':sum(r['minute0']>r['day0'] for r in rows),
        'patterns_with_reduced_support1':sum(r['minute1']>r['day1'] for r in rows),
        'lost_customer_pattern_matches0':sum(r['minute0']-r['day0'] for r in rows),
        'lost_customer_pattern_matches1':sum(r['minute1']-r['day1'] for r in rows),
        'largest_losses':sorted(rows,key=lambda r:(r['minute0']-r['day0'])+(r['minute1']-r['day1']),reverse=True)[:5],
        'scope':'fixed 785 customers and same 1048 patterns; only temporal coarsening changes'}
    save_json('时间粒度对照.json',result)
    return result

def audit_fashion(con):
    source=str(ROOT/'数据'/'服装交易'/'transactions'/'train'/'*.parquet')
    raw=con.execute('select count(*),count(distinct customer_id),count(distinct article_id),min(t_dat),max(t_dat) from read_parquet(?)',[source]).fetchone()
    labels=dict(con.execute('select concat(\'type:\',cast(product_type_no as varchar)), any_value(product_type_name) from read_parquet(?) group by 1',
        [str(ROOT/'数据'/'服装交易'/'articles'/'train'/'*.parquet')]).fetchall())
    save_json('服装类别名称.json',labels)
    results=read(WAREHOUSE/'服装日级'/'变化'/'完整统计.json')
    # A separately written greedy matcher audits three patterns over ALL evaluation sequences.
    chosen=sorted(results,key=lambda r:r['q_by'])[:3]
    counts=[[0,0,0,0] for r in chosen];n=0
    pattern_uri=str(WAREHOUSE/'服装日级'/'序列'/'顾客序列'/'**'/'*.parquet')
    cursor=con.execute("select customer, period, sequence from read_parquet(?,hive_partitioning=true) where split='evaluation' order by customer,period",[pattern_uri])
    previous=None
    while batch:=cursor.fetchmany(1024):
        for customer,period,sequence in batch:
            hits=[contains(sequence,r['pattern']) for r in chosen]
            if period==0:
                assert previous is None
                previous=(customer,hits)
            else:
                assert previous is not None and previous[0]==customer
                n+=1
                for i,(a,b) in enumerate(zip(previous[1],hits)):
                    for j,value in enumerate([a,b,a and not b,b and not a]):counts[i][j]+=int(value)
                previous=None
    assert previous is None
    for expected,actual in zip(chosen,counts):
        assert actual==[expected[k] for k in ['count0','count1','discordant0','discordant1']]
        assert n==expected['customers']
    out={'raw_rows':raw[0],'raw_customers':raw[1],'raw_products':raw[2],
         'first_date':str(raw[3]),'last_date':str(raw[4]),
         'independent_greedy_matcher':{'customers':n,'patterns':len(chosen),'all_four_support_counts_match':True},
         'expected_original_rows':31788324,'complete_row_count_matches':raw[0]==31788324}
    assert out['complete_row_count_matches']
    save_json('服装独立核验.json',out)
    return out

def main():
    summary={}
    applications=set()
    for name in ('零售分钟','服装日级','零售日级'):
        directory=WAREHOUSE/name
        if not (directory/'变化'/'_完成.json').exists():continue
        stages={s:read(directory/s/'_完成.json') for s in ['清洗','序列','模式','变化']}
        summary[name]=stages
        applications.update(stage['application_id'] for stage in stages.values())
    assert '零售分钟' in summary and '服装日级' in summary
    con=duckdb.connect()
    con.execute("SET threads=2; SET memory_limit='1GB'")
    temp=ROOT/'临时文件'/'独立核验';temp.mkdir(exist_ok=True)
    con.execute('SET temp_directory=?',[str(temp)])
    summary['independent_fashion_audit']=audit_fashion(con)
    summary['granularity_ablation']=granularity()
    summary['event_metrics']=[event_metrics(a) for a in sorted(applications)]
    summary['data_bytes']=sum(p.stat().st_size for p in (ROOT/'数据'/'服装交易').rglob('*.parquet'))
    summary['warehouse_bytes']=sum(p.stat().st_size for p in WAREHOUSE.rglob('*.parquet'))
    summary['validation_scope']='one physical host; two independent Spark worker/executor processes for H&M; no physical multi-host or YARN execution claim'
    save_json('框架实验汇总.json',summary)
    print(json.dumps({k:v for k,v in summary.items() if k not in ('零售分钟','服装日级','零售日级')},ensure_ascii=False,indent=2))

if __name__=='__main__': main()
