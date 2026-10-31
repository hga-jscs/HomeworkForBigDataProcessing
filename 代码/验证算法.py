from 公共设置 import save_json
from 序列算法 import mine_sequences, contains, contains_gap, brute_counts
from itertools import combinations, product
import random, math

def main():
    random.seed(20261031)
    checks=0
    for case in range(120):
        seqs=[[set(random.sample('ABCD',random.randint(1,3))) for _ in range(random.randint(1,6))] for _ in range(random.randint(2,8))]
        brute=brute_counts(seqs)
        for support in (0.2,0.5,0.8):
            expected={p:c for p,c in brute.items() if c>=math.ceil(len(seqs)*support-1e-12)}
            assert mine_sequences(seqs,support)==expected
            checks+=1
        for seq in seqs:
            times=[i*86400*5 for i in range(len(seq))]
            for pattern in product('ABCD',repeat=3):
                actual=contains_gap(seq,times,pattern,6)
                expected=any(all(pattern[k] in seq[j] for k,j in enumerate(idx)) and all(times[b]-times[a]<=6*86400 for a,b in zip(idx,idx[1:])) for idx in combinations(range(len(seq)),3))
                assert actual==expected
                checks+=1
    # Equal-time basket never creates A -> B; repetition needs separate times.
    assert not contains([{'A','B'}],('A','B'))
    assert contains([{'A','B'},{'A'}],('A','A'))
    # Gap constraints require later A, not only the earliest A.
    assert contains_gap([{'A'},{'A'},{'B'}],[0,99*86400,100*86400],('A','B'),2)
    checks+=3
    result={'random_sequence_databases':120,'assertions':checks,'status':'passed','seed':20261031}
    save_json('算法验证.json',result)
    print(result)

if __name__=='__main__':
    main()
