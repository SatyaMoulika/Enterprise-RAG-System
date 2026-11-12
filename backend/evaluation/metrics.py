import math


def retrieval_metrics(retrieved: list[int], relevant: set[int], k: int) -> dict:
    if k < 1:
        raise ValueError("k must be positive")
    ranked = retrieved[:k]
    if not relevant:
        return {
            "precision": None,
            "recall": None,
            "mrr": None,
            "ndcg": None,
            "empty_result": not ranked,
        }
    seen = set()
    gains = []
    first = 0.0
    for rank, identity in enumerate(ranked, 1):
        hit = identity in relevant and identity not in seen
        gains.append(1 / math.log2(rank + 1) if hit else 0.0)
        if hit and not first:
            first = 1 / rank
        seen.add(identity)
    hits = len(set(ranked) & relevant)
    ideal = sum(1 / math.log2(rank + 1) for rank in range(1, min(k, len(relevant)) + 1))
    return {
        "precision": hits / k,
        "recall": hits / len(relevant),
        "mrr": first,
        "ndcg": sum(gains) / ideal,
        "empty_result": None,
    }
