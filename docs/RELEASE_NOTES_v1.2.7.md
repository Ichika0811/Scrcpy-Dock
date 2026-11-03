# Scrcpy Dock v1.2.7

Windows 免安装版。

## 新增

- 软件内浏览 scrcpy 官方 GitHub Releases。
- 选择稳定版 Windows zip 后自动下载、解压并加入左侧版本库。
- 默认安装目录：`%LOCALAPPDATA%\ScrcpyDock\tools`。
- 下载校验：文件大小、SHA-256（资源提供时）、安全 zip 路径检查、重复目录保护。

## 改进与修复

- 操作图标改为内置 SVG。
- 按钮图标使用 DPI 感知的 QIcon 渲染，修复高 DPI 模糊。
- 终端、页签、收藏、箭头和状态提示统一图标风格。
- 修复刷新版本栏时 `QPushButton already deleted` 未处理异常。
- 保留终端日志自动跟随、命令输入和可收起 IP 分组。

## 使用

解压后运行 `ScrcpyDock.exe`。需要自行准备至少一个 scrcpy 版本目录，项目不附带 scrcpy / ADB 二进制。
