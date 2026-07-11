# Windows 7 打包说明

## 推荐环境

- 在 Windows 10 上打包。
- Python 使用 3.8.x。
- 如果目标 Win7 是 64 位，Win10 上也装 64 位 Python 3.8。
- 如果目标 Win7 是 32 位，Win10 上装 32 位 Python 3.8。

## 一键打包

双击：

```bat
build_win7_package.bat
```

脚本会安装固定版本：

- `pyserial==3.5`
- `pyinstaller==5.13.2`

输出目录：

```text
dist\PROJECT_RS422_Host\
```

把整个 `PROJECT_RS422_Host` 文件夹拷贝到 Win7，运行：

```text
PROJECT_RS422_Host.exe
```

## 说明

当前采用 `onedir` 目录包，不采用单文件 `onefile`。目录包在 Win7 上更稳，启动也更快。
