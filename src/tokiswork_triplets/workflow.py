"""Database-backed triplet sampling workflow utilities.

This module implements a first version of behavior-local sampling where
locality is defined by embedding distance.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
import json
from pathlib import Path
from typing import Callable


Metadata = dict[str, object]
PositiveRule = Callable[["ImageSample", "ImageSample"], bool]
NegativeRule = Callable[["ImageSample", "ImageSample"], bool]


@dataclass(slots=True)
class ImageSample:
    """Represents one image row from the external sample database."""

    sample_id: str
    image_uri: str
    embedding: list[float]
    metadata: Metadata = field(default_factory=dict)
    source_ref: str = ""


@dataclass(slots=True)
class CandidateEdge:
    """A sampled relation from query to candidate with strategy metadata."""

    query_id: str
    candidate_id: str
    role: str
    distance: float
    strategy: str
    reason: str


@dataclass(slots=True)
class TripletRecord:
    """Final triplet plus fields needed for provenance and auditing."""

    query_id: str
    positive_id: str
    negative_id: str
    positive_distance: float
    negative_distance: float
    positive_strategy: str
    negative_strategy: str
    locality_definition: str = "embedding_l2_knn"
    metadata: Metadata = field(default_factory=dict)


class InMemorySampleRepository:
    """In-memory stand-in for an external sample database.

    The same interface can be implemented by a real DB adapter.
    """

    def __init__(self, samples: list[ImageSample] | None = None):
        self._samples: dict[str, ImageSample] = {}
        for sample in samples or []:
            self.upsert(sample)

    def upsert(self, sample: ImageSample) -> None:
        self._samples[sample.sample_id] = sample

    def get(self, sample_id: str) -> ImageSample:
        return self._samples[sample_id]

    def list_samples(self) -> list[ImageSample]:
        return list(self._samples.values())

    def nearest_neighbors(
        self,
        query_id: str,
        *,
        k: int,
    ) -> list[tuple[ImageSample, float]]:
        query = self.get(query_id)
        neighbors: list[tuple[ImageSample, float]] = []
        for candidate in self._samples.values():
            if candidate.sample_id == query_id:
                continue
            dist = _l2_distance(query.embedding, candidate.embedding)
            neighbors.append((candidate, dist))
        neighbors.sort(key=lambda pair: pair[1])
        return neighbors[:k]


class EmbeddingDistanceTripletSampler:
    """v1 sampler using embedding-distance neighborhoods.

    Behavior locality is modeled as nearest neighbors by L2 distance.
    """

    def __init__(
        self,
        *,
        neighbor_k: int = 64,
        positive_rule: PositiveRule | None = None,
        negative_rule: NegativeRule | None = None,
        positive_strategy: str = "embedding_knn_positive_v1",
        negative_strategy: str = "embedding_knn_hard_negative_v1",
    ):
        if neighbor_k <= 0:
            raise ValueError("neighbor_k must be > 0")
        self.neighbor_k = neighbor_k
        self.positive_rule = positive_rule or default_positive_rule
        self.negative_rule = negative_rule or default_negative_rule
        self.positive_strategy = positive_strategy
        self.negative_strategy = negative_strategy

    def sample_triplets(
        self,
        repo: InMemorySampleRepository,
        query_ids: list[str],
    ) -> tuple[list[TripletRecord], list[CandidateEdge]]:
        triplets: list[TripletRecord] = []
        edges: list[CandidateEdge] = []

        for query_id in query_ids:
            query = repo.get(query_id)
            neighborhood = repo.nearest_neighbors(query_id, k=self.neighbor_k)
            positive = self._pick_positive(query, neighborhood)
            negative = self._pick_negative(query, neighborhood)

            for candidate, dist in neighborhood:
                role = "candidate"
                reason = "neighborhood"
                if positive and candidate.sample_id == positive[0].sample_id:
                    role = "positive"
                    reason = "positive_rule_match"
                elif negative and candidate.sample_id == negative[0].sample_id:
                    role = "negative"
                    reason = "negative_rule_match"
                edges.append(
                    CandidateEdge(
                        query_id=query.sample_id,
                        candidate_id=candidate.sample_id,
                        role=role,
                        distance=dist,
                        strategy="embedding_l2_knn",
                        reason=reason,
                    )
                )

            if not positive or not negative:
                continue

            positive_sample, positive_dist = positive
            negative_sample, negative_dist = negative
            triplets.append(
                TripletRecord(
                    query_id=query.sample_id,
                    positive_id=positive_sample.sample_id,
                    negative_id=negative_sample.sample_id,
                    positive_distance=positive_dist,
                    negative_distance=negative_dist,
                    positive_strategy=self.positive_strategy,
                    negative_strategy=self.negative_strategy,
                    metadata={
                        "query_source_ref": query.source_ref,
                        "positive_source_ref": positive_sample.source_ref,
                        "negative_source_ref": negative_sample.source_ref,
                    },
                )
            )

        return triplets, edges

    def _pick_positive(
        self,
        query: ImageSample,
        neighborhood: list[tuple[ImageSample, float]],
    ) -> tuple[ImageSample, float] | None:
        for candidate, dist in neighborhood:
            if self.positive_rule(query, candidate):
                return candidate, dist
        return None

    def _pick_negative(
        self,
        query: ImageSample,
        neighborhood: list[tuple[ImageSample, float]],
    ) -> tuple[ImageSample, float] | None:
        for candidate, dist in neighborhood:
            if self.negative_rule(query, candidate):
                return candidate, dist
        return None


def default_positive_rule(query: ImageSample, candidate: ImageSample) -> bool:
    """Default positive: same label or augmentation family."""

    query_label = query.metadata.get("label")
    cand_label = candidate.metadata.get("label")
    if query_label and query_label == cand_label:
        return True

    cand_parent = candidate.metadata.get("parent_sample_id")
    query_parent = query.metadata.get("parent_sample_id")
    if cand_parent and cand_parent == query.sample_id:
        return True
    if query_parent and query_parent == candidate.sample_id:
        return True
    if cand_parent and query_parent and cand_parent == query_parent:
        return True

    return False


def default_negative_rule(query: ImageSample, candidate: ImageSample) -> bool:
    """Default negative: not positive and label differs when label exists."""

    if default_positive_rule(query, candidate):
        return False

    query_label = query.metadata.get("label")
    cand_label = candidate.metadata.get("label")
    if query_label is None or cand_label is None:
        return True
    return query_label != cand_label


def build_sample_manifest(samples: list[ImageSample]) -> dict[str, Metadata]:
    """Build a provenance-preserving manifest keyed by sample_id."""

    manifest: dict[str, Metadata] = {}
    for sample in samples:
        manifest[sample.sample_id] = {
            "sample_id": sample.sample_id,
            "image_uri": sample.image_uri,
            "source_ref": sample.source_ref,
            "metadata": sample.metadata,
        }
    return manifest


def to_fiftyone_payload(
    samples: list[ImageSample],
    edges: list[CandidateEdge],
) -> list[dict[str, object]]:
    """Create a payload that can be imported into FiftyOne by caller code.

    The function avoids a hard dependency on FiftyOne in this repository.
    """

    edge_map: dict[str, list[dict[str, object]]] = {}
    for edge in edges:
        edge_map.setdefault(edge.query_id, []).append(
            {
                "candidate_id": edge.candidate_id,
                "role": edge.role,
                "distance": edge.distance,
                "strategy": edge.strategy,
                "reason": edge.reason,
            }
        )

    payload: list[dict[str, object]] = []
    for sample in samples:
        payload.append(
            {
                "sample_id": sample.sample_id,
                "filepath": sample.image_uri,
                "source_ref": sample.source_ref,
                "metadata": sample.metadata,
                "candidate_edges": edge_map.get(sample.sample_id, []),
            }
        )
    return payload


def export_triplets_jsonl(path: str | Path, triplets: list[TripletRecord]) -> None:
    """Export normalized triplets as JSONL."""

    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for item in triplets:
            f.write(json.dumps(asdict(item), ensure_ascii=False) + "\n")


def export_manifest_json(path: str | Path, manifest: dict[str, Metadata]) -> None:
    """Export sample manifest for provenance lookup."""

    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)
        f.write("\n")


def _l2_distance(a: list[float], b: list[float]) -> float:
    if len(a) != len(b):
        raise ValueError("Embeddings must have same dimensions")
    return sum((x - y) ** 2 for x, y in zip(a, b)) ** 0.5
