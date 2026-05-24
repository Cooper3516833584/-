"""JSON 报告导出。"""

import json
from pathlib import Path
from ..schemas import ReviewRunResult


def export_json(result: ReviewRunResult, output_path: Path) -> None:
    """将审稿结果导出为 JSON 文件。"""
    data = {
        "run_id": result.run_id,
        "article": {
            "title": result.article.title,
            "author": result.article.author,
            "column": result.article.column,
            "article_type": result.article.article_type,
            "images": result.article.images,
            "source_path": result.article.source_path,
        },
        "selector_result": result.selector_result.model_dump(),
        "selected_agent_ids": result.selected_agent_ids,
        "retrieved_context": [
            {
                "chunk_id": c.chunk_id,
                "doc_id": c.doc_id,
                "source_type": c.source_type,
                "title": c.title,
                "score": c.score,
            }
            for c in result.retrieved_context
        ],
        "agent_results": [r.model_dump() for r in result.agent_results],
        "merged_findings": [f.model_dump() for f in result.merged_findings],
        "final_report": result.final_report,
        "errors": result.errors,
        "warnings": result.warnings,
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
