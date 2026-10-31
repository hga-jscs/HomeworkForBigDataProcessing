"""Singleton-step sequences over timestamped baskets; no within-basket ordering."""
from collections import defaultdict
from itertools import combinations, product
import math

def mine_sequences(sequences, support=0.02, max_length=3):
    """Exact prefix projection, retaining earliest end per customer (no gap limit).

    Return pattern -> supporting customer count, in the singleton-step language.
    Each basket is an unordered collection and each extension uses a later basket.
    """
    threshold = math.ceil(len(sequences)*support-1e-12)
    output = {}
    def grow(prefix, states):
        projected = defaultdict(list)
        for customer, begin in states:
            seen = set()
            for index in range(begin, len(sequences[customer])):
                for item in sequences[customer][index]:
                    if item not in seen:
                        projected[item].append((customer,index+1))
                        seen.add(item)
        for item in sorted(projected):
            occurrences = projected[item]
            if len(occurrences) >= threshold:
                pattern = prefix+(item,)
                output[pattern] = len(occurrences)
                if len(pattern) < max_length:
                    grow(pattern,occurrences)
    grow((),[(i,0) for i in range(len(sequences))])
    return output

def contains(sequence, pattern):
    step=0
    for basket in sequence:
        if pattern[step] in basket:
            step+=1
            if step==len(pattern):
                return True
    return False

def contains_gap(sequence, times, pattern, max_gap_days):
    """Keep every reachable endpoint: the earliest-end shortcut is invalid here."""
    ends=[i for i,b in enumerate(sequence) if pattern[0] in b]
    gap=max_gap_days*86400
    for item in pattern[1:]:
        possible=[]
        pointer=0
        for j,basket in enumerate(sequence):
            if item not in basket:
                continue
            while pointer<len(ends) and times[j]-times[ends[pointer]]>gap:
                pointer+=1
            if pointer<len(ends) and ends[pointer]<j:
                possible.append(j)
        ends=possible
        if not ends:
            return False
    return bool(ends)

def brute_counts(sequences,max_length=3):
    result=defaultdict(int)
    for sequence in sequences:
        seen=set()
        for length in range(1,max_length+1):
            for indices in combinations(range(len(sequence)),length):
                seen.update(product(*(sequence[i] for i in indices)))
        for pattern in seen:
            result[pattern]+=1
    return dict(result)
