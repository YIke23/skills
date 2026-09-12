#!/usr/bin/env python3
"""この Mac で Claude Code に生えているスキルを全系統から集め、GitHub との差分を付けて JSON で吐く。

    python3 collect_inventory.py                    # 差分あり（git fetch する）
    python3 collect_inventory.py --no-fetch         # ネットワークに出ない。手元の情報だけ
    python3 collect_inventory.py --cwd /path/to/proj  # プロジェクトスキルを見る基準

標準ライブラリだけで動く。**読み取り専用。** `git fetch` 以外はディスクにも
リモートにも一切書かない。`plugin update` も `marketplace update` もしない
（どちらも「今どれだけ遅れているか」を消してしまうため。判断はユーザーに残す）。

## なぜスクリプトなのか

スキルの出自は3系統あり、そのどれもが違う場所・違う形式で版を持っている。
CLI プラグインは git SHA、デスクトップのプラグインは semver、組み込みは本体の版。
手で追うと必ずどこかを取りこぼすうえ、次に挙げる罠を毎回踏み直すことになる。

## 踏んではいけない罠（すべて実測で確認済み）

1. **`claude plugin list` はデスクトップアプリ側を1件も返さない。**
   `anthropic-skills:*` や `design:*` は `~/Library/Application Support/Claude/
   local-agent-mode-sessions/` 配下にしか実体が無い。CLI だけ見ると半分以上落ちる。

2. **キャッシュ配下の `skills/` を数えても意味がない。** marketplace の
   `source: "./"` はリポジトリ全体を展開するので、実際には生えないスキルの
   ディレクトリまで並ぶ。実際に生えるのは `.claude-plugin/marketplace.json` の
   `skills` 配列が選んだものだけ。これを無視すると数が倍近くに膨らむ。

3. **`plugin list --json` の `version` は semver ではなく marketplace リポジトリの
   コミット SHA。** だから「導入済みが marketplace の HEAD より何コミット遅れているか」を
   git で正確に計算できる。逆に semver として比較しようとすると何も分からない。

4. **`marketplace update` 済みでも導入済みプラグインの版は切り替わらない。**
   キャッシュには新コミットが展開されているのに `installed_plugins.json` は古い SHA を
   指したまま。つまり「marketplace は GitHub と同期しているのにプラグインが古い」が
   正常に起こりうる状態で、marketplace 側の ahead/behind だけ見ていると見逃す。

5. **`local-agent-mode-sessions` のパス順は系統ごとに入れ替わる。**
   rpm 側は `<A>/<B>/rpm/`、skills-plugin 側は `skills-plugin/<B>/<A>/` になっている。
   決め打ちで組み立てると片方が空振りするので、glob で探す。

6. **組み込みスキルはディスクに SKILL.md を持たない**（本体バイナリに埋まっている）。
   だからこのスクリプトは組み込みを列挙できない。そこはセッション側の一覧が正で、
   呼び出し側が補う。ここで空リストを返すのは「無い」ではなく「ここでは分からない」。

7. **スキルを1本も持たないプラグインがある。** `commit-commands` は `commands/*.md`
   だけを配る。セッションの一覧にはスキルと並んで出てくるので、`skills/` しか
   見ないと「使えるのに表に無い」ことになる。だから両方を `kind` で区別して集める。

出力は JSON 1個。キーの意味は同ディレクトリの SKILL.md を見ること。
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

HOME = Path.home()
CLAUDE_DIR = HOME / ".claude"
DESKTOP_SESSIONS = (HOME / "Library" / "Application Support" / "Claude"
                    / "local-agent-mode-sessions")

# スキルディレクトリの中身を比較するとき、差分として意味を持たないもの。
IGNORED_NAMES = {".DS_Store", ".in_use", "__pycache__", ".git", ".pytest_cache"}
IGNORED_SUFFIXES = {".pyc", ".pyo"}

TIMEOUT_LOCAL = 30
TIMEOUT_NET = 90


# --- 下請け -------------------------------------------------------------

def run(cmd: list[str], cwd: Path | None = None, timeout: int = TIMEOUT_LOCAL
        ) -> tuple[int, str, str]:
    """外部コマンドを叩く。落ちても例外にしない（欠けた情報は欠けたと報告する）。"""
    try:
        p = subprocess.run(cmd, cwd=str(cwd) if cwd else None, timeout=timeout,
                           capture_output=True, text=True, stdin=subprocess.DEVNULL)
        return p.returncode, p.stdout, p.stderr
    except FileNotFoundError as e:
        return 127, "", str(e)
    except subprocess.TimeoutExpired:
        return 124, "", f"timeout after {timeout}s"
    except Exception as e:                                  # noqa: BLE001
        return 1, "", str(e)


def claude_bin() -> str | None:
    """claude CLI の実体。PATH に無い Mac が普通にあるので $CLAUDE_CODE_EXECPATH を優先する。"""
    exec_path = os.environ.get("CLAUDE_CODE_EXECPATH")
    if exec_path and Path(exec_path).exists():
        return exec_path
    for cand in (CLAUDE_DIR / "local" / "claude", Path("/usr/local/bin/claude")):
        if cand.exists():
            return str(cand)
    code, out, _ = run(["which", "claude"])
    return out.strip() if code == 0 and out.strip() else None


def claude_json(binary: str | None, args: list[str]) -> object | None:
    if not binary:
        return None
    code, out, _ = run([binary, *args])
    if code != 0 or not out.strip():
        return None
    try:
        return json.loads(out)
    except json.JSONDecodeError:
        return None


def read_json(path: Path) -> object | None:
    try:
        return json.loads(path.read_text(encoding="utf-8", errors="replace"))
    except Exception:                                       # noqa: BLE001
        return None


def frontmatter(skill_md: Path) -> dict:
    """SKILL.md 冒頭の YAML から name / description / version /
    disable-model-invocation だけ拾う。

    YAML パーサは標準ライブラリに無い。ここで欲しいのは3フィールドだけなので、
    依存を足すより行を読む。複数行の折り返し（`>-` や字下げ継続）に対応する。
    """
    try:
        text = skill_md.read_text(encoding="utf-8", errors="replace")
    except Exception:                                       # noqa: BLE001
        return {}
    if not text.startswith("---"):
        return {}
    end = text.find("\n---", 3)
    if end == -1:
        return {}
    out: dict[str, str] = {}
    key = None
    for raw in text[3:end].splitlines():
        m = re.match(r"^([A-Za-z_][\w-]*)\s*:\s*(.*)$", raw)
        if m:
            key = m.group(1)
            val = m.group(2).strip()
            if val in (">", ">-", "|", "|-", ""):
                val = ""
            out[key] = val.strip("'\"")
        elif key and raw.strip() and raw[:1] in " \t":
            out[key] = (out[key] + " " + raw.strip()).strip()
        elif not raw.strip():
            continue
        else:
            key = None
    return {k: out.get(k, "")
            for k in ("name", "description", "version", "disable-model-invocation")}


def skill_dirs(root: Path) -> list[Path]:
    if not root.is_dir():
        return []
    return sorted(d for d in root.iterdir()
                  if d.is_dir() and (d / "SKILL.md").is_file())


def file_map(root: Path) -> dict[str, str]:
    """スキルディレクトリ配下の相対パス → 中身の sha256（先頭12桁）。

    ファイル構成の差と、同名ファイルの中身の差を、両方1回の走査で出せるようにする。
    """
    out: dict[str, str] = {}
    if not root.is_dir():
        return out
    for p in root.rglob("*"):
        if not p.is_file() or p.is_symlink():
            continue
        parts = set(p.relative_to(root).parts)
        if parts & IGNORED_NAMES or p.suffix in IGNORED_SUFFIXES:
            continue
        try:
            digest = hashlib.sha256(p.read_bytes()).hexdigest()[:12]
        except Exception:                                   # noqa: BLE001
            digest = "unreadable"
        out[str(p.relative_to(root))] = digest
    return out


def describe(skill_md: Path) -> dict:
    fm = frontmatter(skill_md)
    d = (fm.get("description") or "").strip()
    # disable-model-invocation: true のスキルはモデルの一覧に出ない。
    # ディスクにはあるが自分からは呼べないので、件数に混ぜると偽陽性になる。
    manual = str(fm.get("disable-model-invocation", "")).lower() in ("true", "yes", "1")
    return {"declared_name": fm.get("name") or "",
            "description": d,
            "description_short": (d[:140] + "…") if len(d) > 140 else d,
            "manual_only": manual}


def command_files(root: Path) -> list[Path]:
    """プラグインが配るスラッシュコマンド。`commands/*.md`。

    スキルを持たず commands だけのプラグインがある（罠7）ので、これも集める。
    """
    if not root.is_dir():
        return []
    return sorted(p for p in root.glob("*.md") if p.is_file())


# --- marketplace（GitHub との接点） -------------------------------------

def git(repo: Path, args: list[str], timeout: int = TIMEOUT_LOCAL) -> str | None:
    code, out, _ = run(["git", *args], cwd=repo, timeout=timeout)
    return out.strip() if code == 0 else None


def collect_marketplaces(binary: str | None, do_fetch: bool) -> list[dict]:
    """設定済み marketplace ごとに、GitHub 側との位置関係を出す。

    ここが「GitHub 上の正」に触る唯一の場所。marketplace のクローンが
    リモートより遅れているかどうかを ahead/behind で出す。**fetch しかしない。**
    """
    raw = claude_json(binary, ["plugin", "marketplace", "list", "--json"]) or []
    out = []
    for mp in raw if isinstance(raw, list) else []:
        loc = Path(mp.get("installLocation", "")) if mp.get("installLocation") else None
        entry = {
            "name": mp.get("name"),
            "source": mp.get("source"),
            "remote": mp.get("url") or mp.get("repo"),
            "install_location": str(loc) if loc else None,
            "is_git": bool(loc and (loc / ".git").exists()),
            "head_sha": None, "upstream": None,
            "ahead": None, "behind": None,
            "fetched": False, "sync_note": None,
            "dirty": None,
            "plugins_declared": [],
        }

        if entry["is_git"] and loc:
            entry["head_sha"] = git(loc, ["rev-parse", "HEAD"])
            entry["upstream"] = git(loc, ["rev-parse", "--abbrev-ref", "@{u}"])
            status = git(loc, ["status", "--porcelain"])
            entry["dirty"] = bool(status) if status is not None else None
            if do_fetch:
                code, _, err = run(["git", "fetch", "--quiet"], cwd=loc,
                                   timeout=TIMEOUT_NET)
                entry["fetched"] = code == 0
                if code != 0:
                    entry["sync_note"] = f"fetch 失敗: {err.strip()[:160]}"
            else:
                entry["sync_note"] = "--no-fetch。ahead/behind は最後の fetch 時点の値"
            counts = git(loc, ["rev-list", "--left-right", "--count", "HEAD...@{u}"])
            if counts and len(counts.split()) == 2:
                entry["ahead"], entry["behind"] = (int(x) for x in counts.split())
            elif entry["upstream"] is None:
                entry["sync_note"] = (entry["sync_note"] or
                                      "upstream 未設定。GitHub との比較ができない")

            mj = read_json(loc / ".claude-plugin" / "marketplace.json")
            if isinstance(mj, dict):
                for p in mj.get("plugins", []) or []:
                    if isinstance(p, dict) and p.get("name"):
                        entry["plugins_declared"].append({
                            "name": p["name"],
                            "skill_paths": [s for s in (p.get("skills") or [])
                                            if isinstance(s, str)],
                        })
        out.append(entry)
    return out


def active_skill_names(cache_root: Path, plugin_name: str) -> list[str] | None:
    """そのプラグインが実際に生やすスキル名。キャッシュ配下の marketplace.json が正。

    `source: "./"` の marketplace はリポジトリ全体を展開するので、
    `<cache>/skills/` を数えると生えないスキルまで混ざる。実際に生えるのは
    `skills` 配列が選んだものだけなので、そこから名前を取る。
    配列が無い（= ディレクトリ規約に任せている）marketplace では None を返し、
    呼び出し側にディレクトリ走査へ落ちてもらう。
    """
    mj = read_json(cache_root / ".claude-plugin" / "marketplace.json")
    if not isinstance(mj, dict):
        return None
    for p in mj.get("plugins", []) or []:
        if isinstance(p, dict) and p.get("name") == plugin_name:
            paths = [s for s in (p.get("skills") or []) if isinstance(s, str)]
            return [Path(s.rstrip("/")).name for s in paths] or None
    return None


def plugin_drift(mp: dict | None, cache_sha: str | None,
                 skill_paths: list[str]) -> dict:
    """導入済みプラグインが marketplace の HEAD からどれだけ遅れているか。

    罠4 がここ。marketplace が GitHub と同期していても、導入済みは古い SHA を
    指したままでいられる。だから marketplace の ahead/behind とは別に、
    キャッシュの SHA を HEAD と突き合わせる必要がある。
    """
    d = {"state": "unknown", "commits_behind": None,
         "changed_paths": [], "note": None}
    if not mp or not mp.get("is_git") or not mp.get("install_location"):
        d["note"] = "marketplace が git クローンではないため比較できない"
        return d
    if not cache_sha:
        d["note"] = "導入済みバージョンが取れなかった"
        return d

    repo = Path(mp["install_location"])
    head = mp.get("head_sha")
    if head and head.startswith(cache_sha):
        d["state"] = "current"
        return d

    if git(repo, ["cat-file", "-e", f"{cache_sha}^{{commit}}"]) is None:
        d["state"] = "unrelated"
        d["note"] = (f"導入済みの {cache_sha} が marketplace のクローンに無い。"
                     "改名・URL 変更後に入れ直していない可能性がある")
        return d

    count = git(repo, ["rev-list", "--count", f"{cache_sha}..HEAD"])
    d["commits_behind"] = int(count) if count and count.isdigit() else None
    d["state"] = "behind" if d["commits_behind"] else "current"

    # そのコミット差が、このプラグインの中身に本当に触れているか。
    # 触れていなければ「遅れているが実害なし」で、更新の優先度が下がる。
    if skill_paths and d["commits_behind"]:
        rel = [s.lstrip("./") for s in skill_paths]
        changed = git(repo, ["diff", "--name-only", f"{cache_sha}..HEAD", "--", *rel])
        d["changed_paths"] = sorted(set(changed.splitlines())) if changed else []
        if not d["changed_paths"]:
            d["note"] = ("marketplace は進んでいるが、このプラグインが配るスキルの"
                         "ファイルは変わっていない")
    return d


# --- 系統ごとの収集 -----------------------------------------------------

def collect_cli_plugins(binary: str | None, marketplaces: list[dict]
                        ) -> tuple[list[dict], list[dict]]:
    """CLI のプラグイン（`~/.claude/plugins/`）とそこから生えるスキル。"""
    installed = claude_json(binary, ["plugin", "list", "--json"]) or []
    by_name = {m["name"]: m for m in marketplaces if m.get("name")}
    plugins, skills = [], []

    for p in installed if isinstance(installed, list) else []:
        pid = p.get("id") or ""
        name, _, mp_name = pid.partition("@")
        cache = Path(p["installPath"]) if p.get("installPath") else None
        mp = by_name.get(mp_name)
        active = active_skill_names(cache, name) if cache else None
        found = skill_dirs(cache / "skills") if cache else []
        if active is not None:
            found = [d for d in found if d.name in active]

        skill_paths: list[str] = []
        if mp:
            for decl in mp.get("plugins_declared", []):
                if decl["name"] == name:
                    skill_paths = decl["skill_paths"]

        cmds = command_files(cache / "commands") if cache else []
        drift = plugin_drift(mp, p.get("version"), skill_paths)
        plugins.append({
            "origin": "cli-plugin",
            "id": pid, "name": name, "marketplace": mp_name,
            "version": p.get("version"), "version_kind": "git-sha",
            "enabled": p.get("enabled"), "scope": p.get("scope"),
            "install_path": str(cache) if cache else None,
            "installed_at": p.get("installedAt"),
            "last_updated": p.get("lastUpdated"),
            "skill_count": len(found), "command_count": len(cmds),
            "drift": drift,
        })
        common = {"origin": "cli-plugin", "plugin": name, "marketplace": mp_name,
                  "drift_state": drift["state"], "drift_note": drift.get("note")}
        for d in found:
            skills.append({
                "kind": "skill", "name": d.name, "namespace": f"{name}:{d.name}",
                "path": str(d), "invocable_as": f"/{name}:{d.name}",
                **common, **describe(d / "SKILL.md"),
            })
        for f in cmds:
            skills.append({
                "kind": "command", "name": f.stem, "namespace": f"{name}:{f.stem}",
                "path": str(f), "invocable_as": f"/{name}:{f.stem}",
                **common, **describe(f),
            })
    return plugins, skills


def newest_session_dirs() -> list[Path]:
    """デスクトップのセッション作業ディレクトリ。古い残骸も混ざるので mtime 順。"""
    if not DESKTOP_SESSIONS.is_dir():
        return []
    return sorted((d for d in DESKTOP_SESSIONS.iterdir()
                   if d.is_dir() and d.name != "skills-plugin"),
                  key=lambda p: p.stat().st_mtime, reverse=True)


def collect_desktop_plugins() -> tuple[list[dict], list[dict], list[str]]:
    """デスクトップアプリのプラグイン。`claude plugin list` には**出てこない**系統。"""
    plugins, skills, notes = [], [], []
    rpms = sorted(DESKTOP_SESSIONS.glob("*/*/rpm"),
                  key=lambda p: p.stat().st_mtime, reverse=True) \
        if DESKTOP_SESSIONS.is_dir() else []
    if not rpms:
        return plugins, skills, notes
    if len(rpms) > 1:
        notes.append(f"デスクトップのセッション作業ディレクトリが {len(rpms)} 組ある。"
                     "最新のものだけを現役として読んだ（残りは過去セッションの残骸）")

    rpm = rpms[0]
    manifest = read_json(rpm / "manifest.json")
    meta = {}
    if isinstance(manifest, dict):
        for p in manifest.get("plugins", []) or []:
            if isinstance(p, dict) and p.get("id"):
                meta[p["id"]] = p

    for pdir in sorted(rpm.glob("plugin_*")):
        pj = read_json(pdir / ".claude-plugin" / "plugin.json") or {}
        info = meta.get(pdir.name, {})
        name = (pj.get("name") if isinstance(pj, dict) else None) \
            or info.get("name") or pdir.name
        found = skill_dirs(pdir / "skills")
        cmds = command_files(pdir / "commands")
        plugins.append({
            "origin": "desktop-plugin",
            "id": pdir.name, "name": name,
            "display_name": info.get("displayName"),
            "marketplace": info.get("marketplaceName"),
            "version": (pj.get("version") if isinstance(pj, dict) else None),
            "version_kind": "semver",
            "enabled": True, "scope": "desktop",
            "install_path": str(pdir),
            "installed_at": None,
            "last_updated": info.get("updatedAt"),
            "skill_count": len(found), "command_count": len(cmds),
            "drift": {"state": "not-comparable", "commits_behind": None,
                      "changed_paths": [],
                      "note": ("デスクトップアプリがアカウント経由で配る系統。"
                               "手元に git クローンが無いため GitHub との差分は取れない。"
                               "更新はアプリ側が行う")},
        })
        common = {"origin": "desktop-plugin", "plugin": name,
                  "marketplace": info.get("marketplaceName"),
                  "drift_state": "not-comparable", "drift_note": None}
        for d in found:
            skills.append({
                "kind": "skill", "name": d.name, "namespace": f"{name}:{d.name}",
                "path": str(d), "invocable_as": f"/{name}:{d.name}",
                **common, **describe(d / "SKILL.md"),
            })
        for f in cmds:
            skills.append({
                "kind": "command", "name": f.stem, "namespace": f"{name}:{f.stem}",
                "path": str(f), "invocable_as": f"/{name}:{f.stem}",
                **common, **describe(f),
            })
    return plugins, skills, notes


def collect_desktop_managed() -> tuple[list[dict], list[dict]]:
    """claude.ai 側で有効化したスキル。`anthropic-skills` 合成プラグインとして届く。

    ディレクトリには有効化していないスキルも置かれていることがあるので、
    現役の判定は manifest.json の `skills` 配列を正とする。
    """
    roots = sorted((DESKTOP_SESSIONS / "skills-plugin").glob("*/*"),
                   key=lambda p: p.stat().st_mtime, reverse=True) \
        if (DESKTOP_SESSIONS / "skills-plugin").is_dir() else []
    if not roots:
        return [], []
    root = roots[0]
    pj = read_json(root / ".claude-plugin" / "plugin.json") or {}
    name = (pj.get("name") if isinstance(pj, dict) else None) or "anthropic-skills"

    manifest = read_json(root / "manifest.json")
    listed = None
    if isinstance(manifest, dict) and isinstance(manifest.get("skills"), list):
        listed = {s.get("name") for s in manifest["skills"]
                  if isinstance(s, dict) and s.get("name")}

    found = skill_dirs(root / "skills")
    active = [d for d in found if listed is None or d.name in listed]
    dormant = sorted(d.name for d in found if listed is not None
                     and d.name not in listed)

    plugin = {
        "origin": "desktop-managed",
        "id": name, "name": name, "display_name": None,
        "marketplace": "claude.ai アカウント設定",
        "version": (pj.get("version") if isinstance(pj, dict) else None),
        "version_kind": "semver",
        "enabled": True, "scope": "desktop",
        "install_path": str(root),
        "installed_at": None,
        "last_updated": None,
        "skill_count": len(active), "command_count": 0,
        "dormant_on_disk": dormant,
        "drift": {"state": "not-comparable", "commits_behind": None,
                  "changed_paths": [],
                  "note": ("claude.ai のスキル設定で有効化したものを、アプリが1個の"
                           "合成プラグインにまとめて渡している。手元に git クローンが"
                           "無いため GitHub との差分は取れない")},
    }
    skills = [{
        "kind": "skill", "name": d.name, "namespace": f"{name}:{d.name}",
        "origin": "desktop-managed", "plugin": name,
        "marketplace": "claude.ai アカウント設定",
        "path": str(d), "invocable_as": f"/{name}:{d.name}",
        "drift_state": "not-comparable", "drift_note": None,
        **describe(d / "SKILL.md"),
    } for d in active]
    return [plugin], skills


def collect_loose_skills(cwd: Path) -> list[dict]:
    """名前空間の付かないもの。ユーザースキルとプロジェクトスキル、およびコマンド。

    素の名前で候補に出るのはこの系統と組み込みだけ。プラグイン由来は必ず
    名前空間が付くので、一覧では名前の形が出自の手掛かりになる。
    """
    out = []
    # ホーム直下で作業していると project 側の探索先が user 側と同じ実体になる。
    # 素直に2回走らせると同じスキルが2行になり、重複ロードの誤検知にもなる。
    def roots(sub: str) -> list[tuple[Path, str]]:
        user, proj = CLAUDE_DIR / sub, cwd / ".claude" / sub
        pairs = [(user, "user")]
        same = (proj.resolve() == user.resolve()) if proj.exists() else (proj == user)
        if not same:
            pairs.append((proj, "project"))
        return pairs

    for root, origin in roots("skills"):
        for d in skill_dirs(root):
            out.append({
                "kind": "skill",
                "name": d.name, "namespace": d.name, "origin": origin,
                "plugin": None, "marketplace": None,
                "path": str(d), "invocable_as": f"/{d.name}",
                "drift_state": "pending", "drift_note": None,
                **describe(d / "SKILL.md"),
            })
    for root, origin in roots("commands"):
        for f in command_files(root):
            out.append({
                "kind": "command",
                "name": f.stem, "namespace": f.stem, "origin": origin,
                "plugin": None, "marketplace": None,
                "path": str(f), "invocable_as": f"/{f.stem}",
                "drift_state": "not-comparable", "drift_note": None,
                **describe(f),
            })
    return out


# --- ローカル手コピーと GitHub の構成差 ---------------------------------

def compare_loose(loose: list[dict], marketplaces: list[dict],
                  plugin_skills: list[dict]) -> list[dict]:
    """`~/.claude/skills` に手で置いたスキルを、GitHub 側の同名スキルと突き合わせる。

    ここが T2 の公式手段に無い部分。`plugin list` はプラグインの版しか見ないので、
    「リポジトリには参照ファイルがあるのに、手元のコピーは SKILL.md だけ」という
    状態を**同期済みに見せてしまう**。ファイル単位で比べないと捕まらない。

    照合先は marketplace のクローンに加えて、ユーザーの作業クローン（`~/dev/skills`）。
    marketplace のクローンは `plugin marketplace update` を打つまで更新されないので、
    そちらだけを基準にすると「手元が古い」と「クローンが古い」を取り違える。
    作業クローンの方が新しいことがあるため、両方を候補に出して origin を添える。
    見つからなければ、そのスキルは追跡対象外（手元だけの存在）と報告する。
    """
    refs: dict[str, list[dict]] = {}

    # ユーザーの作業クローン。存在しない Mac もあるので、無ければ黙って飛ばす。
    for wc in (Path.home() / "dev" / "skills",):
        if not (wc / ".git").is_dir():
            continue
        _, head, _ = run(["git", "-C", str(wc), "rev-parse", "--short", "HEAD"])
        _, porcelain, _ = run(["git", "-C", str(wc), "status", "--porcelain"])
        _, origin, _ = run(["git", "-C", str(wc), "remote", "get-url", "origin"])
        # 取得のみ。作業ツリーには触らない。
        run(["git", "-C", str(wc), "fetch", "--quiet", "origin"], timeout=TIMEOUT_NET)
        _, counts, _ = run(["git", "-C", str(wc), "rev-list", "--left-right",
                            "--count", "HEAD...@{upstream}"])
        try:
            ahead, behind = (int(x) for x in counts.split())
        except ValueError:
            ahead = behind = None
        for d in skill_dirs(wc / "skills"):
            refs.setdefault(d.name, []).append({
                "path": d, "marketplace": "(作業クローン)",
                "remote": origin.strip(), "head_sha": head.strip(),
                "behind": behind, "ahead": ahead,
                "is_working_clone": True, "dirty": bool(porcelain.strip()),
            })

    for mp in marketplaces:
        loc = mp.get("install_location")
        if not loc or not mp.get("is_git"):
            continue
        for d in skill_dirs(Path(loc) / "skills"):
            refs.setdefault(d.name, []).append({
                "path": d, "marketplace": mp.get("name"),
                "remote": mp.get("remote"), "head_sha": mp.get("head_sha"),
                "behind": mp.get("behind"),
            })

    by_name: dict[str, list[dict]] = {}
    for s in plugin_skills:
        if s.get("kind") == "skill":
            by_name.setdefault(s["name"], []).append(s)

    report = []
    for s in loose:
        # コマンドは単一ファイルで、ディレクトリ構成の比較という概念が無い。
        if s.get("kind") != "skill":
            continue
        also = [x["namespace"] for x in by_name.get(s["name"], [])]
        cands = refs.get(s["name"], [])
        row = {
            "name": s["name"], "origin": s["origin"], "local_path": s["path"],
            "reference": None, "remote": None, "reference_head_sha": None,
            "state": "untracked",
            "missing_files": [], "extra_files": [], "differing_files": [],
            "also_loaded_as": also,
            "note": None,
        }
        if not cands:
            row["note"] = ("同名のスキルがどの marketplace クローンにも無い。"
                           "手元だけの存在なので GitHub との比較対象が無い")
            report.append(row)
            continue

        # GitHub が正。ずれていないクローンほど基準として信頼できるので、
        # (遅れ, 進み, 未コミットの変更) が小さい順に採る。
        def _rank(c: dict) -> tuple:
            return ((c.get("behind") or 0), (c.get("ahead") or 0),
                    1 if c.get("dirty") else 0)

        cands = sorted(cands, key=_rank)
        ref = cands[0]
        local, remote = file_map(Path(s["path"])), file_map(ref["path"])
        row.update({
            "reference": str(ref["path"]), "remote": ref["remote"],
            "reference_head_sha": ref["head_sha"],
            "missing_files": sorted(set(remote) - set(local)),
            "extra_files": sorted(set(local) - set(remote)),
            "differing_files": sorted(k for k in set(local) & set(remote)
                                      if local[k] != remote[k]),
        })
        if len(cands) > 1:
            row["note"] = (f"同名の参照元が {len(cands)} 箇所にある。"
                           f"{ref['marketplace']} を採った")
        if ref.get("is_working_clone"):
            bits = []
            if ref.get("ahead"):
                bits.append(f"origin より {ref['ahead']} コミット進んでいる（未 push）")
            if ref.get("dirty"):
                bits.append("未コミットの変更がある")
            if bits:
                row["note"] = ((row["note"] + " / ") if row["note"] else "") + \
                    ("照合先の作業クローンは " + "、".join(bits) +
                     "。GitHub 上の正とは一致していない")
        if row["missing_files"] or row["differing_files"] or row["extra_files"]:
            row["state"] = "diverged"
        else:
            row["state"] = "in-sync"
        if ref.get("behind"):
            row["note"] = ((row["note"] + " / ") if row["note"] else "") + \
                (f"参照元のクローン自体が GitHub より {ref['behind']} コミット遅れている。"
                 "比較の基準が最新ではない")
        report.append(row)
    return report


def find_shadowed(marketplaces: list[dict], plugins: list[dict],
                  loose: list[dict]) -> list[dict]:
    """プラグインとして配られているのに、手元のコピーの方が使われているスキル。

    これは「入れていない marketplace のプラグイン」全部ではない。公式 marketplace の
    カタログを丸ごと並べると数十行になって、本当の事故が埋もれる。
    ここが見たいのは**同じスキルが両方に存在する**場合だけ。

    典型はこれ。試作のために `~/.claude/skills/` に置いたスキルをリポジトリへ移した後、
    手元のコピーを消し忘れる。プラグインを入れていないので名前空間が付かず、
    一見ふつうのユーザースキルに見えるが、実体は GitHub 側から取り残された古い枝になる。
    """
    have = {(p.get("marketplace"), p.get("name")) for p in plugins}
    loose_names = {s["name"] for s in loose if s.get("kind") == "skill"}
    out = []
    for mp in marketplaces:
        for decl in mp.get("plugins_declared", []):
            if (mp.get("name"), decl["name"]) in have:
                continue
            names = [Path(s.rstrip("/")).name for s in decl["skill_paths"]]
            overlap = sorted(set(names) & loose_names)
            if not overlap:
                continue
            out.append({
                "plugin": decl["name"], "marketplace": mp.get("name"),
                "remote": mp.get("remote"),
                "skills": names,
                "also_loose_on_disk": overlap,
                "install_hint": f"plugin install {decl['name']}@{mp.get('name')}",
            })
    return out


# --- 入口 ---------------------------------------------------------------

def main() -> int:
    ap = argparse.ArgumentParser(
        description="Claude Code のスキルを全系統から集め、GitHub との差分を付ける")
    ap.add_argument("--cwd", type=Path, default=Path.cwd(),
                    help="プロジェクトスキルを探す基準（既定はカレント）")
    ap.add_argument("--no-fetch", action="store_true",
                    help="git fetch しない。ahead/behind は最後の fetch 時点の値になる")
    ap.add_argument("-o", "--out", type=Path, help="JSON の書き出し先（既定は標準出力）")
    args = ap.parse_args()

    binary = claude_bin()
    notes: list[str] = []
    if not binary:
        notes.append("claude CLI が見つからない（$CLAUDE_CODE_EXECPATH も未設定）。"
                     "CLI プラグインと marketplace の情報が丸ごと欠ける")

    marketplaces = collect_marketplaces(binary, not args.no_fetch)
    cli_plugins, cli_skills = collect_cli_plugins(binary, marketplaces)
    desk_plugins, desk_skills, desk_notes = collect_desktop_plugins()
    managed_plugins, managed_skills = collect_desktop_managed()
    notes += desk_notes

    loose = collect_loose_skills(args.cwd)
    plugin_skills = cli_skills + desk_skills + managed_skills
    loose_drift = compare_loose(loose, marketplaces, plugin_skills)

    by_state = {r["name"]: r["state"] for r in loose_drift}
    for s in loose:
        if s.get("kind") == "skill":
            s["drift_state"] = by_state.get(s["name"], "pending")

    skills = plugin_skills + loose
    # 同名が複数系統から同時にロードされている状態。名前空間まで一致することもある
    # （CLI とデスクトップに同じ名前のプラグインが入っている場合）ので、
    # 名前空間だけを並べても区別が付かない。出自とパスまで持たせる。
    dupes: dict[str, list[dict]] = {}
    for s in skills:
        dupes.setdefault(f"{s['kind']}:{s['name']}", []).append({
            "namespace": s["namespace"], "origin": s["origin"],
            "plugin": s.get("plugin"), "path": s["path"],
        })

    version = None
    if binary:
        m = re.search(r"claude-code/([^/]+)/", binary)
        if m:
            version = m.group(1)
        else:
            code, out, _ = run([binary, "--version"])
            version = out.strip() or None if code == 0 else None

    payload = {
        "collected_at": datetime.now(timezone.utc).astimezone().isoformat(),
        "host": {"cwd": str(args.cwd), "claude_code_version": version,
                 "claude_bin": binary, "fetched": not args.no_fetch},
        "builtin_skills": {
            "enumerable": False,
            "note": ("組み込みスキルは本体バイナリに埋まっており、ディスクに SKILL.md が"
                     "無いためここでは列挙できない。セッションで見えている一覧が正なので、"
                     "呼び出し側が補うこと。バージョンに追随するので差分の概念は無い"),
        },
        "marketplaces": marketplaces,
        "plugins": cli_plugins + desk_plugins + managed_plugins,
        "skills": sorted(skills, key=lambda s: (s["origin"], s["kind"], s["name"])),
        "loose_skill_drift": loose_drift,
        "shadowed_plugins": find_shadowed(marketplaces,
                                          cli_plugins + desk_plugins, loose),
        "duplicate_names": {k: v for k, v in sorted(dupes.items()) if len(v) > 1},
        "totals": {
            "entries": len(skills),
            # manual_only（disable-model-invocation: true）はモデルからは呼べないので
            # 呼べる件数から外す。台帳の行には残すが、別枠で数える。
            "skills": sum(1 for s in skills
                          if s["kind"] == "skill" and not s.get("manual_only")),
            "commands": sum(1 for s in skills
                            if s["kind"] == "command" and not s.get("manual_only")),
            "manual_only": sum(1 for s in skills if s.get("manual_only")),
            "by_origin": {o: sum(1 for s in skills if s["origin"] == o)
                          for o in sorted({s["origin"] for s in skills})},
            "plugins": len(cli_plugins) + len(desk_plugins) + len(managed_plugins),
            "marketplaces_behind": sum(1 for m in marketplaces if (m.get("behind") or 0)),
            "plugins_behind": sum(1 for p in cli_plugins
                                  if p["drift"]["state"] == "behind"),
            "loose_diverged": sum(1 for r in loose_drift if r["state"] == "diverged"),
        },
        "notes": notes,
    }

    text = json.dumps(payload, ensure_ascii=False, indent=2)
    if args.out:
        args.out.write_text(text, encoding="utf-8")
        t = payload["totals"]
        print(f"書き出した: {args.out}  "
              f"スキル {t['skills']} / コマンド {t['commands']} / "
              f"手動のみ {t['manual_only']} / "
              f"プラグイン {t['plugins']}  "
              f"（marketplace 遅れ {t['marketplaces_behind']} / "
              f"プラグイン遅れ {t['plugins_behind']} / "
              f"構成差 {t['loose_diverged']}）", file=sys.stderr)
    else:
        print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
