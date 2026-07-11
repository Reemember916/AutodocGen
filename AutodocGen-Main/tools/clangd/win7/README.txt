LLVM/clangd 14.0.6 Win7 离线部署指南
======================================

## 场景

Win7 内网机器无法联网，需要在 Win10 上先准备好 clangd 二进制，再导入 Win7。

## 在 Win10 上的操作

### 方法 A：最小二进制集（推荐，exe 体积小）

1. 下载 LLVM-14.0.6-win64.exe：
   https://github.com/llvm/llvm-project/releases/tag/llvmorg-14.0.6
   放到本目录（tools/clangd/win7/）

2. 运行：
   prepare_clangd_min.bat

3. 生成的目录：
   tools/clangd/win7/llvm/bin-min/
   包含 clangd.exe + 依赖 DLL（约 80 个文件，~150MB）

4. 将 bin-min/ 目录拷贝到 Win7 的相同位置

### 方法 B：完整安装（简单，体积大）

1. 下载 LLVM-14.0.6-win64.exe，放到本目录

2. 运行：
   install_clangd_win7.bat

3. 生成的目录：
   tools/clangd/win7/llvm/bin/
   完整 LLVM 安装（~500MB）

4. 将整个 llvm/ 目录拷贝到 Win7

## 在 Win7 上的操作

### 打包 exe

1. 确保 bin-min/ 或 llvm/bin/ 已就位
2. 运行 PyInstaller：
   pyinstaller AutoDocGen.spec
3. spec 文件自动检测 bin-min（优先）或 bin（回退）
4. clangd 二进制打包进 exe

### 不打包，直接运行源码

1. 确保 llvm/bin/clangd.exe 就位
2. 运行 python AutoDocGen_V1.4.py
3. 运行时自动发现 clangd

## 运行时路径查找顺序

lsp_gateway.py 的 _resolve_clangd_path() 按以下顺序查找：

1. ini 配置 logic_lsp_clangd_path（显式指定）
2. tools/clangd/win7/llvm/bin/clangd.exe（打包或安装）
3. tools/clangd/win7/clangd.exe
4. tools/clangd/clangd.exe
5. 系统 PATH 中的 clangd（shutil.which）

## 验证

运行 AutoDocGen 后查看日志：
- 看到 "[LSP] clangd 进程已退出" → clangd 存在但启动失败（检查 DLL）
- 没有任何 [LSP] 日志 → clangd 未找到（检查路径）
- 看到 clangd_version 非空 → 正常工作
