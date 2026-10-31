from 公共设置 import ROOT, save_json
from 序列算法 import mine_sequences, contains, contains_gap
import json, time, datetime, sys, platform, csv, math
from collections import Counter
import numpy as np
import scipy
from scipy.stats import binomtest
import psutil, duckdb, matplotlib

SEED=20261031

def by_adjust(pvalues):
    p=np.asarray(pvalues,dtype=float)
    order=np.argsort(p,kind='stable'); m=len(p)
    adjusted=p[order]*m*np.sum(1/np.arange(1,m+1))/np.arange(1,m+1)
    adjusted=np.minimum.accumulate(adjusted[::-1])[::-1].clip(0,1)
    q=np.empty(m); q[order]=adjusted
    return q

def flags_for(sequences,patterns):
    result=np.zeros((len(sequences),len(patterns)),dtype=bool)
    # Prefix trie shares scans across patterns; unlimited gaps permit earliest ends.
    trie={}
    for index,pattern in enumerate(patterns):
        node=trie
        for item in pattern:
            node=node.setdefault(item,{})
        node[None]=index
    for user,seq in enumerate(sequences):
        def traverse(node,start):
            if None in node:
                result[user,node[None]]=True
            wanted=set(node)-{None}
            for j in range(start,len(seq)):
                for item in seq[j]&wanted:
                    traverse(node[item],j+1)
                    wanted.remove(item)
                if not wanted:
                    break
        traverse(trie,0)
    return result

def compare(x,y):
    lost=np.sum(x&~y,axis=0); gained=np.sum(~x&y,axis=0)
    p=[float(binomtest(int(b),int(a+b),0.5).pvalue) if a+b else 1.0 for a,b in zip(lost,gained)]
    return lost,gained,np.asarray(p),by_adjust(p)

def main():
    start=time.perf_counter()
    source=json.loads((ROOT/'数据'/'顾客序列.json').read_text(encoding='utf-8'))
    desc=json.loads((ROOT/'数据'/'商品说明.json').read_text(encoding='utf-8'))
    ids={split:sorted([c for c,v in source.items() if v['split']==split],key=int) for split in ('discovery','evaluation')}
    sequences={split:{year:[[set(b['items']) for b in source[c][year]] for c in ids[split]] for year in ('2010','2011')} for split in ids}
    times={year:[[datetime.datetime.fromisoformat(b['time']).timestamp() for b in source[c][year]] for c in ids['evaluation']] for year in ('2010','2011')}
    train=sequences['discovery']['2010']; test=sequences['evaluation']; n=len(ids['evaluation'])
    t=time.perf_counter(); patterns_all=mine_sequences(train,0.02,3); mining_seconds=time.perf_counter()-t
    patterns=sorted([p for p in patterns_all if len(p)>=2])
    print('Mining:',len(patterns_all),'patterns;',len(patterns),'tested;',mining_seconds,'seconds',flush=True)
    save_json('发现模式.json',[{'pattern':p,'count':c,'support':c/len(train)} for p,c in sorted(patterns_all.items())])
    flags={year:flags_for(test[year],patterns) for year in test}
    np.savez_compressed(ROOT/'结果'/'顾客模式矩阵.npz',customer_ids=np.array(ids['evaluation']),patterns=np.array(['>'.join(p) for p in patterns]),year2010=flags['2010'],year2011=flags['2011'])
    lost,gained,pvalues,qvalues=compare(flags['2010'],flags['2011'])
    differences=flags['2011'].astype(np.int8)-flags['2010'].astype(np.int8)
    rng=np.random.default_rng(SEED)
    # Joint customer resampling, preserving within-customer pattern dependence.
    weights=rng.multinomial(n,np.ones(n)/n,size=2000).astype(np.float32)
    boots=(weights@differences.astype(np.float32))/n
    ci=np.percentile(boots,[2.5,97.5],axis=0)
    rows=[]
    for j,pattern in enumerate(patterns):
        rows.append({'pattern':list(pattern),'description':' → '.join(desc.get(k,k) or k for k in pattern),'discovery_count':patterns_all[pattern],
            'count2010':int(flags['2010'][:,j].sum()),'count2011':int(flags['2011'][:,j].sum()),'support2010':float(flags['2010'][:,j].mean()),'support2011':float(flags['2011'][:,j].mean()),
            'delta':float(differences[:,j].mean()),'lost':int(lost[j]),'gained':int(gained[j]),'p':float(pvalues[j]),'q_by':float(qvalues[j]),'ci_low':float(ci[0,j]),'ci_high':float(ci[1,j])})
    save_json('跨年变化.json',rows)
    with open(ROOT/'结果'/'跨年变化.csv','w',encoding='utf-8-sig',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=rows[0].keys());writer.writeheader();writer.writerows(rows)
    print('Evaluation:',int((qvalues<=.05).sum()),'BY significant;',int((pvalues<=.05).sum()),'uncorrected',flush=True)
    # Same-family sensitivities; secondary, not a new discovery search.
    sensitivities=[]
    for gap in (30,90):
        t=time.perf_counter()
        limited={year:np.array([[contains_gap(seq,ts,p,gap) for p in patterns] for seq,ts in zip(test[year],times[year])],dtype=bool) for year in test}
        _,_,pv,qv=compare(limited['2010'],limited['2011'])
        delta=limited['2011'].mean(axis=0)-limited['2010'].mean(axis=0)
        sensitivities.append({'variant':f'gap{gap}','significant':int((qv<=.05).sum()),'same_sign_as_primary':float(np.mean(np.sign(delta)==np.sign(differences.mean(axis=0)))), 'delta':delta.tolist(),'q_by':qv.tolist(),'seconds':time.perf_counter()-t})
        print('Gap',gap,'done',flush=True)
    balanced={year:[seq[:min(len(test['2010'][i]),len(test['2011'][i]))] for i,seq in enumerate(test[year])] for year in test}
    bf={year:flags_for(balanced[year],patterns) for year in test}
    _,_,bp,bq=compare(bf['2010'],bf['2011'])
    bd=bf['2011'].mean(axis=0)-bf['2010'].mean(axis=0)
    sensitivities.append({'variant':'balanced_baskets','significant':int((bq<=.05).sum()),'delta':bd.tolist(),'q_by':bq.tolist(),'same_sign_as_primary':float(np.mean(np.sign(bd)==np.sign(differences.mean(axis=0))))})
    save_json('稳健性实验.json',sensitivities)
    # Unordered comparator on distinct-product pairs, using identical customers.
    pair_ids=[j for j,p in enumerate(patterns) if len(p)==2 and p[0]!=p[1]]
    unions=[set().union(*seq) for seq in test['2010']]
    unordered=[]
    for j in pair_ids:
        a,b=patterns[j]
        co=sum(a in u and b in u for u in unions)
        rev=sum(contains(seq,(b,a)) for seq in test['2010'])
        unordered.append({'pattern':list(patterns[j]),'cooccurrence':co,'forward':int(flags['2010'][:,j].sum()),'reverse':rev})
    save_json('无序对照.json',unordered)
    # Patterns selected solely using discovery data; preserve itemset composition.
    top=sorted(pair_ids,key=lambda j:(-patterns_all[patterns[j]],patterns[j]))[:10]
    selected=[patterns[j] for j in top]
    observed=flags['2010'][:,top].sum(axis=0)
    perm=np.empty((499,len(top)),dtype=int)
    rng=np.random.default_rng(SEED+1)
    for b in range(499):
        shuffled=[[seq[k] for k in rng.permutation(len(seq))] for seq in test['2010']]
        perm[b]=flags_for(shuffled,selected).sum(axis=0)
        if (b+1)%100==0: print('Order permutations',b+1,flush=True)
    # Exchangeable two-sided statistic around pooled mean (observed + random draws).
    center=np.vstack([observed,perm]).mean(axis=0)
    perm_p=(1+(np.abs(perm-center)>=np.abs(observed-center)-1e-12).sum(axis=0))/500
    permutation=[{'pattern':list(p),'observed':int(observed[j]),'null_mean':float(perm[:,j].mean()),'null_interval':np.percentile(perm[:,j],[2.5,97.5]).tolist(),'p':float(perm_p[j]),'p_bonferroni':float(min(1,perm_p[j]*len(top)))} for j,p in enumerate(selected)]
    save_json('顺序置换.json',permutation)
    # Mining sensitivity; genuine customer subsets, never duplicated records.
    sensitivity=[]
    for support in (0.01,0.02,0.03,0.05):
        t=time.perf_counter(); mined=mine_sequences(train,support,3)
        entry={'support':support,'threshold':math.ceil(support*len(train)),'counts':dict(Counter(len(p) for p in mined)),'seconds':time.perf_counter()-t}
        sensitivity.append(entry); print('Threshold',entry,flush=True)
    save_json('阈值实验.json',sensitivity)
    scales=[]
    for fraction in (.25,.5,1.0):
        ordered=sorted(range(len(train)),key=lambda i:ids['discovery'][i])
        subset=[train[i] for i in ordered[:max(1,int(len(train)*fraction))]]
        elapsed=[]
        for _ in range(3):
            t=time.perf_counter(); mine_sequences(subset,.02,3); elapsed.append(time.perf_counter()-t)
        scales.append({'fraction':fraction,'customers':len(subset),'runs_seconds':elapsed,'median_seconds':float(np.median(elapsed))})
    save_json('规模实验.json',scales)
    lengths={year:{'mean':float(np.mean([len(s) for s in test[year]])),'median':float(np.median([len(s) for s in test[year]])),'total':sum(len(s) for s in test[year])} for year in test}
    summary={'seed':SEED,'mining_seconds':mining_seconds,'patterns_all':len(patterns_all),'patterns_by_length':dict(Counter(map(len,patterns_all))), 'tested':len(patterns),
        'discovery_customers':len(train),'evaluation_customers':n,'significant_by':int((qvalues<=.05).sum()),'significant_uncorrected':int((pvalues<=.05).sum()),
        'significant_increase':int(((qvalues<=.05)&(differences.mean(axis=0)>0)).sum()),'significant_decrease':int(((qvalues<=.05)&(differences.mean(axis=0)<0)).sum()),
        'basket_lengths':lengths,'total_seconds':time.perf_counter()-start,'peak_working_set_bytes':psutil.Process().memory_info().peak_wset,
        'python':sys.version,'platform':platform.platform(),'numpy':np.__version__,'scipy':scipy.__version__,'duckdb':duckdb.__version__,'matplotlib':matplotlib.__version__,
        'physical_memory_bytes':psutil.virtual_memory().total,'logical_cpu_count':psutil.cpu_count(),'cpu':'Intel Core i9-14900HX (24 physical cores, 32 logical processors)',
        'threads_note':'DuckDB 4 threads; sequence mining single Python process; no distributed cluster',
        'primary_top':sorted(rows,key=lambda r:(r['q_by'],-abs(r['delta'])))[:12]}
    save_json('实验汇总.json',summary)
    print(json.dumps(summary,ensure_ascii=False,indent=2),flush=True)

if __name__=='__main__':
    main()
