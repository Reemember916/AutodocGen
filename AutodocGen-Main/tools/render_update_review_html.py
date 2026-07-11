#!/usr/bin/env python3
"""Render a static HTML review page for AutoDocGen update plans."""

from __future__ import annotations

import argparse
import html
import json
import os
from datetime import datetime
from typing import Any


def _json_for_script(data: Any) -> str:
    text = json.dumps(data, ensure_ascii=False)
    return text.replace("</", "<\\/")


def _html_shell(plan: dict[str, Any]) -> str:
    generated_at = html.escape(datetime.now().isoformat(timespec="seconds"))
    title = "AutoDocGen Update Review"
    plan_json = _json_for_script(plan)
    return f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{title}</title>
  <style>
    :root {{
      --bg: #f7f5ef;
      --panel: #ffffff;
      --ink: #24231f;
      --muted: #6c695f;
      --line: #ddd8ca;
      --accent: #6f745d;
      --safe: #276749;
      --review: #9a5b00;
      --manual: #8a3a3a;
      --applied: #245c8a;
      --failed: #9f1d1d;
      --code: #202124;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "Microsoft YaHei", sans-serif;
      background: var(--bg);
      color: var(--ink);
      font-size: 14px;
    }}
    header {{
      padding: 18px 24px 12px;
      border-bottom: 1px solid var(--line);
      background: rgba(255,255,255,.65);
      position: sticky;
      top: 0;
      z-index: 5;
      backdrop-filter: blur(8px);
    }}
    h1 {{ margin: 0 0 8px; font-size: 22px; font-weight: 650; }}
    .meta {{ color: var(--muted); display: flex; gap: 16px; flex-wrap: wrap; }}
    .wrap {{
      display: grid;
      grid-template-columns: minmax(320px, 38%) minmax(420px, 1fr);
      gap: 0;
      min-height: calc(100vh - 82px);
    }}
    aside {{
      border-right: 1px solid var(--line);
      padding: 16px;
      overflow: auto;
      max-height: calc(100vh - 82px);
    }}
    main {{
      padding: 18px 22px 28px;
      overflow: auto;
      max-height: calc(100vh - 82px);
    }}
    .controls {{
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 8px;
      margin-bottom: 12px;
    }}
    input, select, textarea, button {{
      font: inherit;
      border: 1px solid var(--line);
      border-radius: 6px;
      background: white;
      color: var(--ink);
    }}
    input, select {{ padding: 8px 9px; min-width: 0; }}
    input[type="file"] {{ display: none; }}
    textarea {{ width: 100%; min-height: 82px; padding: 8px; resize: vertical; }}
    button {{
      padding: 8px 10px;
      cursor: pointer;
      background: var(--accent);
      color: white;
      border-color: var(--accent);
    }}
    button.secondary {{ background: white; color: var(--ink); border-color: var(--line); }}
    .summary {{
      display: flex;
      gap: 8px;
      flex-wrap: wrap;
      margin: 10px 0 14px;
    }}
    .pill {{
      border: 1px solid var(--line);
      border-radius: 999px;
      padding: 4px 8px;
      background: white;
      color: var(--muted);
    }}
    .item {{
      padding: 10px 11px;
      border: 1px solid var(--line);
      background: var(--panel);
      border-radius: 8px;
      margin-bottom: 8px;
      cursor: pointer;
    }}
    .item.active {{ border-color: var(--accent); box-shadow: 0 0 0 2px rgba(111,116,93,.16); }}
    .item-title {{ display: flex; justify-content: space-between; gap: 8px; margin-bottom: 5px; }}
    .item-name {{ font-weight: 650; overflow-wrap: anywhere; }}
    .tag {{ font-size: 12px; padding: 2px 6px; border-radius: 999px; color: white; white-space: nowrap; }}
    .safe {{ background: var(--safe); }}
    .review {{ background: var(--review); }}
    .manual {{ background: var(--manual); }}
    .applied {{ background: var(--applied); }}
    .failed {{ background: var(--failed); }}
    .sub {{ color: var(--muted); font-size: 12px; overflow-wrap: anywhere; }}
    .section {{
      border-bottom: 1px solid var(--line);
      padding-bottom: 14px;
      margin-bottom: 16px;
    }}
    h2 {{ margin: 0 0 10px; font-size: 19px; }}
    h3 {{ margin: 14px 0 8px; font-size: 15px; }}
    dl {{ display: grid; grid-template-columns: 120px 1fr; gap: 6px 10px; }}
    dt {{ color: var(--muted); }}
    dd {{ margin: 0; overflow-wrap: anywhere; }}
    .codegrid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }}
    pre {{
      background: var(--code);
      color: #f3f0e8;
      padding: 12px;
      border-radius: 8px;
      overflow: auto;
      min-height: 120px;
      max-height: 360px;
      white-space: pre-wrap;
      font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
      font-size: 12px;
      line-height: 1.45;
    }}
    .decision-row {{ display: grid; grid-template-columns: 190px 1fr; gap: 10px; margin-bottom: 10px; }}
    .empty {{ color: var(--muted); padding: 40px 0; }}
    @media (max-width: 900px) {{
      .wrap {{ grid-template-columns: 1fr; }}
      aside, main {{ max-height: none; }}
      aside {{ border-right: 0; border-bottom: 1px solid var(--line); }}
      .codegrid {{ grid-template-columns: 1fr; }}
      .controls {{ grid-template-columns: 1fr; }}
    }}
  </style>
</head>
<body>
  <header>
    <h1>AutoDocGen Update Review</h1>
    <div class="meta">
      <span>generated: {generated_at}</span>
      <span id="countMeta"></span>
      <span id="sourceMeta"></span>
    </div>
  </header>
  <div class="wrap">
    <aside>
      <div class="controls">
        <select id="viewMode">
          <option value="changes">代码变更</option>
          <option value="alignment">CSU 映射</option>
        </select>
        <input id="search" placeholder="搜索函数/文件/原因">
        <select id="statusFilter"><option value="">全部状态</option></select>
        <select id="actionFilter"><option value="">全部类型</option></select>
        <button id="exportBtn">导出 decisions JSON</button>
        <button class="secondary" id="importBtn">导入 decisions JSON</button>
      </div>
      <input id="importFile" type="file" accept="application/json,.json">
      <div class="summary" id="summary"></div>
      <div id="list"></div>
    </aside>
    <main id="detail">
      <div class="empty">选择左侧条目开始审查。</div>
    </main>
  </div>
  <script id="planData" type="application/json">{plan_json}</script>
  <script>
    const plan = JSON.parse(document.getElementById('planData').textContent);
    const items = plan.items || [];
    const alignmentItems = plan.alignment_items || [];
    const decisions = {{}};
    const alignmentDecisions = {{}};
    let selected = 0;
    let selectedAlignment = 0;

    const el = (id) => document.getElementById(id);
    const esc = (s) => String(s ?? '').replace(/[&<>"']/g, c => ({{'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}}[c]));
    const label = (item) => item.func_name || item.rel_path || '(unnamed)';
    const alignmentLabel = (item) => item.doc_title || item.doc_func_name || item.csu_id || '(unnamed CSU)';
    const statusClass = (s) => ['safe','review','manual','applied','failed'].includes(s) ? s : (s === 'matched_high' ? 'safe' : (s === 'ambiguous' ? 'review' : 'manual'));
    const storageKey = `autodoc-review:${{plan.metadata?.old_doc || ''}}:${{plan.metadata?.new_code || ''}}:${{items.length}}`;
    const alignmentStorageKey = `${{storageKey}}:alignment`;

    function unique(values) {{
      return [...new Set(values.filter(Boolean))].sort();
    }}

    function joinList(values) {{
      if (!Array.isArray(values)) return esc(values || '');
      return esc(unique(values.map(x => String(x || '').trim())).join(', '));
    }}

    function initFilters() {{
      const mode = el('viewMode').value;
      const statusValues = mode === 'alignment' ? unique(alignmentItems.map(x => x.status)) : unique(items.map(x => x.status));
      const actionValues = mode === 'alignment' ? ['alignment'] : unique(items.map(x => x.action));
      el('statusFilter').innerHTML = '<option value="">全部状态</option>' + statusValues.map(s => `<option value="${{esc(s)}}">${{esc(s)}}</option>`).join('');
      el('actionFilter').innerHTML = '<option value="">全部类型</option>' + actionValues.map(a => `<option value="${{esc(a)}}">${{esc(a)}}</option>`).join('');
      const meta = plan.metadata || {{}};
      el('countMeta').textContent = mode === 'alignment' ? `${{alignmentItems.length}} CSU mappings` : `${{items.length}} items`;
      el('sourceMeta').textContent = meta.new_code ? `new: ${{meta.new_code}}` : '';
    }}

    function renderSummary() {{
      const counts = {{}};
      if (el('viewMode').value === 'alignment') {{
        for (const item of alignmentItems) counts[item.status] = (counts[item.status] || 0) + 1;
      }} else {{
        for (const item of items) counts[item.status] = (counts[item.status] || 0) + 1;
      }}
      el('summary').innerHTML = Object.entries(counts)
        .sort((a,b) => a[0].localeCompare(b[0]))
        .map(([k,v]) => `<span class="pill">${{esc(k)}}: ${{v}}</span>`)
        .join('');
    }}

    function filteredItems() {{
      const q = el('search').value.trim().toLowerCase();
      const status = el('statusFilter').value;
      const action = el('actionFilter').value;
      if (el('viewMode').value === 'alignment') {{
        return alignmentItems.map((item, index) => ({{item, index}})).filter(({{item}}) => {{
          if (status && item.status !== status) return false;
          if (action && action !== 'alignment') return false;
          if (!q) return true;
          const ev = item.evidence || {{}};
          return [item.status, item.csu_id, item.doc_title, item.doc_func_name, item.doc_prototype,
            item.matched_function, item.rel_path, item.signature, ev.prototype, ev.candidate_count]
            .some(v => String(v || '').toLowerCase().includes(q));
        }});
      }}
      return items.map((item, index) => ({{item, index}})).filter(({{item}}) => {{
        if (status && item.status !== status) return false;
        if (action && item.action !== action) return false;
        if (!q) return true;
        const al = item.alignment || {{}};
        return [item.action, item.status, item.rel_path, item.func_name, item.csu_id, item.reason,
          al.status, al.matched_function, al.rel_path, al.doc_title]
          .some(v => String(v || '').toLowerCase().includes(q));
      }});
    }}

    function renderList() {{
      const rows = filteredItems();
      if (el('viewMode').value === 'alignment') {{
        el('list').innerHTML = rows.map(({{item, index}}) => `
          <div class="item ${{index === selectedAlignment ? 'active' : ''}}" onclick="selectAlignment(${{index}})">
            <div class="item-title">
              <div class="item-name">${{esc(alignmentLabel(item))}}</div>
              <span class="tag ${{statusClass(item.status)}}">${{esc(item.status)}}</span>
            </div>
            <div class="sub">${{esc(item.csu_id)}} · ${{esc(item.doc_func_name || '')}}</div>
            <div class="sub">${{esc(item.rel_path || item.evidence?.function_name || '')}}</div>
          </div>`).join('') || '<div class="empty">无匹配 CSU。</div>';
        return;
      }}
      el('list').innerHTML = rows.map(({{item, index}}) => `
        <div class="item ${{index === selected ? 'active' : ''}}" onclick="selectItem(${{index}})">
          <div class="item-title">
            <div class="item-name">${{esc(label(item))}}</div>
            <span class="tag ${{statusClass(item.status)}}">${{esc(item.status)}}</span>
          </div>
          <div class="sub">${{esc(item.action)}} · ${{esc(item.rel_path)}}</div>
          <div class="sub">${{esc(item.reason || item.csu_id || '')}}</div>
        </div>`).join('') || '<div class="empty">无匹配条目。</div>';
    }}

    window.selectItem = function(index) {{
      selected = index;
      renderList();
      renderDetail();
    }}

    window.selectAlignment = function(index) {{
      selectedAlignment = index;
      renderList();
      renderAlignmentDetail();
    }}

    function currentDecision(index) {{
      return decisions[index] || {{decision: '', target_csu_id: '', insert_after_csu_id: '', notes: ''}};
    }}

    function persistDecisions() {{
      try {{
        localStorage.setItem(storageKey, JSON.stringify(decisions));
        localStorage.setItem(alignmentStorageKey, JSON.stringify(alignmentDecisions));
      }} catch (err) {{}}
    }}

    function loadPersistedDecisions() {{
      try {{
        const raw = localStorage.getItem(storageKey);
        if (raw) {{
          const saved = JSON.parse(raw);
          if (saved && typeof saved === 'object' && !Array.isArray(saved)) {{
            for (const [key, value] of Object.entries(saved)) {{
              const index = Number(key);
              if (!Number.isInteger(index) || index < 0 || index >= items.length) continue;
              if (value && typeof value === 'object') decisions[index] = value;
            }}
          }}
        }}
        const rawAlignment = localStorage.getItem(alignmentStorageKey);
        if (rawAlignment) {{
          const savedAlignment = JSON.parse(rawAlignment);
          if (savedAlignment && typeof savedAlignment === 'object' && !Array.isArray(savedAlignment)) {{
            for (const [key, value] of Object.entries(savedAlignment)) {{
              const index = Number(key);
              if (!Number.isInteger(index) || index < 0 || index >= alignmentItems.length) continue;
              if (value && typeof value === 'object') alignmentDecisions[index] = value;
            }}
          }}
        }}
      }} catch (err) {{}}
    }}

    function importDecisionPayload(payload) {{
      const incoming = Array.isArray(payload) ? payload : (payload?.decisions || []);
      let count = 0;
      if (Array.isArray(incoming)) {{
        for (const dec of incoming) {{
          if (!dec || typeof dec !== 'object') continue;
          const index = Number(dec.item_index);
          if (!Number.isInteger(index) || index < 0 || index >= items.length) continue;
          decisions[index] = {{...dec}};
          count += 1;
        }}
      }}
      const incomingAlignment = payload?.alignment_decisions || [];
      if (Array.isArray(incomingAlignment)) {{
        for (const dec of incomingAlignment) {{
          if (!dec || typeof dec !== 'object') continue;
          const index = Number(dec.alignment_index);
          if (!Number.isInteger(index) || index < 0 || index >= alignmentItems.length) continue;
          alignmentDecisions[index] = {{...dec}};
          count += 1;
        }}
      }}
      persistDecisions();
      renderList();
      if (el('viewMode').value === 'alignment') renderAlignmentDetail(); else renderDetail();
      return count;
    }}

    function setDecisionField(index, key, value) {{
      decisions[index] = currentDecision(index);
      decisions[index][key] = value;
      decisions[index].item_index = index;
      decisions[index].action = items[index]?.action || '';
      decisions[index].func_name = items[index]?.func_name || '';
      decisions[index].rel_path = items[index]?.rel_path || '';
      decisions[index].csu_id = items[index]?.csu_id || '';
      persistDecisions();
    }}

    function currentAlignmentDecision(index) {{
      return alignmentDecisions[index] || {{manual_function: '', manual_rel_path: '', notes: ''}};
    }}

    function setAlignmentDecisionField(index, key, value) {{
      const item = alignmentItems[index] || {{}};
      alignmentDecisions[index] = currentAlignmentDecision(index);
      alignmentDecisions[index][key] = value;
      alignmentDecisions[index].alignment_index = index;
      alignmentDecisions[index].csu_id = item.csu_id || '';
      alignmentDecisions[index].doc_title = item.doc_title || '';
      alignmentDecisions[index].doc_func_name = item.doc_func_name || '';
      alignmentDecisions[index].status = item.status || '';
      persistDecisions();
    }}

    function renderDetail() {{
      const item = items[selected];
      if (!item) {{
        el('detail').innerHTML = '<div class="empty">选择左侧条目开始审查。</div>';
        return;
      }}
      const ch = item.change || {{}};
      const al = item.alignment || {{}};
      const ev = al.evidence || {{}};
      const dec = currentDecision(selected);
      el('detail').innerHTML = `
        <div class="section">
          <h2>${{esc(label(item))}}</h2>
          <dl>
            <dt>status</dt><dd><span class="tag ${{statusClass(item.status)}}">${{esc(item.status)}}</span></dd>
            <dt>action</dt><dd>${{esc(item.action)}}</dd>
            <dt>file</dt><dd>${{esc(item.rel_path)}}</dd>
            <dt>function</dt><dd>${{esc(item.func_name)}}</dd>
            <dt>csu_id</dt><dd>${{esc(item.csu_id)}}</dd>
            <dt>reason</dt><dd>${{esc(item.reason)}}</dd>
            <dt>old signature</dt><dd>${{esc(ch.old_signature || '')}}</dd>
            <dt>new signature</dt><dd>${{esc(ch.new_signature || ch.seg || '')}}</dd>
            <dt>changed headers</dt><dd>${{joinList(ch.impacted_by_headers || ch.header_file || '')}}</dd>
            <dt>matched headers</dt><dd>${{joinList(ch.impacted_headers || ch.matched_header_file || '')}}</dd>
          </dl>
        </div>
        <div class="section">
          <h3>Doc-Code Alignment</h3>
          <dl>
            <dt>status</dt><dd>${{esc(al.status || '')}}</dd>
            <dt>confidence</dt><dd>${{esc(al.confidence ?? '')}}</dd>
            <dt>doc title</dt><dd>${{esc(al.doc_title || '')}}</dd>
            <dt>doc function</dt><dd>${{esc(al.doc_func_name || '')}}</dd>
            <dt>matched code</dt><dd>${{esc(al.matched_function || '')}}</dd>
            <dt>code file</dt><dd>${{esc(al.rel_path || '')}}</dd>
            <dt>prototype</dt><dd>${{esc(ev.prototype || '')}}</dd>
            <dt>candidate count</dt><dd>${{esc(ev.candidate_count ?? '')}}</dd>
          </dl>
        </div>
        <div class="section">
          <h3>Decision</h3>
          <div class="decision-row">
            <select id="decisionSelect">
              <option value="">未选择</option>
              <option value="skip">跳过</option>
              <option value="manual">人工处理</option>
              <option value="replace_csu">替换 CSU</option>
              <option value="insert_after_csu">插入到 CSU 后</option>
              <option value="delete_csu">删除 CSU</option>
            </select>
            <input id="targetCsu" placeholder="目标 CSU ID（插入时可留空）" value="${{esc(dec.target_csu_id || item.csu_id || '')}}">
          </div>
          <div class="decision-row">
            <input id="insertAfter" placeholder="插入到哪个 CSU 后" value="${{esc(dec.insert_after_csu_id || '')}}">
            <button class="secondary" id="saveDecision">保存当前决策</button>
          </div>
          <textarea id="notes" placeholder="备注">${{esc(dec.notes || '')}}</textarea>
        </div>
        <div class="section">
          <h3>Code Diff</h3>
          <div class="codegrid">
            <div><div class="sub">更改前</div><pre>${{esc(ch.old_text || '')}}</pre></div>
            <div><div class="sub">更改后</div><pre>${{esc(ch.new_text || '')}}</pre></div>
          </div>
        </div>
      `;
      el('decisionSelect').value = dec.decision || '';
      el('decisionSelect').onchange = (e) => setDecisionField(selected, 'decision', e.target.value);
      el('targetCsu').oninput = (e) => setDecisionField(selected, 'target_csu_id', e.target.value);
      el('insertAfter').oninput = (e) => setDecisionField(selected, 'insert_after_csu_id', e.target.value);
      el('notes').oninput = (e) => setDecisionField(selected, 'notes', e.target.value);
      el('saveDecision').onclick = () => {{
        setDecisionField(selected, 'decision', el('decisionSelect').value);
        setDecisionField(selected, 'target_csu_id', el('targetCsu').value);
        setDecisionField(selected, 'insert_after_csu_id', el('insertAfter').value);
        setDecisionField(selected, 'notes', el('notes').value);
        renderList();
      }};
    }}

    function renderAlignmentDetail() {{
      const item = alignmentItems[selectedAlignment];
      if (!item) {{
        el('detail').innerHTML = '<div class="empty">选择左侧 CSU 映射开始审查。</div>';
        return;
      }}
      const ev = item.evidence || {{}};
      const dec = currentAlignmentDecision(selectedAlignment);
      const needsHuman = !['matched_high'].includes(item.status || '');
      const judgmentText = item.status === 'manual_matched'
        ? '人工映射已应用。后续 update_plan / apply-review 会按这个函数与 CSU 对应关系处理。'
        : (needsHuman ? '这个旧文档 CSU 到底对应哪个代码函数；确认后在下面填写函数名和文件。' : '工具已高置信匹配。通常只需抽查函数名、原型和文件是否合理。');
      el('detail').innerHTML = `
        <div class="section">
          <h2>${{esc(alignmentLabel(item))}}</h2>
          <dl>
            <dt>判断结论</dt><dd><span class="tag ${{statusClass(item.status)}}">${{esc(item.status || '')}}</span></dd>
            <dt>你要判断</dt><dd>${{esc(judgmentText)}}</dd>
            <dt>CSU ID</dt><dd>${{esc(item.csu_id || '')}}</dd>
            <dt>文档标题</dt><dd>${{esc(item.doc_title || '')}}</dd>
            <dt>文档函数</dt><dd>${{esc(item.doc_func_name || '')}}</dd>
            <dt>文档原型</dt><dd>${{esc(item.doc_prototype || '')}}</dd>
            <dt>匹配函数</dt><dd>${{esc(item.matched_function || '')}}</dd>
            <dt>代码文件</dt><dd>${{esc(item.rel_path || '')}}</dd>
            <dt>代码原型</dt><dd>${{esc(item.signature || '')}}</dd>
            <dt>置信度</dt><dd>${{esc(item.confidence ?? '')}}</dd>
            <dt>证据</dt><dd>${{esc(JSON.stringify(ev))}}</dd>
          </dl>
        </div>
        <div class="section">
          <h3>人工映射</h3>
          <div class="decision-row">
            <input id="manualFunction" placeholder="确认对应的代码函数名" value="${{esc(dec.manual_function || item.matched_function || item.doc_func_name || '')}}">
            <input id="manualRelPath" placeholder="确认对应的代码文件路径" value="${{esc(dec.manual_rel_path || item.rel_path || '')}}">
          </div>
          <textarea id="alignmentNotes" placeholder="备注：为什么这样映射 / 为什么不映射">${{esc(dec.notes || '')}}</textarea>
          <div class="decision-row">
            <button class="secondary" id="saveAlignment">保存映射判断</button>
            <button class="secondary" id="markNoMatch">标记为无对应函数</button>
          </div>
        </div>
      `;
      el('manualFunction').oninput = (e) => setAlignmentDecisionField(selectedAlignment, 'manual_function', e.target.value);
      el('manualRelPath').oninput = (e) => setAlignmentDecisionField(selectedAlignment, 'manual_rel_path', e.target.value);
      el('alignmentNotes').oninput = (e) => setAlignmentDecisionField(selectedAlignment, 'notes', e.target.value);
      el('saveAlignment').onclick = () => {{
        setAlignmentDecisionField(selectedAlignment, 'manual_function', el('manualFunction').value);
        setAlignmentDecisionField(selectedAlignment, 'manual_rel_path', el('manualRelPath').value);
        setAlignmentDecisionField(selectedAlignment, 'notes', el('alignmentNotes').value);
        renderList();
      }};
      el('markNoMatch').onclick = () => {{
        setAlignmentDecisionField(selectedAlignment, 'manual_function', '');
        setAlignmentDecisionField(selectedAlignment, 'manual_rel_path', '');
        setAlignmentDecisionField(selectedAlignment, 'notes', '人工确认：无对应代码函数');
        renderAlignmentDetail();
        renderList();
      }};
    }}

    function exportDecisions() {{
      const payload = {{
        schema_version: 1,
        generated_at: new Date().toISOString(),
        source_plan: plan.metadata || {{}},
        decisions: Object.values(decisions).filter(x => x.decision || x.notes || x.target_csu_id || x.insert_after_csu_id),
        alignment_decisions: Object.values(alignmentDecisions).filter(x => x.manual_function || x.manual_rel_path || x.notes)
      }};
      const blob = new Blob([JSON.stringify(payload, null, 2)], {{type: 'application/json'}});
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = 'review_decisions.json';
      a.click();
      URL.revokeObjectURL(url);
    }}

    function importDecisionsFromFile(file) {{
      if (!file) return;
      const reader = new FileReader();
      reader.onload = () => {{
        try {{
          importDecisionPayload(JSON.parse(String(reader.result || '')));
        }} catch (err) {{
          alert('无法导入 JSON：' + err.message);
        }}
      }};
      reader.readAsText(file, 'utf-8');
    }}

    function renderAll() {{
      initFilters();
      renderSummary();
      renderList();
      if (el('viewMode').value === 'alignment') renderAlignmentDetail(); else renderDetail();
    }}

    el('viewMode').onchange = () => {{
      el('statusFilter').value = '';
      el('actionFilter').value = '';
      renderAll();
    }};
    for (const id of ['search','statusFilter','actionFilter']) {{
      el(id).addEventListener('input', renderList);
      el(id).addEventListener('change', renderList);
    }}
    el('exportBtn').onclick = exportDecisions;
    el('importBtn').onclick = () => el('importFile').click();
    el('importFile').onchange = (e) => importDecisionsFromFile(e.target.files?.[0]);
    loadPersistedDecisions();
    renderAll();
  </script>
</body>
</html>
"""


def render_review_html(plan: dict[str, Any], output_path: str) -> str:
    output_path = os.path.abspath(os.path.expanduser(output_path))
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(_html_shell(plan))
    return output_path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("plan_json")
    parser.add_argument("-o", "--output", required=True)
    args = parser.parse_args()

    with open(args.plan_json, "r", encoding="utf-8") as f:
        plan = json.load(f)
    out = render_review_html(plan, args.output)
    print(out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
