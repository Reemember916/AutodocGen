# AutoDocGen 文档增量更新使用说明

本文说明如何使用 AutoDocGen 的嵌入式 C 项目设计文档增量更新能力。

目标输入：

- 旧版本代码目录
- 新版本代码目录
- 旧 Word 设计文档

目标输出：

- 新 Word 设计文档
- 代码差异 Word
- 代码差异 JSON
- 更新计划 JSON
- 更新报告 Markdown
- 人工审查 HTML

## 1. 前置条件

需要本地存在 DocDiff：

```bash
/Users/ree/Downloads/DocDiff-main/cli.py
```

AutoDocGen 默认会使用该路径。若 DocDiff 在其他位置，运行时传入 `--docdiff-root`。

旧 Word 文档中 CSU 标题需要包含类似下面的编号：

```text
SomeFunc（D/R_SDD01_001_001）
```

工具会识别普通 `Heading 4`、中文 `标题 4`、`609_4`，以及基于这些标题样式的自定义样式。

## 2. 仅生成计划

先运行 `plan-only`，不修改 Word，只生成差异、计划、报告和审查 HTML。

```bash
python3 tools/update_doc_from_code_diff.py \
  --old-code /path/to/old_code \
  --new-code /path/to/new_code \
  --old-doc /path/to/old_design.docx \
  --out /path/to/new_design.docx \
  --mode plan-only
```

输出文件会与 `--out` 同名前缀：

```text
new_design.code_change.docx
new_design.code_changes.json
new_design.update_plan.json
new_design.update_report.md
new_design.update_review.html
```

## 3. 自动应用安全项

`apply-safe` 会复制旧文档到 `--out`，然后只替换安全项。

安全项定义：

- 变化是 C 函数修改
- 新源码文件存在
- 旧文档中该函数唯一匹配一个 CSU

命令：

```bash
python3 tools/update_doc_from_code_diff.py \
  --old-code /path/to/old_code \
  --new-code /path/to/new_code \
  --old-doc /path/to/old_design.docx \
  --out /path/to/new_design.docx \
  --mode apply-safe
```

注意：不要把 `--out` 指向旧文档。工具会拒绝覆盖旧文档。

## 4. 人工审查 HTML

打开：

```text
new_design.update_review.html
```

可对 review/manual 项选择：

- `skip`：跳过
- `manual`：人工处理
- `replace_csu`：替换已有 CSU
- `insert_after_csu`：插入到某个 CSU 后
- `delete_csu`：删除 CSU

HTML 会在浏览器本地自动保存审查进度，刷新页面后会恢复。也可以导入已有的 `review_decisions.json`。

完成审查后，点击导出，得到：

```text
review_decisions.json
```

## 5. 应用人工决策

```bash
python3 tools/update_doc_from_code_diff.py \
  --old-code /path/to/old_code \
  --new-code /path/to/new_code \
  --old-doc /path/to/old_design.docx \
  --out /path/to/new_design_reviewed.docx \
  --mode apply-review \
  --review-decisions /path/to/review_decisions.json
```

`apply-review` 会先执行 safe 项，再执行人工决策。

已支持执行：

- `replace_csu`
- `insert_after_csu`
- `delete_csu`

决策匹配会校验稳定字段：

- action
- rel_path
- func_name
- csu_id

即使 `item_index` 因计划重排失效，也会尽量按稳定字段匹配，避免套错条目。

## 6. CSU 编号策略

默认策略是保守的：

- 新增 CSU 时自动使用同模块最大编号 + 1
- 不重排已有 CSU 编号
- 删除 CSU 后不自动改变其他 CSU 编号

如果确实要按模块内 H4 顺序重排编号，显式加：

```bash
--renumber-module-csu
```

该开关只建议在确认外部引用不依赖旧 CSU ID 时使用。

## 7. GUI 使用

GUI 首页有“文档增量更新”卡片。

填写：

- 旧代码目录
- 新代码目录
- 旧 Word 文档
- 可选 `review_decisions.json`
- 模式：`plan-only`、`apply-safe`、`apply-review`
- 可选“重排模块 CSU 编号”

点击“运行增量更新”。

GUI 后台与 CLI 使用同一套更新逻辑。

## 8. PROJECT 当前验证结果

当前真实样本：

```text
old code: /Users/ree/Downloads/PROJECT-2007-0613
new code: /Users/ree/Downloads/PROJECT-2007-S01-0001-0621_src
old doc:  /Users/ree/Downloads/123_fixed2_test.docx
```

当前 `plan-only` 结果：

```text
safe:   72
manual: 129
review: 344
total:  545
```

当前 `apply-safe` 已验证可生成新 Word：

```text
/Users/ree/Downloads/123_fixed2_test_project_csu_index_apply_safe.docx
```

## 9. 当前边界

以下内容仍默认进入人工处理或审查：

- 全局变量、宏、结构体等文件全局区域变化
- 匹配不到 CSU 的函数
- 多个 CSU 匹配同一函数
- 头文件变化影响的函数
- 新增函数插入位置
- 删除函数确认
- 可能重命名函数确认

这是刻意保守的设计，避免静默误改 Word 文档。
