"""
CodeGraph — Multi-Agent Codebase Analyzer
Pipeline: ingestion → parse → dependency → layer classify → docs (Qwen) → flowchart → tour
"""
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Dict, Any
import uuid
import asyncio
import traceback
from drive_service import save_graph_to_drive
from agents.ingestion_agent import IngestionAgent
from agents.parser_agent import ParserAgent
from agents.dependency_agent import DependencyAgent
from agents.layer_agent import LayerAgent
from agents.documentation_agent import DocumentationAgent
from agents.flowchart_agent import FlowchartAgent
from agents.tour_agent import TourAgent

app = FastAPI(title="CodeGraph API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

JOBS: Dict[str, Dict[str, Any]] = {}


class AnalyzeRequest(BaseModel):
    source: str
    source_type: str = "github"


class NodeDetailRequest(BaseModel):
    job_id: str
    node_id: str


@app.get("/")
async def root():
    return {"status": "ok", "service": "CodeGraph"}


@app.get("/health")
async def health():
    import httpx
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            r = await client.get("http://localhost:11434/api/tags")
            tags = r.json().get("models", [])
            has_model = any("qwen2.5-coder" in m.get("name", "") for m in tags)
            return {
                "ollama_reachable": True,
                "qwen_available": has_model,
                "models": [m.get("name") for m in tags],
            }
    except Exception as e:
        return {"ollama_reachable": False, "error": str(e)}


@app.post("/analyze")
async def analyze(req: AnalyzeRequest):
    job_id = str(uuid.uuid4())
    JOBS[job_id] = {
        "status": "queued",
        "progress": 0,
        "stage": "queued",
        "result": None,
        "error": None,
    }
    asyncio.create_task(_run_pipeline(job_id, req.source, req.source_type))
    return {"job_id": job_id, "status": "queued"}


@app.get("/status/{job_id}")
async def status(job_id: str):
    if job_id not in JOBS:
        raise HTTPException(404, "job not found")
    j = JOBS[job_id]
    return {"status": j["status"], "progress": j["progress"], "stage": j["stage"], "error": j["error"]}


@app.get("/graph/{job_id}")
async def graph(job_id: str):
    if job_id not in JOBS:
        raise HTTPException(404, "job not found")
    j = JOBS[job_id]
    if j["status"] != "complete":
        raise HTTPException(409, f"job not complete (status: {j['status']})")
    return j["result"]


@app.post("/node_detail")
async def node_detail(req: NodeDetailRequest):
    if req.job_id not in JOBS:
        raise HTTPException(404, "job not found")
    j = JOBS[req.job_id]
    if j["status"] != "complete":
        raise HTTPException(409, "job not complete")
    result = j["result"]
    node = next((n for n in result["nodes"] if n["id"] == req.node_id), None)
    if not node:
        raise HTTPException(404, "node not found")

    if node.get("detail"):
        return {"node_id": req.node_id, "detail": node["detail"]}

    doc_agent = DocumentationAgent()
    detail = await doc_agent.explain_node(node, result)
    node["detail"] = detail
    return {"node_id": req.node_id, "detail": detail}


@app.get("/tour/{job_id}")
async def get_tour(job_id: str):
    """Return the guided tour for a completed job."""
    if job_id not in JOBS:
        raise HTTPException(404, "job not found")
    j = JOBS[job_id]
    if j["status"] != "complete":
        raise HTTPException(409, "job not complete")
    return j["result"].get("tour", {"steps": []})

@app.get("/drive/graphs")
async def list_drive_graphs():
    """List all graphs previously saved to Drive."""
    from drive_service import list_saved_graphs
    try:
        return {"graphs": list_saved_graphs()}
    except Exception as e:
        raise HTTPException(500, str(e))


@app.get("/drive/graphs/{file_id}")
async def load_drive_graph(file_id: str):
    """Load a specific saved graph from Drive."""
    from drive_service import load_graph_from_drive
    try:
        return load_graph_from_drive(file_id)
    except Exception as e:
        raise HTTPException(500, str(e))


async def _run_pipeline(job_id: str, source: str, source_type: str):
    try:
        JOBS[job_id]["status"] = "running"

        JOBS[job_id]["stage"] = "ingesting"
        JOBS[job_id]["progress"] = 5
        repo_path, repo_meta = await IngestionAgent().run(source, source_type)

        JOBS[job_id]["stage"] = "parsing"
        JOBS[job_id]["progress"] = 20
        parsed = await ParserAgent().run(repo_path)

        JOBS[job_id]["stage"] = "mapping_dependencies"
        JOBS[job_id]["progress"] = 35
        graph_data = await DependencyAgent().run(parsed)

        JOBS[job_id]["stage"] = "classifying_layers"
        JOBS[job_id]["progress"] = 45
        graph_data = await LayerAgent().run(graph_data, parsed)

        JOBS[job_id]["stage"] = "generating_docs"
        JOBS[job_id]["progress"] = 60
        graph_data = await DocumentationAgent().run(graph_data)

        JOBS[job_id]["stage"] = "building_flowchart"
        JOBS[job_id]["progress"] = 80
        flowchart = await FlowchartAgent().run(parsed, graph_data)
        graph_data["flowchart"] = flowchart

        JOBS[job_id]["stage"] = "generating_tour"
        JOBS[job_id]["progress"] = 92
        tour = await TourAgent().run(parsed, graph_data)
        graph_data["tour"] = tour

        graph_data["meta"] = repo_meta
        try:
            repo_name = repo_meta.get("name", "unknown_repo")
            save_graph_to_drive(graph_data, repo_name)
        except Exception as e:
            print(f"Drive save failed (non-fatal): {e}")
        

        JOBS[job_id]["progress"] = 100
        JOBS[job_id]["stage"] = "complete"
        JOBS[job_id]["status"] = "complete"
        JOBS[job_id]["result"] = graph_data
    

    except Exception as e:
        JOBS[job_id]["status"] = "failed"
        JOBS[job_id]["error"] = f"{type(e).__name__}: {e}\n{traceback.format_exc()}"


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
