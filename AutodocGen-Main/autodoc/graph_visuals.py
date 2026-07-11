"""Call graph visualization helpers for Word and offline HTML outputs."""

from __future__ import annotations

import html
import json
import os
import re
import shutil
import subprocess
from typing import Any, Iterable, Optional

from . import utils


ROLE_STYLES = {
    "focal": {"color": "#2563eb", "fill": "#dbeafe"},
    "caller": {"color": "#ea580c", "fill": "#ffedd5"},
    "callee": {"color": "#16a34a", "fill": "#dcfce7"},
    "impact": {"color": "#dc2626", "fill": "#fee2e2"},
    "module": {"color": "#7c3aed", "fill": "#ede9fe"},
    "external": {"color": "#64748b", "fill": "#f1f5f9"},
}


def _extra(cfg: Optional[Any]) -> dict[str, Any]:
    return dict(getattr(cfg, "extra_params", {}) or {}) if cfg is not None else {}


def _cfg_value(cfg: Optional[Any], name: str, default: Any = "") -> Any:
    extra = _extra(cfg)
    if name in extra:
        return extra.get(name)
    if cfg is not None and hasattr(cfg, name):
        value = getattr(cfg, name)
        if value not in (None, ""):
            return value
    return default


def normalize_graph_output(value: Any) -> str:
    text = str(value or "off").strip().lower()
    if text in {"0", "false", "no", "off", "none", "disabled"}:
        return "off"
    if text in {"word", "doc", "docx"}:
        return "word"
    if text in {"html", "web"}:
        return "html"
    if text in {"1", "true", "yes", "on", "both", "all"}:
        return "both"
    return "off"


def graph_output_from_cfg(cfg: Optional[Any]) -> str:
    return normalize_graph_output(_cfg_value(cfg, "graph_output", "off"))


def word_graph_enabled(cfg: Optional[Any]) -> bool:
    return bool(getattr(cfg, "_autodoc_graph_configured", False)) and graph_output_from_cfg(cfg) in {"both", "word"}


def html_graph_enabled(cfg: Optional[Any]) -> bool:
    return bool(getattr(cfg, "_autodoc_graph_configured", False)) and graph_output_from_cfg(cfg) in {"both", "html"}


def graph_enabled(cfg: Optional[Any]) -> bool:
    return bool(getattr(cfg, "_autodoc_graph_configured", False)) and graph_output_from_cfg(cfg) != "off"


def graph_depth(cfg: Optional[Any]) -> int:
    try:
        return max(1, min(10, int(_cfg_value(cfg, "graph_depth", 2) or 2)))
    except Exception:
        return 2


def graph_max_nodes(cfg: Optional[Any]) -> int:
    try:
        return max(5, min(500, int(_cfg_value(cfg, "graph_max_nodes", 40) or 40)))
    except Exception:
        return 40


def configure_graph_output(cfg: Optional[Any], output_docx: str) -> dict[str, str]:
    if cfg is None:
        return {}
    mode = graph_output_from_cfg(cfg)
    base = os.path.splitext(os.path.abspath(output_docx))[0] + "_graphs"
    assets = os.path.join(base, "assets")
    try:
        cfg._autodoc_graph_configured = mode != "off"
        cfg._autodoc_graph_output_dir = base
        cfg._autodoc_graph_assets_dir = assets
        cfg._autodoc_graph_html_path = os.path.join(base, "index.html")
        cfg._autodoc_graph_payloads = []
        if mode != "off":
            os.makedirs(assets, exist_ok=True)
    except Exception:
        pass
    return {"dir": base, "assets": assets, "html": os.path.join(base, "index.html")}


def _slug(value: str) -> str:
    text = re.sub(r"[^A-Za-z0-9_.-]+", "_", value or "").strip("_")
    return text[:80] or "graph"


def _node_id(name: str, file_path: str = "", line: int = 0) -> str:
    base = utils._safe_strip(name) or "unknown"
    file_part = utils._safe_strip(file_path)
    return f"{base}|{file_part}|{int(line or 0)}"


def _merge_node(nodes: dict[str, dict[str, Any]], node: dict[str, Any]) -> None:
    node_id = utils._safe_strip(node.get("id"))
    if not node_id:
        return
    current = nodes.get(node_id)
    if not current:
        nodes[node_id] = node
        return
    if current.get("role") == "external" and node.get("role") != "external":
        current["role"] = node.get("role")
    if not current.get("filePath") and node.get("filePath"):
        current["filePath"] = node.get("filePath")
    if not current.get("startLine") and node.get("startLine"):
        current["startLine"] = node.get("startLine")


def _record_to_node(record: Any, role: str) -> dict[str, Any]:
    if isinstance(record, dict):
        name = utils._safe_strip(record.get("name"))
        file_path = utils._safe_strip(record.get("filePath") or record.get("file_path"))
        line = int(record.get("startLine") or record.get("start_line") or 0)
        kind = utils._safe_strip(record.get("kind")) or "function"
        qualified = utils._safe_strip(record.get("qualifiedName") or record.get("qualified_name"))
    else:
        name = utils._safe_strip(record)
        file_path = ""
        line = 0
        kind = "function"
        qualified = ""
    return {
        "id": _node_id(name, file_path, line),
        "name": name,
        "kind": kind,
        "qualifiedName": qualified,
        "filePath": file_path,
        "startLine": line,
        "role": role,
    }


def build_function_graph_payload(func_data: dict[str, Any], cfg: Optional[Any] = None) -> dict[str, Any]:
    func_info = dict((func_data or {}).get("func_info") or {})
    file_context = dict((func_data or {}).get("file_context") or {})
    func_name = utils._safe_strip(func_info.get("func_name")) or "unknown"
    source_file = utils._safe_strip(file_context.get("source_file"))
    focal_record = dict(file_context.get("codegraph_node") or {})
    focal = _record_to_node(
        {
            "name": focal_record.get("name") or func_name,
            "kind": focal_record.get("kind") or "function",
            "filePath": focal_record.get("filePath") or source_file,
            "startLine": focal_record.get("startLine") or 0,
            "qualifiedName": focal_record.get("qualifiedName") or "",
        },
        "focal",
    )
    nodes: dict[str, dict[str, Any]] = {}
    edges: list[dict[str, Any]] = []
    _merge_node(nodes, focal)

    callers = list(file_context.get("codegraph_callers") or file_context.get("caller_funcs") or [])
    callees = list(file_context.get("codegraph_callees") or file_context.get("callee_funcs") or [])
    impact = list(file_context.get("codegraph_impact") or [])
    max_nodes = graph_max_nodes(cfg)

    for item in callers:
        node = _record_to_node(item, "caller")
        if not node["name"]:
            continue
        _merge_node(nodes, node)
        edges.append({"source": node["id"], "target": focal["id"], "kind": "calls"})
        if len(nodes) >= max_nodes:
            break

    for item in callees:
        if len(nodes) >= max_nodes:
            break
        node = _record_to_node(item, "callee")
        if not node["name"]:
            continue
        _merge_node(nodes, node)
        edges.append({"source": focal["id"], "target": node["id"], "kind": "calls"})

    for item in impact:
        if len(nodes) >= max_nodes:
            break
        node = _record_to_node(item, "impact")
        if not node["name"] or node["id"] == focal["id"]:
            continue
        _merge_node(nodes, node)
        edges.append({"source": node["id"], "target": focal["id"], "kind": "impact"})

    status = dict(file_context.get("codegraph_status") or {})
    return {
        "id": _slug(f"{os.path.basename(source_file)}_{func_name}"),
        "type": "function",
        "title": func_name,
        "sourceFile": source_file,
        "status": status,
        "truncated": len(nodes) >= max_nodes,
        "nodes": list(nodes.values()),
        "edges": _dedupe_edges(edges),
    }


def build_project_overview_payload(func_entries: Iterable[dict[str, Any]], cfg: Optional[Any] = None, *, root_dir: str = "") -> dict[str, Any]:
    nodes: dict[str, dict[str, Any]] = {}
    edges: list[dict[str, Any]] = []
    known: dict[str, str] = {}
    max_nodes = graph_max_nodes(cfg)
    entries = list(func_entries or [])
    for entry in entries:
        func_info = dict((entry or {}).get("func_info") or {})
        file_context = dict((entry or {}).get("file_context") or {})
        name = utils._safe_strip(func_info.get("func_name"))
        source_file = utils._safe_strip(file_context.get("source_file"))
        if not name:
            continue
        node = _record_to_node(
            {
                "name": name,
                "kind": "function",
                "filePath": _rel(source_file, root_dir),
            },
            "focal",
        )
        _merge_node(nodes, node)
        known[name] = node["id"]
        if len(nodes) >= max_nodes:
            break
    for entry in entries:
        func_info = dict((entry or {}).get("func_info") or {})
        file_context = dict((entry or {}).get("file_context") or {})
        source_name = utils._safe_strip(func_info.get("func_name"))
        source_id = known.get(source_name)
        if not source_id:
            continue
        for callee in list(file_context.get("callee_funcs") or []):
            target_name = utils._safe_strip(callee if not isinstance(callee, dict) else callee.get("name"))
            target_id = known.get(target_name)
            if target_id:
                edges.append({"source": source_id, "target": target_id, "kind": "calls"})
    return {
        "id": "project_overview",
        "type": "project",
        "title": "项目调用关系总览",
        "sourceFile": os.path.abspath(root_dir) if root_dir else "",
        "nodes": list(nodes.values())[:max_nodes],
        "edges": _dedupe_edges(edges),
        "truncated": len(nodes) >= max_nodes,
    }


def _rel(path: str, root: str) -> str:
    if not path:
        return ""
    if not root:
        return path
    try:
        return os.path.relpath(os.path.abspath(path), os.path.abspath(root)).replace(os.sep, "/")
    except Exception:
        return path


def _dedupe_edges(edges: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str]] = set()
    for edge in edges:
        key = (
            utils._safe_strip(edge.get("source")),
            utils._safe_strip(edge.get("target")),
            utils._safe_strip(edge.get("kind")),
        )
        if not key[0] or not key[1] or key in seen:
            continue
        seen.add(key)
        out.append({"source": key[0], "target": key[1], "kind": key[2] or "calls"})
    return out


def payload_has_edges(payload: dict[str, Any]) -> bool:
    return bool((payload or {}).get("nodes")) and bool((payload or {}).get("edges"))


def append_payload(cfg: Optional[Any], payload: dict[str, Any]) -> None:
    if cfg is None or not html_graph_enabled(cfg):
        return
    try:
        payloads = getattr(cfg, "_autodoc_graph_payloads", None)
        if not isinstance(payloads, list):
            payloads = []
            cfg._autodoc_graph_payloads = payloads
        payloads.append(payload)
    except Exception:
        pass


def build_dot(payload: dict[str, Any]) -> str:
    lines = [
        "digraph G {",
        "  graph [rankdir=LR, bgcolor=\"white\", pad=\"0.25\", nodesep=\"0.45\", ranksep=\"0.75\"];",
        "  node [shape=box, style=\"rounded,filled\", fontname=\"Helvetica\", fontsize=11, margin=\"0.10,0.06\"];",
        "  edge [fontname=\"Helvetica\", fontsize=9, color=\"#64748b\", arrowsize=0.7];",
    ]
    for node in payload.get("nodes") or []:
        role = utils._safe_strip(node.get("role")) or "external"
        style = ROLE_STYLES.get(role, ROLE_STYLES["external"])
        label = _dot_label(node)
        lines.append(
            f"  {_dot_quote(node['id'])} [label={_dot_quote(label)}, color=\"{style['color']}\", fillcolor=\"{style['fill']}\"];"
        )
    for edge in payload.get("edges") or []:
        color = "#dc2626" if edge.get("kind") == "impact" else "#64748b"
        lines.append(f"  {_dot_quote(edge['source'])} -> {_dot_quote(edge['target'])} [color=\"{color}\"];")
    lines.append("}")
    return "\n".join(lines)


def _dot_label(node: dict[str, Any]) -> str:
    name = utils._safe_strip(node.get("name")) or "unknown"
    file_path = utils._safe_strip(node.get("filePath"))
    line = int(node.get("startLine") or 0)
    suffix = ""
    if file_path:
        suffix = os.path.basename(file_path)
        if line:
            suffix += f":{line}"
    return f"{name}\n{suffix}" if suffix else name


def _dot_quote(value: str) -> str:
    return json.dumps(str(value or ""), ensure_ascii=False)


def render_payload_png(payload: dict[str, Any], cfg: Optional[Any] = None) -> str:
    if not word_graph_enabled(cfg) or not payload_has_edges(payload):
        return ""
    assets = utils._safe_strip(getattr(cfg, "_autodoc_graph_assets_dir", ""))
    if not assets:
        return ""
    os.makedirs(assets, exist_ok=True)
    base = _slug(payload.get("id") or payload.get("title") or "graph")
    dot_path = os.path.join(assets, base + ".dot")
    png_path = os.path.join(assets, base + ".png")
    try:
        with open(dot_path, "w", encoding="utf-8") as fh:
            fh.write(build_dot(payload))
        dot_exe = utils._safe_strip(_cfg_value(cfg, "graphviz_dot_path", "")) or shutil.which("dot") or ""
        if dot_exe:
            proc = subprocess.run(
                [dot_exe, "-Tpng", dot_path, "-o", png_path],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=30,
                check=False,
            )
            if proc.returncode == 0 and os.path.exists(png_path):
                return png_path
    except Exception:
        pass
    return render_simple_png(payload, png_path)


def render_simple_png(payload: dict[str, Any], png_path: str) -> str:
    try:
        from PIL import Image, ImageDraw, ImageFont
    except Exception:
        return ""
    nodes = list(payload.get("nodes") or [])
    edges = list(payload.get("edges") or [])
    width = 1200
    height = max(420, 110 + len(nodes) * 34)
    image = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(image)
    try:
        font = ImageFont.truetype("Arial Unicode.ttf", 18)
        small = ImageFont.truetype("Arial Unicode.ttf", 14)
    except Exception:
        font = ImageFont.load_default()
        small = ImageFont.load_default()
    draw.text((28, 24), utils._safe_strip(payload.get("title")) or "调用关系图", fill="#0f172a", font=font)
    y = 70
    for node in nodes:
        role = utils._safe_strip(node.get("role")) or "external"
        style = ROLE_STYLES.get(role, ROLE_STYLES["external"])
        draw.rounded_rectangle((32, y, 430, y + 26), radius=6, fill=style["fill"], outline=style["color"], width=2)
        label = utils._safe_strip(node.get("name")) or "unknown"
        draw.text((44, y + 5), label[:52], fill="#0f172a", font=small)
        y += 34
    y = 70
    x = 500
    for edge in edges[: max(1, min(18, len(edges)))]:
        src = _find_node_name(nodes, edge.get("source"))
        dst = _find_node_name(nodes, edge.get("target"))
        draw.text((x, y), f"{src} -> {dst}"[:82], fill="#334155", font=small)
        y += 28
    image.save(png_path)
    return png_path if os.path.exists(png_path) else ""


def _find_node_name(nodes: list[dict[str, Any]], node_id: str) -> str:
    for node in nodes:
        if node.get("id") == node_id:
            return utils._safe_strip(node.get("name")) or "unknown"
    return "unknown"


def fallback_rows(payload: dict[str, Any]) -> list[list[str]]:
    nodes = {node.get("id"): node for node in (payload.get("nodes") or [])}
    rows: list[list[str]] = []
    for edge in payload.get("edges") or []:
        src = nodes.get(edge.get("source")) or {}
        dst = nodes.get(edge.get("target")) or {}
        rows.append([
            "影响" if edge.get("kind") == "impact" else "调用",
            utils._safe_strip(src.get("name")),
            utils._safe_strip(dst.get("name")),
        ])
    return rows


def write_html_report(cfg: Optional[Any], *, title: str = "AutoDocGen CodeGraph") -> str:
    if cfg is None or not html_graph_enabled(cfg):
        return ""
    payloads = list(getattr(cfg, "_autodoc_graph_payloads", []) or [])
    html_path = utils._safe_strip(getattr(cfg, "_autodoc_graph_html_path", ""))
    if not html_path:
        return ""
    os.makedirs(os.path.dirname(html_path), exist_ok=True)
    data = {"title": title, "graphs": payloads}
    with open(html_path, "w", encoding="utf-8") as fh:
        fh.write(_html_document(data))
    return html_path


def _html_document(data: dict[str, Any]) -> str:
    data_json = json.dumps(data, ensure_ascii=False).replace("</", "<\\/")
    title = html.escape(utils._safe_strip(data.get("title")) or "AutoDocGen CodeGraph")
    return f"""<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<style>
html,body{{margin:0;height:100%;font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Arial,"Microsoft YaHei",sans-serif;background:#f8fafc;color:#0f172a;}}
.app{{display:grid;grid-template-columns:320px 1fr;height:100%;}}
.side{{border-right:1px solid #dbe3ef;background:#ffffff;display:flex;flex-direction:column;min-width:0;}}
.brand{{padding:16px 18px;border-bottom:1px solid #e2e8f0;}}
.brand h1{{font-size:18px;margin:0 0 4px;}}
.brand p{{font-size:12px;margin:0;color:#64748b;}}
.controls{{display:grid;gap:10px;padding:14px;border-bottom:1px solid #e2e8f0;}}
input,select,button{{font:inherit;border:1px solid #cbd5e1;border-radius:6px;background:white;color:#0f172a;padding:8px 10px;}}
button{{cursor:pointer;background:#0f172a;color:white;border-color:#0f172a;}}
.list{{overflow:auto;padding:8px;}}
.item{{display:block;width:100%;text-align:left;background:white;color:#0f172a;border:1px solid #e2e8f0;margin:6px 0;border-radius:6px;padding:9px 10px;}}
.item.active{{border-color:#2563eb;box-shadow:0 0 0 2px #bfdbfe;}}
.canvas{{position:relative;overflow:hidden;background:linear-gradient(#f8fafc,#eef2f7);}}
.toolbar{{position:absolute;top:12px;right:12px;display:flex;gap:8px;z-index:2;}}
.meta{{position:absolute;left:12px;bottom:12px;right:12px;background:rgba(255,255,255,.92);border:1px solid #dbe3ef;border-radius:8px;padding:10px 12px;font-size:13px;z-index:2;}}
svg{{width:100%;height:100%;display:block;}}
.node rect{{stroke-width:2;rx:8;ry:8;}}
.node text{{font-size:12px;dominant-baseline:middle;pointer-events:none;}}
.edge{{stroke:#64748b;stroke-width:1.8;fill:none;marker-end:url(#arrow);}}
.edge.impact{{stroke:#dc2626;}}
.hidden{{display:none;}}
</style>
</head>
<body>
<div class="app">
  <aside class="side">
    <div class="brand"><h1>{title}</h1><p>离线交互式调用关系图谱</p></div>
    <div class="controls">
      <input id="search" placeholder="搜索函数、文件或模块">
      <select id="filter">
        <option value="all">全部关系</option>
        <option value="calls">调用关系</option>
        <option value="impact">影响范围</option>
      </select>
      <button id="fit">适配视图</button>
    </div>
    <div id="graphList" class="list"></div>
  </aside>
  <main class="canvas">
    <div class="toolbar"><button id="zoomIn">+</button><button id="zoomOut">-</button></div>
    <svg id="svg" role="img" aria-label="CodeGraph"></svg>
    <div id="meta" class="meta">请选择左侧图谱。</div>
  </main>
</div>
<script>
const DATA = {data_json};
const styles = {json.dumps(ROLE_STYLES)};
let current = 0, scale = 1, panX = 0, panY = 0;
const list = document.getElementById('graphList');
const svg = document.getElementById('svg');
const meta = document.getElementById('meta');
const search = document.getElementById('search');
const filter = document.getElementById('filter');
function label(g){{return `${{g.type === 'project' ? '项目' : '函数'}} · ${{g.title || '未命名'}} · ${{(g.nodes||[]).length}} 节点`;}}
function renderList(){{
  list.innerHTML = '';
  (DATA.graphs||[]).forEach((g,i)=>{{
    const b=document.createElement('button'); b.className='item'+(i===current?' active':''); b.textContent=label(g);
    b.onclick=()=>{{current=i; scale=1; panX=0; panY=0; renderList(); renderGraph();}};
    list.appendChild(b);
  }});
}}
function visibleNode(n){{
  const q=search.value.trim().toLowerCase();
  if(!q) return true;
  return [n.name,n.filePath,n.qualifiedName,n.kind].join(' ').toLowerCase().includes(q);
}}
function layout(nodes){{
  const w=svg.clientWidth||900, h=svg.clientHeight||600, cx=w/2, cy=h/2;
  const focal=nodes.find(n=>n.role==='focal') || nodes[0];
  const out={{}};
  if(focal) out[focal.id]={{x:cx,y:cy}};
  const groups={{caller:[],callee:[],impact:[],external:[],module:[]}};
  nodes.forEach(n=>{{if(!focal||n.id!==focal.id)(groups[n.role]||groups.external).push(n);}});
  place(groups.caller, cx-280, cy, 160); place(groups.callee, cx+280, cy, 160); place(groups.impact, cx, cy+210, 180); place(groups.external.concat(groups.module), cx, cy-210, 180);
  function place(arr,x,y,spread){{arr.forEach((n,i)=>{{const off=(i-(arr.length-1)/2)*(spread/Math.max(1,arr.length-1||1));out[n.id]={{x:x,y:y+off}};}});}}
  return out;
}}
function renderGraph(){{
  const g=(DATA.graphs||[])[current]; if(!g){{svg.innerHTML=''; meta.textContent='没有可显示的图谱。'; return;}}
  const edgeFilter=filter.value;
  const nodes=(g.nodes||[]).filter(visibleNode);
  const nodeIds=new Set(nodes.map(n=>n.id));
  const edges=(g.edges||[]).filter(e=>nodeIds.has(e.source)&&nodeIds.has(e.target)&&(edgeFilter==='all'||e.kind===edgeFilter));
  const pos=layout(nodes);
  svg.innerHTML=`<defs><marker id="arrow" markerWidth="10" markerHeight="8" refX="9" refY="4" orient="auto"><path d="M0,0 L10,4 L0,8 Z" fill="#64748b"></path></marker></defs><g id="viewport"></g>`;
  const view=svg.querySelector('#viewport'); view.setAttribute('transform',`translate(${{panX}},${{panY}}) scale(${{scale}})`);
  edges.forEach(e=>{{const a=pos[e.source],b=pos[e.target]; if(!a||!b)return; const p=document.createElementNS('http://www.w3.org/2000/svg','path'); p.setAttribute('class','edge '+(e.kind||'')); p.setAttribute('d',`M ${{a.x}} ${{a.y}} C ${{(a.x+b.x)/2}} ${{a.y}}, ${{(a.x+b.x)/2}} ${{b.y}}, ${{b.x}} ${{b.y}}`); view.appendChild(p);}});
  nodes.forEach(n=>{{const p=pos[n.id]; const s=styles[n.role]||styles.external; const grp=document.createElementNS('http://www.w3.org/2000/svg','g'); grp.setAttribute('class','node'); grp.setAttribute('transform',`translate(${{p.x-90}},${{p.y-18}})`); grp.innerHTML=`<rect width="180" height="36" fill="${{s.fill}}" stroke="${{s.color}}"></rect><text x="90" y="18" text-anchor="middle">${{escapeHtml(n.name||'unknown')}}</text>`; grp.onclick=()=>showMeta(g,n); view.appendChild(grp);}});
  meta.textContent=`${{label(g)}}，显示 ${{nodes.length}} 个节点、${{edges.length}} 条边。`;
}}
function showMeta(g,n){{meta.innerHTML=`<b>${{escapeHtml(n.name||'unknown')}}</b><br>${{escapeHtml(n.kind||'function')}} · ${{escapeHtml(n.filePath||'')}}${{n.startLine?':'+n.startLine:''}}`;}}
function escapeHtml(s){{return String(s).replace(/[&<>"']/g,c=>({{'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}}[c]));}}
document.getElementById('zoomIn').onclick=()=>{{scale*=1.2; renderGraph();}};
document.getElementById('zoomOut').onclick=()=>{{scale/=1.2; renderGraph();}};
document.getElementById('fit').onclick=()=>{{scale=1; panX=0; panY=0; renderGraph();}};
search.oninput=renderGraph; filter.onchange=renderGraph;
renderList(); renderGraph();
</script>
</body>
</html>
"""


__all__ = [
    "append_payload",
    "build_function_graph_payload",
    "build_project_overview_payload",
    "configure_graph_output",
    "fallback_rows",
    "graph_enabled",
    "graph_max_nodes",
    "graph_output_from_cfg",
    "html_graph_enabled",
    "payload_has_edges",
    "render_payload_png",
    "word_graph_enabled",
    "write_html_report",
]
