# QUAD OS single-model default

QUAD OS uses `king-quad-os-unified` as its one default chat model in Ollama.
The model is a Modelfile alias of `king-quad-os`, with a 4,096-token context
and a 512-token output cap. It reuses the installed weight layers and keeps the
existing QUAD OS system prompt. AI Gateway profiles select this same base model;
their authorization and tool scopes remain profile-specific.

## Why aliases stay installed

The local inventory contains 51 Ollama tags, but inspection of their Modelfiles
found seven base-weight groups. Forty tags, including `king-quad-os`, share the
same Gemma 3 weight blob. Ollama tags also carry their own prompt and parameter
settings. Keeping those tags avoids breaking older scripts while the gateway
converges on one default.

Embeddings, vision-specific flows, and code-specialized workflows can still use
their purpose-built models where those capabilities are required. The unified
default covers general reasoning and everyday QUAD OS work.

## Laptop memory profile

The inspected machine has an RTX 4070 Laptop GPU with 8 GB VRAM and 32 GB system
RAM. At review time, Ollama reported about 7.4 GB VRAM in use, GPU utilization
at 100%, and about 2.3 GB free system RAM. The main `king-quad-os` Modelfile had
a 65,536-token context. The unified alias caps context at 4K to reduce KV-cache
pressure and keep more room for the GPU's other workloads.

For the native Windows Ollama service, a measured production tuning pass should
consider `OLLAMA_NUM_PARALLEL=1`, `OLLAMA_MAX_LOADED_MODELS=1`, and a short
`OLLAMA_KEEP_ALIVE` when ComfyUI shares the GPU. Apply those settings only after
an idle-window benchmark confirms chat latency and creative-workload recovery.

## Verification boundary

The alias was created locally and its parameters, shared base weights, and
inherited system prompt were inspected. All 11 AI Gateway profiles now target
the same model. A live generation-speed benchmark remains to be run when GPU
utilization and available RAM return to a safe baseline; the current saturated
snapshot is not a valid performance measurement.

## Weight consolidation and video models

The current Ollama API inventory contains 52 tags and seven distinct base
weight blobs. Forty-one tags, including the unified QUAD OS alias, point to the
same Gemma 3 base blob. Those tags already share the stored weights; merging
them again would not reclaim meaningful disk space and would discard their
separate prompts and parameters. Keep one default chat model in the Gateway and
retain specialist vision, embedding, and coding models for their task-specific
capabilities. Ollama Modelfiles can reference a base model and compatible
adapters; they are not a safe way to blend unrelated model families into one
universal weight set.

ComfyUI now registers Kandinsky 5 as its only local visual and video-generation
engine. The LTX, Wan, RIFE, and FILM model workflows are removed from active
routing. Kandinsky's three diffusion weights remain. Its Hunyuan VAE and shared
text encoders remain because Kandinsky workflows use them; the similarly named
Hunyuan 3D models are also retained because they are not video generators.

The local ComfyUI cleanup removes about 41.39 GiB of LTX, Wan, RIFE, and FILM
weights and their model-specific files. The GPU Router image now includes only
the canonical job contract, Kandinsky media role/workflow records, and the
RTX 4070 GPU profile it needs at runtime; the Docker build allowlist continues
to exclude unrelated private configuration.
