# Release validation - 2026-10-31

Etincelles Token Meter 0.2.0 - official Etincelles bubble.

| Check | Result |
| --- | --- |
| Windows 11 x64 / Python 3.13.5 | 44 automated tests passed; all application modules compile |
| Spark Ubuntu / Arm64 / Python 3.12 | 44 automated tests passed; all application modules compile |
| Windows source and standalone GUI | Official logo, rounded native window region, header dragging, minimize/restore, Options and settings checked |
| Linux GTK 3 GUI | Official logo, native rounded window shape, undecorated window and five-second idle readout rendered against live vLLM |
| Python wheel | All official logo assets match source PNG/ICO checksums; embedded Python source compiles |
| Source installer and uninstaller | Actual Linux test under a temporary home passed; copied logo files removed and unrelated file preserved |
| Windows standalone installer | Shortcut ownership, startup toggle, uninstall and unrelated-file retention passed; user settings restored |
| Five-second idle policy | Existing regression coverage retained; active delayed requests are not mistaken for idle |

The logo's supplied PNGs are preserved byte-for-byte; the ICO wraps supplied 32-256 pixel PNGs without changing image pixels. Palette values and window behavior are described in BRANDING.md.

## RTX 4090 integration

An already downloaded Qwen2.5-Coder 7B Instruct Q4_K_M ran through Ollama 0.40.13 and the branded widget's capture proxy. Native measurement math is unchanged from the previous release.

- Prompt: 2,130 tokens / 0.267524000 native seconds = 7961.902484 Read tok/s.
- Output: 256 tokens / 1.741270000 native seconds = 147.019130 Write tok/s.
- Ollama reported 4,928,516,914 bytes in VRAM out of 4,928,516,914 loaded-model bytes.
- Both captured rates matched native count/duration ratios within 1e-8 tok/s.
- This is a functional integration check, not an isolated benchmark or a performance promise. Cache state, prompt size and engine accounting affect rates.

The existing adapters remain: vLLM was checked live on the Spark; Ollama was checked live on the RTX 4090. llama.cpp and custom hooks have native-format fixture coverage; no new live llama.cpp integration is claimed.

The GitHub Actions matrix checks Windows and Ubuntu with Python 3.10 and 3.13. Current run results are available in the repository's Actions tab. Private test evidence, local settings and build environments are excluded from the public source.
