# RunPod MiniMax H3 template

Our own RunPod pod template for MiniMax H3 in ComfyUI, aimed at video of a real
person (likeness) doing athletic movements. Inspired by
[Hearmeman24/comfyui-minimax](https://github.com/Hearmeman24/comfyui-minimax),
but written from scratch, without its boot-time sync from GitHub: the image is
the whole template, and nothing changes until we build a new version.

## What's in the image

| Layer | Source |
| --- | --- |
| Ubuntu 24.04, CUDA 13.0, Python 3.12, torch 2.11, ComfyUI v0.42.1, ComfyUI-Manager, JupyterLab, SageAttention | `hearmeman/comfyui-base`, pinned by digest in the [Dockerfile](Dockerfile) |
| Custom nodes | Pinned in the [Dockerfile](Dockerfile), listed below |
| Boot script | [src/start.sh](src/start.sh) |

### Custom nodes

ComfyUI v0.42.1 already includes pose control (Fun ControlNet with SDPose pose
extraction), frame interpolation (RIFE, FILM) and video load/save, so those
need no extra packs.

| Pack | Why | License |
| --- | --- | --- |
| [ComfyUI-KJNodes](https://github.com/kijai/ComfyUI-KJNodes) | Utilities many community workflows use | GPL-3.0 |
| [ComfyUI-VideoHelperSuite](https://github.com/Kosinkadink/ComfyUI-VideoHelperSuite) | Video load/combine nodes many community workflows use | GPL-3.0 |
| [Comfyui_Minimax_h3_latent_Upscaler](https://github.com/LBH-123-AI/Comfyui_Minimax_h3_latent_Upscaler) | Latent upscaling for H3 | MIT |
| [ComfyUI-H3-Motion-Context](https://github.com/NikoDemon80/ComfyUI-H3-Motion-Context) | Clip chaining that carries motion and audio across joins | GPL-3.0 |
| [ComfyUI-MiniMaxH3Mod](https://github.com/Luisacaotica/ComfyUI-MiniMaxH3Mod) | RefMods: likeness references without training a LoRA | MIT |
| [rgthree-comfy](https://github.com/rgthree/rgthree-comfy) | Fast Groups Bypasser (switch workflow sections on/off), Power Lora Loader (stack LoRAs with per-LoRA toggles) | MIT |
| [ComfyUI-Spectrum-MiniMax-H3](https://github.com/xmarre/ComfyUI-Spectrum-MiniMax-H3) | Optional sampling speed-up with approximate output; inactive unless its node is in the workflow | GPL-3.0 |

The build loads every node once on CPU and fails if any pack fails to import.

## Volume layout

Everything that should survive a pod lives on the network volume at `/workspace`:

```
/workspace/ComfyUI/models   models (/ComfyUI/models links here)
/workspace/ComfyUI/input    input images and videos
/workspace/ComfyUI/output   generated videos
/workspace/ComfyUI/user     settings and saved workflows
/workspace/logs             comfyui.log, downloads.log, jupyter.log
```

## Environment variables

### Launch

| Variable | Default | Effect |
| --- | --- | --- |
| `USE_SAGE` | `false` | `true` launches ComfyUI with SageAttention. Off by default: INT8 + Sage can morph the end of clips |
| `DYNAMIC_VRAM` | `auto` | ComfyUI's dynamic VRAM loading. `auto` keeps it on, but turns it off when `USE_SAGE=true`; `true`/`false` force it. See [below](#dynamic-vram) |
| `COMFY_EXTRA_ARGS` | _empty_ | Extra ComfyUI command-line flags |
| `JUPYTER_ENABLED` | `true` | `false` skips JupyterLab |
| `JUPYTER_TOKEN` | _empty_ | Token JupyterLab asks for. Empty means no login |

### Model downloads

Nothing is downloaded unless a switch is set. Downloads run in the background
on every boot, so ComfyUI opens straight away; models appear as each file
finishes (press **R** in ComfyUI to refresh). Files already on the volume
with the right size are skipped, so a restart costs seconds. A stopped
download resumes on the next boot (unfinished files end in `.part`, which
ComfyUI ignores). Progress goes to the pod log and
`/workspace/logs/downloads.log`; the last line says `ALL DOWNLOADS FINISHED`
or lists what failed.

Switches take `true`/`false`. Choice variables take one value, or several
separated by commas to download more than one (for example
`H3_PRECISION=pruned_int8,pruned_bf16` to compare the two).

| Variable | Default | Downloads | Size |
| --- | --- | --- | --- |
| `DOWNLOAD_REF2VA` | `false` | H3 reference-to-video model (likeness from reference photos; used for pose control too) | see `H3_PRECISION` |
| `DOWNLOAD_FL2VA` | `false` | H3 text/image-to-video model (first/last frame) | see `H3_PRECISION` |
| `H3_PRECISION` | `pruned_int8` | Which build of each H3 model above. `pruned_int8` 21 GB (Comfy's default), `pruned_fp8` 21 GB, `pruned_w6a8` 16 GB, `pruned_bf16` 40 GB (unquantized), `full_int8` 34 GB, `full_bf16` 66 GB | per model |
| `TEXT_ENCODER` | `int8` | H3's Qwen3-VL 32B text encoder, fetched with any H3 model. `int8` 27 GB, `nvfp4` 16 GB (Blackwell GPUs only: RTX 50xx, RTX PRO 6000), `bf16` 52 GB | per choice |
| `VIDEO_VAE` | `fp16` | H3 video VAE, fetched with any H3 model. `fp16` 5.2 GB, `int8` 2.8 GB (decodes ~2x faster). The audio VAE (0.6 GB) always comes along | per choice |
| `DOWNLOAD_POSE_CONTROL` | `false` | Fun ControlNet Union 2.0 patch (int8 4.5 GB, or bf16 8.4 GB for `*bf16` precisions) + SDPose pose extractor (1.9 GB) + RT-DETR person detector (0.1 GB) | 6.6 GB |
| `DOWNLOAD_UPSCALER` | `false` | H3 latent upscaler (bf16) | 0.7 GB |
| `DOWNLOAD_INTERPOLATION` | `false` | RIFE 4.26 and FILM for ComfyUI's built-in frame interpolation | 0.1 GB |
| `DOWNLOAD_TURBO_LORAS` | `false` | LightX2V 8-step turbo LoRAs (v1.1) for the enabled H3 models (both if none is). **Drafts only**: they smooth skin and hair detail | 2 GB each |
| `DOWNLOAD_ANTIBURN` | `false` | H3 Anti-Burn LoRA, for clips chained after the first | 0.3 GB |
| `PROMPT_HELPER` | `none` | Qwen3.5 for ComfyUI's built-in Generate Text node, which runs on the pod (prompts never leave it). `2b` 4.5 GB, `4b` 9.3 GB, `9b` 19.3 GB | per choice |
| `HF_LORAS` | _empty_ | Extra LoRAs from Hugging Face: comma-separated file links (`/blob/` or `/resolve/`), saved to `models/loras` | per file |
| `CIVITAI_LORAS` | _empty_ | Extra LoRAs from CivitAI: comma-separated model **version** IDs (the number after `modelVersionId=` in the page URL), saved to `models/loras` | per file |
| `HF_TOKEN` | _empty_ | Hugging Face token, for gated or private files | |
| `CIVITAI_TOKEN` | _empty_ | CivitAI API key; most CivitAI downloads need one | |

Example first-boot sizes:

| Setup | Download |
| --- | --- |
| `DOWNLOAD_REF2VA=true` (defaults: pruned_int8, int8 encoder, fp16 VAE) | 54 GB |
| + `DOWNLOAD_POSE_CONTROL=true` | 61 GB |
| + `DOWNLOAD_FL2VA=true` | 82 GB |
| `DOWNLOAD_REF2VA=true`, `H3_PRECISION=pruned_bf16` | 73 GB |
| `DOWNLOAD_REF2VA=true`, `TEXT_ENCODER=nvfp4` (Blackwell) | 42 GB |

Size the network volume with room for outputs on top; 150 GB covers both H3
models with pose control and the extras.

### Dynamic VRAM

ComfyUI's dynamic VRAM (on by default) streams weights onto the GPU as
they're needed. With H3 int8/fp8 models it can crash a run with
`CUDA error: an illegal memory access was encountered`, after which every
later run fails until ComfyUI restarts
([Comfy-Org/ComfyUI#15271](https://github.com/Comfy-Org/ComfyUI/issues/15271),
still open). Most reports involve SageAttention, so `DYNAMIC_VRAM=auto` turns
it off only when `USE_SAGE=true`. If you see that error without Sage, set
`DYNAMIC_VRAM=false`. The cost is less efficient VRAM use, which matters
little on a 96 GB card and can mean out-of-memory errors on small ones.

## Ports

- `8188` ComfyUI (HTTP)
- `8888` JupyterLab (HTTP)

## Building

GitHub Actions ([build.yml](.github/workflows/build.yml)) builds when a `v*`
tag is pushed, and pushes to `ghcr.io/<owner>/<repo>` as `X.Y.Z` and `latest`.
Pushing commits alone builds nothing. No local Docker is needed. Before
building, it checks that every model URL a switch can pick still exists
(`python3 src/download_models.py --check` runs the same check locally). Release a
version by tagging the commit (or in GitHub Desktop: History, right-click,
Create Tag, then Push origin):

```bash
git tag v0.3.0 && git push origin v0.3.0
```

Point the RunPod template at a version tag such as `0.3.0`, never `latest`.
Pods need a host with CUDA 13.0 or higher.

## Roadmap

1. ~~Foundation: own repo on a pinned base image~~
2. ~~Repo and build pipeline~~
3. ~~Custom nodes~~
4. Env-driven model downloads to the volume (precision, pose control, upscaler, interpolation, LoRAs) ← current
5. Workflows (Ref2VA, pose control + Ref2VA, chaining, interpolation)
6. RunPod template entry
7. Test on a cheap pod, then an RTX PRO 6000
