#!/usr/bin/env python3
"""README の材料を、リポジトリの中身から機械的に拾い出す。

README に書くべき事実のうち、コードや設定ファイルから確実に言えるものを先に並べる。
書き手の記憶や「この手のプロジェクトは普通こうだ」という推測で README を書くと、
存在しないスクリプト名や、もう使っていない環境変数が紛れ込む。

拾うもの:
  - 既存の文書（README / CLAUDE.md / AGENTS.md / docs/ / CONTRIBUTING）
  - 実行系（package.json の scripts と engines、Makefile のターゲット、composer.json、
    pyproject.toml、docker compose のサービス、バージョン指定ファイル）
  - 環境変数（コードが読んでいる名前と、.env.example 類に載っている名前の突き合わせ）
  - 外部サービスの手掛かり（依存パッケージ名と設定ファイル）
  - CI とデプロイの設定ファイル
  - モバイルアプリの手掛かり（Expo / React Native / Flutter / Capacitor / ネイティブ、
    EAS のビルドプロファイル、fastlane の lane、版番号の置き場所、署名ファイルが git に入っていないか）
  - git の remote と、直近1年のコミット数上位（問い合わせ先の候補）

**.env 本体は開かない。** 開くのは名前に example / sample / template / dist を含む雛形だけ。
値は一切出力しない（名前だけ）。

使い方:
    python3 scan_repo.py <リポジトリのパス> [--json]
"""

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

SKIP_DIRS = {
    ".git", "node_modules", "vendor", ".next", "dist", "build", "out", "coverage",
    ".venv", "venv", "__pycache__", ".turbo", ".cache", "storybook-static",
    ".nuxt", ".svelte-kit", "target", ".idea", ".vscode", "tmp", "public",
}
CODE_EXT = {
    ".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs", ".vue", ".svelte", ".py", ".rb",
    ".php", ".go", ".rs", ".java", ".kt", ".swift", ".sh", ".yml", ".yaml", ".toml",
}
MAX_FILES = 6000
MAX_BYTES = 400_000

ENV_TEMPLATE = re.compile(r"^\.env.*\.(example|sample|template|dist)$|^\.envrc\.example$|^env\.example$", re.I)

ENV_PATTERNS = [
    re.compile(r"process\.env\.([A-Z][A-Z0-9_]+)"),
    re.compile(r"process\.env\[\s*['\"]([A-Z][A-Z0-9_]+)['\"]\s*\]"),
    re.compile(r"import\.meta\.env\.([A-Z][A-Z0-9_]+)"),
    re.compile(r"Deno\.env\.get\(\s*['\"]([A-Z][A-Z0-9_]+)['\"]"),
    re.compile(r"os\.environ(?:\.get)?\(\s*['\"]([A-Z][A-Z0-9_]+)['\"]"),
    re.compile(r"os\.environ\[\s*['\"]([A-Z][A-Z0-9_]+)['\"]\s*\]"),
    re.compile(r"os\.getenv\(\s*['\"]([A-Z][A-Z0-9_]+)['\"]"),
    re.compile(r"\benv\(\s*['\"]([A-Z][A-Z0-9_]+)['\"]"),          # Laravel
    re.compile(r"getenv\(\s*['\"]([A-Z][A-Z0-9_]+)['\"]"),          # PHP / C
    re.compile(r"ENV\[\s*['\"]([A-Z][A-Z0-9_]+)['\"]\s*\]"),        # Ruby
    re.compile(r"ENV\.fetch\(\s*['\"]([A-Z][A-Z0-9_]+)['\"]"),
    re.compile(r"os\.Getenv\(\s*\"([A-Z][A-Z0-9_]+)\""),            # Go
    re.compile(r"\$\{\{\s*secrets\.([A-Z][A-Z0-9_]+)\s*\}\}"),      # GitHub Actions
]
# 実行環境が勝手に入れる変数。README に書く必要が無い。
ENV_IGNORE = {
    "NODE_ENV", "PATH", "HOME", "PWD", "USER", "CI", "PORT", "TZ", "LANG", "SHELL",
    "GITHUB_TOKEN", "GITHUB_ACTIONS", "GITHUB_REF", "GITHUB_SHA", "RUNNER_OS",
    "VERCEL", "VERCEL_ENV", "VERCEL_URL", "NEXT_RUNTIME", "APP_ENV", "DEBUG",
}

# 依存パッケージ名 → 外部サービス名。部分一致で当てる。
SERVICE_HINTS = [
    ("supabase", "Supabase"), ("@clerk/", "Clerk"), ("auth0", "Auth0"),
    ("firebase", "Firebase"), ("stripe", "Stripe"), ("@sentry/", "Sentry"),
    ("sentry/sentry", "Sentry"), ("aws-sdk", "AWS"), ("@aws-sdk/", "AWS"), ("boto3", "AWS"),
    ("aws/aws-sdk-php", "AWS"), ("@google/genai", "Google Gemini"),
    ("@google/generative-ai", "Google Gemini"), ("google-cloud", "Google Cloud"),
    ("@google-cloud/", "Google Cloud"), ("openai", "OpenAI"), ("anthropic", "Anthropic"),
    ("@vercel/", "Vercel"), ("resend", "Resend"), ("sendgrid", "SendGrid"),
    ("mailgun", "Mailgun"), ("twilio", "Twilio"), ("algolia", "Algolia"),
    ("datadog", "Datadog"), ("newrelic", "New Relic"), ("@planetscale/", "PlanetScale"),
    ("@neondatabase/", "Neon"), ("@upstash/", "Upstash"), ("ioredis", "Redis"),
    ("predis", "Redis"), ("redis", "Redis"), ("pusher", "Pusher"), ("slack", "Slack"),
    ("line-bot", "LINE"), ("@line/", "LINE"), ("contentful", "Contentful"),
    ("microcms", "microCMS"), ("@notionhq/", "Notion"), ("cloudinary", "Cloudinary"),
    ("posthog", "PostHog"), ("mixpanel", "Mixpanel"), ("@segment/", "Segment"),
    ("googleapis", "Google API"), ("@googlemaps/", "Google Maps"), ("mongodb", "MongoDB"),
    ("mongoose", "MongoDB"), ("@prisma/", "Prisma（DB 接続先を確認）"),
]
CONFIG_HINTS = {
    "vercel.json": "Vercel", "netlify.toml": "Netlify", "fly.toml": "Fly.io",
    "render.yaml": "Render", "railway.json": "Railway", "app.yaml": "Google App Engine",
    "firebase.json": "Firebase", "wrangler.toml": "Cloudflare Workers",
    "wrangler.jsonc": "Cloudflare Workers", "serverless.yml": "Serverless Framework",
    "amplify.yml": "AWS Amplify", "Procfile": "Heroku 系", "Dockerfile": "Docker",
    "docker-compose.yml": "Docker Compose", "compose.yml": "Docker Compose",
    "docker-compose.yaml": "Docker Compose", "compose.yaml": "Docker Compose",
    "bitbucket-pipelines.yml": "Bitbucket Pipelines", ".gitlab-ci.yml": "GitLab CI",
    "cdk.json": "AWS CDK", "terraform": "Terraform", "supabase": "Supabase（ローカル設定）",
    "deployment": "デプロイ設定（deployment/）", "deploy": "デプロイ設定（deploy/）",
    "infra": "インフラ設定（infra/）", "k8s": "Kubernetes", "helm": "Helm",
    ".circleci": "CircleCI",
}
VERSION_FILES = [".nvmrc", ".node-version", ".tool-versions", ".python-version",
                 ".ruby-version", ".php-version", "rust-toolchain.toml", ".go-version"]


def walk(root: Path):
    count = 0
    stack = [root]
    while stack:
        d = stack.pop()
        try:
            entries = sorted(d.iterdir())
        except OSError:
            continue
        for p in entries:
            if p.is_dir():
                if p.name in SKIP_DIRS or p.name.startswith(".") and p.name not in {".github", ".circleci"}:
                    continue
                stack.append(p)
            elif p.is_file():
                count += 1
                if count > MAX_FILES:
                    return
                yield p


def read(p: Path) -> str:
    try:
        if p.stat().st_size > MAX_BYTES:
            return ""
        return p.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def rel(p: Path, root: Path) -> str:
    return str(p.relative_to(root))


def git(root: Path, *args: str) -> str:
    try:
        return subprocess.run(["git", "-C", str(root), *args], capture_output=True,
                              text=True, timeout=20).stdout.strip()
    except (OSError, subprocess.TimeoutExpired):
        return ""


def makefile_targets(text: str) -> list[str]:
    out = []
    for m in re.finditer(r"^([A-Za-z0-9][A-Za-z0-9_.:-]*)\s*:(?!=)", text, re.M):
        name = m.group(1)
        if name.startswith(".") or name in out:
            continue
        out.append(name)
    return out


def compose_services(text: str) -> list[str]:
    m = re.search(r"^services:\s*\n((?:[ \t]+.*\n?|\s*\n)*)", text, re.M)
    if not m:
        return []
    return re.findall(r"^  ([A-Za-z0-9_.-]+):", m.group(1), re.M)


def mobile(root: Path, deps: dict) -> dict:
    """モバイルアプリの手掛かり。検証端末へのビルド・更新の章を書くための材料。"""
    m: dict = {"frameworks": [], "eas_build_profiles": [], "fastlane_lanes": [],
               "version_sources": [], "distribution_hints": [], "signing_files_in_git": []}
    dep_names = {d.lower() for d in deps}
    appjson = root / "app.json"
    if "expo" in dep_names or (root / "eas.json").is_file() or \
            (appjson.is_file() and '"expo"' in read(appjson)) or any(root.glob("app.config.*")):
        m["frameworks"].append("Expo")
    elif "react-native" in dep_names:
        m["frameworks"].append("React Native")
    if (root / "pubspec.yaml").is_file():
        m["frameworks"].append("Flutter")
        v = re.search(r"^version:\s*(\S+)", read(root / "pubspec.yaml"), re.M)
        if v:
            m["version_sources"].append(f"pubspec.yaml version: {v.group(1)}")
    if "@capacitor/core" in dep_names or any(root.glob("capacitor.config.*")):
        m["frameworks"].append("Capacitor")
    xcodeproj = sorted(p for p in list(root.glob("*.xcodeproj")) + list(root.glob("ios/**/*.xcodeproj"))
                       if "Pods" not in p.parts and "DerivedData" not in p.parts)
    gradle = [p for p in [root / "android/app/build.gradle", root / "android/app/build.gradle.kts",
                          root / "app/build.gradle", root / "app/build.gradle.kts"] if p.is_file()]
    if xcodeproj and not m["frameworks"]:
        m["frameworks"].append("ネイティブ iOS")
    if gradle and not m["frameworks"]:
        m["frameworks"].append("ネイティブ Android")
    if not (m["frameworks"] or xcodeproj or gradle):
        return {}

    eas = root / "eas.json"
    if eas.is_file():
        try:
            m["eas_build_profiles"] = list(json.loads(read(eas)).get("build", {}).keys())
        except json.JSONDecodeError:
            pass
        m["distribution_hints"].append("EAS（eas.json）")
    for ff in [root / "fastlane/Fastfile", root / "ios/fastlane/Fastfile", root / "android/fastlane/Fastfile"]:
        if ff.is_file():
            t = read(ff)
            lanes = re.findall(r"^\s*(?:private_)?lane\s+:(\w+)", t, re.M)
            m["fastlane_lanes"] += [f"{rel(ff, root)}: {l}" for l in lanes]
            for key, label in [("pilot", "TestFlight（fastlane pilot）"), ("upload_to_testflight", "TestFlight（fastlane）"),
                               ("firebase_app_distribution", "Firebase App Distribution（fastlane）"),
                               ("upload_to_play_store", "Google Play（fastlane supply）"), ("supply", "Google Play（fastlane supply）"),
                               ("match", "証明書を match で管理")]:
                if key in t and label not in m["distribution_hints"]:
                    m["distribution_hints"].append(label)
    for g in gradle:
        t = read(g)
        for key in ["versionCode", "versionName"]:
            v = re.search(rf"{key}\s*=?\s*([\"'\w.]+)", t)
            if v:
                m["version_sources"].append(f"{rel(g, root)} {key}: {v.group(1)}")
        if "appdistribution" in t.lower():
            m["distribution_hints"].append("Firebase App Distribution（Gradle）")
    for x in xcodeproj[:1]:
        pbx = x / "project.pbxproj"
        t = read(pbx)
        for key in ["MARKETING_VERSION", "CURRENT_PROJECT_VERSION"]:
            v = re.search(rf"{key} = ([^;]+);", t)
            if v:
                m["version_sources"].append(f"{rel(pbx, root)} {key}: {v.group(1)}")
    if appjson.is_file():
        t = read(appjson)
        for key in ["version", "buildNumber", "versionCode"]:
            v = re.search(rf'"{key}"\s*:\s*("?[\w.]+"?)', t)
            if v:
                m["version_sources"].append(f"app.json {key}: {v.group(1)}")
    tracked = git(root, "-c", "core.quotepath=off", "ls-files").splitlines()
    m["signing_files_in_git"] = [f for f in tracked if re.search(
        r"\.(jks|keystore|p12|p8|mobileprovision|cer)$|google-services\.json$|GoogleService-Info\.plist$", f, re.I)]
    return m


def scan(root: Path) -> dict:
    facts: dict = {"repo": str(root)}

    # 既存の文書
    docs = []
    seen = []
    for name in ["README.md", "README", "readme.md", "CLAUDE.md", "AGENTS.md",
                 "CONTRIBUTING.md", ".github/pull_request_template.md", "CHANGELOG.md"]:
        p = root / name
        # macOS の既定は大文字小文字を区別しないので、README.md と readme.md が同じ実体を指す
        if p.is_file() and not any(p.samefile(q) for q in seen):
            seen.append(p)
            docs.append({"path": name, "lines": read(p).count("\n")})
    docs_dir = root / "docs"
    doc_files = sorted(rel(p, root) for p in docs_dir.rglob("*.md")) if docs_dir.is_dir() else []
    facts["docs"] = docs
    facts["docs_dir_md"] = doc_files[:40]
    facts["docs_dir_md_total"] = len(doc_files)

    # 実行系
    run: dict = {}
    pkg = root / "package.json"
    if pkg.is_file():
        try:
            data = json.loads(read(pkg))
        except json.JSONDecodeError:
            data = {}
        run["package.json"] = {
            "name": data.get("name"),
            "scripts": data.get("scripts", {}),
            "engines": data.get("engines", {}),
            "packageManager": data.get("packageManager"),
        }
        deps = {**data.get("dependencies", {}), **data.get("devDependencies", {})}
    else:
        deps = {}
    locks = [n for n in ["package-lock.json", "pnpm-lock.yaml", "yarn.lock", "bun.lockb",
                         "bun.lock", "composer.lock", "poetry.lock", "uv.lock", "Pipfile.lock",
                         "Gemfile.lock", "go.sum", "Cargo.lock"] if (root / n).is_file()]
    run["lockfiles"] = locks
    for mk in ["Makefile", "makefile", "GNUmakefile"]:
        if (root / mk).is_file():
            run["make_targets"] = makefile_targets(read(root / mk))
            break
    if (root / "justfile").is_file():
        run["just_recipes"] = re.findall(r"^([A-Za-z0-9_-]+)\s*(?:[^:\n=]*)?:(?!=)", read(root / "justfile"), re.M)
    comp = root / "composer.json"
    if comp.is_file():
        try:
            cdata = json.loads(read(comp))
        except json.JSONDecodeError:
            cdata = {}
        run["composer.json"] = {"scripts": list(cdata.get("scripts", {}).keys()),
                                "php": cdata.get("require", {}).get("php")}
        deps.update(cdata.get("require", {}))
        deps.update(cdata.get("require-dev", {}))
    py = root / "pyproject.toml"
    if py.is_file():
        t = read(py)
        run["pyproject.toml"] = {
            "requires-python": (re.search(r"requires-python\s*=\s*['\"]([^'\"]+)", t) or [None, None])[1],
            "scripts": re.findall(r"^\s*([A-Za-z0-9_-]+)\s*=\s*['\"][\w.]+:[\w.]+['\"]", t, re.M),
        }
        for dep in re.findall(r"['\"]([A-Za-z0-9_.-]+)[<>=~!\[; ]", t):
            deps.setdefault(dep.lower(), "")
    req = root / "requirements.txt"
    if req.is_file():
        for line in read(req).splitlines():
            name = re.split(r"[<>=~!\[; ]", line.strip(), 1)[0]
            if name and not name.startswith("#"):
                deps.setdefault(name.lower(), "")
    for cname in ["compose.yml", "compose.yaml", "docker-compose.yml", "docker-compose.yaml"]:
        if (root / cname).is_file():
            run.setdefault("compose_services", {})[cname] = compose_services(read(root / cname))
    versions = {}
    for vf in VERSION_FILES:
        if (root / vf).is_file():
            versions[vf] = read(root / vf).strip()[:200]
    run["version_files"] = versions
    facts["run"] = run

    # 走査（環境変数・CI）
    used: dict[str, set[str]] = {}
    templates: dict[str, list[str]] = {}
    ci = []
    for p in walk(root):
        r = rel(p, root)
        if ENV_TEMPLATE.match(p.name):
            names = re.findall(r"^\s*(?:export\s+)?([A-Z][A-Z0-9_]+)\s*=", read(p), re.M)
            templates[r] = names
            continue
        if r.startswith(".github/workflows/") or p.name in {"bitbucket-pipelines.yml", ".gitlab-ci.yml"}:
            ci.append(r)
        if p.suffix not in CODE_EXT and p.name not in {"Dockerfile"}:
            continue
        text = read(p)
        for pat in ENV_PATTERNS:
            for name in pat.findall(text):
                if name in ENV_IGNORE:
                    continue
                used.setdefault(name, set()).add(r)
    in_template = {n for names in templates.values() for n in names}
    facts["env"] = {
        "templates": templates,
        "used_in_code": {k: sorted(v)[:3] for k, v in sorted(used.items())},
        "used_but_not_in_template": sorted(set(used) - in_template),
        "in_template_but_unused": sorted(in_template - set(used)),
        "note": ".env 本体は読んでいない。値は出力しない。",
    }
    # .env 本体の有無だけは見る（中身は読まない）。暗号化ファイルは復号手順が要る合図。
    facts["env"]["env_files_present"] = sorted(
        p.name for p in root.iterdir() if p.is_file() and p.name.startswith(".env")
        and not ENV_TEMPLATE.match(p.name))

    # 外部サービス
    services: dict[str, list[str]] = {}
    for dep in deps:
        for key, svc in SERVICE_HINTS:
            if key in dep.lower():
                services.setdefault(svc, []).append(f"依存: {dep}")
                break
    for cfg, svc in CONFIG_HINTS.items():
        if (root / cfg).exists():
            services.setdefault(svc, []).append(f"設定: {cfg}")
    facts["services"] = services
    facts["ci"] = sorted(ci)
    facts["mobile"] = mobile(root, deps)

    # git
    facts["git"] = {
        "remote": git(root, "remote", "get-url", "origin"),
        "default_branch": git(root, "symbolic-ref", "--short", "refs/remotes/origin/HEAD"),
        # 最終更新の新しい順。ブランチ戦略の材料。長く更新の無いブランチは運用から外れている可能性がある
        "remote_branches": [b.removeprefix("origin/") for b in git(
            root, "for-each-ref", "--sort=-committerdate", "--format=%(refname:short)", "refs/remotes/origin").splitlines()
            if b not in ("origin", "origin/HEAD")][:15],
        "last_commit": git(root, "log", "-1", "--format=%cs %s"),
        "top_committers_1y": git(root, "shortlog", "-sn", "--no-merges", "--since=1.year", "HEAD").splitlines()[:5],
    }
    # トップレベルのディレクトリ（git 管理のファイルがあるものだけ）。README のディレクトリ構成の材料
    top: dict[str, int] = {}
    for f in git(root, "-c", "core.quotepath=off", "ls-files").splitlines():
        if "/" in f:
            d = f.split("/", 1)[0]
            top[d] = top.get(d, 0) + 1
    facts["top_level_dirs"] = sorted(top.items())
    lic = [n for n in ["LICENSE", "LICENSE.md", "LICENSE.txt", "COPYING"] if (root / n).is_file()]
    facts["license"] = lic
    return facts


def render(f: dict) -> str:
    L = [f"# リポジトリの事実: {f['repo']}", ""]
    L.append("## 既存の文書")
    for d in f["docs"]:
        L.append(f"- {d['path']}（{d['lines']} 行）")
    if f["docs_dir_md_total"]:
        L.append(f"- docs/ 配下の .md: {f['docs_dir_md_total']} 本（先頭40本）")
        L += [f"  - {p}" for p in f["docs_dir_md"]]
    if not f["docs"] and not f["docs_dir_md_total"]:
        L.append("- なし")
    L += ["", "## 実行系"]
    run = f["run"]
    if "package.json" in run:
        pj = run["package.json"]
        L.append(f"- package.json name={pj['name']} engines={pj['engines'] or 'なし'} packageManager={pj['packageManager'] or 'なし'}")
        for k, v in pj["scripts"].items():
            L.append(f"  - script `{k}`: {v}")
    L.append(f"- lockfile: {', '.join(run['lockfiles']) or 'なし'}")
    for key in ["make_targets", "just_recipes"]:
        if run.get(key):
            L.append(f"- {key}: {', '.join(run[key])}")
    for key in ["composer.json", "pyproject.toml"]:
        if key in run:
            L.append(f"- {key}: {json.dumps(run[key], ensure_ascii=False)}")
    for cname, svcs in run.get("compose_services", {}).items():
        L.append(f"- {cname} のサービス: {', '.join(svcs) or '（読めず）'}")
    for vf, v in run["version_files"].items():
        L.append(f"- {vf}: {v}")
    L += ["", "## 環境変数（名前だけ。値は読んでいない）"]
    env = f["env"]
    L.append(f"- 雛形: {', '.join(env['templates']) or 'なし'}")
    L.append(f"- 置かれている .env 系ファイル（中身は未読）: {', '.join(env['env_files_present']) or 'なし'}")
    L.append(f"- コードが読んでいる変数: {len(env['used_in_code'])} 個")
    if len(env["used_in_code"]) <= 40:
        for k, v in env["used_in_code"].items():
            L.append(f"  - `{k}` ← {', '.join(v)}")
    else:
        # フレームワークの設定ファイルが候補を全部列挙していることが多い（Laravel の config/*.php 等）。
        # 多いときは名前だけ並べる。README に全部書くのではなく、雛形へ誘導する合図。
        L.append("  - 多いので名前だけ: " + ", ".join(env["used_in_code"]))
    if env["used_but_not_in_template"] and env["templates"]:
        miss = env["used_but_not_in_template"]
        head = ", ".join(miss[:30]) + (f" ほか {len(miss) - 30} 個" if len(miss) > 30 else "")
        L.append(f"- 雛形に無いがコードが読む（{len(miss)} 個）: {head}")
    if any(n.endswith(".encrypted") for n in env["env_files_present"]):
        L.append("- 暗号化された .env がある。復号鍵の置き場所と復号コマンドが README に要る")
    if env["in_template_but_unused"]:
        L.append(f"- 雛形にあるがコードに見当たらない: {', '.join(env['in_template_but_unused'])}")
    L += ["", "## 外部サービスの手掛かり（推定。README に書く前に用途を確かめる）"]
    for svc, why in f["services"].items():
        L.append(f"- {svc}: {', '.join(why[:3])}")
    if not f["services"]:
        L.append("- なし")
    L += ["", "## CI"] + ([f"- {c}" for c in f["ci"]] or ["- なし"])
    mb = f.get("mobile") or {}
    if mb:
        L += ["", "## モバイルアプリ（検証端末へのビルドと更新の章が要る）",
              f"- 構成: {', '.join(mb['frameworks']) or '不明'}"]
        if mb["eas_build_profiles"]:
            L.append(f"- EAS のビルドプロファイル: {', '.join(mb['eas_build_profiles'])}")
        if mb["fastlane_lanes"]:
            L.append(f"- fastlane の lane: {', '.join(mb['fastlane_lanes'])}")
        L.append(f"- 配布経路の手掛かり: {', '.join(mb['distribution_hints']) or 'なし（手動配布か。ユーザーに確かめる）'}")
        L += ["- 版番号の置き場所:"] + ([f"  - {v}" for v in mb["version_sources"]] or ["  - 見つからない"])
        if mb["signing_files_in_git"]:
            L.append(f"- **署名・構成ファイルが git に入っている**: {', '.join(mb['signing_files_in_git'])}"
                     "（秘密情報なら履歴から除く相談が要る。google-services.json 等は方針次第）")
    g = f["git"]
    L += ["", "## git",
          f"- remote: {g['remote'] or 'なし'}",
          f"- 既定ブランチ: {g['default_branch'] or '不明'}",
          f"- リモートブランチ（更新の新しい順）: {', '.join(g.get('remote_branches', [])) or 'なし'}",
          f"- 最終コミット: {g['last_commit'] or '不明'}",
          "- 直近1年のコミット数上位（問い合わせ先の候補。本人に確認してから書く）:"]
    L += [f"  - {c.strip()}" for c in g["top_committers_1y"]] or ["  - 不明"]
    L += ["", "## トップレベルのディレクトリ（git 管理のファイル数。README のディレクトリ構成の材料）"]
    L += [f"- {d}/（{n}）" for d, n in f.get("top_level_dirs", [])] or ["- なし"]
    L += ["", f"## ライセンス: {', '.join(f['license']) or 'ファイルなし'}"]
    return "\n".join(L)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("repo")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    root = Path(a.repo).expanduser().resolve()
    if not root.is_dir():
        print(f"ERROR: ディレクトリが無い: {root}", file=sys.stderr)
        return 1
    facts = scan(root)
    print(json.dumps(facts, ensure_ascii=False, indent=2) if a.json else render(facts))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
