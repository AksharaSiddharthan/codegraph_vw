"""Pipeline smoke test with mocked Ollama."""
import asyncio
import sys
import os
from unittest.mock import patch, AsyncMock

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from agents.ingestion_agent import IngestionAgent
from agents.parser_agent import ParserAgent
from agents.dependency_agent import DependencyAgent
from agents.layer_agent import LayerAgent
from agents.documentation_agent import DocumentationAgent
from agents.flowchart_agent import FlowchartAgent
from agents.tour_agent import TourAgent


async def main():
    target = os.path.dirname(os.path.abspath(__file__))
    print("=" * 70)
    print(f"Pipeline test on: {target}")
    print("=" * 70)

    repo_path, meta = await IngestionAgent().run(target, "local")
    print(f"[1/6] Ingestion ✓  ({repo_path})")

    parsed = await ParserAgent().run(repo_path)
    print(f"[2/6] Parser ✓  ({len(parsed['files'])} files)")

    graph = await DependencyAgent().run(parsed)
    print(f"[3/6] Dependency ✓  ({len(graph['nodes'])} nodes, {len(graph['edges'])} edges)")

    graph = await LayerAgent().run(graph, parsed)
    print(f"[4/6] Layer classification ✓  ({graph['stats']['layers']})")

    with patch.object(DocumentationAgent, "_call_ollama",
                      new=AsyncMock(return_value="[mocked] file purpose summary.")):
        graph = await DocumentationAgent().run(graph)
        n_detail = sum(1 for n in graph["nodes"] if n.get("detail"))
        print(f"[5a/6] Documentation ✓  ({n_detail} pre-summarized)")

    with patch.object(FlowchartAgent, "_narrate",
                      new=AsyncMock(return_value="[mocked flowchart narrative]")):
        flow = await FlowchartAgent().run(parsed, graph)
        graph["flowchart"] = flow
        print(f"[5b/6] Flowchart ✓  ({len(flow['nodes'])} nodes, {len(flow['edges'])} edges)")
        print(f"        lanes used: {sorted({n['lane'] for n in flow['nodes']})}")
        print(f"        entries: {flow['entries']}")

    with patch.object(TourAgent, "_ollama_call",
                      new=AsyncMock(return_value="[mocked tour narration]")):
        tour = await TourAgent().run(parsed, graph)
        print(f"[6/6] Tour ✓  ({tour['total_steps']} steps)")
        for s in tour["steps"]:
            print(f"        step {s['step']}: {s['node_label']} ({s['layer']})")

    # Mermaid output sample
    print("\nMERMAID SPEC PREVIEW:")
    print(flow["mermaid"][:400])

    print("\n✅ All agents passed")


if __name__ == "__main__":
    asyncio.run(main())
