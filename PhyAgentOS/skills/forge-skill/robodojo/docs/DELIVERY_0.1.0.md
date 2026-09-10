# RoboDojo 0.1.0 — Installation (release candidate)

**Status**: candidate, post-split layout. The schema-v3 static-index route is verified
(fresh-instance install on host 120 passed for the pre-split archive; a fresh isolated
instance install of the post-split layout was also checked locally without GPU). No HTTP
Resource Registry is used; no default Skill version changed. Final functional acceptance
is pending.

## What changed: node ownership

This revision removes the vendored benchmark/policy sources and the two in-bundle shell
launchers from the Skill. The nodes are maintained in `framework/forge_runtime` and are
installed as digest Node bundles; the profile reaches them through
`${FORGE_RUNTIME_BIN}/<entrypoint>`.

- The published pre-split objects stay untouched: Skill `robodojo-0.1.0.tar.gz` sha256
  `5c7806843e5cff16a8a407254ffe7736c9b1d5d13982bd1b82195c7e4f5bc907`, Node
  `forge-runtime-0.1.0`, Node `robodojo-endpoint-0.1.0`.
- This revision adds a third Node bundle, `robodojo-benchmark-0.1.0` (node_digest
  `e48cf4e838ba73512ac1eb0c144ea17ea177bb56ad41e524c8332f9a38c19ff2`, entrypoints
  `robodojo_benchmark` and `robodojo_policy`). It is **not uploaded yet**.
- Because the Skill payload changed, its archive must be rebuilt and published under a new
  object key or version before this revision can be installed from TOS. Versioning and
  publishing are maintainer decisions; this revision overwrote nothing in TOS and did not
  register anything in a public index.

## Recommended entry point (credential-enabled, per-run presign)
Use the **unsigned template + refresh helper** — NOT the historical index that carries
pre-signed download URLs. The helper presigns fresh HTTPS download links on the target machine
on every run, so it never depends on a link lifetime. The signed index is written to a private
temp dir and is not tracked in git. This per-run presign route is **established**; a durable
HTTP(S)-hosted index / HTTP Resource Registry is **not a blocker** for this route.

## Verified baseline
- Skill `robodojo-0.1.0.tar.gz` sha256 `5c7806843e5cff16a8a407254ffe7736c9b1d5d13982bd1b82195c7e4f5bc907`
  (pre-split archive; the post-split candidate is rebuilt locally and needs a new object key)
- Node `forge-runtime-0.1.0` node_digest `cee927eb587f3f958c1803086e59692f6f7ae373477b3cfd15118d01d76c408e` (entry `bin/gateway`, 60 files)
- Node `robodojo-endpoint-0.1.0` node_digest `b9a66fb07b04ee1f76bb8221f68f96b35d1f1ce136d3d6cf967cb7a34da8e159` (entry `bin/bench_endpoint`, 27 files)
- Node `robodojo-benchmark-0.1.0` node_digest `e48cf4e838ba73512ac1eb0c144ea17ea177bb56ad41e524c8332f9a38c19ff2` (entries `bin/robodojo_benchmark`, `bin/robodojo_policy`, 20 files) — candidate, not uploaded
- Runtime source commit `aac600574a6d9dba225216e1f2271e069be2e4e2` plus the lint-port commit that makes the Node source byte-identical to the copy previously vendored in the Skill
- TOS bucket `phyagentos-resource-inner`; Skill and Node bundles live under
  `skill-bundles/robodojo/0.1.0/` and
  `node-bundles/{forge_runtime,robodojo_endpoint,robodojo_benchmark}/0.1.0/`.

The `node_digest` values above are reproducible from the source trees on any host (the builder
sorts the payload inventory by POSIX path, so a Windows checkout cannot produce a different
digest than an LF checkout); the *archive* sha256 is not, because the tarball records file
mtimes and ownership. Pin and compare `node_digest`.

## Post-split local verification (no GPU, this revision)

Node sources come from `framework/forge_runtime` and are built with
`scripts/build_node_artifacts.py` (branch `qinhan/robodojo-node-bundles`: base `1630e75`, lint
port `93c2659`, plus the inventory-ordering fix). The Skill is packed with the official
`scripts/package_skill.py`. On a Linux host, with no GPU, no Isaac Sim, no Dora and no Agent:

- Fresh isolated instance, verified empty of Skill / Node / lock / cache before the run.
- Installed with `install_robodojo.py --index <local schema-v3 index>` served over loopback; the
  loopback server replaced TOS presigning because the rebuilt archives are still candidates.
  The run exercised the `prepare_instance` fix (`config.json` + `py/sitecustomize.py`), the
  digest bundle install path and the lock write, and ended with
  `✓ Installed Skill robodojo 0.1.0`.
- `paos skill list` reports `robodojo 0.1.0 / g05 / not started`.
- `paos forge-node verify robodojo {forge_runtime,robodojo_endpoint,robodojo_benchmark}` all
  report "verified against Skill lock".
- The profile environment materialises `bin/{gateway,bench_endpoint,robodojo_benchmark,robodojo_policy}`
  as relative symlinks into `<runtime>/nodes/<node_id>/versions/<artifact_id>/bin/...`, and the
  rendered `launch/profiles/g05/dataflow.yaml` resolves every node `path` to that expanded
  `${FORGE_RUNTIME_BIN}` directory — never to a copy inside the Skill tree. The installed Skill
  contains no `nodes/` and no `profiles/g05/bin/`.
- `python3 scripts/check_bundle_inventory.py --check` reports every Skill file matching the
  template inventory. The inventory is not read at install time, so it drifts silently when a
  Skill file changes; run the checker (or `--write`) on the pack host before registering or
  publishing this candidate.
- Still pending: a presign run against real TOS for this revision, and GPU / Isaac Sim /
  Agent functional acceptance.

## Prerequisites
- Linux x86_64, CUDA GPU (>=16 GB for G05), Isaac Sim host, EGL/GL (`MUJOCO_GL=egl`,
  `PYOPENGL_PLATFORM=egl`), `ffmpeg`, `dora` coordinator/daemon.
- PAOS runtime: `startup_timeout_s` is already supported by upstream `dev`. Digest-locked
  multi-file Node bundle support is provided by `feature/skill-runtime-node-bundles` (PR #112),
  which this Skill revision depends on. `paos skill install --index` supports the schema-v3
  static index. `forge-node install <artifact_id>` needs an HTTP Resource Registry URL and is
  **not** configured — use the `--index` route.
- **TOS read permission for `phyagentos-resource-inner`** plus `tosutil` (this is a
  credential-required install, not a public credential-less one). If the target machine cannot
  obtain this permission, "download-authorization method missing" is a delivery blocker.

## Install helper (regenerates download links on each run)
The template `paos-forge-packages.template.yaml` records a `bucket_key` and an
`expected_sha256` per package. `install_robodojo.py` presigns a fresh HTTPS link for each key
(via `tosutil presign`), downloads each object once to measure `size` and confirm
`expected_sha256`, writes a temporary schema-v3 index with `direct_download_url` / `sha256` /
`size` filled in (`paos skill install --index` rejects an index without them), and then runs the
verified install command.

The helper is **self-contained**: it finds the template next to itself (or in the repo layout
`<script>/../docs/`), and it **prepares the isolated instance** on the target machine by
creating `<config>.parent/config.json` and `<config>.parent/py/sitecustomize.py` (which anchors
`get_data_dir()` to the instance via `PhyAgentOS.set_config_path`). No manually-created
`sitecustomize.py` from a prior acceptance tree is required. `paos`/`tosutil` are resolved via
`--paos`/`--tosutil`, then `PAOS_BIN`/`TOSUTIL`, then `PATH`; no hardcoded host path is assumed,
and a missing entry exits with setup guidance.

```bash
# 1) put install_robodojo.py next to paos-forge-packages.template.yaml (e.g. from TOS support/)
# 2) choose an isolated instance config path
export PAOS_CONFIG=/your/instance/config.json

# 3) run the helper (uses tosutil on PATH; override with --tosutil; --paos for paos CLI)
python3 install_robodojo.py --tosutil /path/to/tosutil --vp 1d
```
The helper sets `PAOS_CONFIG` + `PYTHONPATH=<instance>/py` for the `paos` child and creates the
isolation files if absent. Equivalent manual form after links are refreshed:
```bash
paos skill install robodojo --version 0.1.0 --index <generated-index.yaml>
```

## Expired links
Re-run `install_robodojo.py` — it regenerates `direct_download_url` and re-verifies the content
hash on every run and prints `generated_at` + the presign validity. You never edit the YAML by
hand. The signed index is written to a private temp dir and is not tracked. Do **not** use the
historical `paos-forge-packages.0.1.0.yaml` (its links are time-limited).

## Verify the install

> In-repo copy note: the frozen TOS support copy of this file lists the node verification
> arguments in the older order; the CLI signature is `paos forge-node verify <skill> <node_id>`,
> as shown below.
```bash
paos skill list
paos skill inspect robodojo
paos forge-node verify robodojo forge_runtime
paos forge-node verify robodojo robodojo_endpoint
paos forge-node verify robodojo robodojo_benchmark
```
Expected: `robodojo 0.1.0 / g05 / stopped`, Gateway `http://127.0.0.1:19011`,
tools `bench.describe, bench.run`, all three nodes verified.

Install does not load the model and does not start the simulator: it only resolves the Skill
bundle, verifies the Node archives against the locked digests, and materialises
`<env>/bin/{gateway,bench_endpoint,robodojo_benchmark,robodojo_policy}` plus the rendered
dataflow. Those four entrypoints are relative symlinks into the installed Node bundles, so the
Skill never falls back to a development checkout such as `FORGE_PKGS_ROOT` or
`BENCH_ENDPOINT_SRC`.

## External assets (not bundled)
G05 checkpoint/processor + Isaac Sim are external (RoboDojo-sim-arx_x5-joint-0, action_source=fm,
action_steps=32, continuous_action=True; model source OpenGalaxea/g05-robodojo analog). Configure
`G05_CKPT_PATH`, `G05_PROCESSOR_PATH`, `ROBODOJO_ENV`, `ROBODOJO_ROOT`, `XPOLICYLAB_ROOT`,
`CUDA_HOME`, `CUDA_VISIBLE_DEVICES`, `ROBODOJO_DEVICE_ID`, `ROBODOJO_CACHE_ROOT`,
`ROBODOJO_RESULT_DIR`. The policy node also reads `TASK_NAME` (the dataflow passes it through
from the host); the frozen manifest does not declare it, so export it explicitly —
`profiles/g05/env.template.sh` sets `put_bottles_into_dustbin`.

## Start a profile (later; not part of this install check)
```bash
paos skill start robodojo --profile g05
paos skill status robodojo
paos skill stop robodojo
```

## Known / pending
- Agent auto-stop after a run is not implemented; benchmark finishing leaves the Skill running.
  This is not treated as an error — the pending item is that the Agent actually stops and confirms
  when the user explicitly asks.
- No HTTP Resource Registry service is configured. The candidate static-index route is verified;
  durable HTTPS hosting of the index + maintainer registration would be for public/long-lived
  publishing and are **not required** for the per-run presign install route above.
- The `robodojo-benchmark-0.1.0` object and the rebuilt Skill archive are not published yet; the
  template records them as candidates.
- `final_acceptance` is pending; no default-version change, no public index mutation.
