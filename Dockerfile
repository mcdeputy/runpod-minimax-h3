# syntax=docker/dockerfile:1
#
# Base: Hearmeman's shared ComfyUI image. It provides Ubuntu 24.04, CUDA 13.0,
# Python 3.12 in /opt/venv, torch 2.11 (frozen via PIP_CONSTRAINT), ComfyUI
# v0.42.1 at /ComfyUI, ComfyUI-Manager, JupyterLab, aria2, ffmpeg and an
# installed SageAttention wheel. Pinned by digest, so an upstream retag can
# never change what we build. To move to a new ComfyUI release, pick a newer
# tag from hub.docker.com/r/hearmeman/comfyui-base and update tag + digest.
ARG BASE_IMAGE=hearmeman/comfyui-base:cu130-comfy0.42.1-63be2f9b-torch2.11.0@sha256:47e68b93da7a705a28a75454f863a8c9ecc776078b8c7d549570daa43f4b3551
FROM ${BASE_IMAGE}

# Custom nodes, each pinned to a commit ("repo|sha").
#
# ComfyUI v0.42.1 already ships what our plan needs for pose control (Fun
# ControlNet + SDPose pose extraction), frame interpolation (RIFE, FILM), and
# video load/save, so those need no packs. What's left:
#   KJNodes                common utilities used by many community workflows
#   VideoHelperSuite       video load/combine nodes used by many community workflows
#   H3 latent upscaler     Minimax H3 Latent Upscaler (3D), from the Comfy docs
#   H3 Motion Context      clip chaining that carries motion and audio across joins
#   MiniMaxH3Mod           RefMods (likeness references without training a LoRA)
#   rgthree-comfy          Fast Groups Bypasser (switch workflow sections on/off),
#                          Power Lora Loader (stack LoRAs with per-LoRA toggles)
#   Spectrum-MiniMax-H3    optional sampling speed-up with approximate output;
#                          does nothing unless its node is added to a graph
ARG CUSTOM_NODES="\
https://github.com/kijai/ComfyUI-KJNodes.git|eaa8fee753faf37d1539804d89a46d3e0f40963d \
https://github.com/rgthree/rgthree-comfy.git|d7297b42f0fa78bec1c0411478f887423c249502 \
https://github.com/xmarre/ComfyUI-Spectrum-MiniMax-H3.git|806fe498d574a726fecb8818917f00a4b993fd77 \
https://github.com/Kosinkadink/ComfyUI-VideoHelperSuite.git|4d907bee61e92c2e65af3bd6383a4e4d356126d1 \
https://github.com/LBH-123-AI/Comfyui_Minimax_h3_latent_Upscaler.git|40316cf008b2fd8663263270669eb4da23f89d2c \
https://github.com/NikoDemon80/ComfyUI-H3-Motion-Context.git|518c083d11d80fa5920222ad89889924ee4401c9 \
https://github.com/Luisacaotica/ComfyUI-MiniMaxH3Mod.git|517e8c419a8584fbf69fceb487bc39d83e6a6ec8"

# PIP_CONSTRAINT (set by the base) keeps every install below from moving torch.
RUN --mount=type=cache,target=/root/.cache/pip \
    set -e; \
    for entry in $CUSTOM_NODES; do \
        repo="${entry%|*}"; sha="${entry#*|}"; \
        dir="/ComfyUI/custom_nodes/$(basename "$repo" .git)"; \
        git init -q "$dir"; \
        git -C "$dir" remote add origin "$repo"; \
        git -C "$dir" fetch -q --depth=1 origin "$sha"; \
        git -C "$dir" checkout -q --detach FETCH_HEAD; \
        if [ -f "$dir/requirements.txt" ]; then pip install -r "$dir/requirements.txt"; fi; \
    done

# Build-time gate: load every node the way ComfyUI does at startup (on CPU,
# no GPU needed) and fail the build if any pack fails to import.
RUN set -e; \
    cd /ComfyUI; \
    python main.py --cpu --quick-test-for-ci > /tmp/node-check.log 2>&1 \
        || { cat /tmp/node-check.log; exit 1; }; \
    grep -A20 "Import times for custom nodes" /tmp/node-check.log; \
    if grep -q "IMPORT FAILED" /tmp/node-check.log; then cat /tmp/node-check.log; exit 1; fi; \
    rm -rf /tmp/node-check.log /ComfyUI/user /ComfyUI/temp /ComfyUI/output /ComfyUI/input/*

COPY src/ /opt/template/
# download_models.py hands transfers to aria2c (from the base image).
RUN chmod +x /opt/template/start.sh && command -v aria2c

# ComfyUI, JupyterLab
EXPOSE 8188 8888

CMD ["/opt/template/start.sh"]
