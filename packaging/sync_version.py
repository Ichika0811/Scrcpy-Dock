"""Keep packaging/docs version references in sync with app/__init__.py."""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VERSION_FILE = ROOT / "app" / "__init__.py"
VERSION_RE = re.compile(r'__version__\s*=\s*"([0-9]+\.[0-9]+\.[0-9]+)"')


def current_version() -> str:
    match = VERSION_RE.search(VERSION_FILE.read_text(encoding="utf-8"))
    if not match:
        raise SystemExit("cannot find __version__ in app/__init__.py")
    return match.group(1)


def replace_required(path: Path, pattern: str, replacement: str) -> None:
    text = path.read_text(encoding="utf-8")
    updated, count = re.subn(pattern, replacement, text)
    if not count:
        raise SystemExit(f"version pattern not found in {path}")
    path.write_text(updated, encoding="utf-8", newline="\n")


def main() -> int:
    version = current_version()
    numeric = version.split(".")
    tuple_version = f"({numeric[0]}, {numeric[1]}, {numeric[2]}, 0)"

    info = ROOT / "packaging" / "version_info.txt"
    text = info.read_text(encoding="utf-8")
    text = re.sub(r"filevers=\([^)]*\)", f"filevers={tuple_version}", text)
    text = re.sub(r"prodvers=\([^)]*\)", f"prodvers={tuple_version}", text)
    text = re.sub(r"StringStruct\(u'FileVersion', u'[^']*'\)", f"StringStruct(u'FileVersion', u'{version}')", text)
    text = re.sub(r"StringStruct\(u'ProductVersion', u'[^']*'\)", f"StringStruct(u'ProductVersion', u'{version}')", text)
    info.write_text(text, encoding="utf-8", newline="\n")

    replace_required(
        ROOT / "README.md",
        r"badge/version-[0-9]+\.[0-9]+\.[0-9]+-",
        f"badge/version-{version}-",
    )
    replace_required(
        ROOT / "README.md",
        r"ScrcpyDock-v[0-9]+\.[0-9]+\.[0-9]+-win64\.zip",
        f"ScrcpyDock-v{version}-win64.zip",
    )
    replace_required(
        ROOT / "docs" / "PUBLISHING.md",
        r"v[0-9]+\.[0-9]+\.[0-9]+",
        f"v{version}",
    )
    replace_required(
        ROOT / "docs" / "PUBLISHING.md",
        r"ScrcpyDock-v[0-9]+\.[0-9]+\.[0-9]+-win64\.zip",
        f"ScrcpyDock-v{version}-win64.zip",
    )
    print(version)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
