# 发布到 GitHub

## 1. 创建仓库

在 GitHub 新建一个空仓库（不要勾选初始化 README / LICENSE / .gitignore）。

## 2. 关联并推送

在项目根目录执行：

```powershell
git remote add origin https://github.com/<your-name>/scrcpy-dock.git
git push -u origin main
```

如果还没有本地提交，先检查：

```powershell
git status
git log --oneline -1
```

本仓库已经包含初始提交 `Initial commit: Scrcpy Dock v1.2.5`。

## 3. 创建 Release

1. 在 GitHub 仓库打开 **Releases → Draft a new release**。
2. Tag 填 `v1.2.5`，标题填 `Scrcpy Dock v1.2.5`。
3. 上传 Windows 免安装包：

```text
ScrcpyDock-v1.2.5-win64.zip
```

4. 把 `CHANGELOG.md` 中 `1.2.5` 部分粘贴到 release notes。
5. 发布。

## 4. 仓库建议设置

- Description：`Windows desktop manager for multiple scrcpy versions, devices and terminals.`
- Topics：`scrcpy`、`adb`、`android`、`pyside6`、`qt`、`windows`、`docker`、`redroid`
- 不需要提交 `release/`、`release-v*/`、`build/`、日志或本地 `config.json`，这些已写入 `.gitignore`。

## 5. 源码上传方式

如果使用网页上传而不是 `git push`，上传：

```text
ScrcpyDock-src-v1.2.5.zip
```

不要把 43MB 的 Windows 免安装包放进源码仓库；它应作为 Release 附件。
