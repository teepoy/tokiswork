#!/usr/bin/env python
"""Tests for database-backed embedding triplet workflow."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from tokiswork_triplets import (
    EmbeddingDistanceTripletSampler,
    ImageSample,
    InMemorySampleRepository,
    build_sample_manifest,
    export_manifest_json,
    export_triplets_jsonl,
    to_fiftyone_payload,
)


class TripletWorkflowTest(unittest.TestCase):
    def setUp(self) -> None:
        # q1 is closest to p1 (same label), then n1 (different label) as a hard negative.
        self.samples = [
            ImageSample(
                sample_id="q1",
                image_uri="/data/q1.jpg",
                embedding=[0.0, 0.0],
                metadata={"label": "cat", "split": "train"},
                source_ref="dataset_a:row_1",
            ),
            ImageSample(
                sample_id="p1",
                image_uri="/data/p1.jpg",
                embedding=[0.1, 0.1],
                metadata={"label": "cat", "split": "train"},
                source_ref="dataset_a:row_2",
            ),
            ImageSample(
                sample_id="n1",
                image_uri="/data/n1.jpg",
                embedding=[0.2, 0.2],
                metadata={"label": "dog", "split": "train"},
                source_ref="dataset_a:row_3",
            ),
            ImageSample(
                sample_id="n_far",
                image_uri="/data/n_far.jpg",
                embedding=[5.0, 5.0],
                metadata={"label": "dog", "split": "train"},
                source_ref="dataset_a:row_4",
            ),
        ]

    def test_embedding_sampler_v1(self) -> None:
        repo = InMemorySampleRepository(self.samples)
        sampler = EmbeddingDistanceTripletSampler(neighbor_k=3)

        triplets, edges = sampler.sample_triplets(repo, ["q1"])

        self.assertEqual(len(triplets), 1)
        t = triplets[0]
        self.assertEqual(t.query_id, "q1")
        self.assertEqual(t.positive_id, "p1")
        self.assertEqual(t.negative_id, "n1")
        self.assertEqual(t.locality_definition, "embedding_l2_knn")
        self.assertLess(t.positive_distance, t.negative_distance)
        self.assertEqual(t.metadata["query_source_ref"], "dataset_a:row_1")

        roles = {(e.candidate_id, e.role) for e in edges if e.query_id == "q1"}
        self.assertIn(("p1", "positive"), roles)
        self.assertIn(("n1", "negative"), roles)

    def test_manifest_and_exports(self) -> None:
        repo = InMemorySampleRepository(self.samples)
        sampler = EmbeddingDistanceTripletSampler(neighbor_k=3)
        triplets, edges = sampler.sample_triplets(repo, ["q1"])

        manifest = build_sample_manifest(repo.list_samples())
        self.assertIn("q1", manifest)
        self.assertEqual(manifest["q1"]["source_ref"], "dataset_a:row_1")

        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            triplets_path = root / "triplets.jsonl"
            manifest_path = root / "manifest.json"

            export_triplets_jsonl(triplets_path, triplets)
            export_manifest_json(manifest_path, manifest)

            self.assertTrue(triplets_path.exists())
            self.assertTrue(manifest_path.exists())

            lines = triplets_path.read_text(encoding="utf-8").strip().splitlines()
            self.assertEqual(len(lines), 1)
            parsed_triplet = json.loads(lines[0])
            self.assertEqual(parsed_triplet["query_id"], "q1")

            parsed_manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            self.assertEqual(parsed_manifest["n1"]["metadata"]["label"], "dog")

        payload = to_fiftyone_payload(repo.list_samples(), edges)
        payload_by_id = {item["sample_id"]: item for item in payload}
        self.assertIn("candidate_edges", payload_by_id["q1"])
        self.assertGreaterEqual(len(payload_by_id["q1"]["candidate_edges"]), 2)


if __name__ == "__main__":
    unittest.main()
