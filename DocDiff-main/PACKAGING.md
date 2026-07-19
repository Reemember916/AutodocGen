# DocDiff Win7 打包说明

## 推荐环境

- **操作系统**：Windows 7 SP1（或兼容的 Win10，但产物需在 Win7 验证）
- **Python**：3.8.x（Win7 上最稳）
- **网络**：能 `pip install`，或已准备离线 wheel

## 一键打包（推荐用 Minimal 树）

1. 把整个 `DocDiff_Win7_Minimal` 文件夹拷到 Win7 机器  
2. 双击 **`build_win7.bat`**（或在 cmd 中执行）  
3. 成功后得到：

```
DocDiff_Win7_Minimal\dist\DocDiffWin7.exe
```

也可在**项目根目录**执行同名 `build_win7.bat`（使用完整源码树）。

## 脚本会做什么

1. 检查 `python`  
2. 安装 `requirements.txt`（`python-docx`、`lxml`）  
3. 尝试安装 `openpyxl`（xlsx 问题单台账，失败则仅 CSV/JSON）  
4. 安装 `pyinstaller==5.13.2`  
5. 打包 **单文件、无控制台黑框** GUI：`gui_app.py` → `DocDiffWin7.exe`  

已加入 `tickets` / `diff` / `render` 等 hidden-import，避免运行时缺模块。

## 运行 EXE

- 双击 `DocDiffWin7.exe` 打开「DocDiff 更改单生成器」  
- 无需安装 Python  
- 首次启动可能稍慢（单文件解压）  

问题单 LLM 匹配若要用，需在系统环境变量配置 API（与 CLI 相同）：

- `DOCDIFF_LLM_API_KEY`  
- `DOCDIFF_LLM_API_BASE`（可选）  
- `DOCDIFF_LLM_MODEL`（可选）  

默认 **rules** 匹配可完全离线。

## 本机（macOS/Linux）说明

当前 CI/沙箱是 Linux，**不能**直接生成 Win7 的 `.exe`。  
请把发布包拷到 Win7 后执行 `build_win7.bat`。

macOS 若只想本地试 GUI：

```bash
python3 gui_app.py
```

## 故障排查

| 现象 | 处理 |
|------|------|
| 找不到 python | 安装 3.8 并勾选 Add to PATH |
| pip 失败 | 换源或离线 wheel |
| 启动闪退 | 用 `pyinstaller` 去掉 `--windowed` 看控制台报错；或检查杀软拦截 |
| 缺 tickets 模块 | 使用本仓库最新 `build_win7.bat`（含 hidden-import） |
| xlsx 台账读不了 | `pip install openpyxl` 后重新打包，或改用 csv |

## 版本检查清单（打包前）

- [ ] `DocDiff_Win7_Minimal` 已与根目录核心模块同步（`tickets/`、`diff/`、`render/`、`cli.py`、`gui_app.py`）  
- [ ] 本机 `python -m unittest` 关键要用例通过  
- [ ] Win7 上实际点一次：docx 对比 + 问题单台账 + 生成更改单  
