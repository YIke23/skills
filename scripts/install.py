#!/usr/bin/env python3
"""作業中のスキル1本を ~/.claude/skills へ写す / 消す。

    python3 scripts/install.py install <name>
    python3 scripts/install.py uninstall <name>

~/.claude/skills は完成品の置き場ではなく、書いている途中の1本を置く作業場。
全件コピーは作らない（プラグイン版と二重に並ぶため）。
"""
import shutil, sys, pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent
WORKSPACE = pathlib.Path.home() / ".claude" / "skills"


def die(msg):
    print(f"ERROR {msg}", file=sys.stderr)
    sys.exit(1)


def resolve_name(name):
    """フォルダ名として安全な単一要素であることを確かめる。"""
    if not name:
        die("name= が空。使い方: make install name=<skill>")
    if name in (".", "..") or "/" in name or "\\" in name or name.startswith("."):
        die(f"name={name!r} は不正。skills/ 直下のフォルダ名を1つだけ渡す")
    return name


def dest_for(name):
    """WORKSPACE の直下であることを保証したうえで宛先を返す。"""
    dest = WORKSPACE / name
    if dest.parent.resolve(strict=False) != WORKSPACE.resolve(strict=False):
        die(f"{dest} が {WORKSPACE} の直下にならない")
    return dest


def install(name):
    src = ROOT / "skills" / name
    if not (src / "SKILL.md").is_file():
        avail = ", ".join(sorted(d.name for d in (ROOT / "skills").iterdir() if d.is_dir()))
        die(f"skills/{name}/SKILL.md がない。あるのは: {avail}")

    dest = dest_for(name)
    WORKSPACE.mkdir(parents=True, exist_ok=True)
    if dest.is_symlink():
        die(f"{dest} は symlink。手で外してからやり直す")
    replaced = dest.exists()
    if replaced:
        shutil.rmtree(dest)
    shutil.copytree(src, dest)

    print(f"{'更新' if replaced else 'コピー'} skills/{name} → {dest}")
    print("Claude Code を再起動して、実際に呼んで発火するか確かめる。")
    print(f"終わったら make uninstall name={name} で作業場を空に戻す。")


def uninstall(name):
    dest = dest_for(name)
    if dest.is_symlink():
        dest.unlink()
        print(f"symlink を外した {dest}")
        return
    if not dest.exists():
        print(f"skip {dest} は無い（すでに空）")
        return
    if not dest.is_dir():
        die(f"{dest} がフォルダではない。手で確かめる")
    shutil.rmtree(dest)
    print(f"削除 {dest}")

    rest = sorted(p.name for p in WORKSPACE.iterdir()) if WORKSPACE.is_dir() else []
    if rest:
        print(f"WARN 作業場に残っている: {', '.join(rest)}")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        die("使い方: python3 scripts/install.py {install|uninstall} <name>")
    cmd, raw = sys.argv[1], sys.argv[2].strip()
    name = resolve_name(raw)
    if cmd == "install":
        install(name)
    elif cmd == "uninstall":
        uninstall(name)
    else:
        die(f"不明なコマンド: {cmd}")
