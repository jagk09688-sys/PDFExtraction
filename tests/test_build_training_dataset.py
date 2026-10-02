import json
import sys
import tempfile
from pathlib import Path

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from build_training_dataset import build


def test_build_accepts_auto_draft_annotations_when_allowed():
    with tempfile.TemporaryDirectory() as tmp_dir:
        root = Path(tmp_dir)
        project_dir = root / "commercial_dataset" / "projects" / "demo_project"
        (project_dir / "pages").mkdir(parents=True)
        (project_dir / "annotations").mkdir(parents=True)

        page_path = project_dir / "pages" / "page_001.png"
        Image.new("RGB", (10, 10), color="white").save(page_path)
        Image.new("RGB", (10, 10), color="white").save(project_dir / "pages" / "page_002.png")

        annotation = {
            "page_number": 1,
            "image_width": 10,
            "image_height": 10,
            "source_pdf": "demo.pdf",
            "annotator": "AUTO_DRAFT_REQUIRES_REVIEW",
            "timestamp": "2026-01-01T00:00:00Z",
            "rooms": [{"label": "UNREVIEWED_ROOM", "polygon": [[1, 1], [1, 9], [9, 9], [9, 1]]}],
            "dimensions": [],
            "text_labels": [],
            "structural_elements": [],
            "table_rows": [],
        }
        (project_dir / "annotations" / "page_001.json").write_text(json.dumps(annotation), encoding="utf-8")
        noisy_annotation = dict(annotation)
        noisy_annotation["page_number"] = 2
        noisy_annotation["rooms"] = annotation["rooms"] * 3
        (project_dir / "annotation_drafts").mkdir(parents=True)
        (project_dir / "annotation_drafts" / "page_002.json").write_text(json.dumps(noisy_annotation), encoding="utf-8")

        output_root = root / "pseudo_dataset"
        build(root / "commercial_dataset", output_root, val_ratio=0.0, seed=42, allow_auto_drafts=True, max_pseudo_rooms=2)

        assert (output_root / "train" / "images" / "demo_project__page_001.png").exists()
        assert (output_root / "train" / "masks" / "demo_project__page_001.png").exists()
        report = json.loads((output_root / "quality_report.json").read_text(encoding="utf-8"))
        assert report["eligible_projects"] == 1
        assert report["pseudo_label_projects"] == 1
        assert report["pseudo_label_pages"] == 1
        assert report["eligible_pages"] == 1
        assert any(
            "exceed the pseudo-label limit" in reason
            for excluded in report["excluded_pages"]
            for reason in excluded["reasons"]
        )


if __name__ == "__main__":
    test_build_accepts_auto_draft_annotations_when_allowed()
