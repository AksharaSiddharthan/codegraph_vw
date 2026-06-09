"""
Flowchart Agent — builds a left-to-right process flowchart of the project.
Groups files into architectural lanes (entry → api → business → data → ui)
and traces calls between them. Also asks the LLM for a narrative.
"""
import ast
import os
import httpx
import asyncio

OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://localhost:11434")
MODEL = os.environ.get("OLLAMA_MODEL", "qwen2.5-coder:7b")

# Left-to-right order of lanes in the flowchart
LANE_ORDER = ["entry", "api", "business", "data", "ui", "util", "config", "test", "other"]


class FlowchartAgent:
    async def run(self, parsed: dict, graph_data: dict):
        files = parsed["files"]

        # Build symbol-to-file map for cross-file call resolution
        symbol_to_file = {}
        for f in files:
            for c in f["classes"]:
                symbol_to_file.setdefault(c["name"], f["path"])
            for fn in f["functions"]:
                symbol_to_file.setdefault(fn["name"], f["path"])

        # Cross-file call edges (Python AST only)
        call_edges = self._extract_call_edges(files, symbol_to_file)

        # Layer lookup from already-classified graph
        file_layer = {n["path"]: n.get("layer", "other")
                      for n in graph_data["nodes"] if n["type"] == "file"}

        # Identify internal imports between files using the dependency-agent edges
        # so the flowchart still has connectivity for projects with no cross-file calls.
        import_edges = []
        path_set_all = set(file_layer.keys())
        for e in graph_data.get("edges", []):
            if e["type"] == "imports":
                s = e["source"].replace("file::", "")
                t = e["target"].replace("file::", "")
                if s in path_set_all and t in path_set_all:
                    import_edges.append({"source_file": s, "target_file": t, "symbol": "imports"})

        # Choose the files that participate in the flowchart:
        # everything that's an entry point, any file involved in a call or import edge,
        # and one or two representative files from every populated architectural lane.
        entry_files = {f["path"] for f in files
                       if file_layer.get(f["path"]) == "entry"}
        involved = set(entry_files)
        for e in call_edges + import_edges:
            involved.add(e["source_file"])
            involved.add(e["target_file"])

        # Make sure every populated lane is represented (otherwise a simple
        # project with no cross-file calls would show only the entry point).
        for lane in LANE_ORDER:
            if lane in {"test", "other"}:
                continue
            lane_files = [p for p, l in file_layer.items() if l == lane]
            if lane_files and not any(file_layer.get(p) == lane for p in involved):
                # pick the biggest two files in this lane
                lane_files.sort(
                    key=lambda p: next(
                        (n.get("n_classes", 0) + n.get("n_functions", 0)
                         for n in graph_data["nodes"]
                         if n["type"] == "file" and n["path"] == p), 0),
                    reverse=True,
                )
                involved.update(lane_files[:2])

        # Final fallback: if we still found nothing, grab the biggest files
        if not involved:
            top = sorted(files, key=lambda f: f["size"], reverse=True)[:8]
            involved = {f["path"] for f in top}

        # Group involved files by lane
        lanes = {l: [] for l in LANE_ORDER}
        for path in involved:
            lane = file_layer.get(path, "other")
            lanes.setdefault(lane, []).append(path)

        # Build flowchart nodes
        flow_nodes = []
        for lane in LANE_ORDER:
            for path in lanes.get(lane, []):
                flow_nodes.append({
                    "id": f"flow::{path}",
                    "label": os.path.basename(path),
                    "path": path,
                    "lane": lane,
                    "is_entry": path in entry_files,
                })

        # Edges: keep only those between involved files
        flow_edges = []
        seen = set()
        for e in call_edges:
            if e["source_file"] in involved and e["target_file"] in involved:
                key = (e["source_file"], e["target_file"])
                if key in seen:
                    continue
                seen.add(key)
                flow_edges.append({
                    "source": f"flow::{e['source_file']}",
                    "target": f"flow::{e['target_file']}",
                    "label": e["symbol"],
                })

        # Add import-based edges to flesh out connectivity
        path_set = involved
        for f in files:
            if f["path"] not in path_set:
                continue
            for imp in f["imports"]:
                mod = imp.get("module", "")
                if not mod:
                    continue
                for tgt in path_set:
                    if tgt == f["path"]:
                        continue
                    no_ext = os.path.splitext(tgt)[0]
                    dotted = no_ext.replace("/", ".")
                    base = os.path.basename(no_ext)
                    if mod == dotted or mod == base or mod.endswith("." + base):
                        key = (f["path"], tgt)
                        if key not in seen:
                            seen.add(key)
                            flow_edges.append({
                                "source": f"flow::{f['path']}",
                                "target": f"flow::{tgt}",
                                "label": "imports",
                            })
                        break

        # Mermaid spec (optional; useful for export)
        mermaid = self._to_mermaid(flow_nodes, flow_edges)

        # LLM narrative
        narrative = await self._narrate(graph_data, flow_nodes, flow_edges, entry_files)

        return {
            "nodes": flow_nodes,
            "edges": flow_edges,
            "lanes": LANE_ORDER,
            "entries": sorted(entry_files),
            "mermaid": mermaid,
            "narrative": narrative,
        }

    # ---------- call-edge extraction ----------

    def _extract_call_edges(self, files, symbol_to_file):
        edges = []
        for f in files:
            if f["language"] != "python":
                continue
            try:
                with open(f["abs_path"], "r", encoding="utf-8", errors="ignore") as fh:
                    tree = ast.parse(fh.read())
            except Exception:
                continue
            seen = set()
            for node in ast.walk(tree):
                if isinstance(node, ast.Call):
                    name = None
                    if isinstance(node.func, ast.Name):
                        name = node.func.id
                    elif isinstance(node.func, ast.Attribute):
                        name = node.func.attr
                    if name and name in symbol_to_file and symbol_to_file[name] != f["path"]:
                        key = (f["path"], symbol_to_file[name], name)
                        if key in seen:
                            continue
                        seen.add(key)
                        edges.append({
                            "source_file": f["path"],
                            "target_file": symbol_to_file[name],
                            "symbol": name,
                        })
        return edges

    def _to_mermaid(self, nodes, edges):
        # Returns a Mermaid flowchart string, useful for export / copy-paste
        id_map = {}
        lines = ["flowchart LR"]
        for i, n in enumerate(nodes):
            short = f"n{i}"
            id_map[n["id"]] = short
            shape_open, shape_close = ("[", "]")
            if n["is_entry"]:
                shape_open, shape_close = ("([", "])")
            lines.append(f'    {short}{shape_open}"{n["label"]}<br/>{n["lane"]}"{shape_close}')
        for e in edges:
            s = id_map.get(e["source"])
            t = id_map.get(e["target"])
            if s and t:
                lines.append(f'    {s} -->|{e["label"]}| {t}')
        return "\n".join(lines)

    # ---------- narrative ----------

    async def _narrate(self, graph_data, flow_nodes, flow_edges, entry_files):
        stats = graph_data.get("stats", {})
        summary = [
            f"Files: {stats.get('n_files', 0)}",
            f"Classes: {stats.get('n_classes', 0)}, Functions: {stats.get('n_functions', 0)}",
            f"External deps: {stats.get('n_deps', 0)}",
            f"Entry points: {', '.join(sorted(entry_files)) or '(none)'}",
            "",
            "Files in flow (grouped by layer):",
        ]
        by_lane = {}
        for n in flow_nodes:
            by_lane.setdefault(n["lane"], []).append(n["path"])
        for lane in LANE_ORDER:
            if lane in by_lane:
                summary.append(f"  {lane}: {', '.join(by_lane[lane][:8])}")
        summary.append("")
        summary.append("Connections:")
        for e in flow_edges[:25]:
            s = e["source"].replace("flow::", "")
            t = e["target"].replace("flow::", "")
            summary.append(f"  {s}  --{e['label']}-->  {t}")

        prompt = (
            "You are explaining how a codebase works to a developer who just opened it.\n"
            "Write 4-6 sentences describing the project's flow: where execution starts, "
            "how data moves through layers (entry → api → business → data), and how the "
            "main pieces fit together. Reference actual file names. No preamble, no headings.\n\n"
            "===== STRUCTURAL SUMMARY =====\n" + "\n".join(summary)
        )
        if len(prompt) > 6000:
            prompt = prompt[:6000] + "\n[truncated]"

        try:
            async with httpx.AsyncClient(timeout=180.0) as client:
                r = await client.post(
                    f"{OLLAMA_URL}/api/generate",
                    json={"model": MODEL, "prompt": prompt, "stream": False,
                          "options": {"temperature": 0.3, "num_predict": 400, "num_ctx": 8192}},
                )
                r.raise_for_status()
                return r.json().get("response", "").strip()
        except Exception as e:
            return f"(narrative generation failed: {e})"
