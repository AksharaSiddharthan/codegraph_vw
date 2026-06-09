"""Parser Agent — extracts classes, functions, imports from source files."""
import ast
import os
import re

SUPPORTED_EXTS = {".py", ".js", ".jsx", ".ts", ".tsx"}
IGNORE_DIRS = {
    ".git", "node_modules", "__pycache__", ".venv", "venv", "env",
    "dist", "build", ".next", ".pytest_cache", ".mypy_cache",
    "site-packages", ".tox", "target", ".idea", ".vscode",
}
MAX_FILE_SIZE = 500_000


class ParserAgent:
    async def run(self, repo_path: str):
        files = self._walk(repo_path)
        parsed = {"repo_path": repo_path, "files": []}
        for fpath in files:
            rel = os.path.relpath(fpath, repo_path).replace(os.sep, "/")
            ext = os.path.splitext(fpath)[1].lower()
            try:
                with open(fpath, "r", encoding="utf-8", errors="ignore") as f:
                    source = f.read()
            except Exception:
                continue

            file_info = {
                "path": rel,
                "abs_path": fpath,
                "ext": ext,
                "language": self._lang(ext),
                "size": len(source),
                "classes": [],
                "functions": [],
                "imports": [],
                "source_snippet": source[:2000],
            }

            if ext == ".py":
                self._parse_python(source, file_info)
            elif ext in {".js", ".jsx", ".ts", ".tsx"}:
                self._parse_js(source, file_info)

            parsed["files"].append(file_info)

        return parsed

    def _walk(self, root: str):
        out = []
        for dirpath, dirnames, filenames in os.walk(root):
            dirnames[:] = [d for d in dirnames if d not in IGNORE_DIRS and not d.startswith(".")]
            for fn in filenames:
                ext = os.path.splitext(fn)[1].lower()
                if ext not in SUPPORTED_EXTS:
                    continue
                full = os.path.join(dirpath, fn)
                try:
                    if os.path.getsize(full) > MAX_FILE_SIZE:
                        continue
                except OSError:
                    continue
                out.append(full)
        return out

    def _lang(self, ext: str):
        return {".py": "python", ".js": "javascript", ".jsx": "javascript",
                ".ts": "typescript", ".tsx": "typescript"}.get(ext, "unknown")

    def _parse_python(self, source: str, file_info: dict):
        try:
            tree = ast.parse(source)
        except SyntaxError:
            return
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                methods = [n.name for n in node.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]
                bases = []
                for b in node.bases:
                    try:
                        bases.append(ast.unparse(b))
                    except Exception:
                        pass
                file_info["classes"].append({
                    "name": node.name, "lineno": node.lineno,
                    "bases": bases, "methods": methods,
                    "docstring": ast.get_docstring(node) or "",
                })
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if any(node is c for c in tree.body):
                    file_info["functions"].append({
                        "name": node.name, "lineno": node.lineno,
                        "args": [a.arg for a in node.args.args],
                        "is_async": isinstance(node, ast.AsyncFunctionDef),
                        "docstring": ast.get_docstring(node) or "",
                    })
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    file_info["imports"].append({
                        "module": alias.name, "alias": alias.asname, "kind": "import",
                    })
            elif isinstance(node, ast.ImportFrom):
                module = node.module or ""
                for alias in node.names:
                    file_info["imports"].append({
                        "module": module, "name": alias.name,
                        "alias": alias.asname, "kind": "from",
                    })

    _re_class = re.compile(r"^\s*(?:export\s+(?:default\s+)?)?class\s+(\w+)(?:\s+extends\s+([\w.]+))?", re.MULTILINE)
    _re_fn = re.compile(r"^\s*(?:export\s+(?:default\s+)?)?(?:async\s+)?function\s+(\w+)\s*\(", re.MULTILINE)
    _re_arrow = re.compile(r"^\s*(?:export\s+)?(?:const|let|var)\s+(\w+)\s*=\s*(?:async\s*)?\(", re.MULTILINE)
    _re_import = re.compile(r"""^\s*import\s+(?:(\*\s+as\s+\w+|\{[^}]+\}|\w+)(?:\s*,\s*(\{[^}]+\}|\w+))?\s+from\s+)?['"]([^'"]+)['"]""", re.MULTILINE)
    _re_require = re.compile(r"""require\s*\(\s*['"]([^'"]+)['"]\s*\)""")

    def _parse_js(self, source: str, file_info: dict):
        for m in self._re_class.finditer(source):
            lineno = source[:m.start()].count("\n") + 1
            file_info["classes"].append({
                "name": m.group(1), "lineno": lineno,
                "bases": [m.group(2)] if m.group(2) else [],
                "methods": [], "docstring": "",
            })
        for m in self._re_fn.finditer(source):
            lineno = source[:m.start()].count("\n") + 1
            file_info["functions"].append({
                "name": m.group(1), "lineno": lineno, "args": [],
                "is_async": "async" in m.group(0), "docstring": "",
            })
        for m in self._re_arrow.finditer(source):
            lineno = source[:m.start()].count("\n") + 1
            file_info["functions"].append({
                "name": m.group(1), "lineno": lineno, "args": [],
                "is_async": "async" in m.group(0), "docstring": "",
            })
        for m in self._re_import.finditer(source):
            file_info["imports"].append({"module": m.group(3), "kind": "import"})
        for m in self._re_require.finditer(source):
            file_info["imports"].append({"module": m.group(1), "kind": "require"})
