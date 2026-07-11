# Win10 构建 Win7 内网 EXE 说明

## 目标

在 Windows 10 外网/构建机上使用 Python 3.8.20 + PyInstaller 5.13.2，生成可拷贝到 Windows 7 SP1 x64 内网电脑运行的 AutoDocGen 应用。

## 构建环境

- Windows 10 x64
- Python 3.8.20 x64
- pip
- PyInstaller 5.13.2

Python 3.8.20 是 Windows 7 可用的最后一代官方 Python。不要用 Python 3.9+ 构建 Win7 exe。

## 构建步骤

```bat
cd /d D:\AutoDocGen_win10_build

python -m pip install --upgrade pip
python -m pip install -r requirements_win7.txt --no-warn-script-location

python -c "import docx, requests, PyQt5; print('deps ok')"

pyinstaller --noconfirm AutoDocGen.spec
```

构建产物：

```text
dist\AutoDocGen\AutoDocGen.exe
```

把整个目录复制到 Win7 内网电脑：

```text
dist\AutoDocGen\
```

不要只复制单个 exe；当前 spec 使用目录模式，包含 Qt、资源、DocDiff、tools、配置等随附文件。

## 运行

双击：

```text
AutoDocGen.exe
```

命令行：

```bat
AutoDocGen.exe --version
AutoDocGen.exe gui
AutoDocGen.exe doc -d C:\project -o C:\out.docx
```

## 文档增量更新功能

本构建包已包含：

- `tools/update_doc_from_code_diff.py`
- `tools/render_update_review_html.py`
- `DocDiff-main`

GUI 的“文档增量更新”会默认使用随包的 `DocDiff-main`。如果要手动指定，也可以在 GUI 中填写 DocDiff 根目录。

## clangd / LSP

默认包里只放 Win7 clangd 准备脚本，不强制包含 clangd 二进制。

如需 LSP：

```bat
tools\clangd\win7\prepare_clangd_min.bat
pyinstaller --noconfirm AutoDocGen.spec
```

如果内网 Win7 不需要 LSP，保持默认即可；工具会回退到规则解析。

## 常见问题

### ImportError: DLL load failed

Win7 缺运行库。安装 KB2533623、VC++ Runtime，或使用已打齐补丁的 Win7 SP1 x64。

### PyQt5 无法启动

确认安装：

```bat
python -c "import PyQt5.QtWidgets; print('qt ok')"
```

### 文档增量更新找不到 DocDiff

确认构建目录里存在：

```text
DocDiff-main\cli.py
```

如果没有，重新解压本构建包后再构建。

### Win7 运行时缺配置

确认 `dist\AutoDocGen\` 下存在：

```text
autodocgen.ini
symbol_dictionary.json
qt_gui\assets\
DocDiff-main\
```
