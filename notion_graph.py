#!/usr/bin/env python3
"""
Paper RAG Knowledge Graph Visualizer
Notion DB에서 Papers, Chunks, Concepts, Research Ideas를 읽어
인터랙티브 네트워크 그래프(HTML)를 생성합니다.

Usage:
  # Notion API 연동 (재사용)
  export NOTION_API_KEY="your-integration-token"
  python notion_graph.py

  # 또는 현재 데이터로 즉시 실행
  python notion_graph.py --demo
"""

import argparse
import json
import os
import sys
from dataclasses import dataclass, field
from pyvis.network import Network


# ─── Data Source IDs (Paper RAG Dashboard 아래 DB들) ───
PAPERS_DS = "740a5a39-56c2-456f-a809-f3cfacf47813"
CHUNKS_DS = "5bead46f-80ef-4cd0-b795-1e34d26363cd"
CONCEPTS_DS = "fda94a20-4188-4005-b75e-043c49dbfd65"
IDEAS_DS = "ad639987-3412-4830-bda1-d58f9c1ee472"


# ─── Style Config ───
STYLE = {
    "paper":   {"color": "#4A90D9", "shape": "dot",     "size": 35, "font_size": 16},
    "chunk":   {"color": "#F5A623", "shape": "dot",     "size": 18, "font_size": 11},
    "concept": {"color": "#7ED321", "shape": "diamond", "size": 28, "font_size": 14},
    "idea":    {"color": "#D0021B", "shape": "triangle","size": 22, "font_size": 12},
}

EDGE_STYLE = {
    "paper-chunk":   {"color": "#4A90D9", "width": 1.5},
    "chunk-concept": {"color": "#7ED321", "width": 1.2},
    "paper-idea":    {"color": "#D0021B", "width": 1.2, "dashes": True},
}


@dataclass
class Node:
    id: str
    label: str
    node_type: str  # paper, chunk, concept, idea
    title: str = ""  # hover tooltip
    group: str = ""


@dataclass
class Edge:
    source: str
    target: str
    edge_type: str
    label: str = ""


@dataclass
class GraphData:
    nodes: list = field(default_factory=list)
    edges: list = field(default_factory=list)


def fetch_from_notion() -> GraphData:
    """Notion API에서 4개 DB를 읽어 GraphData를 구성합니다."""
    from notion_client import Client

    token = os.environ.get("NOTION_API_KEY")
    if not token:
        print("Error: NOTION_API_KEY 환경변수를 설정하세요.")
        print("  export NOTION_API_KEY='ntn_...'")
        sys.exit(1)

    notion = Client(auth=token)
    graph = GraphData()

    def query_all(data_source_id):
        """Notion data source의 모든 페이지를 가져옵니다 (v3 API)."""
        pages = []
        cursor = None
        while True:
            kwargs = {"data_source_id": data_source_id, "page_size": 100}
            if cursor:
                kwargs["start_cursor"] = cursor
            resp = notion.data_sources.query(**kwargs)
            pages.extend(resp["results"])
            if not resp["has_more"]:
                break
            cursor = resp["next_cursor"]
        return pages

    def get_title(props):
        for v in props.values():
            if v["type"] == "title" and v["title"]:
                return "".join(t["plain_text"] for t in v["title"])
        return "Untitled"

    def get_text(props, key):
        p = props.get(key)
        if p and p["type"] == "rich_text" and p["rich_text"]:
            return "".join(t["plain_text"] for t in p["rich_text"])
        return ""

    def get_select(props, key):
        p = props.get(key)
        if p and p["type"] == "select" and p["select"]:
            return p["select"]["name"]
        return ""

    def get_multi_select(props, key):
        p = props.get(key)
        if p and p["type"] == "multi_select":
            return [o["name"] for o in p["multi_select"]]
        return []

    def get_relations(props, key):
        p = props.get(key)
        if p and p["type"] == "relation":
            return [r["id"] for r in p["relation"]]
        return []

    # 1. Papers
    print("  Fetching Papers...")
    for page in query_all(PAPERS_DS):
        pid = page["id"]
        props = page["properties"]
        title = get_title(props)
        status = get_select(props, "Status")
        relevance = get_select(props, "Relevance")
        domains = get_multi_select(props, "Domain")
        summary = get_text(props, "One-line Summary")

        tooltip = f"<b>{title}</b><br>"
        tooltip += f"Status: {status} | Relevance: {relevance}<br>"
        tooltip += f"Domain: {', '.join(domains)}<br>"
        if summary:
            tooltip += f"<br>{summary}"

        graph.nodes.append(Node(
            id=pid, label=title[:40], node_type="paper",
            title=tooltip, group="paper"
        ))

    # 2. Concepts
    print("  Fetching Concepts...")
    for page in query_all(CONCEPTS_DS):
        pid = page["id"]
        props = page["properties"]
        name = get_title(props)
        desc = get_text(props, "Description")
        cats = get_multi_select(props, "Category")

        tooltip = f"<b>💡 {name}</b><br>"
        tooltip += f"Category: {', '.join(cats)}<br>"
        if desc:
            tooltip += f"<br>{desc[:200]}"

        graph.nodes.append(Node(
            id=pid, label=name, node_type="concept",
            title=tooltip, group="concept"
        ))

    # 3. Chunks
    print("  Fetching Chunks...")
    for page in query_all(CHUNKS_DS):
        pid = page["id"]
        props = page["properties"]
        title = get_title(props)
        content = get_text(props, "Content")
        section = get_select(props, "Section")
        ctype = get_select(props, "Type")
        importance = get_select(props, "Importance")

        tooltip = f"<b>🧩 {title}</b><br>"
        tooltip += f"Section: {section} | Type: {ctype} | Importance: {importance}<br>"
        if content:
            tooltip += f"<br>{content[:300]}"

        graph.nodes.append(Node(
            id=pid, label=title[:30], node_type="chunk",
            title=tooltip, group="chunk"
        ))

        # Edges: Chunk → Paper
        for paper_id in get_relations(props, "Source Paper"):
            graph.edges.append(Edge(
                source=paper_id, target=pid, edge_type="paper-chunk"
            ))

        # Edges: Chunk → Concept
        for concept_id in get_relations(props, "Concepts"):
            graph.edges.append(Edge(
                source=pid, target=concept_id, edge_type="chunk-concept"
            ))

    # 4. Research Ideas
    print("  Fetching Research Ideas...")
    for page in query_all(IDEAS_DS):
        pid = page["id"]
        props = page["properties"]
        title = get_title(props)
        desc = get_text(props, "Description")
        priority = get_select(props, "Priority")
        status = get_select(props, "Status")

        tooltip = f"<b>🔬 {title}</b><br>"
        tooltip += f"Priority: {priority} | Status: {status}<br>"
        if desc:
            tooltip += f"<br>{desc[:200]}"

        graph.nodes.append(Node(
            id=pid, label=title[:30], node_type="idea",
            title=tooltip, group="idea"
        ))

        # Edges: Idea → Paper
        for paper_id in get_relations(props, "Source Paper"):
            graph.edges.append(Edge(
                source=paper_id, target=pid, edge_type="paper-idea"
            ))

    return graph


def build_demo_data() -> GraphData:
    """현재 마이그레이션된 데이터로 데모 그래프를 생성합니다."""
    graph = GraphData()

    # Papers
    papers = [
        ("p1", "VLA-as-a-Module", "Draft | Relevance: High\nDomain: VLA, RL, Robot\n\nFrozen VLA 내부 다중 신호를 compact embedding으로\n결합하여 사람 개입 없는 자율 online RL 파이프라인 구축"),
        ("p2", "π0", "Physical Intelligence | Relevance: High\nDomain: VLA, Robot, Diffusion\n\nFlow matching 기반 VLA로 다양한 로봇 조작 능력을\n대규모 데이터에서 학습하는 범용 로봇 제어 모델"),
        ("p3", "π0.5", "Physical Intelligence | Relevance: High\nDomain: VLA, Robot\n\nPaliGemma VLM backbone + flow matching action expert로\nopen-world 일반화를 달성한 VLA 모델"),
    ]
    for pid, label, tooltip in papers:
        graph.nodes.append(Node(id=pid, label=label, node_type="paper", title=tooltip))

    # Concepts
    concepts = [
        ("c1", "Flow Matching", "Architecture, Training"),
        ("c2", "Frozen VLA\n+ Lightweight RL", "Architecture, Training"),
        ("c3", "Cross-Modal\nAlignment (z_align)", "Architecture, Evaluation"),
        ("c4", "VLM-as-a-Judge", "Evaluation, Loss/Reward"),
        ("c5", "Graceful\nDegradation", "Architecture, Theory"),
        ("c6", "Residual RL", "Training"),
    ]
    for cid, label, cats in concepts:
        graph.nodes.append(Node(id=cid, label=label, node_type="concept", title=f"Category: {cats}"))

    # Chunks from VLA-as-a-Module
    vla_chunks = [
        ("ch1",  "RLT 3가지\n사람 개입 한계",     "Problem|Fact|High",     ["c2"]),
        ("ch2",  "Multi-Signal\nCompact Embedding", "Method|Fact|High",      ["c2", "c1"]),
        ("ch3",  "z_align → task\nprogress proxy",  "Method|Claim|High",     ["c3", "c4"]),
        ("ch4",  "Continuous\nBlending Gating",     "Method|Fact|High",      ["c6"]),
        ("ch5",  "Graceful\nDegradation 원리",      "Method|Claim|High",     ["c5"]),
        ("ch6",  "VLM-as-a-Judge\n+ z_align reward","Method|Fact|High",      ["c4", "c3"]),
        ("ch7",  "Unseen Task\nLevel 2-3 한정",     "Limitation|Fact|Mid",   []),
        ("ch8",  "z_unc\ncomputational cost",       "Limitation|Fact|Mid",   []),
    ]
    for chid, label, meta, concept_ids in vla_chunks:
        section, ctype, imp = meta.split("|")
        tooltip = f"Section: {section} | Type: {ctype} | Importance: {imp}"
        graph.nodes.append(Node(id=chid, label=label, node_type="chunk", title=tooltip))
        graph.edges.append(Edge(source="p1", target=chid, edge_type="paper-chunk"))
        for cid in concept_ids:
            graph.edges.append(Edge(source=chid, target=cid, edge_type="chunk-concept"))

    # Chunks from π0
    pi0_chunks = [
        ("ch9",  "VLM + Flow\nMatching Arch",       "Method|Fact|High",     ["c1"]),
        ("ch10", "Action Expert\n설계",              "Method|Fact|High",     ["c1"]),
        ("ch11", "Cross-Embodiment\n사전학습",       "Method|Fact|High",     []),
        ("ch12", "Blockwise Causal\nAttention Mask", "Method|Fact|Mid",      []),
        ("ch13", "추론 속도\n73ms 달성",             "Result|Fact|Mid",      ["c1"]),
        ("ch14", "다단계 정교\n조작 성공",           "Result|Fact|High",     []),
    ]
    for chid, label, meta, concept_ids in pi0_chunks:
        section, ctype, imp = meta.split("|")
        tooltip = f"Section: {section} | Type: {ctype} | Importance: {imp}"
        graph.nodes.append(Node(id=chid, label=label, node_type="chunk", title=tooltip))
        graph.edges.append(Edge(source="p2", target=chid, edge_type="paper-chunk"))
        for cid in concept_ids:
            graph.edges.append(Edge(source=chid, target=cid, edge_type="chunk-concept"))

    # Research Ideas
    ideas = [
        ("i1", "Level 4\nunseen task 적응",       "p1", "Mid|Open"),
        ("i2", "z_unc 1-pass\n근사 방법",          "p1", "High|Open"),
        ("i3", "실제 로봇\nauto-reset 없는 RL",    "p1", "Mid|Open"),
        ("i4", "Action expert\nscaling law",       "p2", "Mid|Open"),
        ("i5", "Flow matching →\nconsistency model","p2", "High|Open"),
    ]
    for iid, label, paper_id, meta in ideas:
        priority, status = meta.split("|")
        tooltip = f"Priority: {priority} | Status: {status}"
        graph.nodes.append(Node(id=iid, label=label, node_type="idea", title=tooltip))
        graph.edges.append(Edge(source=paper_id, target=iid, edge_type="paper-idea"))

    return graph


def build_network(graph: GraphData, output_path: str = "paper_rag_graph.html"):
    """GraphData로부터 Pyvis 네트워크 그래프를 생성합니다."""
    net = Network(
        height="900px",
        width="100%",
        bgcolor="#1a1a2e",
        font_color="#e0e0e0",
        directed=False,
        select_menu=False,
        filter_menu=True,
        cdn_resources="remote",
    )

    # Physics options for nice layout
    net.set_options(json.dumps({
        "physics": {
            "forceAtlas2Based": {
                "gravitationalConstant": -80,
                "centralGravity": 0.008,
                "springLength": 180,
                "springConstant": 0.04,
                "damping": 0.5,
                "avoidOverlap": 0.6
            },
            "solver": "forceAtlas2Based",
            "stabilization": {"iterations": 200}
        },
        "interaction": {
            "hover": True,
            "tooltipDelay": 100,
            "navigationButtons": True,
            "keyboard": {"enabled": True}
        },
        "nodes": {
            "borderWidth": 2,
            "borderWidthSelected": 4,
            "font": {"face": "Pretendard, -apple-system, sans-serif"}
        },
        "edges": {
            "smooth": {"type": "continuous"},
            "selectionWidth": 2
        }
    }))

    # Add nodes
    for node in graph.nodes:
        style = STYLE[node.node_type]
        net.add_node(
            node.id,
            label=node.label,
            title=node.title,
            color=style["color"],
            shape=style["shape"],
            size=style["size"],
            font={"size": style["font_size"], "color": "#e0e0e0"},
            group=node.node_type,
            borderWidth=2,
            shadow=True,
        )

    # Add edges
    for edge in graph.edges:
        style = EDGE_STYLE.get(edge.edge_type, {"color": "#666", "width": 1})
        net.add_edge(
            edge.source,
            edge.target,
            color=style["color"],
            width=style["width"],
            dashes=style.get("dashes", False),
            smooth=True,
        )

    # Custom HTML with legend
    html_content = net.generate_html()

    # Inject legend and title
    legend_html = """
    <div style="position:fixed; top:15px; left:15px; background:rgba(26,26,46,0.95);
                padding:20px; border-radius:12px; z-index:1000; border:1px solid #333;
                font-family: Pretendard, -apple-system, sans-serif; color:#e0e0e0;
                box-shadow: 0 4px 20px rgba(0,0,0,0.4);">
        <div style="font-size:18px; font-weight:700; margin-bottom:12px; color:#fff;">
            📊 Paper RAG Knowledge Graph
        </div>
        <div style="display:grid; grid-template-columns:auto 1fr; gap:6px 12px; font-size:13px;">
            <span style="color:#4A90D9; font-size:16px;">●</span>
            <span>Paper <span style="color:#888;">(논문)</span></span>
            <span style="color:#F5A623; font-size:16px;">●</span>
            <span>Chunk <span style="color:#888;">(지식 조각)</span></span>
            <span style="color:#7ED321; font-size:16px;">◆</span>
            <span>Concept <span style="color:#888;">(핵심 개념)</span></span>
            <span style="color:#D0021B; font-size:16px;">▲</span>
            <span>Research Idea <span style="color:#888;">(연구 아이디어)</span></span>
        </div>
        <div style="margin-top:10px; padding-top:10px; border-top:1px solid #444; font-size:11px; color:#888;">
            마우스 올리면 상세 정보 · 드래그로 이동 · 스크롤로 줌
        </div>
    </div>
    """

    stats_html = f"""
    <div style="position:fixed; bottom:15px; right:15px; background:rgba(26,26,46,0.95);
                padding:12px 18px; border-radius:10px; z-index:1000; border:1px solid #333;
                font-family: Pretendard, -apple-system, sans-serif; color:#888; font-size:12px;
                box-shadow: 0 4px 20px rgba(0,0,0,0.4);">
        Nodes: {len(graph.nodes)} · Edges: {len(graph.edges)} · Generated by Paper RAG System
    </div>
    """

    html_content = html_content.replace("</body>", f"{legend_html}{stats_html}</body>")

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html_content)

    print(f"\n✅ Graph saved to: {output_path}")
    print(f"   Nodes: {len(graph.nodes)}, Edges: {len(graph.edges)}")


def main():
    parser = argparse.ArgumentParser(description="Paper RAG Knowledge Graph Visualizer")
    parser.add_argument("--demo", action="store_true", help="현재 마이그레이션 데이터로 데모 실행")
    parser.add_argument("--output", "-o", default="paper_rag_graph.html", help="출력 HTML 파일 경로")
    args = parser.parse_args()

    print("🔍 Paper RAG Knowledge Graph Builder\n")

    if args.demo:
        print("📦 Demo mode: 현재 마이그레이션된 데이터 사용")
        graph = build_demo_data()
    else:
        print("🌐 Notion API에서 데이터 가져오는 중...")
        graph = fetch_from_notion()

    output_dir = os.path.dirname(args.output)
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)
    build_network(graph, args.output)
    print(f"\n🌐 브라우저에서 열기: file://{os.path.abspath(args.output)}")


if __name__ == "__main__":
    main()
