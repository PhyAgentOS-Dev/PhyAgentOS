# robodojo Skill

`robodojo` is a Forge Skill with one official profile, `g05`. It runs the RoboDojo
`put_bottles_into_dustbin` task through Isaac Sim and exposes two Gateway tools to
PAOS: `bench.describe` and `bench.run`.

This Skill ships the description, manifest, g05 profile, dataflow and install
material only. The benchmark node and the G05 policy node are Forge Nodes whose
source lives in `framework/forge_runtime`; the profile reaches them through the
installed Node entrypoints under `${FORGE_RUNTIME_BIN}`.

## Layout

```text
skill.yaml                     manifest (manifest_version 2, profile g05)
SKILL.md                       Skill document referenced by skill_document
profiles/g05/dataflow.yaml     gateway -> bench_endpoint -> robodojo_benchmark -> robodojo_policy
profiles/g05/*.yaml            gateway / bench_endpoint / benchmark config
profiles/g05/env.template.sh   host environment template
scripts/install_robodojo.py    per-run TOS presign + `paos skill install --index`
scripts/check_bundle_inventory.py  verify the template inventory against this tree
docs/                          unsigned schema-v3 index template + 0.1.0 delivery record
```

There is no `nodes/` tree and no `profiles/g05/bin/` launcher here. An earlier
revision of this branch vendored the benchmark/policy sources and two in-bundle shell
launchers inside the Skill, which duplicated the Node sources and let the two copies
drift (four files had already diverged through lint-only edits). The sources of
truth are:

| node | source of truth | build entry |
| --- | --- | --- |
| benchmark + G05 policy | `framework/forge_runtime`, `packages/nodes/benchmarks/robodojo/` | `scripts/build_node_artifacts.py` (`robodojo_benchmark`) |
| gateway | `framework/forge_gateway` tag `v1.0.2` | same script (`forge_runtime`) |
| bench endpoint | `framework/forge_runtime`, `packages/runtime/bench_endpoint/` | same script (`robodojo_endpoint`) |

## Node bundles

| node_id | artifact_id | entrypoints | node_digest |
| --- | --- | --- | --- |
| `forge_runtime` | `forge-runtime-0.1.0` | `gateway` | `cee927eb587f3f958c1803086e59692f6f7ae373477b3cfd15118d01d76c408e` |
| `robodojo_endpoint` | `robodojo-endpoint-0.1.0` | `bench_endpoint` | `b9a66fb07b04ee1f76bb8221f68f96b35d1f1ce136d3d6cf967cb7a34da8e159` |
| `robodojo_benchmark` | `robodojo-benchmark-0.1.0` | `robodojo_benchmark`, `robodojo_policy` | `e48cf4e838ba73512ac1eb0c144ea17ea177bb56ad41e524c8332f9a38c19ff2` |

The benchmark node and the G05 policy node ship as **one** digest bundle with two
entrypoints: they share `_core/`, `config.py` and `adapters/` and run in the same
Python environment, so a second archive would only duplicate the same tree.

## Source / artifact correspondence

- The published `0.1.0` TOS objects (Skill archive sha256 `5c7806843e5cff16a8a407254ffe7736c9b1d5d13982bd1b82195c7e4f5bc907`
  plus the `forge-runtime` / `robodojo-endpoint` Node archives) are frozen snapshots
  of the **pre-split** layout: that Skill archive still contains `nodes/` and
  `profiles/g05/bin/`. They stay untouched.
- This branch is the **post-split** candidate. The Skill archive is rebuilt with the
  official packager (`scripts/package_skill.py`) and needs a new object key or version
  before it can be published. Its sha256 is recorded in the pull request description:
  a file cannot carry the hash of the archive it is packed into.
- Node implementations come from `framework/forge_runtime`. The recorded base is branch
  `qinhan/robodojo-g05-node` at `1630e75a450464307cdab08de6e7d4536d04af86`; this revision adds
  `93c2659` (lint-only port that makes the Node source byte-identical to the copy that had been
  vendored in this Skill) and a `scripts/build_node_artifacts.py` fix that first sorts the
  payload inventory by POSIX path, so one source tree yields one `node_digest` on Windows and on
  Linux alike.
- That branch (`qinhan/robodojo-node-bundles`) is committed locally only.
  `framework/forge_runtime` has no personal fork and the GitLab project cannot be forked without
  an API session, so pushing it — as a topic branch or as a fork — is a maintainer decision
  under the fork + MR contribution flow.
- `node_digest` is content-derived and reproducible across hosts; the Node *archive* sha256 is
  not, because the tarball records file mtimes and ownership.

## Runtime requirement

`skill.yaml` uses two manifest features that must be present in the PAOS runtime:

- `profiles.<name>.startup_timeout_s` — a per-profile Dora readiness timeout
  (the generic LIBERO `lingbot_va` profile uses `900`).
- digest-locked multi-file Node bundles — `artifacts.nodes.<id>.digest` pins the
  installed `node-manifest.json` digest, and the installed Node manifest declares the
  `entrypoints` that provide `gateway`, `bench_endpoint`, `robodojo_benchmark` and
  `robodojo_policy`.

`profiles.<name>.startup_timeout_s` is already supported by upstream `dev`.
Digest-locked bundles come from `feature/skill-runtime-node-bundles` (PR #112); this
branch depends on it. The legacy single-executable `artifact_type: executable_tar_gz`
lock form keeps working unchanged.

## Build

```bash
python scripts/package_skill.py PhyAgentOS/skills/forge-skill/robodojo \
  --output-dir dist/skills
```

The Node bundles are built from `framework/forge_runtime`:

```bash
python scripts/build_node_artifacts.py --out dist/nodes --forge-src /path/to/forge_gateway
```

## Install

Requires read permission for TOS bucket `phyagentos-resource-inner` and `tosutil`.

```bash
export PAOS_CONFIG=/abs/instance/config.json
python3 scripts/install_robodojo.py --tosutil /path/to/tosutil --vp 1d
```

`install_robodojo.py` regenerates fresh presigned download URLs on every run, verifies
each downloaded object against the sha256 recorded in the template, writes a private
temporary schema-v3 index, and calls:

```bash
paos skill install robodojo --version 0.1.0 --index <generated-index.yaml>
```

The historical `paos-forge-packages.0.1.0.yaml` carries expired links and is not the
recommended entry point.

## Verify, start, stop

```bash
paos skill list
paos skill inspect robodojo
paos forge-node verify robodojo forge_runtime
paos forge-node verify robodojo robodojo_endpoint
paos forge-node verify robodojo robodojo_benchmark

paos skill start robodojo --profile g05
paos skill status robodojo
paos skill stop robodojo
```

`paos skill start` needs `dora` on `PATH`. A running Skill leaves Dora up after the
benchmark finishes; the pending item is that an Agent must actually stop and confirm
when the user asks.

## External environment

The manifest declares `FORGE_GATEWAY_PYTHON`, `BENCH_ENDPOINT_PYTHON`, `ROBODOJO_ENV`,
`ROBODOJO_ROOT`, `XPOLICYLAB_ROOT`, `G05_CKPT_PATH`, `G05_PROCESSOR_PATH`, `CUDA_HOME`,
`CUDA_VISIBLE_DEVICES`, `ROBODOJO_CACHE_ROOT`, `ROBODOJO_DEVICE_ID` and
`ROBODOJO_RESULT_DIR`. `profiles/g05/env.template.sh` lists the same values with
descriptions.

`TASK_NAME=put_bottles_into_dustbin` is also exported by `env.template.sh` and read by
`policy_node.py`; it is not part of the frozen `skill.yaml` `required_environment` list,
so the host must set it explicitly until a new candidate manifest is published.

Checkpoint/processor and Isaac Sim are external and are not bundled here. The G05
checkpoint is ~33.9 GB; do not copy it into the Skill package.
