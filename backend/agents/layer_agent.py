"""
Layer Agent — heuristically classifies each file into an architectural layer
so the UI can color-code by layer (entry / api / business / data / ui /
util / config / test). No LLM calls; pure pattern matching for speed.
"""
import os
import re

LAYERS = ["entry", "api", "business", "data", "ui", "util", "config", "test", "other"]

PATH_RULES = [
    # (regex on path, layer)
    (r"(^|/)(tests?|__tests__|spec)(/|$)", "test"),
    (r"(^|/)(routes?|api|controllers?|handlers?|endpoints?|views?)(/|$)", "api"),
    (r"(^|/)(models?|schema|db|database|repositor(y|ies)|dao|entities)(/|$)", "data"),
    (r"(^|/)(services?|usecases?|domain|business|core|logic)(/|$)", "business"),
    (r"(^|/)(components?|pages?|ui|frontend|client|widgets?)(/|$)", "ui"),
    (r"(^|/)(utils?|helpers?|lib|common|shared|tools?)(/|$)", "util"),
    (r"(^|/)(config|settings|conf)(/|$)", "config"),
    (r"(^|/)(migrations?)(/|$)", "data"),
]
FILENAME_RULES = [
    (r"^(main|app|server|index|run|manage|wsgi|asgi)\.(py|js|ts|jsx|tsx)$", "entry"),
    (r".*\.test\.(js|ts|jsx|tsx|py)$", "test"),
    (r".*_test\.(py)$", "test"),
    (r"test_.*\.py$", "test"),
    (r"^(settings|config|conf)\.(py|js|ts)$", "config"),
]

# Content-based hints (Python only — avoids matching JS strings literally inside our own regex sources)
PY_CONTENT_RULES = [
    (re.compile(r"if\s+__name__\s*==\s*['\"]__main__['\"]"), "entry"),
    (re.compile(r"^\s*@(app|router|blueprint)\.(get|post|put|delete|patch)\b", re.MULTILINE), "api"),
    (re.compile(r"^\s*(from\s+sqlalchemy|import\s+sqlalchemy|from\s+django\.db)\b", re.MULTILINE), "data"),
]


class LayerAgent:
    async def run(self, graph_data: dict, parsed: dict):
        # Build content-snippet lookup
        content_by_path = {f["path"]: f.get("source_snippet", "") for f in parsed["files"]}

        for n in graph_data["nodes"]:
            if n["type"] == "file":
                n["layer"] = self._classify_file(n["path"], content_by_path.get(n["path"], ""))
            elif n["type"] in ("class", "function"):
                # inherit from the file containing it
                fp = n.get("file", "")
                n["layer"] = self._classify_file(fp, content_by_path.get(fp, ""))
            elif n["type"] == "dependency":
                n["layer"] = "external"
            else:
                n["layer"] = "other"

        # Tally
        layer_counts = {}
        for n in graph_data["nodes"]:
            l = n.get("layer", "other")
            layer_counts[l] = layer_counts.get(l, 0) + 1
        graph_data["stats"]["layers"] = layer_counts
        return graph_data

    def _classify_file(self, path: str, content: str) -> str:
        if not path:
            return "other"
        path_lower = path.lower()
        fname = os.path.basename(path_lower)

        # Filename rules trump path rules (main.py beats being inside src/)
        for pat, layer in FILENAME_RULES:
            if re.match(pat, fname):
                return layer

        # Path rules
        for pat, layer in PATH_RULES:
            if re.search(pat, path_lower):
                return layer

        # Content rules — only for Python files. Anchor with line start so we
        # match real import/decorator statements, not random substrings in
        # docstrings or string literals.
        if path_lower.endswith(".py"):
            for pat, layer in PY_CONTENT_RULES:
                if pat.search(content):
                    return layer

        return "other"
