from 公共设置 import ROOT,save_json
from 运行实验 import flags_for,by_adjust
from 序列算法 import contains,mine_sequences
import json,random,duckdb,numpy as np

def main():
    source=json.loads((ROOT/'数据'/'顾客序列.json').read_text(encoding='utf-8'))
    patterns=json.loads((ROOT/'结果'/'跨年变化.json').read_text(encoding='utf-8'))
    discovered=json.loads((ROOT/'结果'/'发现模式.json').read_text(encoding='utf-8'))
    ids={s:sorted([c for c,v in source.items() if v['split']==s],key=int) for s in ('discovery','evaluation')}
    train=[[set(b['items']) for b in source[c]['2010']] for c in ids['discovery']]
    allpatterns=[tuple(r['pattern']) for r in discovered]
    # Independently validate trie matching against brute per-pattern matcher.
    rng=random.Random(20261031)
    selected=rng.sample(allpatterns,min(400,len(allpatterns)))
    sample=rng.sample(train,80)
    actual=flags_for(sample,selected)
    expected=np.array([[contains(seq,p) for p in selected] for seq in sample])
    assert np.array_equal(actual,expected)
    # Full training support must agree for all discovered patterns.
    check=flags_for(train,allpatterns).sum(axis=0)
    assert np.array_equal(check,[r['count'] for r in discovered])
    assert np.allclose(by_adjust([.01,.04,.03]),[.055,.0733333333333333,.0733333333333333])
    con=duckdb.connect(str(ROOT/'数据'/'交易仓库.duckdb'),read_only=True)
    yearly=con.execute('''SELECT stock,year(time),count(*),count(DISTINCT customer) FROM clean
        WHERE year(time) IN (2010,2011) AND month(time)<=11 GROUP BY 1,2''').fetchall()
    population={}
    for stock,year,lines,buyers in yearly:
        population.setdefault(stock,{})[str(year)]={'rows':lines,'buyers':buyers}
    significant=[p for p in patterns if p['q_by']<=.05]
    absent=[r for r in significant if any(population.get(i,{}).get('2011',{}).get('rows',0)==0 for i in r['pattern'])]
    with np.load(ROOT/'结果'/'顾客模式矩阵.npz') as matrix:
        # Identical support vectors reveal exact redundancy in the evaluation set.
        signatures={np.packbits(np.r_[matrix['year2010'][:,j],matrix['year2011'][:,j]]).tobytes() for j,r in enumerate(patterns) if r['q_by']<=.05}
    examples=[]
    keys=[('22528','85123A'),('22662','22382'),('85123A','85123A'),('22423','22423')]
    for p in keys:
        found=next((r for r in patterns if tuple(r['pattern'])==p),None)
        if found:
            item_counts={year:{i:sum(any(i in b['items'] for b in source[c][year]) for c in ids['evaluation']) for i in set(p)} for year in ('2010','2011')}
            examples.append({'pattern':p,'primary':found,'item_customer_counts':item_counts,'whole_data_item_counts':{i:population.get(i,{}) for i in set(p)}})
    summary={'trie_brute_cells_checked':int(expected.size),'training_pattern_counts_checked':len(allpatterns),'by_unit_test':'passed',
        'significant_patterns':len(significant),'significant_with_absent_2011_product':len(absent),'unique_significant_support_vectors':len(signatures),
        'significant_by_length':{str(k):sum(len(r['pattern'])==k for r in significant) for k in (2,3)},'examples':examples}
    save_json('结果诊断.json',summary)
    print(json.dumps(summary,ensure_ascii=False,indent=2))

if __name__=='__main__':
    main()
