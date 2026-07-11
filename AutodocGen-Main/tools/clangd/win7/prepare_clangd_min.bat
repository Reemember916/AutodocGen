@echo off
setlocal enabledelayedexpansion

:: ============================================================
:: 在 Win10 上准备 clangd 最小二进制集，用于内网 Win7 导入。
::
:: 用法：
::   1. 在 Win10 上下载 LLVM-14.0.6-win64.exe 放到本目录
::   2. 运行此脚本
::   3. 生成的 llvm\bin-min\ 目录就是最小集
::   4. 把 bin-min\ 拷到 Win7 的相同位置
::   5. 在 Win7 上打包 exe（PyInstaller spec 会自动包含 bin-min）
:: ============================================================

set "SCRIPT_DIR=%~dp0"
set "INSTALLER=%SCRIPT_DIR%LLVM-14.0.6-win64.exe"
set "TARGET_DIR=%SCRIPT_DIR%llvm"
set "BIN_MIN_DIR=%SCRIPT_DIR%llvm\bin-min"

:: --- 检查安装器 ---
if not exist "%INSTALLER%" (
  echo [ERROR] 未找到 LLVM 安装器: %INSTALLER%
  echo         请从 https://github.com/llvm/llvm-project/releases/tag/llvmorg-14.0.6
  echo         下载 LLVM-14.0.6-win64.exe 放到此目录。
  exit /b 1
)

:: --- 如果已安装则跳过 ---
if not exist "%TARGET_DIR%\bin\clangd.exe" (
  echo [INFO] 正在安装 LLVM/clangd 到 %TARGET_DIR%
  "%INSTALLER%" /S /D=%TARGET_DIR%
  if errorlevel 1 (
    echo [ERROR] LLVM 安装失败，错误码 %errorlevel%
    exit /b %errorlevel%
  )
) else (
  echo [INFO] clangd 已安装: %TARGET_DIR%\bin\clangd.exe
)

if not exist "%TARGET_DIR%\bin\clangd.exe" (
  echo [ERROR] 安装后未找到 clangd.exe
  exit /b 2
)

:: --- 提取最小二进制集 ---
echo [INFO] 正在提取最小二进制集到 %BIN_MIN_DIR%
if not exist "%BIN_MIN_DIR%" mkdir "%BIN_MIN_DIR%"

:: clangd 主程序
copy /Y "%TARGET_DIR%\bin\clangd.exe" "%BIN_MIN_DIR%\clangd.exe" >nul 2>&1

:: clangd 依赖的 DLL（逐个检查，存在才拷贝）
:: clangd.exe 依赖的 DLL 通过 dumpbin /dependents 或试错确定
:: 核心依赖列表（LLVM 14.0.6 win64）：
set "DEPS=clang-14.dll libclang.dll LLVM-C.dll LLVMAggressiveInstCombine.dll LLVMAnalysis.dll LLVMAsmParser.dll LLVMAsmPrinter.dll LLVMBinaryFormat.dll LLVMBitReader.dll LLVMBitWriter.dll LLVMCodeGen.dll LLVMCore.dll LLVMCoroutines.dll LLVMCoverage.dll LLVMDebugInfoCodeView.dll LLVMDebugInfoDWARF.dll LLVMDebugInfoMSVC.dll LLVMDebugInfoPDB.dll LLVMDemangle.dll LLVMDllAdapter.dll LLVMExecutionEngine.dll LLVMFrontendOpenMP.dll LLVMFuzzMutate.dll LLVMGlobalISel.dll LLVMInstCombine.dll LLVMInstrumentation.dll LLVMInterpreter.dll LLVMipo.dll LLVMIRReader.dll LLVMJITLink.dll LLVMLibDriver.dll LLVMLineEditor.dll LLVMLinker.dll LLVMLTO.dll LLVMMCJIT.dll LLVMMC.dll LLVMMCDisassembler.dll LLVMMCParser.dll LLVMMCA.dll LLVMMIPSAsmParser.dll LLVMMipsCodeGen.dll LLVMMipsDesc.dll LLVMMipsInfo.dll LLVMMIRParser.dll LLVMMSVCAsmParser.dll LLVMNVPTXCodeGen.dll LLVMNVPTXDesc.dll LLVMNVPTXInfo.dll LLVMObjCARCOpts.dll LLVMObject.dll LLVMObjectYAML.dll LLVMOption.dll AMDOpts.dll LLVMRemarks.dll LLVMRuntimeDyld.dll LLVMScalarOpts.dll LLVMSelectionDAG.dll LLVMSupport.dll LLVMSymbolize.dll LLVMTarget.dll LLVMTextAPI.dll LLVMTransformUtils.dll LLVMVectorize.dll LLVMX86AsmParser.dll LLVMX86CodeGen.dll LLVMX86Desc.dll LLVMX86Disassembler.dll LLVMX86Info.dll LLVMX86Utils.dll LLVMCodeGenPrepare.dll"

set "copied=0"
for %%D in (%DEPS%) do (
  if exist "%TARGET_DIR%\bin\%%D" (
    copy /Y "%TARGET_DIR%\bin\%%D" "%BIN_MIN_DIR%\%%D" >nul 2>&1
    set /a copied+=1
  )
)

:: 验证
if not exist "%BIN_MIN_DIR%\clangd.exe" (
  echo [ERROR] clangd.exe 未成功拷贝到 bin-min
  exit /b 3
)

:: 统计
set "file_count=0"
for %%F in ("%BIN_MIN_DIR%\*") do set /a file_count+=1

echo.
echo [OK] 最小二进制集准备完成
echo      位置: %BIN_MIN_DIR%
echo      文件数: %file_count% (含 clangd.exe + 依赖 DLL)
echo.
echo 下一步:
echo   1. 将 llvm\bin-min\ 目录拷贝到 Win7 的相同位置
echo   2. 在 Win7 上运行 PyInstaller 打包
echo   3. spec 文件会自动将 bin-min 打包进 exe
echo.
echo 或者:
echo   1. 将整个 llvm\ 目录拷贝到 Win7
echo   2. 运行 AutoDocGen.exe 即可（运行时自动发现 llvm\bin\clangd.exe）
exit /b 0
