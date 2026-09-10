#!/usr/bin/env bash
# robodojo / g05 部署环境模板。
#
# 用法：
#   cp env.template.sh env.<host>.sh
#   把下面的 /path/to/... 换成目标机真实值（不要提交带个人路径的副本）
#   source env.<host>.sh
#   python scripts/precheck_robodojo_env.py   # GPU-free 预检
#
# 注意：只包含本 Skill 需要的必要变量，不要用 `env | sort` 导出全量环境。
# 值里不要带引号包住路径（避免把路径当命令）。

# ---------- 工具协议（forge_gateway / forge_tool 源码经 PYTHONPATH 使用） ----------
# forge_bench 里 install 了版本化依赖 forge-msgs==1.0.1、dora-rs==0.4.1。
export FORGE_GATEWAY_PYTHON=/path/to/forge_bench/python
# NOTE(node bundles): forge_gateway / forge_tool are shipped inside the installed
# forge_runtime + robodojo_endpoint Node bundles; FORGE_PKGS_ROOT is NOT needed.
export BENCH_ENDPOINT_PYTHON=/path/to/forge_bench/python
# NOTE(node bundles): bench_endpoint is shipped inside the robodojo_endpoint Node bundle;
# BENCH_ENDPOINT_SRC is NOT needed.

# ---------- RoboDojo / XPolicyLab ----------
# ROBODOJO_ENV 需 python 3.11(3.11.x)、torch 2.7.0+cu128、isaaclab 0.54.3、
# isaacsim 5.1.0.0、opencv-python(cv2)。benchmark 录像用 cv2，不需要 ffmpeg。
export ROBODOJO_ENV=/path/to/robodojo/envs/RoboDojo
export ROBODOJO_ROOT=/path/to/robodojo/repo              # 需含 env/ task/ utils/ src/
export XPOLICYLAB_ROOT=/path/to/robodojo/repo/XPolicyLab # G05 adapter 在 policy/G05
export ROBODOJO_CACHE_ROOT=/path/to/robodojo/cache       # 派生 HF_HOME/MODELSCOPE_CACHE/...；不设则跳过

# ---------- G05 模型 / processor ----------
export G05_CKPT_PATH=/path/to/.../checkpoints/checkpoint   # 约 33.9GB，可读
export G05_PROCESSOR_PATH=/path/to/G05/hf_processor        # 需含 config.json/tokenizer.json/tokenizer_config.json 等

# ---------- policy 选择（profile 固定） ----------
export POLICY_NAME=G05
export ENV_CFG_TYPE=arx_x5
export ACTION_TYPE=joint
export TASK_NAME=put_bottles_into_dustbin

# ---------- CUDA / GPU ----------
# CUDA_HOME 需含 bin/、lib64/。CUDA_VISIBLE_DEVICES 决定策略进程可见 GPU；
# benchmark 的 ROBODOJO_DEVICE_ID 相对“当前可见集合”编号，必须 < 可见 GPU 个数。
export CUDA_HOME=/path/to/cuda
export CUDA_VISIBLE_DEVICES=0,1
export ROBODOJO_DEVICE_ID=0
export ROBODOJO_RESULT_DIR=/path/to/result_dir            # 结果落盘目录，需可写

# 可选：录像目录；不设则用 profile 默认相对路径。
# export ROBODOJO_RECORD_DIR=/path/to/record_dir
# dora CLI lives in the bin dir above; paos skill start needs dora on PATH.
export PATH="/path/to/forge_bench/bin:$PATH"
export PAOS_SRC_ROOT=/path/to/paos_src/phyagentos
# Which python runs the PAOS CLI (paos env); used by scripts/accept_robodojo_skill.sh.
export PAOS_PY=/path/to/paos/bin/python
