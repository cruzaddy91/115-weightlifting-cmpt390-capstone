from __future__ import annotations


def response_label(completion_ratio, pr_delta):
    pr_component = pr_delta if pr_delta is not None else 0.0
    score = (completion_ratio or 0.0) + (pr_component * 0.1)
    return 1 if score >= 0.7 else 0


def recommendation_score(probability, sample_size):
    return (probability or 0.0) * min(1.0, max(sample_size, 1) / 8.0)

