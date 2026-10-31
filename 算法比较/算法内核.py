"""Four exact sequence miners for the SAME restricted pattern language.

Input: one ordered list of unordered baskets per customer. A pattern consists
of singleton steps at strictly increasing basket indices, with unlimited gaps.
These are transparent course implementations of the papers' core strategies,
not reproductions of their original source code or optional constraints/I-steps.
"""
from bisect import bisect_right
from collections import Counter, defaultdict
from itertools import combinations, product
import math

ALGORITHMS=('GSP','PrefixSpan','SPADE','SPAM')

def threshold(support,n):
    if not 0<support<=1:raise ValueError('Support must lie in (0,1]')
    return math.ceil(support*n-1e-12)

def encode(sequences,support):
    single=Counter(item for sequence in sequences for item in {x for basket in sequence for x in basket})
    minimum=threshold(support,len(sequences))
    labels=sorted(x for x,count in single.items() if count>=minimum)
    index={label:i for i,label in enumerate(labels)}
    encoded=[tuple(tuple(sorted({index[x] for x in basket if x in index})) for basket in sequence) for sequence in sequences]
    counts={index[label]:single[label] for label in labels}
    return encoded,labels,counts,minimum

def trie_build(patterns):
    children=[{}];terminal=[-1]
    for pid,pattern in enumerate(patterns):
        node=0
        for item in pattern:
            if item not in children[node]:
                children[node][item]=len(children);children.append({});terminal.append(-1)
            node=children[node][item]
        terminal[node]=pid
    return children,terminal

def trie_matches(sequence,trie):
    children,terminal=trie
    active={0};found=set()
    for basket in sequence:
        following=set()
        for node in active:
            lookup=children[node]
            for item in basket:
                child=lookup.get(item)
                if child is not None:
                    # Leaf nodes cannot extend and need not stay active.
                    if children[child]:following.add(child)
                    pid=terminal[child]
                    if pid>=0:found.add(pid)
        active.update(following)  # Only after the complete unordered basket.
    return found

def gsp(sequences,single,minimum,maximum,stats,limit):
    previous={(item,):count for item,count in single.items()}
    result=dict(previous);stats['generated_candidates']={'1':len(previous)}
    stats['pruned_candidates']={}
    for length in range(2,maximum+1):
        if not previous:break
        prefix_groups=defaultdict(list)
        for pattern in previous:prefix_groups[pattern[:-1]].append(pattern)
        candidates=[];generated=0
        for left in sorted(previous):
            for right in prefix_groups.get(left[1:],()):
                candidate=left+(right[-1],);generated+=1
                if generated>limit:raise RuntimeError('GSP generated-candidate safety limit exceeded')
                if all(candidate[:i]+candidate[i+1:] in previous for i in range(length)):
                    candidates.append(candidate)
        stats['generated_candidates'][str(length)]=generated
        stats['pruned_candidates'][str(length)]=generated-len(candidates)
        counts=[0]*len(candidates)
        trie=trie_build(candidates)
        for sequence in sequences:
            for index in trie_matches(sequence,trie):counts[index]+=1
        previous={pattern:count for pattern,count in zip(candidates,counts) if count>=minimum}
        result.update(previous)
    return result

def prefixspan(sequences,single,minimum,maximum,stats,limit):
    result={};stats['projected_states']=0
    def grow(prefix,states):
        stats['projected_states']+=len(states)
        extensions=defaultdict(list)
        for customer,start in states:
            seen=set()
            for position in range(start,len(sequences[customer])):
                for item in sequences[customer][position]:
                    if item not in seen:
                        extensions[item].append((customer,position+1));seen.add(item)
        for item in sorted(extensions):
            positions=extensions[item]
            if len(positions)>=minimum:
                pattern=prefix+(item,);result[pattern]=len(positions)
                if len(result)>limit:raise RuntimeError('Pattern safety limit exceeded')
                if len(pattern)<maximum:grow(pattern,positions)
    grow((),[(sid,0) for sid in range(len(sequences))])
    return result

def temporal_join(left,right):
    """SPADE temporal join of (sid, eid) lists in a shared-prefix class.

    Retain every right endpoint after the earliest left endpoint for each sid.
    This shortcut is exact for unlimited gaps, not for a max-gap constraint.
    """
    output={}
    if len(left)<=len(right):
        for sid,ends in left.items():
            other=right.get(sid)
            if other:
                start=bisect_right(other,ends[0])
                if start<len(other):output[sid]=other[start:]
    else:
        for sid,other in right.items():
            ends=left.get(sid)
            if ends:
                start=bisect_right(other,ends[0])
                if start<len(other):output[sid]=other[start:]
    return output

def spade(sequences,single,minimum,maximum,stats,limit):
    vertical={item:defaultdict(list) for item in single}
    for sid,sequence in enumerate(sequences):
        for eid,basket in enumerate(sequence):
            for item in basket:vertical[item][sid].append(eid)
    vertical={item:{sid:tuple(ends) for sid,ends in groups.items()} for item,groups in vertical.items()}
    stats['initial_endpoints']=sum(len(v) for item in vertical.values() for v in item.values())
    stats['temporal_joins']=0
    result={(item,):len(groups) for item,groups in vertical.items()}
    def grow(equivalence_class):
        if not equivalence_class or len(equivalence_class[0][0])>=maximum:return
        for left_pattern,left in equivalence_class:
            children=[]
            for right_pattern,right in equivalence_class:
                stats['temporal_joins']+=1
                joined=temporal_join(left,right)
                if len(joined)>=minimum:
                    pattern=left_pattern+(right_pattern[-1],)
                    result[pattern]=len(joined);children.append((pattern,joined))
                    if len(result)>limit:raise RuntimeError('Pattern safety limit exceeded')
            grow(children)
    grow([((item,),vertical[item]) for item in sorted(vertical)])
    return result

def bitmap_join(prefix,extension):
    """SPAM S-step, using a separate integer bitmap for each customer.

    Customer boundaries are explicit; bit operations never carry across people.
    Zero-based basket positions after the least prefix end form a suffix mask.
    """
    output={}
    if len(prefix)<=len(extension):
        for sid,bits in prefix.items():
            following=extension.get(sid,0)
            if following:
                earliest_end_plus_one=(bits & -bits).bit_length()
                intersection=following & (-1 << earliest_end_plus_one)
                if intersection:output[sid]=intersection
    else:
        for sid,following in extension.items():
            bits=prefix.get(sid,0)
            if bits:
                intersection=following & (-1 << ((bits & -bits).bit_length()))
                if intersection:output[sid]=intersection
    return output

def spam(sequences,single,minimum,maximum,stats,limit):
    bitmaps={item:{} for item in single}
    for sid,sequence in enumerate(sequences):
        for eid,basket in enumerate(sequence):
            bit=1<<eid
            for item in basket:bitmaps[item][sid]=bitmaps[item].get(sid,0)|bit
    stats['initial_bitmap_entries']=sum(len(value) for value in bitmaps.values())
    stats['bitmap_joins']=0
    result={(item,):len(groups) for item,groups in bitmaps.items()}
    def grow(pattern,bitmap,allowed):
        if len(pattern)>=maximum:return
        children=[]
        for item in allowed:
            stats['bitmap_joins']+=1
            extended=bitmap_join(bitmap,bitmaps[item])
            if len(extended)>=minimum:
                result[pattern+(item,)]=len(extended);children.append((item,extended))
                if len(result)>limit:raise RuntimeError('Pattern safety limit exceeded')
        next_allowed=[item for item,_ in children]
        for item,extended in children:grow(pattern+(item,),extended,next_allowed)
    allowed=sorted(bitmaps)
    for item in allowed:grow((item,),bitmaps[item],allowed)
    return result

MINERS={'GSP':gsp,'PrefixSpan':prefixspan,'SPADE':spade,'SPAM':spam}

def mine(algorithm,sequences,support=.05,maximum=3,limit=2000000):
    if maximum<1:raise ValueError('maximum must be positive')
    if algorithm not in MINERS:raise ValueError(algorithm)
    if not sequences:return {},{'customers':0,'patterns':0}
    encoded,labels,single,minimum=encode(sequences,support)
    stats={'customers':len(sequences),'minimum_count':minimum,'frequent_items':len(single)}
    output=MINERS[algorithm](encoded,single,minimum,maximum,stats,limit)
    decoded={tuple(labels[x] for x in pattern):count for pattern,count in output.items()}
    stats['patterns']=len(decoded)
    return decoded,stats

def exhaustive(sequences,support,maximum):
    counts=Counter()
    for sequence in sequences:
        seen=set()
        for length in range(1,maximum+1):
            for positions in combinations(range(len(sequence)),length):
                seen.update(product(*(set(sequence[j]) for j in positions)))
        counts.update(seen)
    minimum=threshold(support,len(sequences))
    return {p:c for p,c in counts.items() if c>=minimum}
