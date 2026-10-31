# Release validation - 2026-10-31

Etincelles Token Meter 0.3.0 - automatic neon dark mode.

- 59 tests passed on Windows 11 / Python 3.13.5 and Spark Ubuntu / Arm64 / Python 3.12.
- All application modules compile. Existing timing, idle, proxy, installer and native-window regression coverage is retained.
- Windows preference detection covers app-versus-shell priority, missing values and invalid registry types. App appearance has priority in Windows custom color mode.
- Linux detection covers standardized portal values, GNOME color-scheme and GTK fallback behavior.
- Following the desktop, explicit light/dark overrides and changing appearance without clearing timing/capture state have regression coverage.
- Actual Windows and Spark desktop preferences both reported dark mode. Source and standalone Windows previews selected the neon theme automatically.
- Windows appearance menu switching was checked. The Spark GUI was exercised through injected dark/light/dark desktop-preference changes in one running process; desktop settings were not changed.
- Light mode retains the original logo-derived palette. Dark mode uses neon green #A8FF4F and neon gold #FFE44D, with static glow accents and the original unchanged logo.

Native inference measurement math is unchanged from 0.2.0, whose actual RTX 4090/Ollama and Spark/vLLM checks matched engine timing. This appearance update does not claim a new performance benchmark. Example images use clearly labeled illustrative readings.

GitHub Actions checks Windows and Ubuntu with Python 3.10 and 3.13. Current remote results are available in the repository's Actions tab. Private settings and validation evidence are excluded from the public source.
