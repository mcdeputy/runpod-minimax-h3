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
| Custom nodes | _step 3_ |
| Boot script | [src/start.sh](src/start.sh) |

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

GitHub Actions ([build.yml](.github/workflows/build.yml)) builds on every push
to `main` and on `v*` tags, and pushes to `ghcr.io/<owner>/<repo>`. No local
Docker is needed. Release a version with:

```bash
git tag v0.1.0 && git push origin v0.1.0
```

## Roadmap

1. ~~Foundation: own repo on a pinned base image~~
2. Repo and build pipeline ← current
3. Custom nodes (pose control, video helpers, frame interpolation)
4. Env-driven model downloads to the volume (precision, pose control, upscaler, interpolation, LoRAs)
5. Workflows (Ref2VA, pose control + Ref2VA, chaining, interpolation)
6. RunPod template entry
7. Test on a cheap pod, then an RTX PRO 6000
