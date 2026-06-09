"""
Documentation Agent — uses Qwen2.5-Coder via Ollama to write per-node
explanations. Top files get pre-summarized; everything else is on-demand
when the user clicks a node.
"""
import httpx
import asyncio
import os

OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://localhost:11434")
MODEL = os.environ.get("OLLAMA_MODEL", "qwen2.5-coder:7b")

SEM = asyncio.Semaphore(3)
MAX_PREFETCH = 15


class DocumentationAgent:
    async def run(self, graph_data: dict):
        files = [n for n in graph_data["nodes"] if n["type"] == "file"]
        files.sort(
            key=lambda n: (n.get("n_classes", 0) + n.get("n_functions", 0), n.get("size", 0)),
            reverse=True,
        )
        targets = files[:MAX_PREFETCH]
        results = await asyncio.gather(
            *[self.explain_node(n, graph_data) for n in targets],
            return_exceptions=True,
        )
        for node, res in zip(targets, results):
            node["detail"] = res if not isinstance(res, Exception) else f"(unavailable: {res})"
        return graph_data

    async def explain_node(self, node: dict, graph_data: dict) -> str:
        async with SEM:
            return await self._call_ollama(self._build_prompt(node, graph_data))

    def _build_prompt(self, node: dict, graph_data: dict) -> str:
        t = node["type"]
        if t == "file":
            return self._file_prompt(node, graph_data)
        if t == "class":
            return self._class_prompt(node)
        if t == "function":
            return self._function_prompt(node)
        if t == "dependency":
            return self._dep_prompt(node)
        return f"Briefly describe this code element: {node.get('label','?')}"

    def _file_prompt(self, node, graph_data):
        path = node["path"]
        contained = [n for n in graph_data["nodes"]
                     if n.get("file") == path and n["type"] in ("class", "function")]
        listing = "\n".join(f"- {c['type']}: {c['label']}" for c in contained[:20])
        layer = node.get("layer", "unknown")
        return (
            f"You are documenting a file in a codebase.\n\n"
            f"File: {path}\n"
            f"Language: {node.get('language', 'unknown')}\n"
            f"Architectural layer: {layer}\n"
            f"Contains:\n{listing}\n\n"
            f"In 2-3 sentences, explain what this file's role is in the project. "
            f"Be concrete and specific. No filler, no preamble."
        )

    def _class_prompt(self, node):
        methods = ", ".join(node.get("methods", [])[:15]) or "(none listed)"
        bases = ", ".join(node.get("bases", [])) or "(none)"
        doc = node.get("docstring") or "(no docstring)"
        return (
            f"You are documenting a class.\n\n"
            f"Class: {node['label']}\n"
            f"File: {node.get('file')}\n"
            f"Inherits from: {bases}\n"
            f"Methods: {methods}\n"
            f"Existing docstring: {doc}\n\n"
            f"In 2-3 sentences, explain what this class does and its main "
            f"responsibility. Be concrete. No preamble."
        )

    def _function_prompt(self, node):
        args = ", ".join(node.get("args", [])) or "(no args)"
        doc = node.get("docstring") or "(no docstring)"
        return (
            f"You are documenting a function.\n\n"
            f"Function: {node['label']}({args})\n"
            f"File: {node.get('file')}\n"
            f"Async: {node.get('is_async', False)}\n"
            f"Existing docstring: {doc}\n\n"
            f"In 1-2 sentences, explain what this function does. "
            f"Be concrete. No preamble."
        )

    def _dep_prompt(self, node):
        return f"In one sentence, what is the '{node['label']}' library/package commonly used for? No preamble."

    async def _call_ollama(self, prompt: str, retries: int = 2) -> str:
        if len(prompt) > 6000:
            prompt = prompt[:6000] + "\n\n[truncated]"
        last_err = None
        for attempt in range(retries + 1):
            try:
                async with httpx.AsyncClient(timeout=120.0) as client:
                    r = await client.post(
                        f"{OLLAMA_URL}/api/generate",
                        json={
                            "model": MODEL, "prompt": prompt, "stream": False,
                            "options": {"temperature": 0.2, "num_predict": 200, "num_ctx": 8192},
                        },
                    )
                    r.raise_for_status()
                    return r.json().get("response", "").strip()
            except httpx.HTTPStatusError as e:
                last_err = e
                if e.response.status_code == 500 and attempt < retries:
                    prompt = prompt[: len(prompt) // 2] + "\n\n[truncated]"
                    await asyncio.sleep(1)
                    continue
                break
            except httpx.HTTPError as e:
                last_err = e
                if attempt < retries:
                    await asyncio.sleep(1)
                    continue
                break
            except Exception as e:
                return f"(error: {e})"
        return f"(LLM call failed: {last_err})"
