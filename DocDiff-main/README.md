# DocDiff（Word 文档更改单生成器）

对比两份 `.docx` 软件设计类文档，按章节/小节识别“新增 / 删除 / 修改”，并生成一份“软件文档更改说明书”（更改单 `.docx`）。

## 功能

- 解析 `.docx`：按标题层级（H1~H4）构建文档 AST（抽取普通段落 + 表格）。
- 稳定匹配章节（多级）：
  1. 括号内唯一编号（`D/R_SDD01_001_003`、`SDD-001-003`、`REQ_12_3` 等）
  2. 重复编号时按归一化标题/正文消歧
  3. 归一化章节路径（去掉标题尾随脚注数字、统一全半角括号/空白）
  4. 标题+正文 fuzzy 配对（默认阈值 0.72，可用 `--fuzzy-threshold` 调整）
- 小节分段：识别 `a)~z)`（含全角）以及 `1)` / `（1）` 等编号作为 segment。
- 变更输出（更改单）：
  - 段落：只输出发生变化的段落块（而不是整段落/整小节）；纯空白/全半角差异不报变更。
  - 表格：只输出发生变化的行（默认附带表头行）；**统一网格样式重建**（浅蓝表头、细边框、宋体），不拷贝原文档合并单元格/复杂边框，避免渲染异常。
  - 诊断：`--dump-ast`（章节结构）、`--dump-match`（配对方法/分数/未匹配候选）。
- 归档增强：更改单元数据区（文号/版本/编制人/日期/密级）、表格按主键列对齐（字段名/名称/ID 等）、`--json-out` 机器可读差异、`--problem-start` 问题续号。

## 安装

建议使用 Python 3.10+（本项目在 Python 3.13 环境运行）。

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

依赖：
- `python-docx`
- `lxml`

## 快速开始

1. 准备两份要对比的 Word 文档（`.docx`）。
2. 运行（推荐显式传参）：

```bash
python3 cli.py --mode docx --old 旧版.docx --new 新版.docx --out 更改单.docx \
  --tickets samples/问题单台账_示例.csv
```

### 问题单台账（人工填写）

一次代码/文档版本变更里，问题单编号应唯一，格式为：

**`项目型号-WT-两位序号`**，例如 `DFKS112-WT-01`、`DFKS112-WT-02`（`DFKS112` 为项目型号）。

台账三列：

| 序号 | 问题 | 问题单编号 |
|------|------|------------|
| 1 | xxx需求变更 | DFKS112-WT-01 |
| 2 | xxx函数冗余 | DFKS112-WT-02 |

- **序号**与更改单「问题N」对齐（默认从 1 起；可用 `--problem-start` 续号）
- 支持 `.csv`（推荐）、`.json`、`.xlsx`（需 openpyxl）
- **自动编号**：填前缀即可，不必手写每一行单号：

```bash
# 仅前缀：第1条→DFKS112-WT-01，第2条→DFKS112-WT-02…
python3 cli.py --mode docx --old 旧.docx --new 新.docx --out 更改单.docx \
  --ticket-prefix DFKS112-WT

# 台账（可只填「问题」描述）+ 前缀补全缺省单号
python3 cli.py --mode docx --old 旧.docx --new 新.docx --out 更改单.docx \
  --tickets 问题单台账.csv --ticket-prefix DFKS112-WT
```

- 导出模板（可指定前缀）：

```bash
python3 cli.py --write-ticket-template 问题单台账.csv --ticket-prefix DFKS112-WT
```

- GUI：问题单台账路径 +「问题单前缀」+「导出模板」+ **自动匹配问题单** 勾选
- 标题示例：`（问题1，修改，DFKS112-WT-01）章节 - seg`
- 示例：`samples/问题单台账_示例.csv`

**自动匹配（方案 A）**：台账里先写好「问题」描述（可含 `D/R_…`、函数名、文件路径），生成时按内容挂到对应变更，并按问题单序号重排「问题N」：

```bash
python3 cli.py --mode docx --old 旧.docx --new 新.docx --out 更改单.docx \
  --tickets 问题单台账.csv --ticket-prefix DFKS112-WT \
  --auto-match-tickets --dump-ticket-match ticket_match.json
```

匹配优先级：doc-id → 路径/文件名 → 函数名/符号 → 标题关键字 → 文本相似。  
未匹配条目仍可按前缀自动编号；详见 `ticket_match.json` 中的 `matches` / `unmatched_*`。

#### 匹配策略（可选 LLM）

| 策略 | 说明 |
|------|------|
| `rules`（默认） | doc-id / 路径 / 函数名 / 关键字 / 相似度 |
| `llm` | 仅调用 OpenAI 兼容 Chat Completions |
| `hybrid` | 规则优先，未匹配再交给 LLM 补全 |

```bash
# 规则（离线）
python3 cli.py --mode docx ... --tickets 台账.csv --auto-match-tickets --match-strategy rules

# 混合：规则 + LLM（需 API）
export DOCDIFF_LLM_API_KEY=sk-...
export DOCDIFF_LLM_API_BASE=https://api.openai.com/v1   # 或内网兼容网关
export DOCDIFF_LLM_MODEL=gpt-4o-mini
python3 cli.py --mode docx ... --tickets 台账.csv --auto-match-tickets \
  --match-strategy hybrid --dump-ticket-match tm.json

# 也可命令行传参
python3 cli.py ... --match-strategy llm --llm-api-key sk-... --llm-model gpt-4o-mini
```

LLM 仅使用标准库 `urllib`，无额外 pip 依赖；无 Key 时 `hybrid` 自动退化为 `rules`。


排查误匹配时：

```bash
python3 cli.py --mode docx --old 旧版.docx --new 新版.docx --out 更改单.docx \
  --dump-match match.json --fuzzy-threshold 0.80
```

带归档元数据与 JSON 台账：

```bash
python3 cli.py --mode docx --old 旧版.docx --new 新版.docx --out 更改单.docx \
  --doc-no WG-2026-001 --version V1.2 --author 张三 \
  --json-out changes.json --problem-start 1
```

### 代码更改单模式

除了 `.docx` 文档，本项目现在支持“代码更改单”输出：

```bash
python3 cli.py --mode code --old <旧代码目录或文件> --new <新代码目录或文件> --out 代码更改单.docx
```

说明：
- 当 `--old/--new` 为目录时：按相对路径对比代码文件，输出新增/删除/修改。
- 当 `--old/--new` 为单文件时：直接对比该文件内容。
- 默认仅对比 C 源码与头文件（`.c`/`.h`）；`.c` 文件走函数级对齐 diff，`.h` 文件走行级 diff。如需扩展到其他后缀，可修改 `code_diff/collect_code_changes.py` 的 `DEFAULT_CODE_EXTS`。
- 输出文档标题为“软件代码更改说明书”。

## 图形界面（GUI）

项目已提供 `tkinter` 图形界面入口（无需额外 GUI 库）：

```bash
python3 gui_app.py
```

界面支持：
- 切换模式：`docx`（文档更改单）/ `code`（代码更改单）
- 选择旧版 / 新版 / 输出路径
- **问题单台账**路径 +「导出模板」（序号/问题/问题单编号）
- docx：Fuzzy 阈值、文号/版本/编制人、表格主键对齐
- 实时运行日志

在 `code` 模式下：
- 旧版/新版路径可选择目录（推荐）
- 也支持单文件对比（要求旧版/新版都为文件）

## 适配 Win7 打包为 EXE

为提高 Win7 兼容性，建议在 **Windows 7 + Python 3.8.x** 环境构建。

1. 把项目放到 Win7 机器上。
2. 双击运行 `build_win7.bat`（或在 cmd 中执行）。
3. 打包成功后输出：`dist\\DocDiffWin7.exe`

说明：
- 脚本会自动安装 `requirements.txt` 依赖。
- 脚本固定使用 `pyinstaller==5.13.2`（对老系统兼容更稳）。
- 生成的是带窗口程序（`--windowed`），不会弹出控制台黑框。

## 文档结构要求（很重要）

当前解析/匹配逻辑对“软件设计说明书/详细设计”这类结构化文档最稳定：

- 使用 **Heading 1~4（标题 1~4）** 标注层级。
- 优先以 **H4** 作为最小可对比单元（Section）；若某个 **H3** 下没有 H4、正文/表格直接挂在 H3 下，则自动回退为以该 H3 作为可对比单元。
- 建议 H4 标题包含稳定编号，且编号位于括号内，例如：
  - `IFBITStateUpdate（D/R_SDD01_001_003）`
  - `状态更新（SDD-001-003）`
  - `接口处理（REQ_12_3）`
- 章节内小节用 `a) / b) / … / z)`（或全角字母）、`1)`、`（1）` 等开头来分段。

如果文档没有以上结构（例如标题样式不规范、编号缺失），匹配会退化为归一化标题路径 + fuzzy；仍可能误报，请用 `--dump-match` 核对。

## 输出说明

输出更改单（`更改单_测试版.docx` 等）格式：

- 每条变更一个小节：`（问题{i}，{类型}）{章节key} - {seg}`
- “更改前 / 更改后”分别只给出差异内容：
  - 段落：仅输出变更的段落块。
  - 表格：仅输出变更的行（并默认带上表头行）。

## 常见问题

### 1) 明明只改了几处，却检测出很多“新增/删除”

通常是因为新旧文档的章节标题文本发生了非语义变化（例如脚注/引用序号导致 `xxx1`），或缺少稳定编号。

本项目已用多级匹配（编号 / 重复编号消歧 / 归一化路径 / fuzzy）降低此类误报；请尽量保证 H4 括号内编号唯一。仍异常时：

```bash
python3 cli.py --mode docx --old 旧.docx --new 新.docx --out out.docx --dump-match match.json
```

查看 `method_counts` 与 `unmatched_old` / `unmatched_new`。可适当提高 `--fuzzy-threshold` 减少弱配对，或降低以合并路径变更。

### 2) 表格行级差异不准 / 合并单元格样式丢失

目前表格行级差异是按“每行单元格文本拼接”做对比，适合大多数“字段增删改”的表格。

- 对于大量合并单元格、复杂边框/样式的表格：
  - 行级 diff 仍然可用，但样式可能无法完全保留；
  - 如需更高保真，需要进一步复制 `w:tblPr`/`w:tcPr` 等样式与合并信息。

## 代码结构

- `cli.py`：命令行入口（`--mode/--old/--new/--out/--dump-ast/--dump-match/--fuzzy-threshold/--json-out/--doc-no/--version/--author/--problem-start/--no-table-key`）。
- `gui_app.py`：图形界面入口（Win7 友好；docx 模式可调 Fuzzy 阈值、文号/版本/编制人、表格主键对齐）。
- `build_win7.bat`：Windows 7 一键打包脚本。
- `canonical/normalize.py`：解析 docx，构建 AST。
- `diff/collect_changes.py`：收集变更与章节多级匹配 / `build_match_report`。
- `diff/block_diff.py`：segment 文本 diff 判定（忽略纯空白/全半角噪声）。
- `render/change_order.py`：生成更改单 docx（元数据区、表格主键列对齐、差异段落/行级输出、宋体；`changes_to_jsonable`）。
- `code_diff/collect_code_changes.py`：收集代码目录/文件差异。
- `render/code_change_order.py`：渲染“软件代码更改说明书”。
- `tests/test_section_matching.py`、`tests/test_phase1_matching.py`、`tests/test_phase2_render.py`：误报与归档能力回归测试。

## TODO（可选改进）

- 表格：更完整复制样式/合并单元格；自定义主键列名配置文件。
- 更改单与单位 Word 模板（页眉页脚/题注）对齐。
- 构建时从根目录同步 `DocDiff_Win7_Minimal` 核心模块，消除双树手工拷贝。
