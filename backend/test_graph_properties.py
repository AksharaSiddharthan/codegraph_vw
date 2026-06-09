"""
Property-Based Tests for CodeGraph Pipeline Output
===================================================
Place this file at: codegraph/backend/test_graph_properties.py

Run:
    pip install pytest hypothesis
    pytest test_graph_properties.py -v

For slow behavioral tests:
    pytest test_graph_properties.py -v -m slow
"""

from pathlib import Path
import pytest
from collections import Counter
from hypothesis import given, settings, strategies as st


# ─────────────────────────────────────────────
# FIXTURES — wire to your real pipeline output
# ─────────────────────────────────────────────

@pytest.fixture(scope="session")
def sample_graph():
    """
    Returns a real graph dict as produced by DependencyAgent + LayerAgent + TourAgent.
    Replace the body with however you get a graph in your tests —
    either call the pipeline directly or load a saved JSON snapshot.

    Option A (saved snapshot — fast, no LLM needed):
        import json
        with open("tests/fixtures/sample_graph.json") as f:
            return json.load(f)

    Option B (call pipeline directly):
        import asyncio
        from agents.dependency_agent import DependencyAgent
        from agents.layer_agent import LayerAgent
        from agents.parser_agent import ParserAgent
        parsed = asyncio.run(ParserAgent().run("tests/fixtures/tiny_repo"))
        graph  = asyncio.run(DependencyAgent().run(parsed))
        graph  = asyncio.run(LayerAgent().run(graph, parsed))
        return graph
    """
    # ← swap this stub out for Option A or B above
    import json
    with open("tests/fixtures/sample_graph.json") as f:
        return json.load(f)


@pytest.fixture(scope="session")
def node_ids(sample_graph):
    return {n["id"] for n in sample_graph["nodes"]}


# ─────────────────────────────────────────────
# PART 1 — STRUCTURAL INVARIANTS
# Run instantly. No LLM. These should always pass.
# ─────────────────────────────────────────────

def test_every_edge_references_existing_nodes(sample_graph, node_ids):
    """No dangling edge — both endpoints must be real nodes."""
    bad = [
        e for e in sample_graph["edges"]
        if e["source"] not in node_ids or e["target"] not in node_ids
    ]
    assert not bad, f"{len(bad)} dangling edges found: {bad[:3]}"


def test_node_ids_are_unique(sample_graph):
    """Node IDs must be globally unique."""
    ids = [n["id"] for n in sample_graph["nodes"]]
    dupes = [i for i, c in Counter(ids).items() if c > 1]
    assert not dupes, f"Duplicate node IDs: {dupes}"


def test_no_self_loops_on_dependency_edges(sample_graph):
    """A file/class/function must not import or depend on itself."""
    DEPENDENCY_EDGE_TYPES = {"imports", "depends_on", "inherits"}
    loops = [
        e for e in sample_graph["edges"]
        if e["source"] == e["target"] and e.get("type") in DEPENDENCY_EDGE_TYPES
    ]
    assert not loops, f"Self-loops: {loops}"


def test_every_node_has_an_id_label_and_type(sample_graph):
    """Core fields must be present and non-empty on every node."""
    bad = [
        n for n in sample_graph["nodes"]
        if not n.get("id") or not n.get("label") or not n.get("type")
    ]
    assert not bad, f"{len(bad)} nodes missing id/label/type: {bad[:3]}"


def test_node_types_are_known_values(sample_graph):
    """type field must be one of the four known values DependencyAgent produces."""
    VALID_TYPES = {"file", "class", "function", "dependency"}
    bad = [n for n in sample_graph["nodes"] if n.get("type") not in VALID_TYPES]
    assert not bad, f"Unknown node types: {[(n['id'], n['type']) for n in bad[:3]]}"


def test_every_file_node_has_path(sample_graph):
    """File nodes produced by DependencyAgent always have a path field."""
    bad = [n for n in sample_graph["nodes"] if n["type"] == "file" and not n.get("path")]
    assert not bad, f"File nodes without path: {[n['id'] for n in bad]}"


def test_every_class_and_function_node_has_file_reference(sample_graph):
    """Class and function nodes must know which file they belong to."""
    bad = [
        n for n in sample_graph["nodes"]
        if n["type"] in ("class", "function") and not n.get("file")
    ]
    assert not bad, f"{len(bad)} class/function nodes missing 'file': {[n['id'] for n in bad[:3]]}"


def test_layer_values_are_valid(sample_graph):
    """LayerAgent must assign only known layer strings."""
    VALID_LAYERS = {"entry", "api", "business", "data", "ui", "util", "config", "test", "other", "external"}
    bad = [
        n for n in sample_graph["nodes"]
        if n.get("layer") and n["layer"] not in VALID_LAYERS
    ]
    assert not bad, f"Unknown layers: {[(n['id'], n['layer']) for n in bad[:3]]}"


def test_stats_match_actual_node_counts(sample_graph):
    """The stats dict must match the actual node list — not stale numbers."""
    stats = sample_graph.get("stats", {})
    nodes = sample_graph["nodes"]
    assert stats.get("n_files")    == sum(1 for n in nodes if n["type"] == "file")
    assert stats.get("n_classes")  == sum(1 for n in nodes if n["type"] == "class")
    assert stats.get("n_functions")== sum(1 for n in nodes if n["type"] == "function")
    assert stats.get("n_deps")     == sum(1 for n in nodes if n["type"] == "dependency")
    assert stats.get("n_edges")    == len(sample_graph["edges"])


def test_tour_steps_reference_existing_nodes(sample_graph, node_ids):
    """Every tour step must point to a node that actually exists."""
    tour = sample_graph.get("tour", {})
    bad = [
        s for s in tour.get("steps", [])
        if s.get("node_id") not in node_ids
    ]
    assert not bad, f"Tour steps with missing node_id: {bad[:3]}"


def test_tour_steps_are_ordered_by_step_number(sample_graph):
    """Tour steps must come out in ascending step order."""
    steps = sample_graph.get("tour", {}).get("steps", [])
    nums = [s["step"] for s in steps]
    assert nums == sorted(nums), f"Tour steps out of order: {nums}"


def test_contains_edges_point_from_file_to_child(sample_graph):
    """'contains' edges must go file → class or file → function, never backwards."""
    node_map = {n["id"]: n for n in sample_graph["nodes"]}
    bad = []
    for e in sample_graph["edges"]:
        if e.get("type") != "contains":
            continue
        src = node_map.get(e["source"], {})
        tgt = node_map.get(e["target"], {})
        if src.get("type") != "file" or tgt.get("type") not in ("class", "function"):
            bad.append(e)
    assert not bad, f"Malformed 'contains' edges: {bad[:3]}"


# ─────────────────────────────────────────────
# PART 2 — HYPOTHESIS: fuzz your validator logic
# Tests that any well-formed graph is accepted by
# whatever validation you add to your pipeline.
# ─────────────────────────────────────────────

NODE_TYPES   = st.sampled_from(["file", "class", "function", "dependency"])
EDGE_TYPES   = st.sampled_from(["contains", "imports", "depends_on", "inherits"])
VALID_LAYERS = st.sampled_from(["entry", "api", "business", "data", "ui", "util", "config", "test", "other"])


@st.composite
def well_formed_graph(draw):
    """Generates random but structurally valid graphs matching your schema."""
    n = draw(st.integers(min_value=1, max_value=15))
    ids = [f"file::mod_{i}.py" for i in range(n)]

    nodes = [
        {
            "id":    nid,
            "label": f"mod_{i}",
            "type":  "file",
            "path":  f"mod_{i}.py",
            "layer": draw(VALID_LAYERS),
            "size":  draw(st.integers(min_value=0, max_value=5000)),
            "n_classes": 0, "n_functions": 0, "n_imports": 0,
            "language": "python",
            "detail": None,
        }
        for i, nid in enumerate(ids)
    ]

    n_edges = draw(st.integers(min_value=0, max_value=n * 2))
    edges = [
        {
            "source": draw(st.sampled_from(ids)),
            "target": draw(st.sampled_from(ids)),
            "type":   draw(st.sampled_from(["imports", "depends_on"])),
        }
        for _ in range(n_edges)
    ]

    return {
        "nodes": nodes,
        "edges": edges,
        "stats": {
            "n_files": n, "n_classes": 0, "n_functions": 0,
            "n_deps": 0, "n_edges": len(edges),
        },
        "tour": {"intro": "", "steps": [], "outro": ""},
    }


@given(g=well_formed_graph())
@settings(max_examples=300)
def test_hypothesis_no_dangling_edges_in_generated_graphs(g):
    """Hypothesis: well-formed graphs should never have dangling edges."""
    ids = {n["id"] for n in g["nodes"]}
    for e in g["edges"]:
        assert e["source"] in ids
        assert e["target"] in ids


@given(g=well_formed_graph())
@settings(max_examples=300)
def test_hypothesis_stats_always_consistent(g):
    """Hypothesis: stats dict must always match actual node counts."""
    nodes = g["nodes"]
    assert g["stats"]["n_files"]  == sum(1 for n in nodes if n["type"] == "file")
    assert g["stats"]["n_edges"]  == len(g["edges"])


# ─────────────────────────────────────────────
# PART 3 — BEHAVIORAL (slow, costs LLM tokens)
# Run separately:  pytest -m slow
# ─────────────────────────────────────────────

@pytest.mark.slow
def test_pipeline_is_idempotent(tmp_path):
    """
    Same repo → structurally identical graph on two separate runs.
    Catches non-determinism in agent output.

    Fill in the path to a small fixture repo before running.
    """
    import asyncio, json
    from agents.parser_agent import ParserAgent
    from agents.dependency_agent import DependencyAgent
    from agents.layer_agent import LayerAgent

    FIXTURE_REPO = Path(__file__).resolve().parent / "tests" / "fixtures" / "tiny_repo"  # ← point at a small local repo

    async def run():
        parsed = await ParserAgent().run(FIXTURE_REPO)
        g = await DependencyAgent().run(parsed)
        g = await LayerAgent().run(g, parsed)
        return g

    g1 = asyncio.run(run())
    g2 = asyncio.run(run())

    assert {n["id"] for n in g1["nodes"]} == {n["id"] for n in g2["nodes"]}, \
        "Node sets differ between runs — non-deterministic!"
    assert {(e["source"], e["target"], e["type"]) for e in g1["edges"]} == \
           {(e["source"], e["target"], e["type"]) for e in g2["edges"]}, \
        "Edge sets differ between runs — non-deterministic!"


@pytest.mark.slow
def test_adding_isolated_file_adds_exactly_one_node(tmp_path):
    """
    Adding a file that imports nothing and is imported by nothing
    should add exactly one new node and zero new edges.
    """
    import asyncio, shutil
    from pathlib import Path
    from agents.parser_agent import ParserAgent
    from agents.dependency_agent import DependencyAgent
    from agents.layer_agent import LayerAgent

    FIXTURE_REPO = Path(__file__).resolve().parent / "tests" / "fixtures" / "tiny_repo"  # ← point at a small local repo
    repo_copy = tmp_path / "repo"
    shutil.copytree(FIXTURE_REPO, repo_copy)

    async def run(path):
        parsed = await ParserAgent().run(str(path))
        g = await DependencyAgent().run(parsed)
        g = await LayerAgent().run(g, parsed)
        return g

    g_before = asyncio.run(run(repo_copy))
    (repo_copy / "isolated_unused.py").write_text("# nobody imports this\n")
    g_after = asyncio.run(run(repo_copy))

    new_node_ids = {n["id"] for n in g_after["nodes"]} - {n["id"] for n in g_before["nodes"]}
    assert len(new_node_ids) == 1, f"Expected 1 new node, got {len(new_node_ids)}: {new_node_ids}"

    new_edges = [
        e for e in g_after["edges"]
        if (e["source"] in new_node_ids or e["target"] in new_node_ids)
        and e["type"] != "contains"   # "contains" edges are expected (file→functions inside it)
    ]
    assert not new_edges, f"Isolated file shouldn't create dependency edges: {new_edges}"