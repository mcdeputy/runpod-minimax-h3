#!/usr/bin/env bash
# Container entrypoint: put ComfyUI's data on the network volume, start
# JupyterLab, then start ComfyUI. Everything is baked into the image; nothing
# is pulled from GitHub at boot.
#
# Environment variables (set on the RunPod template or at deploy time):
#   USE_SAGE          true to launch ComfyUI with SageAttention (default false;
#                     INT8 checkpoints + Sage can morph the end of clips)
#   COMFY_EXTRA_ARGS  extra flags appended to the ComfyUI command line
#   JUPYTER_ENABLED   false to skip JupyterLab (default true)
#   JUPYTER_TOKEN     token JupyterLab asks for (default: no login)

set -uo pipefail

COMFYUI_DIR=/ComfyUI
VOLUME=/workspace
DATA_DIR="$VOLUME/ComfyUI"
LOG_DIR="$VOLUME/logs"

if ! mountpoint -q "$VOLUME"; then
    echo "WARNING: nothing is mounted at $VOLUME. Models and outputs will be lost when the pod is deleted."
fi
mkdir -p "$DATA_DIR"/{models,input,output,user} "$LOG_DIR"

# --- Models on the volume ---------------------------------------------------
# Recreate the image's model folder layout on the volume (folders only, never
# files), then point /ComfyUI/models at it. Idempotent across restarts.
(cd "$COMFYUI_DIR/models" 2>/dev/null && find . -type d -exec mkdir -p "$DATA_DIR/models/{}" \;)
if [ ! -L "$COMFYUI_DIR/models" ]; then
    rm -rf "$COMFYUI_DIR/models"
    ln -s "$DATA_DIR/models" "$COMFYUI_DIR/models"
fi

# --- Model downloads (step 4) -------------------------------------------------

# --- JupyterLab -------------------------------------------------------------
if [ "${JUPYTER_ENABLED:-true}" != "false" ]; then
    if [ -z "${JUPYTER_TOKEN:-}" ]; then
        echo "JupyterLab has no login: anyone with the pod URL can open it. Set JUPYTER_TOKEN to require one."
    fi
    jupyter-lab --ip=0.0.0.0 --port=8888 --allow-root --no-browser \
        --ServerApp.token="${JUPYTER_TOKEN:-}" --ServerApp.password='' \
        --ServerApp.allow_origin='*' --notebook-dir="$VOLUME" \
        > "$LOG_DIR/jupyter.log" 2>&1 &
fi

# --- ComfyUI ----------------------------------------------------------------
args=(
    --listen 0.0.0.0 --port 8188
    --input-directory "$DATA_DIR/input"
    --output-directory "$DATA_DIR/output"
    --user-directory "$DATA_DIR/user"
)
if [ "${USE_SAGE:-false}" = "true" ]; then
    args+=(--use-sage-attention)
fi
read -ra extra <<< "${COMFY_EXTRA_ARGS:-}"
args+=("${extra[@]}")

echo "Starting ComfyUI: python3 main.py ${args[*]}"
cd "$COMFYUI_DIR"
python3 main.py "${args[@]}" 2>&1 | tee -a "$LOG_DIR/comfyui.log"

# Keep the pod up if ComfyUI exits, so the log can be read from JupyterLab.
echo "ComfyUI exited. See $LOG_DIR/comfyui.log. Container kept alive for debugging."
sleep infinity
