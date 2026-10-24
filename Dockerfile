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

# Custom nodes (step 3) go here, each pinned to a commit.

COPY src/ /opt/template/
RUN chmod +x /opt/template/start.sh

# ComfyUI, JupyterLab
EXPOSE 8188 8888

CMD ["/opt/template/start.sh"]
