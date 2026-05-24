"""知识库语料加载器：从 cases/rules/style_guides/risky_phrases/examples 加载 txt。"""

from pathlib import Path
from ..schemas import KnowledgeDocument
from ..loaders.frontmatter import load_txt_with_frontmatter

SOURCE_DIRS: dict[str, str] = {
    "cases": "cases",
    "rules": "rules",
    "style_guides": "style_guides",
    "risky_phrases": "risky_phrases",
    "examples": "examples",
}


def infer_doc_id(metadata: dict, path: Path) -> str:
    """从 metadata 或文件名推断 doc_id。"""
    for key in ["doc_id", "case_id", "rule_id", "style_id",
                "phrase_list_id", "example_id", "id"]:
        if metadata.get(key):
            return str(metadata[key])
    return path.stem


def load_corpus(project_root: Path) -> list[KnowledgeDocument]:
    """加载所有知识库目录下的 txt 文件。"""
    documents: list[KnowledgeDocument] = []

    for source_type, dir_name in SOURCE_DIRS.items():
        source_dir = project_root / dir_name
        if not source_dir.exists():
            continue

        for txt_file in sorted(source_dir.glob("*.txt")):
            if txt_file.name == "README.txt":
                continue

            try:
                metadata, content = load_txt_with_frontmatter(txt_file)
            except ValueError:
                continue

            doc_id = infer_doc_id(metadata, txt_file)
            title = str(metadata.get("title", txt_file.stem))
            tags = list(metadata.get("tags", []))

            documents.append(KnowledgeDocument(
                doc_id=doc_id,
                title=title,
                source_type=source_type,  # type: ignore[arg-type]
                path=str(txt_file.resolve()),
                tags=tags,
                content=content,
                metadata=metadata,
            ))

    return documents
