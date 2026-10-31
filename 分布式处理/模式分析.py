"""Bounded model broadcast + partition-wise support aggregation.

Raw customers never collect to the driver. The candidate catalogue is bounded
before collection. A partition returns only sufficient statistics per pattern.
"""
import math

def make_trie(patterns):
    children, terminals = [{}], [[]]
    for pattern_id, pattern in patterns:
        node = 0
        for item in pattern:
            if item not in children[node]:
                children[node][item] = len(children)
                children.append({}); terminals.append([])
            node = children[node][item]
        terminals[node].append(pattern_id)
    return children, terminals

def matches(sequence, trie):
    children, terminals = trie
    active = {0}; found = set()
    for basket in sequence:
        following = set()
        # Delay all extensions until the whole basket was visited. No within-day order.
        for node in active:
            for item in basket:
                child = children[node].get(item)
                if child is not None:
                    following.add(child)
                    found.update(terminals[child])
        active.update(following)
    return found

def partition_counts(rows, trie):
    counts = {}
    for row in rows:
        earlier = matches(row.sequence0, trie)
        later = matches(row.sequence1, trie)
        for pid in earlier | later:
            values = counts.setdefault(pid,[0,0,0,0])
            a,b = pid in earlier, pid in later
            values[0] += int(a); values[1] += int(b)
            values[2] += int(a and not b); values[3] += int(b and not a)
    yield from ((key,tuple(value)) for key,value in counts.items())

def combine(a,b):
    return tuple(x+y for x,y in zip(a,b))

def statistics(patterns, count_rows, customers):
    from scipy.stats import binomtest
    from scipy.special import gammaln, logsumexp
    import numpy as np
    if customers < 1: raise ValueError('Empty evaluation cohort')
    by_id = dict(count_rows)
    output = []
    for pid, pattern in patterns:
        n0,n1,b,c = by_id.get(pid,(0,0,0,0))
        p = float(binomtest(min(b,c),b+c,.5).pvalue) if b+c else 1.0
        if p > 0:
            log_p = math.log(p)
        else:
            # A large paired cohort can underflow ordinary double-precision p.
            # Preserve the exact binomial-tail calculation in log space.
            total=b+c; k=np.arange(min(b,c)+1,dtype=float)
            log_p=min(0.0,math.log(2)+float(logsumexp(gammaln(total+1)-gammaln(k+1)-gammaln(total-k+1)-total*math.log(2))))
        output.append({'pattern_id':pid,'pattern':list(pattern),'count0':n0,'count1':n1,
            'discordant0':b,'discordant1':c,'customers':customers,
            'support0':n0/customers,'support1':n1/customers,'delta':(n1-n0)/customers,'p':p,
            'log10_p':log_p/math.log(10),'p_underflow':p==0.0})
    m = len(output)
    harmonic = sum(1/i for i in range(1,m+1))
    order = sorted(range(m),key=lambda i:output[i]['log10_p'])
    running_log = 0.0
    for k in range(m-1,-1,-1):
        i = order[k]
        running_log = min(running_log, output[i]['log10_p']*math.log(10)+math.log(m*harmonic/(k+1)))
        output[i]['q_by'] = math.exp(running_log)
        output[i]['log10_q_by'] = running_log/math.log(10)
    return output
