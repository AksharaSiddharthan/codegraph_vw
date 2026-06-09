"""
Tour Agent — generates a guided walkthrough of the codebase. Picks
important nodes in a sensible order (entry → api → business → data),
then asks the LLM to write a friendly explanation for each step, plus an
intro and a conclusion.
"""
import os
import httpx
import asyncio

OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://localhost:11434")
MODEL = os.environ.get("OLLAMA_MODEL", "qwen2.5-coder:7b")

LAYER_PRIORITY = ["entry", "api", "business", "data", "ui", "util", "config"]

# How many tour steps to generate
MAX_TOUR_STEPS = 8

# Concurrency cap for per-step narration calls
SEM = asyncio.Semaphore(3)


class TourAgent:
    async def run(self, parsed: dict, graph_data: dict):
        # Pick the tour itinerary
        itinerary = self._pick_itinerary(graph_data)
        if not itinerary:
            return {"intro": "(no tour available)", "steps": [], "outro": ""}

        # Generate intro
        intro_task = self._generate_intro(graph_data, itinerary)

        # Generate each step's narration in parallel
        step_tasks = [self._narrate_step(i, node, graph_data, itinerary)
                      for i, node in enumerate(itinerary)]

        # Generate outro
        outro_task = self._generate_outro(graph_data, itinerary)

        results = await asyncio.gather(intro_task, *step_tasks, outro_task,
                                       return_exceptions=True)
        intro = results[0] if not isinstance(results[0], Exception) else "Welcome to the codebase tour."
        steps_text = results[1:-1]
        outro = results[-1] if not isinstance(results[-1], Exception) else "End of tour."

        steps = []
        for i, (node, text) in enumerate(zip(itinerary, steps_text)):
            steps.append({
                "step": i + 1,
                "node_id": node["id"],
                "node_label": node["label"],
                "node_type": node["type"],
                "layer": node.get("layer", "other"),
                "path": node.get("path") or node.get("file"),
                "narration": text if not isinstance(text, Exception) else f"(step narration failed: {text})",
            })

        return {
            "intro": intro,
            "steps": steps,
            "outro": outro,
            "total_steps": len(steps),
        }

    # ---------- itinerary picking ----------

    def _pick_itinerary(self, graph_data: dict):
        files = [n for n in graph_data["nodes"] if n["type"] == "file"]
        # Group by layer
        by_layer = {}
        for n in files:
            by_layer.setdefault(n.get("layer", "other"), []).append(n)
        for layer in by_layer:
            by_layer[layer].sort(
                key=lambda n: (n.get("n_classes", 0) + n.get("n_functions", 0), n.get("size", 0)),
                reverse=True,
            )

        # Visit one or two top files per layer in priority order
        itinerary = []
        for layer in LAYER_PRIORITY:
            picks = by_layer.get(layer, [])[:2]
            itinerary.extend(picks)
            if len(itinerary) >= MAX_TOUR_STEPS:
                break

        # If we still have headroom, fill with biggest "other" files
        if len(itinerary) < MAX_TOUR_STEPS:
            for n in by_layer.get("other", [])[: MAX_TOUR_STEPS - len(itinerary)]:
                itinerary.append(n)

        return itinerary[:MAX_TOUR_STEPS]

    # ---------- narration ----------

    async def _generate_intro(self, graph_data, itinerary):
        async with SEM:
            stats = graph_data.get("stats", {})
            layers_present = sorted({n.get("layer", "other") for n in itinerary})
            prompt = (
                "Write a short 2-3 sentence introduction to a guided tour of a codebase. "
                "Set the scene — what the user is about to see. Be friendly and direct, no preamble.\n\n"
                f"Codebase stats: {stats.get('n_files', 0)} files, "
                f"{stats.get('n_classes', 0)} classes, {stats.get('n_functions', 0)} functions.\n"
                f"Layers we'll visit: {', '.join(layers_present)}.\n"
                f"Tour has {len(itinerary)} stops."
            )
            return await self._ollama_call(prompt, max_tokens=150)

    async def _narrate_step(self, step_idx, node, graph_data, itinerary):
        async with SEM:
            total = len(itinerary)
            prev = itinerary[step_idx - 1] if step_idx > 0 else None
            nxt = itinerary[step_idx + 1] if step_idx + 1 < total else None

            # Contained classes/functions
            contained = [n for n in graph_data["nodes"]
                         if n.get("file") == node["path"] and n["type"] in ("class", "function")]
            contained_list = ", ".join(f"{c['type']} {c['label']}" for c in contained[:8]) or "(none)"

            transition = ""
            if prev:
                transition = f"You just saw {prev['label']} ({prev.get('layer', '?')} layer). "
            transition += f"Now we're at stop {step_idx + 1} of {total}."

            prompt = (
                f"You are giving a friendly guided tour of a codebase. "
                f"Write 3-4 sentences explaining the current stop and why it matters.\n\n"
                f"{transition}\n\n"
                f"Current file: {node['path']}\n"
                f"Layer: {node.get('layer', 'other')}\n"
                f"Contains: {contained_list}\n"
                + (f"Next stop: {nxt['label']} ({nxt.get('layer','?')})\n" if nxt else "This is the final stop.\n")
                + "\nExplain what this file does, how it fits into the bigger picture, and "
                "(if there's a next stop) briefly tease the transition. No headings, no preamble."
            )
            return await self._ollama_call(prompt, max_tokens=300)

    async def _generate_outro(self, graph_data, itinerary):
        async with SEM:
            visited = [n["label"] for n in itinerary]
            prompt = (
                "Write a 2-3 sentence wrap-up for a guided codebase tour. Recap what was "
                "covered and suggest the user click around the graph next. No preamble.\n\n"
                f"Files visited: {', '.join(visited)}"
            )
            return await self._ollama_call(prompt, max_tokens=150)

    async def _ollama_call(self, prompt: str, max_tokens: int = 250) -> str:
        if len(prompt) > 6000:
            prompt = prompt[:6000] + "\n[truncated]"
        for attempt in range(3):
            try:
                async with httpx.AsyncClient(timeout=120.0) as client:
                    r = await client.post(
                        f"{OLLAMA_URL}/api/generate",
                        json={
                            "model": MODEL, "prompt": prompt, "stream": False,
                            "options": {"temperature": 0.4, "num_predict": max_tokens, "num_ctx": 8192},
                        },
                    )
                    r.raise_for_status()
                    return r.json().get("response", "").strip()
            except httpx.HTTPStatusError as e:
                if e.response.status_code == 500 and attempt < 2:
                    prompt = prompt[: len(prompt) // 2] + "\n[truncated]"
                    await asyncio.sleep(1)
                    continue
                return f"(LLM error: {e})"
            except Exception as e:
                if attempt < 2:
                    await asyncio.sleep(1)
                    continue
                return f"(error: {e})"
        return "(tour step unavailable)"
