# AutoDocGen 待优化清单

> 最后更新: 2026-06-22

---

## P0 — 下一阶段：Semantic Elements / Evidence / AST 迁移主线

### 1. Semantic Element Inference + Deterministic GJB Renderer

- **文件**: 新增 `autodoc/semantic_elements.py`，后续接入 `autodoc/c_expr.py` / `autodoc/logic.py`
- **目标**: AI 不直接生成最终文档句子；AI/规则/注释/AST 只生成受限语义元素，最终逻辑文本由确定性 GJB 风格 renderer 输出
- **文档风格原则**:
  - 处理逻辑保留 `IF` / `ELSE IF` / `ELSE` / `FOR` / `WHILE` / `SWITCH` / `CASE` / `RETURN` / `BREAK` / `NEXT` / `END IF` 等控制骨架
  - 条件和动作使用短语，不默认改写成长自然段
  - 逻辑行不做跨语句意图归纳；归纳只允许出现在功能说明/概要段
  - AI 只能补 `label` / `role` / `relation` / `action` 等结构化字段，不得直接返回最终逻辑句
- **初始语义元素**:
  - `SemanticElement`
  - `ConditionSemantic`
  - `ActionSemantic`
  - `ReturnSemantic`
- **首个垂直切片**: IF 条件语义元素
  - 输入：`RS422_COMM_FRAME_HEAD_1 == (buf[i] & 0xFFU)`
  - 语义：`left_label=报文头低8位`, `relation=equals`, `right_label=RS422帧头1`
  - 输出：`IF 报文头低8位等于RS422帧头1时`
- **验收**:
  - 不开启 AI 时，规则能生成结构化短句
  - 开启 AI 时，AI 只生成 schema 允许的语义字段，不直接生成最终句子
  - AI 输出不符合 schema 时丢弃并 fallback
  - `Comm422FrameCheck` 的帧头/低8位条件不退化

### 2. Evidence Model Shadow Mode

- **文件**: 新增 `autodoc/evidence/`，接入 `autodoc/pipeline.py` 旁路输出
- **现状**: 已完成 PROJECT 生产缺陷修复：注释规范化、低 8 位/补码表达式、变量绑定、空 ELSE 清理、ii/jj 保留；但输出仍主要由 `logic.py` 字符串/规则路径生成
- **目标**: 不改变 docx 输出，旁路生成机器可用 evidence；人工审查层默认只显示质量摘要，不暴露 AST/IR/clang 细节
- **建议数据结构**:
  - `SourceRange`
  - `FunctionEvidence`
  - `CommentEvidence`
  - `VariableEvidence`
  - `ExpressionEvidence`
  - `LogicStepEvidence`
  - `RenderedLineEvidence`
- **验收**:
  - `TimeCountInit`、`FdataAverage`、`Comm422FrameCheck` 均能生成 evidence-backed quality summary
  - 不改变现有 docx 输出
  - 全量 pytest 通过

### 3. Clang Evidence Provider Shadow Mode

- **文件**: 新增 `autodoc/clang_evidence.py` 或 `autodoc/evidence/clang_provider.py`；复用现有 `compile_commands.json`、`tools/convert_ccs_to_compile_commands.py`、LSP/clangd 基础
- **现状**: 已有 compile-db/clangd/LSP 相关基础，但 clang 尚未作为权威语义源接入；当前主流程仍是 Tree-sitter + regex/rules + 局部 LSP facts
- **目标**: clang/clangd 先只产出旁路 facts，不影响生成
- **采集内容**:
  - compile command health
  - diagnostics
  - symbol/type facts
  - typedef pointer/type info
  - definition/reference availability
- **验收**:
  - clang 不可用时自动降级，不影响生成
  - clang 可用时输出 facts 和质量评分
  - 能解释/覆盖 `FooState* state` 这类 typedef pointer 场景，减少启发式依赖

### 4. AST-backed Expression IR 升级

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

### 5. LogicStep IR Shadow Mode

- **文件**: 新增 `autodoc/logic_ir.py`，旁路接入 `logic.generate_logic_from_body()`
- **目标**: 先不替换渲染，只为每个函数体构建结构化步骤；后续由 `LogicStep + SemanticElement` 交给确定性 renderer 输出 GJB 风格短句
- **初始 Step**:
  - `IfStep`, `ElseIfStep`, `ElseStep`
  - `ForStep`, `WhileStep`, `DoWhileStep`
  - `SwitchStep`, `CaseStep`, `DefaultStep`
  - `AssignmentStep`, `CallStep`, `ReturnStep`, `BreakStep`
- **每个 Step 必须保留**:
  - source range / line
  - attached comments
  - expression IR
  - scope depth
  - confidence / fallback reason
- **验收**:
  - 三个 PROJECT 样例能建立完整 LogicStep 序列
  - 空 ELSE、loop reset、default init 能被结构化标记
  - 旧生成路径输出不变

## P1 — 重要优化

### 5. Tree-sitter 预处理替代正则

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

### 6. Win7 部署链路重建

- **文件**: `tools/tree-sitter/`（新建），`tools/clangd/win7/llvm/`（恢复）
- **现状**: clangd + tree-sitter 均在 macOS 可工作，Win7 工程机无外网无预编译包
- **方案**：
  - clangd: 提供 `clangd.exe` + DLL 的最小绿色包（~80 MB）放 `tools/clangd/win7/llvm/bin/`
  - tree-sitter: 在有外网的 Win10 上 `cargo build --release` 编译 `tree_sitter_c.dll`（~1 MB）放 `tools/tree-sitter/`
- **改动量**: 0 行代码（已有 `shutil.which` fallback + `try: import tree_sitter_c` 兜底）
- **二进制**: clangd ~80 MB + tree-sitter ~1 MB

## P2 — 改进

### 7. 按文件批量查询 hover/typeDef

- **文件**: `autodoc/lsp_gateway.py`
- **现状**: 逐个成员/变量串行请求，N 个成员 = 2N 次 LSP 请求
- **方案**: 正则收集位置 → 批量请求 → 复用结果
- **预期收益**: LSP 请求减少 50%~70%

### 8. LSP 数据质量评估与选择性降级

- **文件**: `autodoc/lsp_facts.py`
- **方案**: `_assess_lsp_quality()` 评估 0~1，低质量时比较 fallback 取较好
- **改动量**: ~60 行

### 9. compile_commands.json 转换脚本

- **文件**: 新增 `tools/convert_ccs_to_compile_commands.py`
- **方案**: 解析 `.cproject` XML → include paths + defines → 标准 compile_commands.json
- **适用**: TI CCS 项目无标准编译数据库

---

## P3 — 增强

### 10. hover 信息结构化解析

- **文件**: `autodoc/lsp_gateway.py`
- **方案**: 解析 hover detail 完整内容，提取 `return_type`、params 类型列表、doc_comment
- **预期收益**: AI prompt 获得更完整类型信息

### 11. references 增强读写分析

- **文件**: `autodoc/lsp_adapter.py`
- **方案**: 利用 references 判断变量读/写频率，提升 fact confidence

### 12. 编译环境自动检测

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
| 13 | GUI 增量模式接入 + `GenConfig.incremental` 透传 (`2e17899`) | 2026-06-01 |
| 14 | Tree-sitter 函数解析旁路交叉校验 | 2026-06-01 |
| 15 | LSP 路径编码兼容 (`file:///C:/...`、UNC、空格/中文路径) | 2026-06-07 |
| 16 | PROJECT source-understanding 生产缺陷修复：注释规范化、低 8 位/补码表达式、变量绑定、空 ELSE 清理、ii/jj 保留 | 2026-06-22 |
