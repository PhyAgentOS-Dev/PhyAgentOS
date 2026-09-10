#!/usr/bin/env python3
"""One-shot robodojo install helper (self-contained).

Reads the unsigned schema-v3 index template shipped next to this script, presigns a fresh
TOS download URL for every ``bucket_key``, downloads each object once to measure ``size``
and confirm ``expected_sha256``, writes a generated schema-v3 index to a private temp dir,
then calls::

    paos skill install robodojo --version 0.1.0 --index <generated-index.yaml>

``paos skill install --index`` rejects an index entry that has no ``sha256``/``size``, which
is why the template carries ``bucket_key`` + ``expected_sha256`` instead of a link and a
hand-written size: the helper derives the real values from the object it just downloaded and
aborts on a hash mismatch.

Requires TOS read permission for the inner bucket plus ``tosutil``; this is a
credential-enabled route, not a credential-less public one. Requires PyYAML (already a PAOS
runtime dependency).

Self-contained preparation:
  * locates the template next to this script (downloaded together from TOS) OR in the repo
    layout (<script>/../docs/paos-forge-packages.template.yaml);
  * if ``--paos-config`` is supplied, prepares the isolated instance so the install does NOT
    depend on a previous acceptance tree: creates <config>.parent/config.json and
    <config>.parent/py/sitecustomize.py (which calls PhyAgentOS set_config_path), and sets
    PAOS_CONFIG + PYTHONPATH for the paos child.

Never modifies PAOS integrity checks, never changes the frozen packages, never tracks the
generated index in git.
"""
from __future__ import annotations

import argparse
import datetime
import hashlib
import os
import shutil
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request
from pathlib import Path

import yaml

BUCKET = "phyagentos-resource-inner"
TEMPLATE_FIELDS = ("bucket_key", "expected_sha256")

# sitecustomize.py keeps get_data_dir() anchored to the instance dir (config.parent).
SITECUSTOMIZE = '''import os
_p = os.environ.get("PAOS_CONFIG")
if _p:
    try:
        from PhyAgentOS.config.loader import set_config_path
        from pathlib import Path
        set_config_path(Path(_p).expanduser().resolve())
    except Exception:
        pass
'''


def resolve_template(explicit: str | None) -> Path:
    """Locate the unsigned template. Same-directory (TOS download) first, repo layout second."""
    if explicit:
        p = Path(explicit)
        if not p.is_file():
            raise SystemExit(f"template not found: {p}")
        return p
    here = Path(__file__).resolve().parent
    candidates = [
        here / "paos-forge-packages.template.yaml",
        here.parent / "docs" / "paos-forge-packages.template.yaml",
    ]
    for cand in candidates:
        if cand.is_file():
            return cand
    raise SystemExit(
        "template not found; place paos-forge-packages.template.yaml next to this script "
        "or pass --template <path>"
    )


def find_tosutil(explicit: str | None) -> str:
    if explicit:
        return explicit
    env = os.environ.get("TOSUTIL")
    if env:
        return env
    found = shutil.which("tosutil")
    if found:
        return found
    raise SystemExit(
        "tosutil not found. Configure it with --tosutil <path>, "
        "TOSUTIL=<path>, or put 'tosutil' on PATH. "
        "It needs read access to the phyagentos-resource-inner bucket."
    )


def find_paos(explicit: str | None) -> str:
    if explicit:
        return explicit
    env = os.environ.get("PAOS_BIN")
    if env:
        return env
    found = shutil.which("paos")
    if found:
        return found
    raise SystemExit(
        "paos not found. Configure it with --paos <path>, "
        "PAOS_BIN=<path>, or put 'paos' on PATH."
    )


def prepare_instance(config_path: Path) -> None:
    """Make an isolated instance so install does not depend on a manually created tree."""
    config_path = config_path.expanduser().resolve()
    data_dir = config_path.parent
    data_dir.mkdir(parents=True, exist_ok=True)
    if not config_path.exists():
        config_path.write_text("{}\n", encoding="utf-8")
    py_dir = data_dir / "py"
    py_dir.mkdir(parents=True, exist_ok=True)
    sc = py_dir / "sitecustomize.py"
    if not sc.exists():
        sc.write_text(SITECUSTOMIZE, encoding="utf-8")


def presign(tosutil: str, key: str, vp: str) -> str:
    r = subprocess.run([tosutil, "presign", f"tos://{BUCKET}/{key}", f"-vp={vp}"],
                       capture_output=True, text=True)
    for line in r.stdout.splitlines():
        line = line.strip()
        if line.startswith("https://"):
            return line
    raise RuntimeError(f"presign failed for {key}: {r.stdout[:200]} {r.stderr[:200]}")


def download_and_hash(url: str, key: str, dest: Path) -> tuple[str, int]:
    """Download one object and return its (sha256, size); never trusts the link metadata."""
    try:
        with urllib.request.urlopen(url, timeout=300) as response, dest.open("wb") as out:
            shutil.copyfileobj(response, out, length=1 << 20)
    except urllib.error.HTTPError as exc:
        raise SystemExit(
            f"cannot download {key}: HTTP {exc.code}. If this is the post-split candidate, "
            "the object has not been published yet."
        ) from exc
    except OSError as exc:
        raise SystemExit(f"cannot download {key}: {exc}") from exc
    digest = hashlib.sha256()
    size = 0
    with dest.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            digest.update(chunk)
            size += len(chunk)
    return digest.hexdigest(), size


def generate_index(document: dict, tosutil: str, vp: str, workdir: Path) -> Path:
    packages = document.get("packages")
    if not isinstance(packages, list) or not packages:
        raise SystemExit("template has no packages list")
    for item in packages:
        if not isinstance(item, dict):
            raise SystemExit("template package entry must be a mapping")
        key = item.pop("bucket_key", None)
        expected = item.pop("expected_sha256", None)
        if not isinstance(key, str) or not key:
            raise SystemExit(f"template package {item.get('kind')!r} has no bucket_key")
        url = presign(tosutil, key, vp)
        local = workdir / Path(key).name
        sha256, size = download_and_hash(url, key, local)
        if isinstance(expected, str) and expected:
            if expected.lower() != sha256:
                raise SystemExit(
                    f"integrity check failed for {key}: template expected {expected.lower()}, "
                    f"object has {sha256}"
                )
            print(f"[robodojo-helper] {key}: sha256 {sha256} matches the template")
        else:
            print(
                f"[robodojo-helper] {key}: no expected_sha256 recorded yet "
                f"(candidate object); recording {sha256}"
            )
        item["direct_download_url"] = url
        item["sha256"] = sha256
        item["size"] = size
        local.unlink()
    document["generated_at"] = datetime.datetime.now(datetime.timezone.utc).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )
    out = workdir / "index.yaml"
    out.write_text(yaml.safe_dump(document, sort_keys=False, allow_unicode=True), encoding="utf-8")
    return out


def load_template(path: Path) -> dict:
    try:
        document = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        raise SystemExit(f"cannot read template {path}: {exc}") from exc
    if not isinstance(document, dict) or document.get("schema_version") != 3:
        raise SystemExit(f"template {path} is not a schema_version 3 index")
    return document


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--template", default=None, help="unsigned schema-v3 template (default: next to script, then repo docs)")
    ap.add_argument("--tosutil", default=None, help="tosutil path (default: TOSUTIL/PATH)")
    ap.add_argument("--paos", default=None, help="paos CLI path (default: PAOS_BIN/PATH)")
    ap.add_argument("--vp", default="1d", help="presign validity, e.g. 1d/24h/1440min/86400s")
    ap.add_argument("--out", default=None, help="generated index path (default: private temp dir)")
    ap.add_argument("--gen-only", action="store_true", help="generate index only, do not install")
    ap.add_argument("--index", default=None, help="use a pre-generated index file instead of generating")
    ap.add_argument("--skill", default="robodojo")
    ap.add_argument("--version", default="0.1.0")
    ap.add_argument("--paos-config", default=os.environ.get("PAOS_CONFIG"))
    args = ap.parse_args()

    template = resolve_template(args.template)

    if args.index:
        idx_path = Path(args.index)
        if not idx_path.is_file():
            raise SystemExit(f"index not found: {idx_path}")
    else:
        document = load_template(template)
        tosutil = find_tosutil(args.tosutil)
        workdir = Path(args.out).expanduser().resolve().parent if args.out else Path(
            tempfile.mkdtemp(prefix="robodojo-index-")
        )
        workdir.mkdir(parents=True, exist_ok=True)
        generated = generate_index(document, tosutil, args.vp, workdir)
        idx_path = Path(args.out).expanduser().resolve() if args.out else generated
        if args.out:
            shutil.move(str(generated), str(idx_path))
        print(f"[robodojo-helper] index written: {idx_path}")
        print(f"[robodojo-helper] generated_at={document['generated_at']} presign_vp={args.vp}")
        print(f"[robodojo-helper] NOTE: download URLs expire after {args.vp}; re-run to refresh.")

    if args.gen_only:
        print(idx_path)
        return 0

    paos = find_paos(args.paos)
    env = dict(os.environ)
    if args.paos_config:
        cfg = Path(args.paos_config)
        prepare_instance(cfg)
        env["PAOS_CONFIG"] = str(cfg.resolve())
        instance_py = str(cfg.resolve().parent / "py")
        existing_pypath = env.get("PYTHONPATH")
        env["PYTHONPATH"] = instance_py + (os.pathsep + existing_pypath if existing_pypath else "")

    cmd = [paos, "skill", "install", args.skill, "--version", args.version, "--index", str(idx_path)]
    print(f"[robodojo-helper] running: {' '.join(cmd)}")
    r = subprocess.run(cmd, env=env)
    return r.returncode


if __name__ == "__main__":
    sys.exit(main())
