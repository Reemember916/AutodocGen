# AutoDocGen V1.4 — 架构总览

## 分层架构图

```mermaid
flowchart TB
    subgraph Entry ["入口层"]
        direction LR
        A1["AutoDocGen_V1.4.py"]
        A2["tools/run_forward_pipeline.py"]
    end

    subgraph UI ["用户界面层"]
        B1["qt_gui/app.py · 启动器"]
        B2["qt_gui/main_window.py · 主窗口"]
        B3["qt_gui/runner.py · 后台任务"]
        B4["qt_gui/settings_store.py · 配置持久化"]
        B5["qt_gui/consistency_panel.py · 一致性面板"]
    end

    subgraph CLI ["命令行层"]
        C["autodoc/cli.py · 参数解析与派发"]
    end

    subgraph Core ["核心编排层"]
        D["autodoc/backend.py · 主调度引擎"]
        E["autodoc/config.py · 配置管理"]
        F["autodoc/pipeline.py · 流水线编排"]
        G["autodoc/incremental.py · 增量生成"]
    end

    subgraph Parse ["源码解析层"]
        H1["autodoc/scanner.py · 文件扫描"]
        H2["autodoc/parse.py · C 解析器"]
        H3["autodoc/comment_normalizer.py · 注释归一"]
        H4["autodoc/compile_db.py · compile_commands.json 解析"]
        H5["autodoc/runtime.py · 运行时上下文"]
    end

    subgraph Analysis ["逻辑分析层"]
        I1["autodoc/logic.py · 逻辑分析"]
        I2["autodoc/logic_ir.py · 逻辑 IR (new)"]
        I3["autodoc/logic_step_ir.py · 逻辑步骤 IR (legacy)"]
        I4["autodoc/c_expr.py · C 表达式解析"]
        I5["autodoc/semantic.py · 语义分析引擎"]
        I6["autodoc/semantic_elements.py · 语义元素"]
        I7["autodoc/semantic_registry.py · 语义注册器"]
        I8["autodoc/semantic_pack.py · 语义包构建"]
    end

    subgraph Naming ["命名 / 符号层"]
        J1["autodoc/naming.py · 符号名处理"]
        J2["autodoc/naming_context.py · 命名上下文"]
        J3["autodoc/term_table.py · 术语表"]
        J4["autodoc/term_checker.py · 术语检查"]
    end

    subgraph LSP ["LSP 集成层"]
        K1["autodoc/lsp_gateway.py · LSP 网关"]
        K2["autodoc/lsp_adapter.py · LSP 适配器"]
        K3["autodoc/lsp_transport.py · 传输层"]
        K4["autodoc/lsp_facts.py · 事实提取"]
    end

    subgraph AI ["AI 集成层"]
        L["autodoc/ai.py · AI 传输与 Prompt 构建"]
    end

    subgraph Evidence ["证据采集层 (旁路)"]
        M1["autodoc/evidence/models.py · 数据结构"]
        M2["autodoc/evidence/collector.py · 采集器"]
        M3["autodoc/evidence/clang_provider.py · Clang 提供者"]
    end

    subgraph CodeGraph ["调用图分析层"]
        N1["autodoc/codegraph_adapter.py · CodeGraph 适配器"]
        N2["autodoc/callgraph.py · 调用图"]
        N3["autodoc/graph_visuals.py · 图可视化"]
    end

    subgraph DocGen ["文档生成层"]
        O1["autodoc/render.py · docx 渲染器"]
        O2["autodoc/revision.py · 修订管理"]
        O3["autodoc/models.py · 数据模型"]
        O4["autodoc/text.py · 文本工具"]
    end

    subgraph Forward ["前向流水线 (Markdown→C)"]
        P1["autodoc/forward/extractor.py · Markdown→HeaderFileIR"]
        P2["autodoc/forward/merger.py · USER CODE 合并"]
        P3["autodoc/forward/generator.py · IR→C 骨架"]
    end

    subgraph Review ["审查工作区区"]
        Q1["autodoc/review_workspace.py · 审查工作区"]
        Q2["autodoc/design_workspace.py · 设计工作区"]
    end

    subgraph Tools ["工具脚本"]
        R1["tools/convert_ccs_to_compile_commands.py"]
        R2["tools/merge_batch_docx.py"]
        R3["tools/update_doc_from_code_diff.py"]
        R4["tools/random_function_doccheck.py"]
        R5["tools/audit_design_workspace.py"]
        R6["tools/llm_judge/llm_judge.py"]
    end

    A1 --> CLI
    A1 --> UI
    A2 --> Forward
    CLI --> Core
    UI --> Core
    Core --> Parse
    Core --> Analysis
    Core --> Naming
    Core --> AI
    Core --> Evidence
    Core --> CodeGraph
    Core --> DocGen
    Core --> Review
    Parse --> Analysis
    Analysis --> Naming
    Analysis --> Evidence
    LSP --> Analysis
    AI --> Analysis
    AI --> Naming
    CodeGraph --> DocGen
    Parse -.-> LSP
```

## 数据流 (前向: 源码→文档)

```mermaid
flowchart LR
    subgraph Input ["输入"]
        IN1["*.c / *.h 源码"]
        IN2["autodocgen.ini"]
    end

    subgraph Process ["处理流水线"]
        P1["Scanner: 扫描文件树"]
        P2["Parser: 提取函数原型/体/注释"]
        P3["Logic: 逻辑步骤分析"]
        P4["Naming: 符号名收口中文化"]
        P5["Semantic: 语义元素萃取"]
        P6["AI: 未覆盖项补全"]
        P7["Evidence: 旁路证据采集"]
        P8["Render: 写入 docx 缓存"]
    end

    subgraph Output ["输出"]
        OUT1["*.docx 设计文档"]
        OUT2["review_bundle.json + index.html"]
        OUT3["design_workspace.json"]
        OUT4["evidence_report.json"]
    end

    IN1 --> P1 --> P2 --> P3 --> P4 --> P5 --> P6 --> P7 --> P8 --> OUT1
    P8 --> OUT2
    P8 --> OUT3
    P7 --> OUT4
```

## 数据流 (逆向: Markdown→C 骨架)

```mermaid
flowchart LR
    subgraph FwdInput ["输入"]
        FI1["*.md 需求文档"]
    end

    subgraph FwdProcess ["前向流水线"]
        FP1["extractor.py · Markdown→HeaderFileIR"]
        FP2["generator.py · IR→C 代码骨架"]
        FP3["merger.py · USER CODE 块无损合并"]
    end

    subgraph FwdOutput ["输出"]
        FO1["*.c / *.h 骨架代码"]
    end

    FI1 --> FP1 --> FP2 --> FP3 --> FO1
```

## 模块依赖关系 (核心路径)

```mermaid
flowchart TB
    cli["autodoc/cli.py"] --> backend["autodoc/backend.py"]
    backend --> config["autodoc/config.py"]
    backend --> pipeline["autodoc/pipeline.py"]
    backend --> scanner["autodoc/scanner.py"]
    backend --> parse["autodoc/parse.py"]
    backend --> logic["autodoc/logic.py"]
    backend --> logic_ir["autodoc/logic_ir.py"]
    backend --> naming["autodoc/naming.py"]
    backend --> render["autodoc/render.py"]
    backend --> ai["autodoc/ai.py"]
    backend --> evidence["autodoc/evidence/collector.py"]
    backend --> lsp_facts["autodoc/lsp_facts.py"]
    backend --> incremental["autodoc/incremental.py"]
    backend --> semantic["autodoc/semantic.py"]
    backend --> codegraph["autodoc/codegraph_adapter.py"]
    backend --> revision["autodoc/revision.py"]
    backend --> review["autodoc/review_workspace.py"]
    backend --> design_ws["autodoc/design_workspace.py"]
    parse --> compile_db["autodoc/compile_db.py"]
    parse --> comment_norm["autodoc/comment_normalizer.py"]
    parse --> runtime["autodoc/runtime.py"]
    logic --> logic_step_ir["autodoc/logic_step_ir.py"]
    logic --> c_expr["autodoc/c_expr.py"]
    logic --> term_checker["autodoc/term_checker.py"]
    logic --> semantic_registry["autodoc/semantic_registry.py"]
    naming --> naming_context["autodoc/naming_context.py"]
    naming --> semantic_pack["autodoc/semantic_pack.py"]
    naming --> semantic_elements["autodoc/semantic_elements.py"]
    naming --> term_table["autodoc/term_table.py"]
    ai --> naming
    evidence --> clang["autodoc/evidence/clang_provider.py"]
    lsp_facts --> lsp_adapter["autodoc/lsp_adapter.py"]
    lsp_adapter --> lsp_gateway["autodoc/lsp_gateway.py"]
    lsp_gateway --> lsp_transport["autodoc/lsp_transport.py"]
    render --> models["autodoc/models.py"]
    render --> text["autodoc/text.py"]
    render --> ui_utils["autodoc/utils.py"]
```

## 目录结构

```
AutodocGen-Main/
├── AutoDocGen_V1.4.py          # 总体入口
├── autodocgen.ini              # 本地配置
├── autodoc/
│   ├── backend.py              # 核心主调度 (6923行)
│   ├── cli.py                  # 命令行解析 + GUI 启动
│   ├── config.py               # GenConfig 配置模型
│   ├── pipeline.py             # 流水线编排 (回归补跑等)
│   ├── parse.py                # C 源码解析器
│   ├── scanner.py              # 文件扫描仪
│   ├── logic.py                # 逻辑分析引擎
│   ├── logic_ir.py             # 逻辑 IR (forward pipeline)
│   ├── logic_step_ir.py        # 逻辑步骤 IR
│   ├── c_expr.py               # C 表达式解析
│   ├── semantic.py             # 语义分析引擎
│   ├── semantic_elements.py    # 语义元素定义
│   ├── semantic_registry.py    # 语义元素注册
│   ├── semantic_pack.py        # 语义包构建
│   ├── naming.py               # 符号名收口/中文处理
│   ├── naming_context.py       # 命名上下文
│   ├── term_table.py           # 术语表
│   ├── term_checker.py         # 术语一致性检查
│   ├── ai.py                   # AI 补全 (4941行)
│   ├── render.py               # docx 渲染 (2291行)
│   ├── incremental.py          # 增量生成
│   ├── revision.py             # 修订管理
│   ├── models.py               # 数据模型
│   ├── text.py                 # 文本工具
│   ├── utils.py                # 通用工具
│   ├── runtime.py              # 运行时上下文
│   ├── compile_db.py           # compile_commands.json
│   ├── comment_normalizer.py   # 注释归一化
│   ├── codegraph_adapter.py    # CodeGraph 适配器
│   ├── callgraph.py            # 调用图
│   ├── graph_visuals.py        # 图可视化
│   ├── lsp_gateway.py          # LSP 网关
│   ├── lsp_adapter.py          # LSP 适配器
│   ├── lsp_transport.py        # LSP 传输层
│   ├── lsp_facts.py            # LSP 事实提取
│   ├── design_workspace.py     # 设计工作区
│   ├── review_workspace.py     # 审查工作区
│   ├── context_pack.py         # 上下文打包
│   ├── _legacy_support.py      # 旧版向后兼容
│   ├── evidence/               # 旁路证据采集
│   │   ├── models.py, collector.py, clang_provider.py
│   └── forward/                # 前向代码生成
│       ├── extractor.py, generator.py, merger.py
├── qt_gui/                     # PyQt5 GUI
│   ├── app.py, main_window.py
│   ├── runner.py, settings_store.py
│   └── consistency_panel.py
└── tools/                      # 辅助工具脚本
    ├── run_forward_pipeline.py
    └── ...
```

## 关键设计决策

| 决策 | 说明 |
|---|---|
| **增量生成** | 缓存 render XML 元素 + 源码 hash，仅重渲染变更函数 |
| **回归补跑** | AI 生成质量得分低时自动多轮重试，逐步改进逻辑文本 |
| **旁路证据** | evidence 系统默认关闭 (`shadow mode`)，不影响 docx 输出 |
| **LSP 集成** | 可选 clangd LSP 获取精确类型/成员/调用上下文 |
| **前后向双管道** | `源码→文档` (backend) + `Markdown→C` (forward) |
