---
lab3_genai_diff:
  instrumentation: "opentelemetry-instrumentation-genai-openai 1.2b0 (opentelemetry-util-genai 1.2b0), opentelemetry-sdk 1.45.0, openai 3.19.2"
  spec_ref: "semantic-conventions@v1.41.1"
  attributes:
    - {name: gen_ai.operation.name, emitted: true, in_spec: true, stability: development}
    - {name: gen_ai.provider.name, emitted: true, in_spec: true, stability: development}
    - {name: gen_ai.request.model, emitted: true, in_spec: true, stability: development}
    - {name: gen_ai.request.temperature, emitted: true, in_spec: true, stability: development}
    - {name: gen_ai.request.max_tokens, emitted: true, in_spec: true, stability: development}
    - {name: gen_ai.response.finish_reasons, emitted: true, in_spec: true, stability: development}
    - {name: gen_ai.response.model, emitted: true, in_spec: true, stability: development}
    - {name: gen_ai.response.id, emitted: true, in_spec: true, stability: development}
    - {name: gen_ai.usage.input_tokens, emitted: true, in_spec: true, stability: development}
    - {name: gen_ai.usage.output_tokens, emitted: true, in_spec: true, stability: development}
    - {name: gen_ai.request.top_p, emitted: false, in_spec: true, stability: development}
    - {name: gen_ai.system, emitted: false, in_spec: true, stability: deprecated}
---
<!-- ai-generated: 70% - Claude Code ran the call, read the registry of v1.41.1 and drafted the text; checked by me -->

# What the library emits, against the spec

The call: `genai/call_llm.py` makes one chat completion through the official `openai` client against a local
Ollama (`qwen3:0.6b`, OpenAI-compatible endpoint `/v1`, run in Docker), instrumented with
`OpenAIInstrumentor` from `opentelemetry-instrumentation-genai-openai` 1.2b0. The SDK's `FileSpanExporter`
(`opentelemetry-exporter-otlp-json-file` 0.66b0) wrote the one span, `chat qwen3:0.6b`, to `genai/spans.json`.
The package versions are pinned in `genai/requirements.txt`.

The reference: `semantic-conventions@v1.41.1`, the last release of the main repository that still held the GenAI
attribute registry (`model/gen-ai/registry.yaml`, and `model/gen-ai/deprecated/registry-deprecated.yaml`).

**What agrees.** All ten `gen_ai.*` attributes on the span are defined in v1.41.1, all with stability
`development`: the operation (`chat`), the provider, the requested and the answered model, the request parameters
I set (`temperature`, `max_tokens`), the finish reasons, the response id, and the input and output token counts.
The library uses `gen_ai.provider.name`, not the deprecated `gen_ai.system`, which v1.41.1 lists only in its
deprecated registry; so for this call there is no attribute the library made up under `gen_ai.*`.

**What does not, or not quite.**

- `gen_ai.provider.name` says `openai`, although the model ran in Ollama. The library derives the provider from
  the client it wraps, not from the server it talked to; only `server.address` (`lab3-ollama`) and the
  non-standard `openai.response.system_fingerprint` (`fp_ollama`) reveal the real backend. A dashboard that groups
  cost or latency by provider would put my local model under OpenAI.
- `gen_ai.request.top_p` is in the spec but not emitted, because I did not set it: the library records request
  parameters only when the caller passes them, so the absence of an attribute does not mean the default was used
  by the server.
- `openai.response.system_fingerprint` sits outside the `gen_ai.*` namespace, under a vendor prefix: it is not part
  of the GenAI registry at all.
- Everything here is `development`: none of these names is stable, and the conventions have since moved to their
  own repository and changed again, so a dashboard or an alert built on these attribute names is built on sand and
  needs its library version pinned together with it.

Prompt and completion content was not captured (the library's default): only the metadata above is in the span.
