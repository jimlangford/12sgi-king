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
