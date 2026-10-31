# Release validation - 2026-10-31

Etincelles Token Meter 0.1.1.

| Check | Result |
| --- | --- |
| Windows 11 x64, Python 3.13.5 | 42 automated tests passed |
| Spark Ubuntu / Arm64, Python 3.12 | 42 automated tests passed; live vLLM metrics read successfully |
| Windows standalone executable | Built with PyInstaller 6.22.3; actual installed GUI and settings dialog inspected |
| Windows user-level installation | Shortcuts, startup enable/disable, uninstall and preservation of an unrelated test file passed |
| Linux GTK 3 frontend | Rendered on the Spark; visual check completed |
| Existing Spark widget | Renamed; 27 existing tests passed; actual idle snapshot reported both dials at 0.0 |
| Five-second idle behavior | Tests cover exact timeout, delayed timing during active work, repeated completion flags, per-dial wake-up and offline state |
| llama.cpp and custom hooks | Native-format fixtures and forwarding tests; no live llama.cpp server integration claimed |

## Real RTX 4090 integration check

Used an already downloaded Qwen2.5-Coder 7B Instruct Q4_K_M through Ollama 0.40.13. A synthetic request went through the installed executable's loopback capture proxy. No model was downloaded and no unrelated GPU application was stopped.

- Prompt: 2,130 tokens / 0.348470000 native seconds = 6112.434356 Read tok/s.
- Output: 256 tokens / 2.571416000 native seconds = 99.556042 Write tok/s.
- Ollama reported 4,928,516,914 bytes allocated in VRAM out of 4,928,516,914 loaded-model bytes.
- Captured values matched both native count/duration ratios within 1e-8 tok/s.
- This confirms measurement and GPU integration. It is not an isolated speed benchmark, a model-quality test or a hardware comparison.
- Read speed can vary with prompt length, cache state and engine accounting; Ollama native timing is labeled separately from vLLM uncached-KV timing.

## Scope

The initial GitHub README, MIT license and Python ignore template were retained in repository history. Private configuration, local test evidence, machine paths, API keys, model weights and build environments are excluded from the public repository. Tests use synthetic fixtures.

The GitHub Actions matrix is configured for Windows and Ubuntu with Python 3.10 and 3.13; remote CI execution is separate from local validation and is not claimed here until GitHub runs it.

Patch 0.1.1 corrects a Linux GTK refresh indentation error introduced in the idle update. Syntax compilation and a fresh Linux GUI check are included in patch validation. Windows timing and the separately installed Spark widget were unaffected.
