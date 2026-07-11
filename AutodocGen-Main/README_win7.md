# AutoDocGen Win7 移植说明

## 系统要求

- **OS**: Windows 7 SP1 (x64) 或 Windows 10
- **Python**: 3.8.20 (Win7 最后官方支持版本)
  - 下载: https://www.python.org/downloads/release/python-3820/
  - 安装时勾选 "Add Python to PATH"
- **VC++ Runtime**: 多数 Win7 系统已自带；如缺请装 KB2533623 + vcredist_x64.exe

## 安装步骤

```cmd
:: 1. 解压 autodoc_win7_port/ 到任意目录，例如 D:\autodocgen\

:: 2. 安装依赖
cd D:\autodocgen
python -m pip install --upgrade pip
python -m pip install -r requirements_win7.txt --no-warn-script-location

:: 3. 验证安装
python -c "import docx, requests, PyQt5; print('OK')"
```

## 快速验证

```cmd
:: CLI 文档生成（不需要 GUI）
python -m autodoc.cli doc -d "C:\path\to\project" -o output.docx

:: 工具脚本
python tools\merge_batch_docx.py --input tmp\batch --output merged.docx
python tools\workspace_to_revision.py output.design_workspace.json -o revision.json
python tools\audit_design_workspace.py output.design_workspace.json --apply
```

## PyInstaller 打包

```cmd
:: 进入移植目录
cd D:\autodocgen

:: 打包为单 exe（包含 CLI + GUI）
pyinstaller --noconfirm --onefile --windowed ^
    --name AutoDocGen ^
    --add-data "autodocgen.ini;." ^
    --add-data "qt_gui\assets;qt_gui\assets" ^
    --hidden-import PyQt5.sip ^
    --hidden-import autodoc.cli ^
    --collect-submodules autodoc ^
    --collect-submodules qt_gui ^
    qt_gui\app.py

:: 打包后产物
dist\AutoDocGen.exe     <- GUI 双击运行
```

### 体积优化（可选）

- 不需要 tree-sitter 备用解析：移除 `--collect-submodules` 中的 `tree_sitter*`
- 去除 `qt_gui\assets` 中不用的图标：保留 main_window 实际用到的 PNG
- 预期体积：约 80-120 MB（PyQt5 + python-docx + tree_sitter）

## Win7 已知问题

1. **PyQt5 5.15.x 在 Win7 需打 KB2533623**（"Update for Universal C Runtime"）
2. **clangd/LSP** 在 Win7 可用，但 `compile_commands.json` 需 MSVC/MinGW；本项目不强制依赖 LSP
3. **AI 提供商** 通过 `autodocgen.ini` 配置，与平台无关；anyrouter.top 走 `https://anyrouter.top/v1/messages`（已测试稳定）

## 配置文件位置

- `autodocgen.ini` — AI 配置、输出格式、增量参数
- `.autodoc/incremental_state.json` — 增量状态（生成后自动）
- `<output>.design_workspace.json` — 设计工作区（生成后自动，需 `extra_params_json` 加 `"design_workspace": "1"`）
- `<output>_review/` — 离线审查 HTML 包（需 `--review-output html`）

## 故障排查

| 症状 | 原因 | 解法 |
|------|------|------|
| `ImportError: DLL load failed` | 缺 VC++ Runtime | 装 vcredist_x64.exe |
| `ModuleNotFoundError: PyQt5.sip` | PyQt5-sip 版本不匹配 | 装 `PyQt5-sip==12.13.0` |
| `OSError: [WinError 193]` 64/32 位混用 | Python 与 pyinstaller 架构不同 | 两者都用 x64 |
| `SSL: CERTIFICATE_VERIFY_FAILED` | 缺 CA 证书 | `pip install certifi` 或 `set SSL_CERT_FILE=...` |
| clangd 启动失败 | Win7 不支持新 clangd | `extra_params_json` 设 `"logic_use_lsp": "0"` |
