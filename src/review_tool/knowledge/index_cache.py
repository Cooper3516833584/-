"""知识索引缓存：避免每次审稿都重新切块。"""

import hashlib
import json
from pathlib import Path
from ..schemas import KnowledgeChunk


def _compute_dir_hash(root: Path) -> str:
    """计算知识库目录下所有 txt 文件的综合哈希。"""
    hasher = hashlib.sha1()
    source_dirs = ["cases", "rules", "style_guides", "risky_phrases", "examples"]
    for dir_name in source_dirs:
        sd = root / dir_name
        if not sd.exists():
            continue
        for txt_file in sorted(sd.glob("*.txt")):
            hasher.update(txt_file.read_bytes())
    return hasher.hexdigest()


def load_cache(root: Path) -> list[KnowledgeChunk] | None:
    """如果缓存有效，返回缓存的 chunk 列表；否则返回 None。"""
    cache_dir = root / ".cache"
    index_file = cache_dir / "corpus_index.jsonl"
    hash_file = cache_dir / "file_hashes.json"

    if not index_file.exists() or not hash_file.exists():
        return None

    current_hash = _compute_dir_hash(root)
    try:
        stored = json.loads(hash_file.read_text(encoding="utf-8"))
        if stored.get("hash") != current_hash:
            return None
    except (json.JSONDecodeError, KeyError):
        return None

    chunks = []
    for line in index_file.read_text(encoding="utf-8").strip().split("\n"):
        if line.strip():
            try:
                chunks.append(KnowledgeChunk.model_validate_json(line))
            except Exception:
                return None
    return chunks if chunks else None


def save_cache(root: Path, chunks: list[KnowledgeChunk]) -> None:
    """保存 chunk 缓存。"""
    cache_dir = root / ".cache"
    cache_dir.mkdir(parents=True, exist_ok=True)

    current_hash = _compute_dir_hash(root)
    hash_file = cache_dir / "file_hashes.json"
    hash_file.write_text(
        json.dumps({"hash": current_hash}, ensure_ascii=False),
        encoding="utf-8",
    )

    index_file = cache_dir / "corpus_index.jsonl"
    lines = [c.model_dump_json() for c in chunks]
    index_file.write_text("\n".join(lines), encoding="utf-8")
