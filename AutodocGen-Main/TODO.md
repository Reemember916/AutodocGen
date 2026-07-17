# AutoDocGen 待优化清单

> 最后更新: 2026-07-17

---

## 当前阶段建议

1. **审查闭环收尾**（进行中 / 本轮）
2. **生产可验证基线**：固定 Python 环境 + 全量 pytest + 3 条 E2E
3. **AST-backed Expression IR**
4. Win7 部署链路

---

## P0 — 下一阶段

### 1. AST-backed Expression IR 升级

- **文件**: `autodoc/c_expr.py`，新增 Tree-sitter expression adapter
- **现状**: 已有轻量 `ExprIR`，能处理 `x & 0xFFU`、低 8 位补码校验和、数组下标、成员访问；尚非 Tree-sitter 主导
- **目标**: `Tree-sitter expression node -> ExprIR` 成为优先路径，现有字符串 parser 退为 fallback
- **验收**: 低 8 位和 checksum 回归全部通过；raw/fallback 不混入半成品中文

### 2. 生产可验证基线

- 固定开发环境（目标 Python 3.8.20 + 当前开发版本）
- 全量 pytest 全绿
- 固化 3 条端到端：
  - C → DOCX → Review → 决策回写
  - Markdown → C 骨架
  - 改 C → 差异计划 → 更新文档
- AI 测试与离线单测分离

---

## P1 — 重要优化

### 3. Tree-sitter 预处理替代正则

- **文件**: `autodoc/parse.py` + `autodoc/callgraph.py` + `autodoc/struct_tree.py`
- **方案**: shadow mode 先行，逐步替换 find_function_prototypes / extract_function_body / comment 提取等

### 4. Win7 部署链路重建

- **文件**: `tools/tree-sitter/`（新建），`tools/clangd/win7/llvm/`（恢复）
- **方案**: 提供 clangd.exe 绿色包 + tree_sitter_c.dll 预编译二进制

### 5. GUI “重试失败函数”真实实现

- **文件**: `qt_gui/main_window.py`
- **现状**: 目前仅提示用户重新生成
- **目标**: 真正重建并执行失败函数任务

---

## P2 — 改进

### 6. 按文件批量查询 hover/typeDef

- **文件**: `autodoc/lsp_gateway.py`
- **预期收益**: LSP 请求减少 50%~70%

### 7. LSP 数据质量评估与选择性降级

- **文件**: `autodoc/lsp_facts.py`

### 8. compile_commands.json 转换脚本

- **文件**: 新增 `tools/convert_ccs_to_compile_commands.py`

---

## P3 — 增强

### 9. hover 信息结构化解析

### 10. references 增强读写分析

### 11. 编译环境自动检测

---

## 已完成

| # | 描述 | 完成日期 |
|---|------|----------|
| 1-16 | 早期里程碑（clangd / 生产缺陷 / AI API / Tree-sitter 等） | 2026-05~06 |
| 17 | Semantic Elements 确定性架构 | 2026-07-12 |
| 18 | Evidence Model Shadow Mode | 2026-07-12 |
| 19 | Clang Evidence Provider | 2026-07-12 |
| 20 | LogicStep IR | 2026-07-12 |
| 21 | 前向代码生成流水线 (extractor → generator → merger) | 2026-07-12 |
| 22 | mini_project 测试工程 | 2026-07-12 |
| 23 | ARCHITECTURE.md | 2026-07-12 |
| 24 | 参数注释 [业务含义] 显式字段输出 | 2026-07-12 |
| 25 | 静态 AST Facts 提取器 (CAsTExtractor) | 2026-07-12 |
| 26 | Markdown 靶向更新器 (MarkdownPatcher) | 2026-07-12 |
| 27 | 反向同步流水线 (run_backward_pipeline.py) | 2026-07-12 |
| 28 | 双向 IR 语义差分判决器 (BiDirectionalResolver) | 2026-07-12 |
| 29 | 可视化评审面板 v2 (三栏布局 + 通用 Qt 导入) | 2026-07-12 |
| 30 | 信号槽修复 + pipeline_hub 总控总线 | 2026-07-12 |
| 31 | pipeline_hub 升级为真实流水线写回 | 2026-07-12 |
| 32 | 生产环境总装脚本 (production_round_trip.py) | 2026-07-12 |
| 33 | GUI 布局自适应 (QScrollArea + 弹性分割器) | 2026-07-12 |
| 34 | CAsTExtractor (void) 参数误识别修复 | 2026-07-12 |
| 35 | GUI 前向生成入口集成 | 2026-07-12 |
| 36 | 交互式审查闭环（generation_review_decisions → revision_profile → 回写 DOCX） | 2026-07-17 |
| 37 | 审查决策命名拆分：generation vs update | 2026-07-17 |
