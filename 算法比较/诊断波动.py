"""Retain outliers and inspect their task metrics; do not remove measurements."""
import json
from collections import defaultdict
from pathlib import Path

ROOT=Path(__file__).resolve().parent.parent
FOLDER=ROOT/'结果'/'算法比较'

def main():
    groups=defaultdict(list)
    for file in (FOLDER/'正式'/'原始记录').glob('*.json'):
        row=json.loads(file.read_text(encoding='utf-8'))
        if row['status']=='complete':groups[(row['scenario']['name'],row['method'])].append((file.name,row))
    anomalies={}
    for (scenario,method),rows in groups.items():
        if len(rows)<3:continue
        times=[r['wall_seconds'] for _,r in rows]
        if max(times)<2.5*min(times):continue
        name,row=max(rows,key=lambda pair:pair[1]['wall_seconds'])
        anomalies[name]={'scenario':scenario,'method':method,'application_id':row['application_id'],
            'wall_seconds_by_repeat':{str(r['repeat']):r['wall_seconds'] for _,r in rows},
            'maximum_to_minimum_ratio':max(times)/min(times),'tasks':[]}
    for app in {value['application_id'] for value in anomalies.values()}:
        stage_groups={}
        for file in sorted((FOLDER/'事件日志'/('eventlog_v2_'+app)).glob('events_*')):
            with file.open(encoding='utf-8') as handle:
                for line in handle:
                    event=json.loads(line)
                    if event.get('Event')=='SparkListenerJobStart':
                        group=event.get('Properties',{}).get('spark.jobGroup.id','')
                        for stage in event.get('Stage IDs',[]):stage_groups[stage]=group
                    if event.get('Event')!='SparkListenerTaskEnd':continue
                    group=stage_groups.get(event.get('Stage ID'))
                    if group not in anomalies:continue
                    info=event['Task Info'];metrics=event.get('Task Metrics',{})
                    anomalies[group]['tasks'].append({'stage':event['Stage ID'],'executor':info['Executor ID'],
                        'duration_ms':info['Finish Time']-info['Launch Time'],
                        'executor_run_ms':metrics.get('Executor Run Time',0),
                        'gc_ms':metrics.get('JVM GC Time',0),
                        'disk_spill_bytes':metrics.get('Disk Bytes Spilled',0),
                        'reason':event.get('Task End Reason',{}).get('Reason')})
    for value in anomalies.values():
        value['maximum_single_task_gc_seconds']=max((row['gc_ms'] for row in value['tasks']),default=0)/1000
        value['slowest_tasks']=sorted(value['tasks'],key=lambda row:row['duration_ms'],reverse=True)[:10]
    output={'selection':'at least 3 repetitions and max/min >= 2.5; descriptive diagnostic only',
        'anomalies':anomalies,'excluded_runs':[],
        'interpretation':'Task GC counters overlap across simultaneous tasks and must not be summed as elapsed time. Logs show prolonged tasks and GC, not a complete causal explanation; host scheduling and swapping were not continuously monitored.'}
    (FOLDER/'波动诊断.json').write_text(json.dumps(output,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'outliers':list(anomalies),'excluded_runs':[]},ensure_ascii=False))

if __name__=='__main__':main()
