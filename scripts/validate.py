#!/usr/bin/env python3
"""push 前の自己点検。marketplace.json と各プラグインの構成、SKILL.md の整合を見る。

レイアウトは plugins/<plugin>/skills/<skill>/SKILL.md。
どのスキルがどのプラグインに属するかはフォルダ構造で決まる。
marketplace.json に skills 配列は書かない（配列を読まない実装があるため）。
"""
import json, pathlib, re, sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
PLUGINS = ROOT / "plugins"
errs, warns = [], []

market = json.loads((ROOT / ".claude-plugin" / "marketplace.json").read_text(encoding="utf-8"))

if (ROOT / "skills").is_dir():
    errs.append("リポジトリ直下に skills/ がある。スキルは plugins/<plugin>/skills/ に置く")

declared = set()
for p in market["plugins"]:
    name = p["name"]
    declared.add(name)
    if p.get("skills"):
        errs.append(f"{name}: marketplace.json に skills 配列がある。"
                    "claude.ai とデスクトップはこれを読まないので廃止した")
    if p.get("source") != f"./plugins/{name}":
        errs.append(f"{name}: source が ./plugins/{name} でない（{p.get('source')!r}）")
        continue
    pdir = PLUGINS / name
    if not pdir.is_dir():
        errs.append(f"{name}: plugins/{name}/ がない")
        continue
    pjson = pdir / ".claude-plugin" / "plugin.json"
    if not pjson.is_file():
        errs.append(f"{name}: plugins/{name}/.claude-plugin/plugin.json がない")
        continue
    meta = json.loads(pjson.read_text(encoding="utf-8"))
    if meta.get("name") != name:
        errs.append(f"{name}: plugin.json の name がフォルダ名と一致しない（{meta.get('name')!r}）")
    if meta.get("description") != p.get("description"):
        errs.append(f"{name}: plugin.json と marketplace.json で description が食い違う")
    if not (pdir / "skills").is_dir():
        warns.append(f"{name}: skills/ が無い（commands だけのプラグインなら正常）")

for pdir in sorted(d for d in PLUGINS.iterdir() if d.is_dir()) if PLUGINS.is_dir() else []:
    if pdir.name not in declared:
        errs.append(f"{pdir.name}: plugins/ にあるが marketplace.json に載っていない")

total = 0
for pdir in sorted(d for d in PLUGINS.iterdir() if d.is_dir()) if PLUGINS.is_dir() else []:
    sdir = pdir / "skills"
    if not sdir.is_dir():
        continue
    for d in sorted(x for x in sdir.iterdir() if x.is_dir()):
        total += 1
        f = d / "SKILL.md"
        if not f.is_file():
            errs.append(f"{pdir.name}/{d.name}: SKILL.md がない")
            continue
        text = f.read_text(encoding="utf-8")
        m = re.match(r"^---\n(.*?)\n---\n", text, re.S)
        if not m:
            errs.append(f"{d.name}: フロントマターがない")
            continue
        fm = m.group(1)
        name = re.search(r'^name:\s*"?([^"\n]+)"?', fm, re.M)
        if not name or name.group(1).strip() != d.name:
            errs.append(f"{d.name}: name がフォルダ名と一致しない")
        desc = re.search(r"^description:\s*(.+)", fm, re.S | re.M)
        if not desc:
            errs.append(f"{d.name}: description がない")
            continue
        body = re.split(r"\n[a-z-]+:", desc.group(1))[0]
        n = len(body.strip())
        if n > 1536:
            errs.append(f"{d.name}: description が {n} 字。1536 字で切られる")
        elif n > 1200:
            warns.append(f"{d.name}: description が {n} 字。上限 1536 に近い")

for w in warns:
    print(f"WARN  {w}")
for e in errs:
    print(f"ERROR {e}")
print(f"\nスキル {total} 本 / プラグイン {len(market['plugins'])} 個 / エラー {len(errs)} 件")
sys.exit(1 if errs else 0)
