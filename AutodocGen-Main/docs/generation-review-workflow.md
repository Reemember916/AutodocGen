# AutoDocGen 首次生成人工审查使用说明

本文说明 **C → DOCX 首次生成** 后的离线审查闭环。

注意：这与“代码增量更新”审查是两条链路，决策文件名不同，不要混用。

| 场景 | 审查页 | 决策文件 |
|---|---|---|
| 首次生成文档 | `*_review/index.html` | `generation_review_decisions.json` |
| 旧/新代码增量更新 | `*.update_review.html` | `update_review_decisions.json` |

## 1. 生成带审查包的文档

### CLI

```bash
cd AutodocGen-Main
python3 -m autodoc.cli doc \
  --project-dir /path/to/project_src \
  --output /path/to/design.docx \
  --review-output html \
  --review-dir /path/to/design_review
```

也可对单文件：

```bash
python3 -m autodoc.cli doc \
  --c-file /path/to/file.c \
  --output /path/to/design.docx \
  --review-output html
```

默认审查目录为 `<输出文件名>_review`。

### GUI

1. 首页选择“工程模式”或“单文件模式”
2. 选择工程目录 / C 文件和 Word 输出路径
3. 在“设置 → 高级”中设置：
   - `review_output = html`
   - 可选 `review_dir = <审查包目录>`
4. 点击“生成文档”

输出：

```text
design.docx
design_review/
  review_bundle.json   # 生成结果与证据，只读
  index.html           # 交互式审查页
```

## 2. 在审查页中人工修改

用浏览器打开：

```text
design_review/index.html
```

推荐用系统浏览器打开（Chrome / Edge）。页面支持：

- 左侧：搜索、状态筛选、待人工修改筛选
- 中间：编辑标题、功能说明、参数中文名、局部变量用途、逻辑步骤
- 右侧：通过 / 待修改 / 驳回、备注、质量警告
- 自动保存到浏览器 localStorage
- 导入 / 导出决策
- “通过无警告项”批量通过

导出文件名固定为：

```text
generation_review_decisions.json
```

导出内容只包含 **人工触碰过** 的函数（编辑、改状态、导入或批量通过），不会把未改函数全部写进去。

文件中会有：

```json
{
  "schema_version": 1,
  "decision_kind": "generation_review",
  "bundle_fingerprint": "...",
  "functions": {
    "src/foo.c::Foo": {
      "status": "approved",
      "title": "...",
      "description": "...",
      "return_desc": "...",
      "logic_lines": ["..."]
    }
  }
}
```

只有 `status = approved` 的函数会在重新生成时生效。

## 3. 应用决策并重新生成

### CLI 两步法

```bash
# 1) 决策 -> revision profile
python3 -m autodoc.cli review-apply \
  --bundle /path/to/design_review/review_bundle.json \
  --decisions /path/to/generation_review_decisions.json \
  -o /path/to/revision_profile.json

# 2) 重新生成时加载 revision profile
python3 -m autodoc.cli doc \
  --project-dir /path/to/project_src \
  --output /path/to/design_reviewed.docx \
  --revision-profile /path/to/revision_profile.json
```

### CLI 一步法

```bash
python3 -m autodoc.cli doc \
  --project-dir /path/to/project_src \
  --output /path/to/design_reviewed.docx \
  --review-decisions /path/to/generation_review_decisions.json \
  --review-bundle /path/to/design_review/review_bundle.json
```

若未显式传 `--review-bundle`，会尝试从决策文件旁、输出同名 `_review/` 等位置自动发现。

### GUI

1. 首页“人工审查决策”选择 `generation_review_decisions.json`
2. 确认工程目录 / 输出路径与首次生成一致
3. 点击 **应用并生成**

GUI 会：

1. 定位对应 `review_bundle.json`
2. 生成临时 `*.revision_profile.json`
3. 按已通过函数重新生成 DOCX

## 4. 过期与安全规则

- 决策绑定 `bundle_fingerprint` 和函数 `source_hash`
- 源码变化后，默认拒绝应用过期决策
- CLI 可用 `--allow-stale-review` / `--allow-stale` 强制应用，不建议常规使用
- 原型与 C 类型保持只读，不应通过审查页修改代码签名

## 5. 与增量更新审查的区别

| 项目 | 首次生成审查 | 增量更新审查 |
|---|---|---|
| 入口 | 生成文档后的 `index.html` | `update_doc_from_code_diff.py` 输出的 `update_review.html` |
| 决策文件 | `generation_review_decisions.json` | `update_review_decisions.json` |
| 决策内容 | 函数文档字段修订 | CSU 替换/插入/删除/跳过等 |
| 应用方式 | `review-apply` / `doc --review-decisions` / GUI“应用并生成” | `update_doc_from_code_diff.py --mode apply-review` |

增量更新详细流程见 [doc-update-workflow.md](doc-update-workflow.md)。
