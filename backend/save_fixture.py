import asyncio, json
from agents.parser_agent import ParserAgent
from agents.dependency_agent import DependencyAgent
from agents.layer_agent import LayerAgent
import os

async def main():
    # Point this at any small repo on your machine
    repo_path = "."   # ← change this to any folder with Python files
    
    parsed = await ParserAgent().run(repo_path)
    graph  = await DependencyAgent().run(parsed)
    graph  = await LayerAgent().run(graph, parsed)
    
    os.makedirs("tests/fixtures", exist_ok=True)
    with open("tests/fixtures/sample_graph.json", "w") as f:
        json.dump(graph, f, indent=2)
    print("Saved to tests/fixtures/sample_graph.json")

asyncio.run(main())