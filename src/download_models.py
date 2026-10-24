#!/usr/bin/env python3
"""Download the models picked by environment variables to the network volume.

Called by start.sh in the background on every boot, so ComfyUI is reachable
while files arrive. Everything is off by default: with no variables set this
downloads nothing. See the README for the variables and disk sizes.

How a file is fetched:
  - It goes to <name>.part first and is renamed only after aria2c finishes,
    so ComfyUI never lists a half-written model.
  - aria2c resumes a .part left by a stopped pod (-c).
  - A file already on the volume is kept if its size matches the server's
    (re-downloaded if it doesn't); if the size can't be checked it is kept.
  - HF_TOKEN / CIVITAI_TOKEN are sent as headers, never put in URLs or logs.

`download_models.py --check` prints and verifies (HTTP HEAD) every URL any
switch can pick, without downloading anything.
"""

import os
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import json

MODELS_DIR = os.environ.get("MODELS_DIR", "/workspace/ComfyUI/models")

HF = "https://huggingface.co"
H3 = f"{HF}/Comfy-Org/MiniMax-H3/resolve/main"

# H3_PRECISION value -> file suffix of the diffusion model (fl2va and ref2va
# come in the same builds and sizes).
PRECISIONS = {
    "pruned_int8": "pruned_int8_convrot",  # 21 GB, Comfy templates' default
    "pruned_fp8": "pruned_fp8_scaled",     # 21 GB
    "pruned_w6a8": "pruned_w6a8",          # 16 GB
    "pruned_bf16": "pruned_bf16",          # 40 GB, unquantized
    "full_int8": "int8_convrot",           # 34 GB, full (unpruned) build
    "full_bf16": "bf16",                   # 66 GB, full unquantized build
}
TEXT_ENCODERS = {
    "int8": "int8_convrot",  # 27 GB
    "nvfp4": "nvfp4_awq",    # 16 GB, Blackwell GPUs only (RTX 50xx, RTX PRO 6000)
    "bf16": "bf16",          # 52 GB
}
VIDEO_VAES = {
    "fp16": "fp16",          # 5.2 GB
    "int8": "int8_convrot",  # 2.8 GB, decodes ~2x faster
}
PROMPT_HELPERS = {"2b", "4b", "9b"}  # Qwen3.5 for ComfyUI's Generate Text node


def env_bool(name):
    return os.environ.get(name, "false").strip().lower() in ("1", "true", "yes", "on")


def env_list(name, default=""):
    raw = os.environ.get(name, default)
    return [v.strip() for v in raw.replace(";", ",").split(",") if v.strip()]


def pick(name, default, allowed):
    """Comma-separated choices from env var `name`. Unknown values are dropped;
    if none is left, the default is used, so a typo never means no model."""
    out = []
    for v in env_list(name, default):
        v = v.lower()
        if v in allowed:
            if v not in out:
                out.append(v)
        else:
            log(f"WARNING: {name}={v} is not one of {', '.join(sorted(allowed))}; ignored")
    if not out:
        if os.environ.get(name, "").strip():
            log(f"WARNING: no valid {name} value; using the default, {default}")
        out = [default]
    return out


def log(msg):
    print(f"[models] {msg}", flush=True)


def hf_url(url):
    """Accept /blob/ links copied from the Hugging Face website."""
    return url.replace("/blob/", "/resolve/", 1) if url.startswith(HF) else url


def plan(check_all=False):
    """List of (subdir, url, filename, kind) to fetch. kind picks the auth header."""
    files = []

    def add(subdir, url, name=None, kind="hf"):
        name = name or os.path.basename(urllib.parse.urlparse(url).path)
        if not any(f[0] == subdir and f[2] == name for f in files):
            files.append((subdir, url, name, kind))

    every = check_all
    modes = [m for m in ("ref2va", "fl2va") if every or env_bool(f"DOWNLOAD_{m.upper()}")]
    precisions = list(PRECISIONS) if every else pick("H3_PRECISION", "pruned_int8", PRECISIONS)

    for mode in modes:
        for p in precisions:
            add("diffusion_models", f"{H3}/diffusion_models/minimax_h3_{mode}_{PRECISIONS[p]}.safetensors")
    if modes:
        for t in (list(TEXT_ENCODERS) if every else pick("TEXT_ENCODER", "int8", TEXT_ENCODERS)):
            add("text_encoders", f"{H3}/text_encoders/qwen3vl_32b_minimax_h3_{TEXT_ENCODERS[t]}.safetensors")
        for v in (list(VIDEO_VAES) if every else pick("VIDEO_VAE", "fp16", VIDEO_VAES)):
            add("vae", f"{H3}/vae/minimax_h3_video_vae_{VIDEO_VAES[v]}.safetensors")
        add("vae", f"{H3}/vae/minimax_h3_audio_vae_fp32.safetensors")

    if every or env_bool("DOWNLOAD_POSE_CONTROL"):
        # Union 2.0 (Sep 2026) supersedes the first release; ComfyUI 0.42.1
        # loads it. bf16 patch for bf16 models, int8 for everything else.
        patches = {"bf16" if "bf16" in p else "int8_convrot" for p in precisions} or {"int8_convrot"}
        for v in sorted(patches):
            add("model_patches", f"{H3}/model_patches/minimax_h3_fun_controlnet_union_2.0_pruned_{v}.safetensors")
        add("checkpoints", f"{HF}/Comfy-Org/SDPose/resolve/main/checkpoints/sdpose_wholebody_fp16.safetensors")
        add("diffusion_models", f"{HF}/Comfy-Org/SDPose/resolve/main/diffusion_models/rt_detr_v4-x-hgnet_fp16.safetensors")

    if every or env_bool("DOWNLOAD_UPSCALER"):
        add("latent_upscale_models", f"{HF}/LBH-123-AI/Minimax_h3_latent_Upscaler/resolve/main/"
            "minimax_h3_latent_upscaler_3d_conv_v1/minimax_h3_latent_upscaler_3d_conv_v1_bf16.safetensors")

    if every or env_bool("DOWNLOAD_INTERPOLATION"):
        # Files for ComfyUI's built-in "Load Frame Interpolation Model" node.
        # RIFE is the fast default; FILM copes better with large motion.
        base = f"{HF}/Comfy-Org/Frame-Interpolation/resolve/main/frame_interpolation"
        add("frame_interpolation", f"{base}/rife_v4.26.safetensors")
        add("frame_interpolation", f"{base}/film_net_fp16.safetensors")

    if every or env_bool("DOWNLOAD_TURBO_LORAS"):
        # Drafts only: distilled schedules smooth skin and hair detail.
        for mode in (modes or ["ref2va", "fl2va"]):
            m = mode[:-1]  # ref2va -> ref2v
            add("loras", f"{HF}/lightx2v/Minimax-h3-Turbo/resolve/main/"
                f"minimax_h3_{m}_turbo_8step_v1.1_768p_comfyui_bf16.safetensors")

    if every or env_bool("DOWNLOAD_ANTIBURN"):
        add("loras", f"{HF}/Imagineer13/H3-Anti-Burn-LoRA/resolve/main/h3_antiburn_universal_v1.safetensors")

    helpers = list(PROMPT_HELPERS) if every else pick("PROMPT_HELPER", "none", PROMPT_HELPERS | {"none"})
    for h in sorted(set(helpers) - {"none"}):
        add("text_encoders", f"{HF}/Comfy-Org/Qwen3.5/resolve/main/text_encoders/qwen3.5_{h}_bf16.safetensors")

    for url in env_list("HF_LORAS"):
        add("loras", hf_url(url))

    for version_id in env_list("CIVITAI_LORAS"):
        info = civitai_file(version_id)
        if info:
            add("loras", info[0], info[1], kind="civitai")

    return files


def auth_headers(kind):
    token = os.environ.get("HF_TOKEN" if kind == "hf" else "CIVITAI_TOKEN", "").strip()
    if kind == "civitai" and not token:
        token = os.environ.get("civitai_token", "").strip()
    return {"Authorization": f"Bearer {token}"} if token else {}


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


def probe(url, kind):
    """Follow redirects with HEAD requests.

    Returns (size or None, url for aria2c, headers for aria2c, last HTTP
    status). The token goes only to the original host: aria2c gets the first
    link outside it (a signed CDN link) with no Authorization header, which
    such links can reject. Hugging Face reports the size as X-Linked-Size on
    a redirect hop; other servers as Content-Length.
    """
    host = urllib.parse.urlparse(url).netloc
    auth = auth_headers(kind)
    opener = urllib.request.build_opener(_NoRedirect)
    size, status, current, handoff = None, None, url, None
    for _ in range(8):
        on_host = urllib.parse.urlparse(current).netloc == host
        headers = {"User-Agent": "runpod-minimax-h3", **(auth if on_host else {})}
        try:
            resp = opener.open(urllib.request.Request(current, method="HEAD", headers=headers), timeout=30)
        except urllib.error.HTTPError as e:
            resp = e
        except (urllib.error.URLError, OSError):
            break
        status = resp.status
        if resp.headers.get("X-Linked-Size"):
            size = int(resp.headers["X-Linked-Size"])
        location = resp.headers.get("Location")
        if status in (301, 302, 303, 307, 308) and location:
            current = urllib.parse.urljoin(current, location)
            if handoff is None and urllib.parse.urlparse(current).netloc != host:
                handoff = current
            continue
        if status == 200 and size is None and resp.headers.get("Content-Length"):
            size = int(resp.headers["Content-Length"])
        break
    if not auth:
        return size, url, {}, status
    return size, handoff or url, ({} if handoff else auth), status


def civitai_file(version_id):
    """(download url, file name) of a CivitAI model version's primary file."""
    if not version_id.isdigit():
        log(f"WARNING: CIVITAI_LORAS entry '{version_id}' is not a model version ID (digits); skipped")
        return None
    api = f"https://civitai.com/api/v1/model-versions/{version_id}"
    try:
        req = urllib.request.Request(api, headers={"User-Agent": "runpod-minimax-h3", **auth_headers("civitai")})
        with urllib.request.urlopen(req, timeout=30) as r:
            data = json.load(r)
    except (urllib.error.URLError, OSError, ValueError) as e:
        log(f"ERROR: CivitAI version {version_id}: could not read {api} ({e}); skipped")
        return None
    files = data.get("files") or []
    primary = next((f for f in files if f.get("primary")), files[0] if files else None)
    if not primary:
        log(f"ERROR: CivitAI version {version_id} lists no files; skipped")
        return None
    return f"https://civitai.com/api/download/models/{version_id}", primary["name"]


def human(n):
    return "?" if n is None else f"{n / 1e9:.2f} GB" if n >= 1e8 else f"{n / 1e6:.1f} MB"


def fetch(subdir, url, name, kind):
    """Returns 'skipped', 'downloaded' or 'failed'."""
    dest_dir = os.path.join(MODELS_DIR, subdir)
    dest = os.path.join(dest_dir, name)
    part = dest + ".part"
    os.makedirs(dest_dir, exist_ok=True)
    expected, source, headers, status = probe(url, kind)
    refused = status in (401, 403, 404)

    if os.path.exists(dest):
        have = os.path.getsize(dest)
        if expected is None or have == expected:
            note = "" if expected is not None else f" (size not checked: {f'HTTP {status}' if refused else 'server unreachable or silent'})"
            log(f"skip  {subdir}/{name}  {human(have)} already on the volume{note}")
            return "skipped"
        log(f"size mismatch for {subdir}/{name}: {human(have)} on the volume, {human(expected)} on the server; downloading again")
        os.remove(dest)

    if refused:
        hint = " (gated or private? set HF_TOKEN / CIVITAI_TOKEN)" if status in (401, 403) else ""
        log(f"FAILED {subdir}/{name}: server answered HTTP {status} for {url}{hint}")
        return "failed"

    free = shutil.disk_usage(dest_dir).free
    if expected and expected > free:
        log(f"WARNING: {subdir}/{name} needs {human(expected)} but the volume reports {human(free)} free")

    resuming = os.path.exists(part)
    log(f"{'resume' if resuming else 'get  '} {subdir}/{name}  {human(expected)}  from {url}")
    cmd = [
        "aria2c", "--continue=true", "--max-connection-per-server=16", "--split=16",
        "--min-split-size=10M", "--file-allocation=none", "--auto-file-renaming=false",
        "--allow-overwrite=true", "--max-tries=5", "--retry-wait=10",
        "--console-log-level=warn", "--summary-interval=60", "--show-console-readout=false",
        "--download-result=hide",
        "--dir", dest_dir, "--out", os.path.basename(part), source,
    ]
    for k, v in headers.items():
        cmd[1:1] = ["--header", f"{k}: {v}"]
    started = time.time()
    # Keep aria2c's once-a-minute progress line ("[#id 3.1GiB/20GiB(15%) ...
    # DL:250MiB ETA:1m10s]") and its errors, drop the banner around them.
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, errors="replace")
    for line in proc.stdout:
        line = line.strip()
        if line and not line.startswith(("***", "===", "---", "FILE:")):
            log(f"   {line}")
    if proc.wait() != 0:
        log(f"FAILED {subdir}/{name} (kept {os.path.basename(part)}; the next boot resumes it)")
        return "failed"
    got = os.path.getsize(part)
    if expected is not None and got != expected:
        log(f"FAILED {subdir}/{name}: got {human(got)}, expected {human(expected)}; removed")
        os.remove(part)
        return "failed"
    os.replace(part, dest)
    secs = max(time.time() - started, 1)
    log(f"done  {subdir}/{name}  {human(got)} in {secs / 60:.1f} min ({got / secs / 1e6:.0f} MB/s)")
    return "downloaded"


def check():
    """Print every URL any switch can pick and verify that it resolves."""
    os.environ.setdefault("PROMPT_HELPER", "none")
    bad = 0
    for subdir, url, name, kind in plan(check_all=True):
        size, _, _, status = probe(url, kind)
        bad += size is None
        print(f"{'OK ' if size else 'BAD'} {human(size):>9}  {status}  {subdir}/{name}")
    return 1 if bad else 0


def main():
    if "--check" in sys.argv:
        return check()
    files = plan()
    if not files:
        log("no download switches set; nothing to download")
        return 0
    log(f"{len(files)} file(s) selected; models go to {MODELS_DIR}")
    results = {"skipped": 0, "downloaded": 0, "failed": 0}
    for f in files:
        results[fetch(*f)] += 1
    summary = ", ".join(f"{v} {k}" for k, v in results.items())
    if results["failed"]:
        log(f"FINISHED WITH ERRORS: {summary}. Restart the pod to retry.")
        return 1
    log(f"ALL DOWNLOADS FINISHED: {summary}. Press R in ComfyUI to refresh model lists.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
