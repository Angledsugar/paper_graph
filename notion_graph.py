#!/usr/bin/env python3
"""
Paper RAG Knowledge Graph Visualizer (D3.js)
Notion DB에서 Papers, Chunks, Concepts, Research Ideas를 읽어
인터랙티브 네트워크 그래프(HTML)를 생성합니다.

Usage:
  export NOTION_API_KEY="your-integration-token"
  python notion_graph.py -o dist/index.html

  python notion_graph.py --demo
"""

import argparse
import json
import os
import sys
import html as html_mod

# ─── Data Source IDs ───
PAPERS_DS = "740a5a39-56c2-456f-a809-f3cfacf47813"
CHUNKS_DS = "5bead46f-80ef-4cd0-b795-1e34d26363cd"
CONCEPTS_DS = "fda94a20-4188-4005-b75e-043c49dbfd65"
IDEAS_DS = "ad639987-3412-4830-bda1-d58f9c1ee472"


def fetch_from_notion():
    from notion_client import Client
    token = os.environ.get("NOTION_API_KEY")
    if not token:
        print("Error: NOTION_API_KEY 환경변수를 설정하세요.")
        sys.exit(1)

    notion = Client(auth=token)
    nodes, edges = [], []

    def query_all(ds_id):
        pages, cursor = [], None
        while True:
            kw = {"data_source_id": ds_id, "page_size": 100}
            if cursor: kw["start_cursor"] = cursor
            resp = notion.data_sources.query(**kw)
            pages.extend(resp["results"])
            if not resp["has_more"]: break
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

    print("  Fetching Papers...")
    for page in query_all(PAPERS_DS):
        pid = page["id"]
        props = page["properties"]
        nodes.append({
            "id": pid, "label": get_title(props), "type": "paper",
            "status": get_select(props, "Status"),
            "relevance": get_select(props, "Relevance"),
            "domain": get_multi_select(props, "Domain"),
            "summary": get_text(props, "One-line Summary"),
        })

    print("  Fetching Concepts...")
    for page in query_all(CONCEPTS_DS):
        pid = page["id"]
        props = page["properties"]
        nodes.append({
            "id": pid, "label": get_title(props), "type": "concept",
            "description": get_text(props, "Description"),
            "category": get_multi_select(props, "Category"),
        })

    print("  Fetching Chunks...")
    for page in query_all(CHUNKS_DS):
        pid = page["id"]
        props = page["properties"]
        nodes.append({
            "id": pid, "label": get_title(props), "type": "chunk",
            "section": get_select(props, "Section"),
            "chunk_type": get_select(props, "Type"),
            "importance": get_select(props, "Importance"),
            "content": get_text(props, "Content")[:200],
        })
        for paper_id in get_relations(props, "Source Paper"):
            edges.append({"source": paper_id, "target": pid, "type": "paper-chunk"})
        for concept_id in get_relations(props, "Concepts"):
            edges.append({"source": pid, "target": concept_id, "type": "chunk-concept"})

    print("  Fetching Research Ideas...")
    for page in query_all(IDEAS_DS):
        pid = page["id"]
        props = page["properties"]
        nodes.append({
            "id": pid, "label": get_title(props), "type": "idea",
            "priority": get_select(props, "Priority"),
            "status": get_select(props, "Status"),
            "description": get_text(props, "Description")[:200],
        })
        for paper_id in get_relations(props, "Source Paper"):
            edges.append({"source": paper_id, "target": pid, "type": "paper-idea"})

    return nodes, edges


def build_demo_data():
    nodes, edges = [], []

    papers = [
        {"id":"p1","label":"VLA-as-a-Module","type":"paper","domain":["VLA","RL","Robot"],"relevance":"High",
         "summary":"Frozen VLA 내부 다중 신호를 compact embedding으로 결합하여 자율 online RL 구축"},
        {"id":"p2","label":"π0","type":"paper","domain":["VLA","Robot","Diffusion"],"relevance":"High",
         "summary":"Flow matching 기반 범용 로봇 제어 VLA 모델"},
        {"id":"p3","label":"π0.5","type":"paper","domain":["VLA","Robot"],"relevance":"High",
         "summary":"PaliGemma + flow matching action expert로 open-world 일반화"},
    ]
    nodes.extend(papers)

    concepts = [
        {"id":"c1","label":"Flow Matching","type":"concept","category":["Architecture","Training"]},
        {"id":"c2","label":"Frozen VLA + RL","type":"concept","category":["Architecture","Training"]},
        {"id":"c3","label":"Cross-Modal Alignment","type":"concept","category":["Architecture"]},
        {"id":"c4","label":"VLM-as-a-Judge","type":"concept","category":["Evaluation","Loss/Reward"]},
        {"id":"c5","label":"Graceful Degradation","type":"concept","category":["Theory"]},
        {"id":"c6","label":"Residual RL","type":"concept","category":["Training"]},
    ]
    nodes.extend(concepts)

    vla_chunks = [
        ("ch1","RLT 3가지 사람 개입 한계","Problem","Fact","High",["c2"]),
        ("ch2","Multi-Signal Compact Embedding","Method","Fact","High",["c2","c1"]),
        ("ch3","z_align → task progress proxy","Method","Claim","High",["c3","c4"]),
        ("ch4","Continuous Blending Gating","Method","Fact","High",["c6"]),
        ("ch5","Graceful Degradation 원리","Method","Claim","High",["c5"]),
        ("ch6","VLM-as-a-Judge + z_align reward","Method","Fact","High",["c4","c3"]),
        ("ch7","Unseen Task Level 2-3 한정","Limitation","Fact","Mid",[]),
        ("ch8","z_unc computational cost","Limitation","Fact","Mid",[]),
    ]
    for cid,label,sec,ct,imp,concept_ids in vla_chunks:
        nodes.append({"id":cid,"label":label,"type":"chunk","section":sec,"chunk_type":ct,"importance":imp})
        edges.append({"source":"p1","target":cid,"type":"paper-chunk"})
        for c in concept_ids:
            edges.append({"source":cid,"target":c,"type":"chunk-concept"})

    pi0_chunks = [
        ("ch9","VLM + Flow Matching Architecture","Method","Fact","High",["c1"]),
        ("ch10","Action Expert 설계","Method","Fact","High",["c1"]),
        ("ch11","Cross-Embodiment 사전학습","Method","Fact","High",[]),
        ("ch12","Blockwise Causal Attention","Method","Fact","Mid",[]),
        ("ch13","추론 속도 73ms","Result","Fact","Mid",["c1"]),
        ("ch14","다단계 정교 조작 성공","Result","Fact","High",[]),
    ]
    for cid,label,sec,ct,imp,concept_ids in pi0_chunks:
        nodes.append({"id":cid,"label":label,"type":"chunk","section":sec,"chunk_type":ct,"importance":imp})
        edges.append({"source":"p2","target":cid,"type":"paper-chunk"})
        for c in concept_ids:
            edges.append({"source":cid,"target":c,"type":"chunk-concept"})

    ideas = [
        ("i1","Level 4 unseen task 적응","p1","Mid"),
        ("i2","z_unc 1-pass 근사","p1","High"),
        ("i3","Auto-reset 없는 RL","p1","Mid"),
        ("i4","Action expert scaling law","p2","Mid"),
        ("i5","Flow → consistency model","p2","High"),
    ]
    for iid,label,pid,pri in ideas:
        nodes.append({"id":iid,"label":label,"type":"idea","priority":pri,"status":"Open"})
        edges.append({"source":pid,"target":iid,"type":"paper-idea"})

    return nodes, edges


HTML_TEMPLATE = r"""<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Paper RAG Knowledge Graph</title>
<style>
  @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');

  * { margin:0; padding:0; box-sizing:border-box; }

  body {
    font-family: 'Inter', -apple-system, sans-serif;
    background: #0a0a14;
    color: #e0e0e0;
    overflow: hidden;
    height: 100vh;
    display: flex;
  }

  /* ─── Sidebar ─── */
  .sidebar {
    width: 280px;
    min-width: 280px;
    height: 100vh;
    background: rgba(14, 14, 26, 0.98);
    border-right: 1px solid rgba(255,255,255,0.06);
    display: flex;
    flex-direction: column;
    z-index: 200;
    overflow: hidden;
  }

  .sidebar-header {
    padding: 24px 20px 16px;
    border-bottom: 1px solid rgba(255,255,255,0.06);
  }
  .sidebar-header h1 {
    font-size: 16px; font-weight: 700;
    background: linear-gradient(135deg, #667eea, #f093fb);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    letter-spacing: -0.3px;
    margin-bottom: 12px;
  }
  .search-box {
    position: relative;
  }
  .search-box input {
    width: 100%;
    background: rgba(255,255,255,0.05);
    border: 1px solid rgba(255,255,255,0.08);
    border-radius: 10px;
    padding: 10px 12px 10px 34px;
    color: #e0e0e0;
    font-size: 12px;
    outline: none;
    font-family: inherit;
    transition: border-color 0.2s;
  }
  .search-box input::placeholder { color: #444; }
  .search-box input:focus { border-color: rgba(102,126,234,0.4); }
  .search-box .search-icon {
    position: absolute; left: 11px; top: 50%; transform: translateY(-50%);
    font-size: 13px; color: #444; pointer-events: none;
  }

  .sidebar-scroll {
    flex: 1;
    overflow-y: auto;
    padding: 0;
  }
  .sidebar-scroll::-webkit-scrollbar { width: 4px; }
  .sidebar-scroll::-webkit-scrollbar-track { background: transparent; }
  .sidebar-scroll::-webkit-scrollbar-thumb { background: rgba(255,255,255,0.08); border-radius: 4px; }

  /* ─── Section ─── */
  .section {
    padding: 16px 20px 12px;
    border-bottom: 1px solid rgba(255,255,255,0.04);
  }
  .section-title {
    font-size: 10px; font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 1.2px;
    color: #555;
    margin-bottom: 10px;
  }

  /* ─── Node Type Buttons ─── */
  .type-btn {
    display: flex; align-items: center; gap: 10px;
    width: 100%;
    padding: 8px 12px;
    margin-bottom: 4px;
    background: transparent;
    border: 1px solid transparent;
    border-radius: 8px;
    cursor: pointer;
    font-family: inherit;
    font-size: 12px;
    color: #bbb;
    transition: all 0.2s;
  }
  .type-btn:hover { background: rgba(255,255,255,0.04); }
  .type-btn.active {
    background: rgba(255,255,255,0.06);
    border-color: rgba(255,255,255,0.1);
    color: #fff;
  }
  .type-btn .dot {
    width: 12px; height: 12px; border-radius: 50%;
    flex-shrink: 0;
    transition: box-shadow 0.2s;
  }
  .type-btn.active .dot { box-shadow: 0 0 8px currentColor; }
  .type-btn .dot.diamond { border-radius: 2px; transform: rotate(45deg); width:10px; height:10px; }
  .type-btn .dot.triangle { border-radius: 0; width:0; height:0;
    border-left: 6px solid transparent; border-right: 6px solid transparent; border-bottom: 10px solid; }
  .type-btn .name { flex: 1; text-align: left; }
  .type-btn .cnt {
    font-size: 10px; color: #444;
    background: rgba(255,255,255,0.04);
    padding: 2px 7px; border-radius: 10px;
    min-width: 24px; text-align: center;
  }
  .type-btn.active .cnt { color: #888; background: rgba(255,255,255,0.08); }

  /* ─── Domain Tags ─── */
  .domain-tags {
    display: flex; flex-wrap: wrap; gap: 6px;
  }
  .domain-tag {
    padding: 4px 10px;
    border-radius: 12px;
    font-size: 11px;
    cursor: pointer;
    border: 1px solid rgba(255,255,255,0.08);
    background: rgba(255,255,255,0.03);
    color: #888;
    transition: all 0.2s;
    user-select: none;
  }
  .domain-tag:hover { background: rgba(255,255,255,0.06); color: #bbb; }
  .domain-tag.active {
    background: rgba(102,126,234,0.15);
    border-color: rgba(102,126,234,0.3);
    color: #99b4ff;
  }

  /* ─── Importance Filter ─── */
  .importance-btns {
    display: flex; gap: 6px;
  }
  .imp-btn {
    flex: 1;
    padding: 6px 0;
    border-radius: 8px;
    font-size: 11px;
    cursor: pointer;
    border: 1px solid rgba(255,255,255,0.08);
    background: rgba(255,255,255,0.03);
    color: #888;
    text-align: center;
    transition: all 0.2s;
    font-family: inherit;
  }
  .imp-btn:hover { background: rgba(255,255,255,0.06); }
  .imp-btn.active { border-color: rgba(245,87,108,0.4); color: #f5576c; background: rgba(245,87,108,0.1); }
  .imp-btn.active[data-imp="High"] { border-color: rgba(245,87,108,0.4); color: #f5576c; background: rgba(245,87,108,0.1); }
  .imp-btn.active[data-imp="Mid"] { border-color: rgba(240,147,251,0.4); color: #f093fb; background: rgba(240,147,251,0.1); }
  .imp-btn.active[data-imp="Low"] { border-color: rgba(79,172,254,0.4); color: #4facfe; background: rgba(79,172,254,0.1); }

  /* ─── Actions ─── */
  .action-btn {
    display: flex; align-items: center; gap: 8px;
    width: 100%;
    padding: 8px 12px;
    margin-bottom: 4px;
    background: transparent;
    border: 1px solid rgba(255,255,255,0.06);
    border-radius: 8px;
    cursor: pointer;
    font-family: inherit;
    font-size: 12px;
    color: #888;
    transition: all 0.2s;
  }
  .action-btn:hover { background: rgba(255,255,255,0.04); color: #bbb; }
  .action-btn .icon { font-size: 14px; width: 20px; text-align: center; }

  /* ─── Paper List ─── */
  .paper-list-item {
    display: flex; align-items: center; gap: 8px;
    padding: 7px 12px;
    margin-bottom: 2px;
    border-radius: 6px;
    cursor: pointer;
    font-size: 11px;
    color: #888;
    transition: all 0.15s;
    overflow: hidden;
  }
  .paper-list-item:hover { background: rgba(102,126,234,0.08); color: #bbb; }
  .paper-list-item.active { background: rgba(102,126,234,0.12); color: #99b4ff; }
  .paper-list-item .pip {
    width: 6px; height: 6px; border-radius: 50%;
    background: #667eea; flex-shrink: 0; opacity: 0.6;
  }
  .paper-list-item .pname {
    flex: 1; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
  }

  /* ─── Footer ─── */
  .sidebar-footer {
    padding: 12px 20px;
    border-top: 1px solid rgba(255,255,255,0.06);
    font-size: 10px; color: #333;
    text-align: center;
    line-height: 1.5;
  }

  /* ─── Graph Area ─── */
  .graph-area {
    flex: 1;
    position: relative;
    overflow: hidden;
  }
  .graph-area svg { display: block; width: 100%; height: 100%; }

  /* ─── Tooltip ─── */
  .tooltip {
    position: fixed; pointer-events: none;
    background: rgba(14, 14, 26, 0.97);
    backdrop-filter: blur(16px);
    border: 1px solid rgba(255,255,255,0.1);
    border-radius: 12px;
    padding: 14px 18px;
    max-width: 360px;
    font-size: 12px; line-height: 1.6;
    box-shadow: 0 12px 48px rgba(0,0,0,0.6);
    z-index: 300;
    opacity: 0; transition: opacity 0.15s;
  }
  .tooltip.show { opacity: 1; }
  .tooltip .tt-title {
    font-weight: 600; font-size: 13px; margin-bottom: 6px;
    color: #fff;
  }
  .tooltip .tt-meta { color: #888; font-size: 11px; margin-bottom: 4px; }
  .tooltip .tt-body { color: #aaa; font-size: 11px; }
  .tooltip .tt-tag {
    display: inline-block; padding: 2px 8px;
    border-radius: 10px; font-size: 10px; font-weight: 500;
    margin-right: 4px; margin-top: 4px;
  }

  /* ─── Stats Badge ─── */
  .stats-badge {
    position: absolute; bottom: 16px; right: 20px;
    font-size: 11px; color: #333;
    z-index: 100;
  }

  /* ─── Minimap ─── */
  .minimap {
    position: absolute; bottom: 16px; left: 16px;
    width: 140px; height: 100px;
    background: rgba(14,14,26,0.8);
    border: 1px solid rgba(255,255,255,0.06);
    border-radius: 8px;
    overflow: hidden;
    z-index: 100;
  }
  .minimap svg { width: 100%; height: 100%; }
  .minimap .viewport-rect {
    fill: rgba(102,126,234,0.12);
    stroke: rgba(102,126,234,0.4);
    stroke-width: 1;
  }
</style>
</head>
<body>

<!-- ─── Left Sidebar ─── -->
<div class="sidebar">
  <div class="sidebar-header">
    <h1>Paper RAG Knowledge Graph</h1>
    <div class="search-box">
      <span class="search-icon">&#128269;</span>
      <input type="text" id="search" placeholder="Search papers, concepts...">
    </div>
  </div>

  <div class="sidebar-scroll">
    <!-- Node Type Filter -->
    <div class="section">
      <div class="section-title">Node Types</div>
      <button class="type-btn active" data-type="paper">
        <div class="dot" style="background:#667eea;"></div>
        <span class="name">Papers</span>
        <span class="cnt" id="cnt-paper">0</span>
      </button>
      <button class="type-btn active" data-type="chunk">
        <div class="dot" style="background:#f093fb;"></div>
        <span class="name">Chunks</span>
        <span class="cnt" id="cnt-chunk">0</span>
      </button>
      <button class="type-btn active" data-type="concept">
        <div class="dot diamond" style="background:#4facfe;"></div>
        <span class="name">Concepts</span>
        <span class="cnt" id="cnt-concept">0</span>
      </button>
      <button class="type-btn active" data-type="idea">
        <div class="dot triangle" style="border-bottom-color:#f5576c;"></div>
        <span class="name">Research Ideas</span>
        <span class="cnt" id="cnt-idea">0</span>
      </button>
    </div>

    <!-- Domain Filter -->
    <div class="section">
      <div class="section-title">Domains</div>
      <div class="domain-tags" id="domain-tags"></div>
    </div>

    <!-- Importance Filter -->
    <div class="section">
      <div class="section-title">Importance</div>
      <div class="importance-btns">
        <button class="imp-btn" data-imp="High">High</button>
        <button class="imp-btn" data-imp="Mid">Mid</button>
        <button class="imp-btn" data-imp="Low">Low</button>
      </div>
    </div>

    <!-- Actions -->
    <div class="section">
      <div class="section-title">View</div>
      <button class="action-btn" id="btn-fit">
        <span class="icon">&#9635;</span> Fit to Screen
      </button>
      <button class="action-btn" id="btn-reset">
        <span class="icon">&#8634;</span> Reset Filters
      </button>
      <button class="action-btn" id="btn-labels">
        <span class="icon">Aa</span> Toggle Labels
      </button>
      <button class="action-btn" id="btn-physics">
        <span class="icon">&#9883;</span> Pause Physics
      </button>
    </div>

    <!-- Paper List -->
    <div class="section" id="paper-list-section">
      <div class="section-title">Papers <span id="paper-list-count" style="color:#444"></span></div>
      <div id="paper-list"></div>
    </div>
  </div>

  <div class="sidebar-footer">
    Drag nodes &middot; Scroll to zoom &middot; Hover for details<br>
    Built with D3.js &middot; Data from Notion
  </div>
</div>

<!-- ─── Graph Area ─── -->
<div class="graph-area" id="graph-area">
  <div class="tooltip" id="tooltip"></div>
  <div class="stats-badge" id="stats"></div>
</div>

<script src="https://d3js.org/d3.v7.min.js"></script>
<script>
const DATA = __GRAPH_DATA__;

const PALETTE = {
  paper:   { fill: '#667eea', glow: 'rgba(102,126,234,0.35)', r: 22 },
  chunk:   { fill: '#f093fb', glow: 'rgba(240,147,251,0.25)', r: 10 },
  concept: { fill: '#4facfe', glow: 'rgba(79,172,254,0.35)', r: 16 },
  idea:    { fill: '#f5576c', glow: 'rgba(245,87,108,0.30)', r: 13 },
};

const EDGE_COLORS = {
  'paper-chunk':   'rgba(102,126,234,0.15)',
  'chunk-concept': 'rgba(79,172,254,0.18)',
  'paper-idea':    'rgba(245,87,108,0.15)',
};
const EDGE_HOVER = {
  'paper-chunk':   'rgba(102,126,234,0.6)',
  'chunk-concept': 'rgba(79,172,254,0.6)',
  'paper-idea':    'rgba(245,87,108,0.6)',
};

// ─── State ───
const state = {
  activeTypes: new Set(['paper','chunk','concept','idea']),
  activeDomains: new Set(),
  activeImportance: null,
  searchQuery: '',
  labelsVisible: true,
  physicsRunning: true,
  selectedPaper: null,
};

// ─── Setup ───
const graphArea = document.getElementById('graph-area');
const W = graphArea.clientWidth, H = graphArea.clientHeight;

// Stats & counts
const counts = {};
DATA.nodes.forEach(n => { counts[n.type] = (counts[n.type]||0)+1; });
Object.entries(counts).forEach(([k,v]) => {
  const el = document.getElementById('cnt-'+k);
  if(el) el.textContent = v;
});
document.getElementById('stats').textContent =
  `${DATA.nodes.length} nodes \u00b7 ${DATA.edges.length} edges`;

// Collect all domains
const allDomains = new Set();
DATA.nodes.forEach(n => { if(n.domain) n.domain.forEach(d => allDomains.add(d)); });
const domainContainer = document.getElementById('domain-tags');
[...allDomains].sort().forEach(d => {
  const tag = document.createElement('span');
  tag.className = 'domain-tag';
  tag.textContent = d;
  tag.dataset.domain = d;
  tag.addEventListener('click', () => {
    tag.classList.toggle('active');
    if(state.activeDomains.has(d)) state.activeDomains.delete(d);
    else state.activeDomains.add(d);
    applyFilters();
  });
  domainContainer.appendChild(tag);
});

// Paper list
const paperNodes = DATA.nodes.filter(n => n.type==='paper').sort((a,b) => a.label.localeCompare(b.label));
document.getElementById('paper-list-count').textContent = `(${paperNodes.length})`;
const paperListEl = document.getElementById('paper-list');
paperNodes.forEach(p => {
  const item = document.createElement('div');
  item.className = 'paper-list-item';
  item.innerHTML = `<div class="pip"></div><div class="pname">${esc(p.label)}</div>`;
  item.addEventListener('click', () => {
    if(state.selectedPaper === p.id) { state.selectedPaper = null; item.classList.remove('active'); applyFilters(); return; }
    document.querySelectorAll('.paper-list-item.active').forEach(el => el.classList.remove('active'));
    state.selectedPaper = p.id;
    item.classList.add('active');
    focusOnNode(p);
  });
  paperListEl.appendChild(item);
});

// ─── SVG ───
const svg = d3.select('#graph-area').append('svg')
  .attr('width', W).attr('height', H);

const defs = svg.append('defs');

// Glow filters
Object.entries(PALETTE).forEach(([type, p]) => {
  const filter = defs.append('filter').attr('id', 'glow-'+type)
    .attr('x','-50%').attr('y','-50%').attr('width','200%').attr('height','200%');
  filter.append('feGaussianBlur').attr('stdDeviation','6').attr('result','blur');
  filter.append('feMerge').selectAll('feMergeNode')
    .data(['blur','SourceGraphic']).enter()
    .append('feMergeNode').attr('in', d=>d);
});

const g = svg.append('g');

// Zoom
const zoom = d3.zoom().scaleExtent([0.1, 5])
  .on('zoom', e => g.attr('transform', e.transform));
svg.call(zoom);

// Force simulation
const sim = d3.forceSimulation(DATA.nodes)
  .force('link', d3.forceLink(DATA.edges).id(d=>d.id).distance(d => {
    if(d.type==='paper-chunk') return 80;
    if(d.type==='chunk-concept') return 100;
    return 90;
  }).strength(0.4))
  .force('charge', d3.forceManyBody().strength(d => {
    if(d.type==='paper') return -400;
    if(d.type==='concept') return -250;
    return -100;
  }))
  .force('center', d3.forceCenter(W/2, H/2))
  .force('collision', d3.forceCollide().radius(d => PALETTE[d.type].r + 8))
  .force('x', d3.forceX(W/2).strength(0.03))
  .force('y', d3.forceY(H/2).strength(0.03));

// Edges
const link = g.append('g').selectAll('line')
  .data(DATA.edges).enter().append('line')
  .attr('stroke', d => EDGE_COLORS[d.type])
  .attr('stroke-width', d => d.type==='paper-chunk'? 1.2 : 0.8)
  .attr('stroke-dasharray', d => d.type==='paper-idea'? '4,4' : null);

// Node groups
const node = g.append('g').selectAll('g')
  .data(DATA.nodes).enter().append('g')
  .attr('cursor','pointer')
  .call(d3.drag()
    .on('start', (e,d) => { if(!e.active) sim.alphaTarget(0.3).restart(); d.fx=d.x; d.fy=d.y; })
    .on('drag', (e,d) => { d.fx=e.x; d.fy=e.y; })
    .on('end', (e,d) => { if(!e.active) sim.alphaTarget(0); d.fx=null; d.fy=null; })
  );

// Draw shapes
node.each(function(d) {
  const el = d3.select(this);
  const p = PALETTE[d.type];
  if(d.type === 'concept') {
    el.append('rect')
      .attr('width', p.r*1.4).attr('height', p.r*1.4)
      .attr('x', -p.r*0.7).attr('y', -p.r*0.7)
      .attr('rx', 4)
      .attr('transform', 'rotate(45)')
      .attr('fill', p.fill).attr('opacity', 0.85)
      .attr('filter', 'url(#glow-'+d.type+')');
  } else if(d.type === 'idea') {
    const s = p.r;
    el.append('polygon')
      .attr('points', `0,${-s} ${s*0.87},${s*0.5} ${-s*0.87},${s*0.5}`)
      .attr('fill', p.fill).attr('opacity', 0.85)
      .attr('filter', 'url(#glow-'+d.type+')');
  } else {
    el.append('circle')
      .attr('r', p.r)
      .attr('fill', p.fill).attr('opacity', d.type==='paper'? 0.9 : 0.7)
      .attr('filter', 'url(#glow-'+d.type+')');
  }
});

// Labels
const labels = node.filter(d => d.type==='paper' || d.type==='concept')
  .append('text')
  .text(d => d.label.length > 22 ? d.label.slice(0,20)+'\u2026' : d.label)
  .attr('dy', d => d.type==='paper' ? PALETTE[d.type].r + 14 : PALETTE[d.type].r + 12)
  .attr('text-anchor','middle')
  .attr('fill', d => d.type==='paper' ? '#aab' : '#8ac')
  .attr('font-size', d => d.type==='paper' ? '11px' : '10px')
  .attr('font-weight', d => d.type==='paper' ? '600' : '400')
  .attr('pointer-events','none');

// ─── Tooltip ───
const tooltip = document.getElementById('tooltip');

function buildTooltip(d) {
  let html = `<div class="tt-title">${esc(d.label)}</div>`;
  if(d.type==='paper') {
    if(d.domain) html += `<div class="tt-meta">${d.domain.map(t=>`<span class="tt-tag" style="background:rgba(102,126,234,0.2);color:#99b">${t}</span>`).join('')}</div>`;
    if(d.relevance) html += `<div class="tt-meta">Relevance: ${d.relevance}</div>`;
    if(d.summary) html += `<div class="tt-body">${esc(d.summary)}</div>`;
  } else if(d.type==='chunk') {
    html += `<div class="tt-meta">${d.section||''} \u00b7 ${d.chunk_type||''} \u00b7 ${d.importance||''}</div>`;
    if(d.content) html += `<div class="tt-body">${esc(d.content)}</div>`;
  } else if(d.type==='concept') {
    if(d.category) html += `<div class="tt-meta">${d.category.map(t=>`<span class="tt-tag" style="background:rgba(79,172,254,0.15);color:#7bc">${t}</span>`).join('')}</div>`;
    if(d.description) html += `<div class="tt-body">${esc(d.description)}</div>`;
  } else if(d.type==='idea') {
    html += `<div class="tt-meta">Priority: ${d.priority||''} \u00b7 ${d.status||''}</div>`;
    if(d.description) html += `<div class="tt-body">${esc(d.description)}</div>`;
  }
  return html;
}

function esc(s) { const d=document.createElement('div'); d.textContent=s||''; return d.innerHTML; }

node.on('mouseover', function(e,d) {
  tooltip.innerHTML = buildTooltip(d);
  tooltip.style.left = (e.clientX+16)+'px';
  tooltip.style.top = (e.clientY-10)+'px';
  tooltip.classList.add('show');

  const connected = new Set();
  connected.add(d.id);
  DATA.edges.forEach(l => {
    const sid = typeof l.source==='object'?l.source.id:l.source;
    const tid = typeof l.target==='object'?l.target.id:l.target;
    if(sid===d.id) connected.add(tid);
    if(tid===d.id) connected.add(sid);
  });
  node.attr('opacity', n => connected.has(n.id) ? 1 : 0.06);
  link.attr('stroke', l => {
    const sid = typeof l.source==='object'?l.source.id:l.source;
    const tid = typeof l.target==='object'?l.target.id:l.target;
    return (sid===d.id||tid===d.id) ? EDGE_HOVER[l.type] : 'rgba(255,255,255,0.01)';
  }).attr('stroke-width', l => {
    const sid = typeof l.source==='object'?l.source.id:l.source;
    const tid = typeof l.target==='object'?l.target.id:l.target;
    return (sid===d.id||tid===d.id) ? 2.5 : 0.3;
  });
})
.on('mousemove', function(e) {
  tooltip.style.left = (e.clientX+16)+'px';
  tooltip.style.top = (e.clientY-10)+'px';
})
.on('mouseout', function() {
  tooltip.classList.remove('show');
  applyFilters();
});

// ─── Tick ───
sim.on('tick', () => {
  link.attr('x1',d=>d.source.x).attr('y1',d=>d.source.y)
    .attr('x2',d=>d.target.x).attr('y2',d=>d.target.y);
  node.attr('transform', d=>`translate(${d.x},${d.y})`);
});

// ─── Filter Logic ───
function applyFilters() {
  const q = state.searchQuery;
  const visible = new Set();

  DATA.nodes.forEach(n => {
    // Type filter
    if(!state.activeTypes.has(n.type)) return;

    // Domain filter (only applies to papers)
    if(state.activeDomains.size > 0 && n.type === 'paper') {
      if(!n.domain || !n.domain.some(d => state.activeDomains.has(d))) return;
    }

    // Importance filter (only applies to chunks)
    if(state.activeImportance && n.type === 'chunk') {
      if(n.importance !== state.activeImportance) return;
    }

    // Search filter
    if(q) {
      const match = n.label.toLowerCase().includes(q)
        || (n.summary||'').toLowerCase().includes(q)
        || (n.description||'').toLowerCase().includes(q)
        || (n.content||'').toLowerCase().includes(q)
        || (n.domain||[]).some(d => d.toLowerCase().includes(q));
      if(!match) return;
    }

    visible.add(n.id);
  });

  // Selected paper focus
  if(state.selectedPaper) {
    const focused = new Set();
    focused.add(state.selectedPaper);
    DATA.edges.forEach(l => {
      const sid = typeof l.source==='object'?l.source.id:l.source;
      const tid = typeof l.target==='object'?l.target.id:l.target;
      if(sid===state.selectedPaper && visible.has(tid)) { focused.add(tid); }
      if(tid===state.selectedPaper && visible.has(sid)) { focused.add(sid); }
    });
    // 2-hop for concept connections
    DATA.edges.forEach(l => {
      const sid = typeof l.source==='object'?l.source.id:l.source;
      const tid = typeof l.target==='object'?l.target.id:l.target;
      if(focused.has(sid) && visible.has(tid)) focused.add(tid);
      if(focused.has(tid) && visible.has(sid)) focused.add(sid);
    });
    node.attr('opacity', n => focused.has(n.id) ? 1 : 0.04);
    link.attr('stroke', l => {
      const sid = typeof l.source==='object'?l.source.id:l.source;
      const tid = typeof l.target==='object'?l.target.id:l.target;
      return (focused.has(sid)&&focused.has(tid)) ? EDGE_HOVER[l.type] : 'rgba(255,255,255,0.01)';
    }).attr('stroke-width', l => {
      const sid = typeof l.source==='object'?l.source.id:l.source;
      const tid = typeof l.target==='object'?l.target.id:l.target;
      return (focused.has(sid)&&focused.has(tid)) ? 2 : 0.3;
    });
    return;
  }

  // Extend visibility to connected nodes (if domain or search active)
  if(state.activeDomains.size > 0 || q) {
    const extended = new Set(visible);
    DATA.edges.forEach(l => {
      const sid = typeof l.source==='object'?l.source.id:l.source;
      const tid = typeof l.target==='object'?l.target.id:l.target;
      if(visible.has(sid) && state.activeTypes.has(DATA.nodes.find(n=>n.id===tid)?.type)) extended.add(tid);
      if(visible.has(tid) && state.activeTypes.has(DATA.nodes.find(n=>n.id===sid)?.type)) extended.add(sid);
    });
    node.attr('opacity', n => extended.has(n.id) ? 1 : 0.04);
    link.attr('opacity', l => {
      const sid = typeof l.source==='object'?l.source.id:l.source;
      const tid = typeof l.target==='object'?l.target.id:l.target;
      return (extended.has(sid)&&extended.has(tid)) ? 1 : 0.02;
    });
    link.attr('stroke', d => EDGE_COLORS[d.type])
      .attr('stroke-width', d => d.type==='paper-chunk'? 1.2 : 0.8);
    return;
  }

  // Type-only filter
  node.attr('opacity', n => visible.has(n.id) ? 1 : 0.04);
  link.attr('opacity', l => {
    const sid = typeof l.source==='object'?l.source.id:l.source;
    const tid = typeof l.target==='object'?l.target.id:l.target;
    return (visible.has(sid)&&visible.has(tid)) ? 1 : 0.02;
  });
  link.attr('stroke', d => EDGE_COLORS[d.type])
    .attr('stroke-width', d => d.type==='paper-chunk'? 1.2 : 0.8);
}

// ─── Type Toggle ───
document.querySelectorAll('.type-btn[data-type]').forEach(el => {
  el.addEventListener('click', () => {
    const type = el.dataset.type;
    el.classList.toggle('active');
    if(state.activeTypes.has(type)) state.activeTypes.delete(type);
    else state.activeTypes.add(type);
    applyFilters();
  });
});

// ─── Importance Toggle ───
document.querySelectorAll('.imp-btn').forEach(el => {
  el.addEventListener('click', () => {
    const imp = el.dataset.imp;
    if(state.activeImportance === imp) {
      state.activeImportance = null;
      el.classList.remove('active');
    } else {
      document.querySelectorAll('.imp-btn').forEach(b => b.classList.remove('active'));
      state.activeImportance = imp;
      el.classList.add('active');
    }
    applyFilters();
  });
});

// ─── Search ───
document.getElementById('search').addEventListener('input', function() {
  state.searchQuery = this.value.toLowerCase().trim();
  state.selectedPaper = null;
  document.querySelectorAll('.paper-list-item.active').forEach(el => el.classList.remove('active'));
  applyFilters();
});

// ─── Focus on Node ───
function focusOnNode(d) {
  const scale = 1.5;
  const tx = W/2 - d.x*scale;
  const ty = H/2 - d.y*scale;
  svg.transition().duration(600).call(zoom.transform,
    d3.zoomIdentity.translate(tx,ty).scale(scale));
  applyFilters();
}

// ─── Action Buttons ───
document.getElementById('btn-fit').addEventListener('click', () => {
  const bounds = g.node().getBBox();
  if(!bounds.width) return;
  const scale = Math.min(W/bounds.width, H/bounds.height) * 0.85;
  const tx = W/2 - (bounds.x+bounds.width/2)*scale;
  const ty = H/2 - (bounds.y+bounds.height/2)*scale;
  svg.transition().duration(600).call(zoom.transform,
    d3.zoomIdentity.translate(tx,ty).scale(scale));
});

document.getElementById('btn-reset').addEventListener('click', () => {
  state.activeTypes = new Set(['paper','chunk','concept','idea']);
  state.activeDomains.clear();
  state.activeImportance = null;
  state.searchQuery = '';
  state.selectedPaper = null;
  document.getElementById('search').value = '';
  document.querySelectorAll('.type-btn').forEach(el => el.classList.add('active'));
  document.querySelectorAll('.domain-tag').forEach(el => el.classList.remove('active'));
  document.querySelectorAll('.imp-btn').forEach(el => el.classList.remove('active'));
  document.querySelectorAll('.paper-list-item.active').forEach(el => el.classList.remove('active'));
  applyFilters();
});

document.getElementById('btn-labels').addEventListener('click', () => {
  state.labelsVisible = !state.labelsVisible;
  labels.attr('display', state.labelsVisible ? null : 'none');
  document.getElementById('btn-labels').style.color = state.labelsVisible ? '#888' : '#4facfe';
});

document.getElementById('btn-physics').addEventListener('click', () => {
  state.physicsRunning = !state.physicsRunning;
  const btn = document.getElementById('btn-physics');
  if(state.physicsRunning) {
    sim.alpha(0.3).restart();
    btn.innerHTML = '<span class="icon">&#9883;</span> Pause Physics';
    btn.style.color = '#888';
  } else {
    sim.stop();
    btn.innerHTML = '<span class="icon">&#9654;</span> Resume Physics';
    btn.style.color = '#4facfe';
  }
});

// ─── Fit on load ───
sim.on('end', () => {
  const bounds = g.node().getBBox();
  if(!bounds.width) return;
  const scale = Math.min(W/bounds.width, H/bounds.height) * 0.85;
  const tx = W/2 - (bounds.x+bounds.width/2)*scale;
  const ty = H/2 - (bounds.y+bounds.height/2)*scale;
  svg.transition().duration(800).call(zoom.transform,
    d3.zoomIdentity.translate(tx,ty).scale(scale));
});
</script>
</body>
</html>"""


def build_html(nodes, edges, output_path):
    graph_data = json.dumps({"nodes": nodes, "edges": edges}, ensure_ascii=False)
    html = HTML_TEMPLATE.replace('__GRAPH_DATA__', graph_data)
    output_dir = os.path.dirname(output_path)
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(html)
    print(f"\n✅ Graph saved to: {output_path}")
    print(f"   Nodes: {len(nodes)}, Edges: {len(edges)}")


def main():
    parser = argparse.ArgumentParser(description="Paper RAG Knowledge Graph")
    parser.add_argument("--demo", action="store_true")
    parser.add_argument("--output", "-o", default="paper_rag_graph.html")
    args = parser.parse_args()

    print("🔍 Paper RAG Knowledge Graph Builder\n")
    if args.demo:
        print("📦 Demo mode")
        nodes, edges = build_demo_data()
    else:
        print("🌐 Notion API에서 데이터 가져오는 중...")
        nodes, edges = fetch_from_notion()

    build_html(nodes, edges, args.output)


if __name__ == "__main__":
    main()
