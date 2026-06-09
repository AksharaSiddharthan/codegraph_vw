# CodeGraph — Multi-Agent Codebase Analyzer

A local-first tool that turns any GitHub repo (or local codebase) into an
interactive **knowledge graph**, a **flowchart**, and a **guided AI tour** —
all powered by **Qwen2.5-Coder:7b** running locally on Ollama.

Inspired by Understand-Anything's approach: graphs that *teach* the codebase,
not just impress with complexity.

## Features

- **Interactive Knowledge Graph** — every file, class, function, and external
  dependency rendered as a clickable node. Color-coded by architectural
  layer (entry / api / business / data / ui / util / config / test).
- **Flowchart view** — horizontal swimlane layout showing how data flows
  through architectural layers, with entry points highlighted.
- **Guided Tour** — auto-generated walkthrough that visits ~8 key files in
  dependency order. Each stop has an LLM-narrated explanation. Tour controls
  highlight the current node on the graph as you advance.
- **Click any node → AI explanation** — Qwen2.5-Coder generates a plain-English
  summary, on-demand and cached.

## Architecture

Seven agents run in sequence:

```
1. Ingestion Agent       git clone (or load local path)
2. Parser Agent          Python AST + JS/TS regex extraction
3. Dependency Agent      builds nodes + edges (contains/imports/inherits/depends-on)
4. Layer Agent           classifies each file into an architectural layer
5. Documentation Agent   Qwen2.5-Coder writes per-node summaries
6. Flowchart Agent       horizontal process flow + Mermaid spec + narrative
7. Tour Agent            picks itinerary, writes intro/per-step/outro narration
```

```
┌─────────────────────────────────────────────────────────────────┐
│                      Frontend (React)                           │
│   ┌──────────────┐  ┌─────────────┐  ┌──────────────────┐       │
│   │ Knowledge    │  │ Flowchart   │  │ Tour / Detail    │       │
│   │ Graph        │  │             │  │ Panel            │       │
│   └──────────────┘  └─────────────┘  └──────────────────┘       │
└──────────────────────────────┬──────────────────────────────────┘
                               │ HTTP
┌──────────────────────────────┴──────────────────────────────────┐
│                    Backend (FastAPI)                            │
│         Pipeline orchestrator (7 agents in sequence)            │
└──────────────────────────────┬──────────────────────────────────┘
                               │ HTTP
                     ┌─────────┴──────────┐
                     │  Ollama            │
                     │  qwen2.5-coder:7b  │
                     └────────────────────┘
```

## Prerequisites

- Python 3.10+
- Node.js 18+
- Git 
- [Ollama](https://ollama.com/) running locally

## Setup

### 1. Pull the model

```bash
ollama pull qwen2.5-coder:7b
ollama serve   # if not already running as a service
```

Verify:
```bash
curl http://localhost:11434/api/tags
```

### 2. Backend

```bash
cd backend
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python main.py
```

Sanity check:
```bash
curl http://localhost:8000/health
```

You want: `{"ollama_reachable": true, "qwen_available": true, ...}`

### 3. Frontend

In a separate terminal:

```bash
cd frontend
npm install
npm run dev
```

Open **http://localhost:5173**.

## Usage

1. Pick GitHub URL or Local path
2. Paste source, click **Analyze**
3. Watch the seven-stage progress bar
4. When done, the **Knowledge Graph** appears
5. Click any node → AI explanation in the right panel
6. Switch to **Flowchart** for the layered process view + flow narrative
7. Click **▶ Start Guided Tour** for the auto-narrated walkthrough

## Quick launch

- Linux/Mac: `./run.sh`
- Windows: double-click `run.bat`

## Layer colour mapping

| Layer       | Colour |
| ----------- | ------ |
| entry       | 🔴 red |
| api         | 🔵 blue |
| business    | 🟢 green |
| data        | 🟡 amber |
| ui          | 🩷 pink |
| util        | 🟣 purple |
| config / test | ⚪ slate |
| external dep | 🟪 violet |

The same palette is used in both the Knowledge Graph and the Flowchart so you can mentally map between them.

## Project structure

```
codegraph/
├── backend/
│   ├── main.py
│   ├── requirements.txt
│   ├── test_pipeline.py           smoke test (mocked Ollama)
│   └── agents/
│       ├── ingestion_agent.py
│       ├── parser_agent.py
│       ├── dependency_agent.py
│       ├── layer_agent.py
│       ├── documentation_agent.py
│       ├── flowchart_agent.py
│       └── tour_agent.py
├── frontend/
│   ├── package.json
│   ├── vite.config.js
│   ├── index.html
│   └── src/
│       ├── main.jsx
│       ├── App.jsx
│       ├── styles.css
│       └── components/
│           ├── InputBar.jsx
│           ├── StatusPanel.jsx
│           ├── KnowledgeGraph.jsx
│           ├── FlowchartGraph.jsx
│           ├── TourPanel.jsx
│           └── NodeDetail.jsx
├── README.md
├── run.sh
└── run.bat
```

## Configuration

Backend env vars:

| Variable        | Default                    | Purpose         |
| --------------- | -------------------------- | --------------- |
| `OLLAMA_URL`    | `http://localhost:11434`   | Ollama base     |
| `OLLAMA_MODEL`  | `qwen2.5-coder:7b`         | Model tag       |

Tunable constants:

- `MAX_FILE_SIZE` (parser_agent.py)
- `IGNORE_DIRS` (parser_agent.py)
- `MAX_PREFETCH` (documentation_agent.py)
- `MAX_TOUR_STEPS` (tour_agent.py) — default 8

## Languages supported

- **Python** — full AST analysis (classes, methods, functions, imports, inheritance, top-level calls)
- **JavaScript / TypeScript / JSX / TSX** — regex extraction (classes, functions, arrow funcs, imports, requires)

Other languages are skipped silently. Extending is a matter of adding a parser branch in `parser_agent.py`.

## Troubleshooting

| Symptom | Fix |
| --- | --- |
| `qwen_available: false` | `ollama pull qwen2.5-coder:7b` |
| `git clone failed` | check the URL or use Local path mode |
| 500 errors from Ollama | already handled with auto-retry + prompt halving; if persistent, check Ollama logs for OOM and try `qwen2.5-coder:3b` |
| Pipeline failed | error and full traceback show in the status panel |
| Empty graph | repo has no Python/JS/TS files, or they're all > MAX_FILE_SIZE |
| Slow LLM | 7B on CPU is ~10–30s per call. Lower `MAX_PREFETCH` and `MAX_TOUR_STEPS` or run Ollama on GPU |

## License

MIT.
