# AutoDocGen 待优化清单

> 最后更新: 2026-07-12

---

## P0 — 下一阶段

### 1. AST-backed Expression IR 升级

- **文件**: `autodoc/c_expr.py`，新增 Tree-sitter expression adapter
- **现状**: 已有轻量 `ExprIR`，能处理 `x & 0xFFU`、低 8 位补码校验和、数组下标、成员访问；尚非 Tree-sitter 主导
- **目标**: `Tree-sitter expression node -> ExprIR` 成为优先路径，现有字符串 parser 退为 fallback；Expression IR 只服务语义元素推断，不直接拼接半成品中文
- **范围**:
  - identifier / literal / call
  - subscript / field / pointer field
  - unary / binary / cast / parenthesized
  - shift / bitwise / comparison / logical
- **验收**:
  - 现有低 8 位和 checksum 回归全部通过
  - raw/fallback 表达式不混入半成品中文
  - 失败时仅该表达式降级

### 2. 前向流水线集成到 GUI

- **文件**: `qt_gui/main_window.py` + `autodoc/forward/`
- **现状**: `tools/run_forward_pipeline.py` 独立可用，但 GUI 未集成
- **目标**: GUI 主页增加"前向生成"选项卡，支持 Markdown 输入 → C 骨架输出
- **验收**: 一键选取 .md 文件，输出 .c/.h 骨架

### 3. GUI 布局自适应

- **文件**: `qt_gui/main_window.py` + `qt_gui/assets/app.qss`
- **现状**: 布局依赖固定分割器尺寸，低分辨率屏幕溢出
- **目标**: 使用 QSplitter 弹性比例 + 最小尺寸约束，确保 1024×768 以上完整显示
- **验收**: 窗口缩放到 1024×768 无元素溢出/截断

---

## P1 — 重要优化

### 4. Tree-sitter 预处理替代正则

- **文件**: `autodoc/parse.py` + `autodoc/callgraph.py` + `autodoc/struct_tree.py`
- **现状**: 已有 tree-sitter 函数解析旁路交叉校验、调用图、struct 成员注入；函数/注释/声明主路径仍保留 regex/规则实现
- **方案**（分步）:
  1. 保持 tree-sitter cross-check 旁路，扩大差异报告覆盖
  2. 在 Evidence Model 中使用 Tree-sitter 函数/声明/注释节点作为结构证据
  3. 稳定后逐步替换：
     - `find_function_prototypes` → `function_definition` + `function_declarator`
     - `extract_function_body` → `compound_statement` 精确范围
     - `_find_all_comment_blocks` → `comment` 节点紧邻前驱
     - `extract_nearby_macros` → `preproc_def`
     - `extract_nearby_typedefs` → `struct_specifier` + `type_definition`
     - include 解析 → `preproc_include`
  4. 旧 regex 路径保留为 fallback，直到 PROJECT + 全量回归稳定
- **预期收益**: 解析精度提升，减少半翻译宏、漏成员、错匹注释、声明误判
- **注意**: 不一次性替换主流程；必须 shadow mode 先行

### 5. Win7 部署链路重建

- **文件**: `tools/tree-sitter/`（新建），`tools/clangd/win7/llvm/`（恢复）
- **现状**: clangd + tree-sitter 均在 macOS 可工作，Win7 工程机无外网无预编译包
- **方案**：
  - clangd: 提供 `clangd.exe` + DLL 的最小绿色包（~80 MB）放 `tools/clangd/win7/llvm/bin/`
  - tree-sitter: 在有外网的 Win10 上 `cargo build --release` 编译 `tree_sitter_c.dll`（~1 MB）放 `tools/tree-sitter/`
- **改动量**: 0 行代码（已有 `shutil.which` fallback + `try: import tree_sitter_c` 兜底）
- **二进制**: clangd ~80 MB + tree-sitter ~1 MB

---

## P2 — 改进

### 6. 按文件批量查询 hover/typeDef

- **文件**: `autodoc/lsp_gateway.py`
- **现状**: 逐个成员/变量串行请求，N 个成员 = 2N 次 LSP 请求
- **方案**: 正则收集位置 → 批量请求 → 复用结果
- **预期收益**: LSP 请求减少 50%~70%

### 7. LSP 数据质量评估与选择性降级

- **文件**: `autodoc/lsp_facts.py`
- **方案**: `_assess_lsp_quality()` 评估 0~1，低质量时比较 fallback 取较好
- **改动量**: ~60 行

### 8. compile_commands.json 转换脚本

- **文件**: 新增 `tools/convert_ccs_to_compile_commands.py`
- **方案**: 解析 `.cproject` XML → include paths + defines → 标准 compile_commands.json
- **适用**: TI CCS 项目无标准编译数据库

---

## P3 — 增强

### 9. hover 信息结构化解析

- **文件**: `autodoc/lsp_gateway.py`
- **方案**: 解析 hover detail 完整内容，提取 `return_type`、params 类型列表、doc_comment
- **预期收益**: AI prompt 获得更完整类型信息

### 10. references 增强读写分析

- **文件**: `autodoc/lsp_adapter.py`
- **方案**: 利用 references 判断变量读/写频率，提升 fact confidence

### 11. 编译环境自动检测

- **文件**: `qt_gui/main_window.py`
- **方案**: 加载工程后检测 compile_commands.json / .cproject / Makefile，提示用户

---

## 已完成

| # | 描述 | 完成日期 |
|---|------|----------|
| 1 | clangd 崩溃自动重连 | 2026-05-26 |
| 2 | 降级日志标记 | 2026-05-26 |
| 3 | `sys` NameError 修复 | 2026-05-27 |
| 4 | clangd `--malloc-trim` flag 探测 | 2026-05-27 |
| 5 | 中文名重复叠加 + CSU 截断 + IFBIT fallback | 2026-06-01 |
| 6 | 成员链重复 (`状态字×3`) | 2026-06-01 |
| 7 | type cast 残留 (`(Uint16)(expr)`) | 2026-06-01 |
| 8 | failures.json 28MB → 7KB | 2026-06-01 |
| 9 | AI Responses API 支持 (new.sharedchat.cc) | 2026-06-01 |
| 10 | Tree-sitter 调用图 + struct 成员注入 | 2026-06-01 |
| 11 | `ai_profile=large_model` + `structured_cond_ai=1` | 2026-06-01 |
| 12 | CJK dedup 覆盖单字符 (`将将` / `有效有效`) | 2026-06-01 |
| 13 | GUI 增量模式接入 + `GenConfig.incremental` 透传 | 2026-06-01 |
| 14 | Tree-sitter 函数解析旁路交叉校验 | 2026-06-01 |
| 15 | LSP 路径编码兼容 (`file:///C:/...`、UNC、空格/中文路径) | 2026-06-07 |
| 16 | PROJECT source-understanding 生产缺陷修复 | 2026-06-22 |
| 17 | **Semantic Elements 确定性架构** — `semantic_elements.py`, `semantic_registry.py`, `semantic_pack.py` | 2026-07-12 |
| 18 | **Evidence Model Shadow Mode** — `autodoc/evidence/` 旁路采集 + quality summary | 2026-07-12 |
| 19 | **Clang Evidence Provider** — `clang_provider.py` typedef pointer / type facts | 2026-07-12 |
| 20 | **LogicStep IR** — `autodoc/logic_ir.py` 结构化步骤 IR | 2026-07-12 |
| 21 | **前向代码生成流水线** — `autodoc/forward/` extractor → generator → merger | 2026-07-12 |
| 22 | **mini_project 测试工程** — 4 C 文件 / 8 函数 / 0.8s 生成 | 2026-07-12 |
| 23 | **ARCHITECTURE.md** — 架构总览文档 | 2026-07-12 |