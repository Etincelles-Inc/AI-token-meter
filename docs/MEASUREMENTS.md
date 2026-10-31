# Native timing and adapter contract

Polling refreshes the display. It is never the denominator used to calculate a native speed.

## vLLM

Fresh Read = delta request_prefill_kv_computed_tokens_sum / delta request_prefill_time_seconds_sum, using matched request histogram counts. Cached prompt tokens are excluded by that engine field. If these metrics are missing, Read stays unavailable.

Completed Write = (delta request_generation_tokens_sum - delta request_generation_tokens_count) / delta request_decode_time_seconds_sum. Subtracting request count excludes one first output token per request. This matches a first-to-last output-token interval.

Live Write = (delta generation_tokens_total - delta time_to_first_token_seconds_count) / delta inter_token_latency_seconds_sum while requests are active. The inter-token interval count is only a consistency gate, never a substitute for token count. Speculative packets may contain multiple tokens.

Counters reset safely. Inconsistent histogram counts wait for a coherent scrape. Initial cumulative observations are labeled Run average; subsequent completions are labeled Last prefill/decode or a cohort size. Multiple engines/requests are weighted by summed engine time, not by the arithmetic mean of speeds.

The vLLM design defines phases and scheduling semantics. Queue/network delay is not treated as prefill compute. Server preemption/scheduling behavior within native phase timings follows the installed engine version.

Primary sources:
- [vLLM metrics](https://docs.vllm.ai/en/latest/usage/metrics/)
- [vLLM metrics design](https://github.com/vllm-project/vllm/blob/main/docs/design/metrics.md)
- [NVIDIA benchmark metric definitions](https://docs.nvidia.com/nim/benchmarking/llm/metrics)

## Ollama

Read = prompt_eval_count / (prompt_eval_duration / 1e9).
Write = eval_count / (eval_duration / 1e9).

These use Ollama's own count/duration convention, which differs from vLLM's first-to-last-token convention. Do not subtract one token again without changing the duration definition. Total duration, queue/load time and network round trips are not used.

Only the final native response supplies these fields; native streaming replies update the meter when done is true. Capture supports both NDJSON streams and ordinary JSON. OpenAI-compatible usage counts do not imply that native timing exists.

Cached prompts and engine accounting can affect the native prompt count/duration relationship. The widget labels this as Ollama native timing rather than claiming vLLM-style uncached KV accounting.

Primary sources:
- [Ollama generate](https://docs.ollama.com/api/generate)
- [Ollama chat](https://docs.ollama.com/api/chat)

## llama.cpp

The metrics adapter uses prompt_tokens_total / prompt_seconds_total and tokens_predicted_total / tokens_predicted_seconds_total deltas under the llamacpp prefix. The first observation uses server-run totals; idle polls hold the last timing.

The capture adapter prefers timings.prompt_per_second and timings.predicted_per_second. If absent it derives rates from prompt_n/prompt_ms and predicted_n/predicted_ms. These are the engine's own timing convention.

[llama.cpp server documentation](https://github.com/ggml-org/llama.cpp/blob/master/tools/server/README.md)

## Custom engine hook

Return an additional top-level token_speedometer object in a JSON response or a streamed JSON event. It must contain measured engine phase data, not client wall-clock approximations:

- uncached_prompt_tokens: nonnegative token count actually processed
- prefill_seconds: native prompt-processing duration
- output_tokens: number of generated tokens including the first
- decode_seconds: native first-to-last generated-token duration

Read is uncached_prompt_tokens/prefill_seconds; Write is (output_tokens-1)/decode_seconds. Missing/zero durations remain unavailable. Ordinary OpenAI usage is deliberately insufficient. Extend response_timing in token_speedometer/adapters.py for engines with another documented native format.

## Display freshness and concurrency

The GUI refreshes four times per second; metrics are normally polled once per second. Changing either cadence does not change a native speed. A held reading includes its age, or Run average where the last request time is unknown. After five seconds with no active or queued requests, the display shows 0.0 tok/s until a new measurement for that dial arrives. Active requests with delayed timing are not considered idle. This is a presentation rule; original native measurements remain available to diagnostics.

Ollama capture shows the latest completed request for the selected model. vLLM and llama.cpp metrics can combine work since the last poll. Neither is advertised as aggregate server throughput or a comparable GPU benchmark without controlling the workload and engine conventions.
