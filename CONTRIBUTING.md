# Contributing

## 开发环境

```powershell
python -m pip install -r requirements.txt
python run.py
```

要求 Python 3.11+。Windows 是主要目标平台。

## 测试

```powershell
python -m unittest discover -s tests -v
```

提交前请确保测试通过，并尽量保持新增逻辑有对应单元测试。

## 代码约定

- UI 使用 PySide6 / Qt Widgets，样式集中在 `app/ui/theme.py`。
- 后台任务不要直接操作 Qt 控件；通过主线程信号回传结果。
- 纯逻辑优先放在 `app/parsers.py`、`app/config.py` 或 `app/services/`，方便测试。
- 不要提交 `release*/`、`build/`、日志、配置文件或真实的设备 IP / 序列号。

## 提交 PR

1. 从 `main` 创建功能分支。
2. 保持提交信息清晰，说明改动范围。
3. 如涉及界面变化，附截图。
4. 不要在 PR 中包含打包产物和本地配置。
