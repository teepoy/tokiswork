"""Minimal Supervised Contrastive Learning (SupCon) example.

This module keeps the implementation intentionally small and dependency-light.
It trains a 2D linear encoder on a toy 2-class dataset using SupCon loss.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass


@dataclass(frozen=True)
class Point:
    x: float
    y: float
    label: int


def _l2_normalize(vec: list[float], eps: float = 1e-12) -> list[float]:
    norm = math.sqrt(sum(v * v for v in vec))
    if norm < eps:
        return [0.0 for _ in vec]
    return [v / norm for v in vec]


def _dot(a: list[float], b: list[float]) -> float:
    return sum(x * y for x, y in zip(a, b))


def _build_toy_data(seed: int = 7, per_class: int = 8) -> list[Point]:
    rng = random.Random(seed)
    points: list[Point] = []
    for _ in range(per_class):
        points.append(Point(rng.gauss(-1.2, 0.4), rng.gauss(-0.8, 0.35), 0))
        points.append(Point(rng.gauss(1.3, 0.45), rng.gauss(1.0, 0.4), 1))
    return points


def _two_views(
    points: list[Point], noise_std: float, rng: random.Random
) -> tuple[list[list[float]], list[int]]:
    features: list[list[float]] = []
    labels: list[int] = []
    for p in points:
        for _ in range(2):
            features.append(
                [p.x + rng.gauss(0.0, noise_std), p.y + rng.gauss(0.0, noise_std)]
            )
            labels.append(p.label)
    return features, labels


def _encode(
    features: list[list[float]], w: list[list[float]], b: list[float]
) -> list[list[float]]:
    encoded: list[list[float]] = []
    for x in features:
        z = [
            x[0] * w[0][0] + x[1] * w[1][0] + b[0],
            x[0] * w[0][1] + x[1] * w[1][1] + b[1],
        ]
        encoded.append(_l2_normalize(z))
    return encoded


def supervised_contrastive_loss(
    embeddings: list[list[float]], labels: list[int], temperature: float = 0.15
) -> float:
    """Compute SupCon loss for a batch of normalized embeddings."""
    n = len(embeddings)
    if n != len(labels):
        raise ValueError("embeddings and labels must have equal length")
    if n < 2:
        raise ValueError("at least 2 samples are required")

    total = 0.0
    valid_anchors = 0

    for i in range(n):
        positives = [j for j in range(n) if j != i and labels[j] == labels[i]]
        if not positives:
            continue

        logits = []
        for j in range(n):
            if j == i:
                continue
            logits.append(_dot(embeddings[i], embeddings[j]) / temperature)

        max_logit = max(logits)
        denom = 0.0
        for j in range(n):
            if j == i:
                continue
            denom += math.exp(
                (_dot(embeddings[i], embeddings[j]) / temperature) - max_logit
            )

        log_denom = math.log(denom) + max_logit

        anchor_loss = 0.0
        for p in positives:
            pos_logit = _dot(embeddings[i], embeddings[p]) / temperature
            anchor_loss += -(pos_logit - log_denom)

        total += anchor_loss / len(positives)
        valid_anchors += 1

    if valid_anchors == 0:
        raise ValueError(
            "no valid anchors found; each class needs at least two samples in the batch"
        )

    return total / valid_anchors


def _nearest_centroid_accuracy(
    embeddings: list[list[float]], labels: list[int]
) -> float:
    class_vectors: dict[int, list[list[float]]] = {}
    for vec, label in zip(embeddings, labels):
        class_vectors.setdefault(label, []).append(vec)

    centroids: dict[int, list[float]] = {}
    for label, vecs in class_vectors.items():
        cx = sum(v[0] for v in vecs) / len(vecs)
        cy = sum(v[1] for v in vecs) / len(vecs)
        centroids[label] = _l2_normalize([cx, cy])

    correct = 0
    for vec, label in zip(embeddings, labels):
        predicted = max(centroids, key=lambda cls: _dot(vec, centroids[cls]))
        if predicted == label:
            correct += 1
    return correct / len(labels)


def _finite_diff_grads(
    features: list[list[float]],
    labels: list[int],
    w: list[list[float]],
    b: list[float],
    temperature: float,
    eps: float = 1e-3,
) -> tuple[list[list[float]], list[float]]:
    grad_w = [[0.0, 0.0], [0.0, 0.0]]
    grad_b = [0.0, 0.0]

    def loss_fn() -> float:
        embeddings = _encode(features, w, b)
        return supervised_contrastive_loss(embeddings, labels, temperature=temperature)

    for r in range(2):
        for c in range(2):
            w[r][c] += eps
            lp = loss_fn()
            w[r][c] -= 2 * eps
            lm = loss_fn()
            w[r][c] += eps
            grad_w[r][c] = (lp - lm) / (2 * eps)

    for i in range(2):
        b[i] += eps
        lp = loss_fn()
        b[i] -= 2 * eps
        lm = loss_fn()
        b[i] += eps
        grad_b[i] = (lp - lm) / (2 * eps)

    return grad_w, grad_b


def run_demo(
    seed: int = 13, epochs: int = 80, lr: float = 0.35, temperature: float = 0.15
) -> dict[str, float]:
    """Train a tiny linear encoder with SupCon and print a compact report."""
    rng = random.Random(seed)
    points = _build_toy_data(seed=seed)
    features, labels = _two_views(points, noise_std=0.12, rng=rng)

    w = [[1.0, 0.0], [0.0, 1.0]]
    b = [0.0, 0.0]

    initial_embeddings = _encode(features, w, b)
    initial_loss = supervised_contrastive_loss(
        initial_embeddings, labels, temperature=temperature
    )
    initial_acc = _nearest_centroid_accuracy(initial_embeddings, labels)

    for _ in range(epochs):
        grad_w, grad_b = _finite_diff_grads(
            features, labels, w, b, temperature=temperature
        )
        for r in range(2):
            for c in range(2):
                w[r][c] -= lr * grad_w[r][c]
        for i in range(2):
            b[i] -= lr * grad_b[i]

    final_embeddings = _encode(features, w, b)
    final_loss = supervised_contrastive_loss(
        final_embeddings, labels, temperature=temperature
    )
    final_acc = _nearest_centroid_accuracy(final_embeddings, labels)

    report = {
        "initial_loss": initial_loss,
        "final_loss": final_loss,
        "initial_centroid_acc": initial_acc,
        "final_centroid_acc": final_acc,
    }

    print("SupCon tiny demo")
    print(f"- initial loss: {initial_loss:.4f}")
    print(f"- final loss:   {final_loss:.4f}")
    print(f"- initial centroid acc: {initial_acc:.3f}")
    print(f"- final centroid acc:   {final_acc:.3f}")

    return report


if __name__ == "__main__":
    run_demo()
