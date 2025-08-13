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
        grouped_counts: Dict[Tuple[str, Optional[str]], int] = {}
        for rec in self._db.get("faces", []):
            name = rec.get("name")
            pid = rec.get("personnel_id")
            key = (name, pid)
            grouped_counts[key] = grouped_counts.get(key, 0) + 1
        results: List[Dict] = []
        for (name, pid), count in sorted(grouped_counts.items(), key=lambda kv: (kv[0][0] or "", kv[0][1] or "")):
            results.append({"name": name, "personnel_id": pid, "samples": count})
        return results

    def add_face(self, name: str, embedding: np.ndarray, personnel_id: Optional[str] = None) -> None:
        if embedding is None or embedding.size == 0:
            raise ValueError("Empty embedding")
        norm = np.linalg.norm(embedding)
        if norm == 0:
            raise ValueError("Zero-norm embedding")
        normalized = (embedding / norm).astype(float).tolist()
        record: Dict = {"name": name, "embedding": normalized}
        if personnel_id:
            record["personnel_id"] = personnel_id
        self._db.setdefault("faces", []).append(record)
        self._write_db(self._db)

    def clear(self) -> None:
        self._db = {"faces": []}
        self._write_db(self._db)

    def best_match(self, embedding: np.ndarray, threshold: float = 0.35) -> Optional[Tuple[str, Optional[str], float]]:
        if not self._db.get("faces"):
            return None
        # Normalize query embedding
        norm = np.linalg.norm(embedding)
        if norm == 0:
            return None
        query = (embedding / norm).astype(float)
        best_name: Optional[str] = None
        best_pid: Optional[str] = None
        best_score: float = -1.0
        for rec in self._db.get("faces", []):
            db_vec = np.array(rec["embedding"], dtype=float)
            score = float(np.dot(query, db_vec))  # cosine similarity as vectors are normalized
            if score > best_score:
                best_score = score
                best_name = rec["name"]
                best_pid = rec.get("personnel_id")
        if best_score >= threshold and best_name is not None:
            return best_name, best_pid, best_score
        return None

    def delete_identity(self, name: str, personnel_id: Optional[str] = None) -> int:
        original = self._db.get("faces", [])
        kept: List[Dict] = []
        removed: int = 0
        for rec in original:
            rec_name = rec.get("name")
            rec_pid = rec.get("personnel_id")
            if rec_name == name and (personnel_id is None and rec_pid is None or rec_pid == personnel_id):
                removed += 1
            else:
                kept.append(rec)
        if removed > 0:
            self._db["faces"] = kept
            self._write_db(self._db)
        return removed

    def rename_identity(
        self,
        old_name: str,
        old_personnel_id: Optional[str],
        new_name: str,
        new_personnel_id: Optional[str],
    ) -> int:
        changed = 0
        for rec in self._db.get("faces", []):
            rec_name = rec.get("name")
            rec_pid = rec.get("personnel_id")
            if rec_name == old_name and (old_personnel_id is None and rec_pid is None or rec_pid == old_personnel_id):
                rec["name"] = new_name
                if new_personnel_id is None:
                    # remove key if exists
                    if "personnel_id" in rec:
                        del rec["personnel_id"]
                else:
                    rec["personnel_id"] = new_personnel_id
                changed += 1
        if changed:
            self._write_db(self._db)
        return changed
