import json
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np


class FaceStorage:
    def __init__(self, data_dir: str = "data", db_filename: str = "faces.json") -> None:
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.db_path = self.data_dir / db_filename
        if not self.db_path.exists():
            self._write_db({"faces": []})
        self._db = self._read_db()

    def _read_db(self) -> Dict:
        try:
            with self.db_path.open("r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {"faces": []}

    def _write_db(self, data: Dict) -> None:
        with self.db_path.open("w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

    def reload(self) -> None:
        self._db = self._read_db()

    def list_faces(self) -> List[Dict]:
        return list(self._db.get("faces", []))

    def list_identities_summary(self) -> List[Dict]:
        name_to_count: Dict[str, int] = {}
        for rec in self._db.get("faces", []):
            name_to_count[rec["name"]] = name_to_count.get(rec["name"], 0) + 1
        return [{"name": name, "samples": count} for name, count in sorted(name_to_count.items())]

    def add_face(self, name: str, embedding: np.ndarray) -> None:
        if embedding is None or embedding.size == 0:
            raise ValueError("Empty embedding")
        # Ensure normalized to unit length
        norm = np.linalg.norm(embedding)
        if norm == 0:
            raise ValueError("Zero-norm embedding")
        normalized = (embedding / norm).astype(float).tolist()
        self._db.setdefault("faces", []).append({"name": name, "embedding": normalized})
        self._write_db(self._db)

    def clear(self) -> None:
        self._db = {"faces": []}
        self._write_db(self._db)

    def best_match(self, embedding: np.ndarray, threshold: float = 0.35) -> Optional[Tuple[str, float]]:
        if not self._db.get("faces"):
            return None
        # Normalize query embedding
        norm = np.linalg.norm(embedding)
        if norm == 0:
            return None
        query = (embedding / norm).astype(float)
        best_name: Optional[str] = None
        best_score: float = -1.0
        for rec in self._db.get("faces", []):
            db_vec = np.array(rec["embedding"], dtype=float)
            score = float(np.dot(query, db_vec))  # cosine similarity as vectors are normalized
            if score > best_score:
                best_score = score
                best_name = rec["name"]
        if best_score >= threshold and best_name is not None:
            return best_name, best_score
        return None
