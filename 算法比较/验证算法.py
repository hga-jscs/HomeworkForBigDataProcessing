"""Exhaustive correctness and partition-union completeness tests."""
from 算法内核 import ALGORITHMS,mine,exhaustive,trie_build,trie_matches,threshold
import random,json,math
from pathlib import Path

def main():
    rng=random.Random(20261101)
    databases=[[[['A','B']]],[[['A'],['A']]],[[['A','B'],[],['C'],['B']]],
        [[],[['A']],[['A'],['B']]],[[['B'],['A']],[['A','B']]]]
    databases += [[[sorted(rng.sample(list('ABCDE'),rng.randint(0,3))) for _ in range(rng.randint(0,6))]
                   for _ in range(rng.randint(1,9))] for _ in range(100)]
    runs=0;partition_checks=0;support_entries=0
    for database in databases:
        for maximum in (1,2,3,4):
            for support in (.2,.5,.8,1.0):
                expected=exhaustive(database,support,maximum)
                for algorithm in ALGORITHMS:
                    actual,_=mine(algorithm,database,support,maximum)
                    assert actual==expected,(algorithm,support,maximum,database,actual,expected)
                    runs+=1;support_entries+=len(actual)
                # Uneven partitions and empty partitions exercise the completeness proof.
                chunks=[database[:1],database[1::2],database[2::2],[]]
                candidates=set()
                for chunk in chunks:
                    local,_=mine('SPAM',chunk,support,maximum)
                    candidates.update(local)
                assert set(expected)<=candidates
                patterns=sorted(candidates);counts=[0]*len(patterns);trie=trie_build(patterns)
                for sequence in database:
                    for index in trie_matches(sequence,trie):counts[index]+=1
                verified={p:c for p,c in zip(patterns,counts) if c>=threshold(support,len(database))}
                assert verified==expected
                partition_checks+=1
    result={'seed':20261101,'databases':len(databases),'algorithm_database_parameter_checks':runs,
            'support_entries_checked':support_entries,'partition_completeness_checks':partition_checks,
            'coverage':['unordered baskets','empty sequences/baskets','repeated items','uneven/empty partitions','lengths 1-4','four support thresholds'],
            'passed':True}
    root=Path(__file__).resolve().parent.parent
    (root/'结果'/'算法正确性.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(result,ensure_ascii=False,indent=2))

if __name__=='__main__':main()
