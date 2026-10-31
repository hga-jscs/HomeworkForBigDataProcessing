from 公共设置 import ROOT,save_json
from 序列算法 import contains
import json

def main():
    data=json.loads((ROOT/'数据'/'顾客序列.json').read_text(encoding='utf-8'))
    users=[v for v in data.values() if v['split']=='evaluation']; n=len(users)
    result=[]
    for a,b in [('22662','22382'),('22528','85123A')]:
        stats={}
        for year in ('2010','2011'):
            sequences=[[set(basket['items']) for basket in u[year]] for u in users]
            co=sum(a in set().union(*s) and b in set().union(*s) for s in sequences)
            forward=sum(contains(s,(a,b)) for s in sequences)
            stats[year]={'unordered_count':co,'sequence_count':forward,'w':co/n,'r':forward/co if co else 0.0,'s':forward/n}
        x,y=stats['2010'],stats['2011']
        composition=(y['w']-x['w'])*x['r']; conditional=y['w']*(y['r']-x['r'])
        assert abs((y['s']-x['s'])-composition-conditional)<1e-12
        result.append({'pattern':[a,b],'years':stats,'cooccurrence_term':composition,'conditional_term':conditional,'note':'descriptive algebraic decomposition, not causal; not an additional hypothesis test'})
    save_json('变化分解.json',result)
    print(json.dumps(result,ensure_ascii=False,indent=2))

if __name__=='__main__':main()
