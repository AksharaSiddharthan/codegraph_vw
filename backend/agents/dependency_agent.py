"""Dependency Agent — builds the knowledge graph (nodes + edges)."""
import os
from collections import defaultdict


class DependencyAgent:
    async def run(self, parsed: dict):
        nodes = []
        edges = []
        node_ids = set()
        files = parsed["files"]
        internal_modules = self._internal_modules(files)

        # files / classes / functions
        for f in files:
            file_id = f"file::{f['path']}"
            node_ids.add(file_id)
            nodes.append({
                "id": file_id,
                "label": os.path.basename(f["path"]),
                "type": "file",
                "language": f["language"],
                "path": f["path"],
                "size": f["size"],
                "n_classes": len(f["classes"]),
                "n_functions": len(f["functions"]),
                "n_imports": len(f["imports"]),
                "detail": None,
            })
            for c in f["classes"]:
                cls_id = f"class::{f['path']}::{c['name']}"
                node_ids.add(cls_id)
                nodes.append({
                    "id": cls_id, "label": c["name"], "type": "class",
                    "file": f["path"], "lineno": c["lineno"],
                    "bases": c["bases"], "methods": c["methods"],
                    "docstring": c["docstring"], "detail": None,
                })
                edges.append({"source": file_id, "target": cls_id, "type": "contains"})
            for fn in f["functions"]:
                fn_id = f"func::{f['path']}::{fn['name']}"
                node_ids.add(fn_id)
                nodes.append({
                    "id": fn_id, "label": fn["name"], "type": "function",
                    "file": f["path"], "lineno": fn["lineno"],
                    "args": fn["args"], "is_async": fn["is_async"],
                    "docstring": fn["docstring"], "detail": None,
                })
                edges.append({"source": file_id, "target": fn_id, "type": "contains"})

        # imports
        for f in files:
            file_id = f"file::{f['path']}"
            for imp in f["imports"]:
                module = imp.get("module", "")
                if not module:
                    continue
                target_file = self._resolve_internal(module, internal_modules, f, files)
                if target_file:
                    tid = f"file::{target_file}"
                    if tid in node_ids:
                        edges.append({"source": file_id, "target": tid, "type": "imports"})
                else:
                    root_mod = module.split(".")[0].split("/")[0]
                    if root_mod and not root_mod.startswith("."):
                        dep_id = f"dep::{root_mod}"
                        if dep_id not in node_ids:
                            node_ids.add(dep_id)
                            nodes.append({
                                "id": dep_id, "label": root_mod,
                                "type": "dependency", "external": True, "detail": None,
                            })
                        edges.append({"source": file_id, "target": dep_id, "type": "depends_on"})

        # inheritance
        class_index = defaultdict(list)
        for n in nodes:
            if n["type"] == "class":
                class_index[n["label"]].append(n["id"])
        for n in nodes:
            if n["type"] != "class":
                continue
            for base in n.get("bases", []):
                base_name = base.split(".")[-1]
                if base_name in class_index:
                    for tid in class_index[base_name]:
                        if tid != n["id"]:
                            edges.append({"source": n["id"], "target": tid, "type": "inherits"})

        return {
            "nodes": nodes,
            "edges": edges,
            "stats": {
                "n_files": sum(1 for n in nodes if n["type"] == "file"),
                "n_classes": sum(1 for n in nodes if n["type"] == "class"),
                "n_functions": sum(1 for n in nodes if n["type"] == "function"),
                "n_deps": sum(1 for n in nodes if n["type"] == "dependency"),
                "n_edges": len(edges),
            },
        }

    def _internal_modules(self, files):
        out = {}
        for f in files:
            if f["language"] != "python":
                continue
            rel = f["path"]
            no_ext = rel[:-3] if rel.endswith(".py") else rel
            dotted = no_ext.replace("/", ".")
            out[dotted] = rel
            out[no_ext] = rel
            if dotted.endswith(".__init__"):
                out[dotted[:-9]] = rel
        return out

    def _resolve_internal(self, module, internal_modules, current_file, all_files):
        if module in internal_modules:
            return internal_modules[module]
        parts = module.split(".")
        for i in range(len(parts), 0, -1):
            candidate = ".".join(parts[:i])
            if candidate in internal_modules:
                return internal_modules[candidate]
        if "/" not in module and "." not in module:
            return None
        if module.startswith("."):
            cur_dir = os.path.dirname(current_file["path"])
            candidate = os.path.normpath(os.path.join(cur_dir, module)).replace(os.sep, "/")
            for f in all_files:
                base = f["path"]
                no_ext = os.path.splitext(base)[0]
                if no_ext == candidate or base == candidate:
                    return base
        return None
