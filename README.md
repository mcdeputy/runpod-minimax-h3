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
/workspace/logs             comfyui.log, jupyter.log
```

## Environment variables

| Variable | Default | Effect |
| --- | --- | --- |
| `USE_SAGE` | `false` | `true` launches ComfyUI with SageAttention. Off by default: INT8 + Sage can morph the end of clips |
| `COMFY_EXTRA_ARGS` | _empty_ | Extra ComfyUI command-line flags |
| `JUPYTER_ENABLED` | `true` | `false` skips JupyterLab |
| `JUPYTER_TOKEN` | _empty_ | Token JupyterLab asks for. Empty means no login |

Model download switches come in step 4.

## Ports

- `8188` ComfyUI (HTTP)
- `8888` JupyterLab (HTTP)

## Building

GitHub Actions ([build.yml](.github/workflows/build.yml)) builds when a `v*`
tag is pushed, and pushes to `ghcr.io/<owner>/<repo>` as `X.Y.Z` and `latest`.
Pushing commits alone builds nothing. No local Docker is needed. Release a
version by tagging the commit (or in GitHub Desktop: History, right-click,
Create Tag, then Push origin):

```bash
git tag v0.2.0 && git push origin v0.2.0
```

Point the RunPod template at a version tag such as `0.2.0`, never `latest`.
Pods need a host with CUDA 13.0 or higher.

## Roadmap

1. ~~Foundation: own repo on a pinned base image~~
2. ~~Repo and build pipeline~~
3. Custom nodes ← current
4. Env-driven model downloads to the volume (precision, pose control, upscaler, interpolation, LoRAs)
5. Workflows (Ref2VA, pose control + Ref2VA, chaining, interpolation)
6. RunPod template entry
7. Test on a cheap pod, then an RTX PRO 6000
