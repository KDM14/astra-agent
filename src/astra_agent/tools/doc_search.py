"""Local documentation and knowledge search tool."""

from __future__ import annotations

import math
import re
from pathlib import Path
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from astra_agent.core.models import PermissionLevel, SideEffectType
from astra_agent.tools.base import BaseTool


class DocSearchInput(BaseModel):
    """Input parameters for documentation search."""
    query: str = Field(..., description="Keywords or questions to search for in documentation.")
    docs_dir: Optional[str] = Field("docs", description="Directory to search (relative to workspace or project root).")
    top_k: int = Field(5, ge=1, le=20, description="Number of top relevant excerpts to return.")


class DocSearchTool(BaseTool):
    """Searches indexed documentation files and returns excerpts with provenance."""

    name = "doc_search"
    description = "Searches local markdown and text documentation for relevant sections."
    permission_level = PermissionLevel.READ_ONLY
    side_effect_type = SideEffectType.NONE
    idempotent = True
    input_schema = DocSearchInput

    def _run(self, inputs: DocSearchInput) -> Dict[str, Any]:
        base_dir = Path(self.workspace_dir).resolve() if self.workspace_dir else Path.cwd()
        target_dir = (base_dir / inputs.docs_dir).resolve() if inputs.docs_dir else base_dir

        if not target_dir.exists() or not target_dir.is_dir():
            # Fallback to base_dir if specific docs dir doesn't exist
            target_dir = base_dir

        query_tokens = set(re.findall(r"\w+", inputs.query.lower()))
        if not query_tokens:
            raise ValueError("Query contains no searchable alphanumeric tokens.")

        results: List[Dict[str, Any]] = []

        for file_path in target_dir.rglob("*"):
            if not file_path.is_file() or file_path.suffix.lower() not in (".md", ".txt", ".rst"):
                continue

            try:
                content = file_path.read_text(encoding="utf-8", errors="ignore")
            except Exception:
                continue

            paragraphs = content.split("\n\n")
            for idx, p in enumerate(paragraphs):
                p_clean = p.strip()
                if not p_clean or len(p_clean) < 20:
                    continue

                p_tokens = re.findall(r"\w+", p_clean.lower())
                matches = [t for t in p_tokens if t in query_tokens]
                if not matches:
                    continue

                # Score based on frequency and token coverage
                coverage = len(set(matches)) / len(query_tokens)
                score = coverage * (1.0 + math.log(1 + len(matches)))

                rel_path = file_path.relative_to(base_dir) if file_path.is_relative_to(base_dir) else file_path.name
                results.append({
                    "score": round(score, 3),
                    "file": str(rel_path),
                    "section_index": idx,
                    "excerpt": p_clean[:500],
                })

        # Sort descending by score
        results.sort(key=lambda x: x["score"], reverse=True)
        top_results = results[:inputs.top_k]

        return {
            "query": inputs.query,
            "total_matches": len(results),
            "results": top_results,
        }
