import json
import pickle
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


class ModelRegistry:
    """Versioned artifacts: <root>/<name>/<version>/{model.pkl, meta.json}.

    Training writes a new version; serving loads the latest (or a pinned one), so
    rolling back is loading an older version. Swap the root for object storage
    (S3/GCS) when several machines need the same artifacts.

    Pickles run code when loaded: only load artifacts written by these pipelines.
    """

    def __init__(self, root: Path):
        self.root = root

    def save(self, obj: Any, name: str, metadata: dict[str, Any] | None = None) -> str:
        version = datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ")
        path = self.root / name / version
        path.mkdir(parents=True)
        with (path / "model.pkl").open("wb") as f:
            pickle.dump(obj, f)
        meta = {"name": name, "version": version, **(metadata or {})}
        (path / "meta.json").write_text(json.dumps(meta, indent=1, default=str))
        return version

    def versions(self, name: str) -> list[str]:
        folder = self.root / name
        return sorted(p.name for p in folder.iterdir() if p.is_dir()) if folder.exists() else []

    def load(self, name: str, version: str | None = None) -> tuple[Any, dict[str, Any]]:
        versions = self.versions(name)
        if not versions:
            raise FileNotFoundError(f"no '{name}' artifacts in {self.root} (run pipelines.train)")
        path = self.root / name / (version or versions[-1])
        with (path / "model.pkl").open("rb") as f:
            obj = pickle.load(f)
        return obj, json.loads((path / "meta.json").read_text())
