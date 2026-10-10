# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project status

"Ryzen Control": Ryzen Master-style control (Curve Optimizer, Curve Shaper, PBO, FMax/Tjmax,
fans) for a Ryzen 7 9800X3D on Linux, GTK4/libadwaita GUI + root helper, RPM/deb/Arch packages.

The source of truth is the plan `docs/plans/2026-10-09-ryzen-control.md` (rev. 4): architecture,
SMU command table, validation ranges, profile format, crash-guard, planned phases and commits.
Read it before touching anything; this file only summarises the essentials. Future plans go in
the same folder (`docs/plans/YYYY-MM-DD-<topic>.md`). Language: source code, comments, README,
plans and commit messages are in English; user-facing strings go through gettext (domains
`ryzenctl` and `ryzen-control`, catalogs in `po/<domain>/<lang>.po`, Italian maintained);
protocol keys and stored values keep their historical Italian names (`canale`, `modo`, `curva`,
`ventola`, `pompa`, `instabile`, …) — renaming them is a coordinated change of ryzenctl +
ryzen-control + selftest.

Done: **phase 1** (`ryzenctl` complete for the CPU part, systemd units, vendored driver, RPM
spec, README). Verified on hardware (9800X3D, SMU 98.81.0, PM table 0x620105): driver signed
automatically with the akmods key, `hwtest` ok for CO, FMax, PPT, TDC, EDC, Tjmax.
**Curve Shaper not verifiable**: RSMU 0xA6 answers OK but 0x84 returns zeros (or arg0 itself)
→ `shaper` is experimental, out of profiles/baseline/hwtest, the setter always fails at readback
(safe by construction). Crash-guard verified on hardware (sysrq crash → profile disabled +
notification, reactivate, restart, clean boot, resume). Tag `v0.1.0` on `main`.
**Phase 2 (fans) verified on hardware** (NCT6799D, no ACPI conflict, no kernel parameter):
`fan enable/status/autodetect/step/curve/identify` ok; autodetect gave pwm2 pompa (pump)
(2125→1898 rpm at 21 %), pwm5/pwm6 ventola (fan), pwm7 (100 %, no tachometer) not testable and
protected; step 10 s/5 s on the fan channels removes the jumps on spikes (3 s of full load, rpm
steady). The chip rounds the steps to ~200 ms. Tag `v0.2.0`.
**Phase 3 (GUI) and phase 4 (calibrations)** written and used on hardware: `ryzen-control`
(pages Monitor, Modes with Quiet/Boost presets and calibrated Eco/Auto, CPU, Curves, Fans;
values coloured against the factory ones; resizable calibration window with progress, duration
estimates, measured voltage per core and mV per step; immediate interruption). `autotune` in
ryzenctl is a step machine (`start/step/status/abort/estimate`, state in
`/var/lib/ryzenctl/autotune.json`, resume after crash, parallel by default). Eco verified on
hardware (CO −20 on 8 cores, ≈ 3.4 mV/step, FMax unchanged); Auto (PPT/FMax knee with RAPL)
under verification; Boost calibrated, pump with cap or fixed speed, choice at the end of the
calibration (Cancel / Save / Save and apply), `trust`, start at login, clickable notification.
Tag `v0.4.2` (VERSION 0.4.2, DKMS module `DRV_VERSION` 0.4.1). Next: phase 5 support for all
Ryzen CPUs (`FAMILIES` table by codename, dynamic `CORES`, fail-closed gate), phase 6 tray icon
(StatusNotifierItem + dbusmenu via Gio, `ryzen-control --tray`, quick commands), phase 7
deb/PKGBUILD.

Lessons from the hardware: the PM table reflects a new limit after tens of ms → readback with
a wait (`READBACK_WAIT`); the baseline is recaptured only at boot, so after an update that
changes the format the lines no longer allowed must be ignored (`profile_lines("baseline")`);
the fake backend must never have real effects (e.g. `notify-send`) because the selftest runs in
the user's session. Calibration: `--cpu-method all` for 5 min is not enough, fft at 16 threads
froze the system at −37 (per-core limit −40) → the final pass starts from the heaviest method
(`FINAL_HEAVY_SEC`); a stress-ng that exits early or with code ≠ 0 is instability
(`Unstable`), never a low metric; every phase with the final CO applied has the `in_progress`
marker (`post`) so a crash is attributed to the combination (+3, final pass repeated); failed
combinations stay in `co_limits.json` (`final_failures`) and are not retried; the crash
attribution (`at_attribute_crash`, no SMU) already happens in `boot`; the heavy method is also
the first phase of the search (`co_limits` files without `method` are not reused). The nct6775
driver does not write back a 0 ms step (minimum register 1 = 400 ms): `FAN_STEP_MIN_MS`,
otherwise `default` failed on the baseline's fan lines. A freeze followed by a reboot from the
button can wipe the files written in the last seconds (btrfs): even freshly created git objects.

## Layout

- `ryzenctl` — Python stdlib, the only privileged entry point (CLI, `serve`, `selftest`).
- `ryzen-control` — Python/PyGObject GUI (GTK4, libadwaita ≥ 1.5), runs as the user; a single
  `pkexec ryzenctl serve` process per session (Helper with reader + FIFO: requests are sent
  without waiting for the previous ones, replies arrive in order); `--mock` uses the fake backend
  with a separate app id (`…Mock`) so as not to activate the installed instance.
- `ryzen_smu/` — upstream driver (amkillam/ryzen_smu, commit d298366) **copied**, not a subtree
  (git-subtree is not installed): origin, excluded files, local change to `smu.c` (PM table
  0x6211xx/0x6212xx) and update procedure in `ryzen_smu/UPSTREAM.md`.
- `Makefile` — the only source of the installed layout (`install` = `install-cli` + `install-gui`
  if present + `install-dkms-src`; `DESTDIR`, `PREFIX`; `APPID` is only used for the file names in
  `data/`, the id `org.ryzencontrol.RyzenControl` is written inside the files). Every package is
  a wrapper that calls the Makefile, never a duplicated layout.
- `data/` — systemd units (`ryzenctl.service`, `ryzenctl-resume.service`), preset, modprobe
  blacklist, polkit policy, .desktop, icon, metainfo, notify autostart.
- `packaging/ryzen-control.spec` (RPM: **a single package** `ryzen-control`, noarch, with the
  driver's DKMS source inside; `Obsoletes: ryzen-smu-dkms` for releases 1-4). The `%post`
  rebuilds the module only if it is missing for the running kernel or the key changes: **when
  the source in `ryzen_smu/` changes, `DRV_VERSION`** (Makefile) **= `%drv_version`** (spec)
  **must be bumped**, otherwise dkms keeps the old module; `VERSION` (app) does not touch the
  module, so a release does not rebuild it; `packaging/debian/` and `packaging/PKGBUILD` in
  phase 7.

Compatibility constraints: Python ≥ 3.9 syntax (no newer feature), libadwaita ≥ 1.5, no Python
dependency beyond PyGObject, no test framework.

## Commands

Without hardware or root (run before every commit):

```sh
python3 ryzenctl selftest       # fake backend; encodings, validation, ceilings, profiles, baseline, crash-guard, serve
make check                      # selftest + layout in a temporary root + systemd-analyze verify + desktop-file-validate + appstreamcli
make driver-check               # builds the driver in a copy outside the repo (kbuild does NOT accept spaces in the path: `make -C ryzen_smu` fails here)
make rpm                        # tarball from HEAD (only what is committed) + RPM in dist/; rpmlint NOT installed
RYZENCTL_ROOT=/tmp/fake python3 ryzenctl boot   # CLI on the fake backend (state in $ROOT/fake_smu.json)
python3 ryzen-control --mock    # GUI without driver or pkexec (phase 3)
```

On hardware (the user runs them, with `! command`; commit after their result): checklist in
README "Hardware verification".

Not testable on this machine: `dpkg-buildpackage`, `namcap`, `stress-ng` (missing).
The deb/Arch packages must be marked "untested" in the README.

## Architecture

```
ryzen-control (GUI, user) ──pkexec──▶ ryzenctl serve (root, validates EVERYTHING)
                                        ├─ /sys/kernel/ryzen_smu_drv/*   (SMU)
CLI: sudo ryzenctl …  ──────────────────┤─ /sys/class/hwmon/nct67xx/*    (fans, phase 2)
systemd: ryzenctl.service, -resume ─────┘─ /etc/ryzenctl, /var/lib/ryzenctl, /run/ryzenctl
```

- **A single command grammar** (`co 7 -3`, `ppt 88`, `fmax 4800`, `shaper 4 -5 -5 0`,
  `power balanced`, …) used identically by the CLI, profile file lines and the `serve` protocol
  (one JSON-array line per request, one `{"ok":…}` line as reply; `boot/shutdown/resume/serve`
  denied via serve). A new command = a `cmd_*` function + an entry in `COMMANDS` (+ in
  `PROFILE_CMDS` if allowed in profiles) + a case in the selftest.
- **`ryzenctl` is the trust boundary**: the GUI validates nothing definitive, it sends and shows
  the errors. `serve` is started once per session (a single pkexec prompt; `trust on` writes a
  polkit rule in `/etc/polkit-1/rules.d/` for the calling user, `PKEXEC_UID`/`SUDO_USER`, and the
  prompt disappears).
- **Fake backend** (`class Fake`, active with `RYZENCTL_ROOT`): simulates SMU, PM table, k10temp,
  power profile; `drop` ignores the next writes (readback proof), `log` records which markers
  existed at every write (ordering proof). New logic = a case in the selftest.
- **Baseline** (`/var/lib/ryzenctl/baseline.conf`, same format as profiles): captured by `boot`
  once per boot (`/run/ryzenctl/booted`), never if `active` exists. Ceiling of every value;
  without a baseline of this boot (`/run/ryzenctl/baseline-done`) no CPU write. Tjmax ≤ baseline
  always; PPT/TDC/EDC ≤ baseline and FMax ≤ baseline unless `unlock on` (ceilings 230 W / 160 A /
  230 A, FMax +200 MHz, warning printed).
- **Crash-guard** (explicit user requirement), markers in `/var/lib/ryzenctl` with fsync:
  `boot` → if `dirty` ∧ `active` writes `crashed {time, profile}`; removes `active`; writes
  `dirty`; captures the baseline; applies fans; applies CPU only if autostart ∧ ¬crashed. `active`
  is written by `write_verify` **before** the SMU write of a value ≠ baseline. `shutdown`
  (ExecStop) removes `dirty`. A restart in the same boot (`booted` present) only puts `dirty`
  back. `boot` never raises exceptions (the unit must stay active so that ExecStop runs). Escape
  hatch: kernel parameter `ryzenctl.off` + blacklisted module (only the service loads it with an
  explicit modprobe).
- **Modes** are static (no daemon, the dynamic behaviour is done by PBO): Default / Quiet (preset) /
  Eco (calibrated) / Auto (calibrated) / Performance (preset) / Boost (calibrated) / Custom.
  `preset <name>` generates the profiles from the baseline (ratios in `PRESETS`); `autotune`
  replaces them with measurements, but only on `autotune save [apply]`: at `phase == done` the
  CPU is at baseline and the profile is proposed in `profile_lines` (the GUI asks Cancel / Save /
  Save and apply; `abort` discards). `serve` executes the requests in order on one thread and
  reads on another: `autotune abort` raises the flag `/run/ryzenctl/autotune-abort` and
  terminates the stress-ng processes registered in `_children`.
- **Fans** (phase 2): no daemon; only `pwmN_step_up_time`/`step_down_time` (and curve points if
  requested) of the SmartFan already programmed by the BIOS are changed. Roles assigned by
  `fan autodetect` (physical test: channel at 40 % for 20 s under load, ΔTctl tells the pump
  apart); by hand one can only demote, never promote to "ventola" (fan). `pwmN_enable` is never
  touched outside the tests (restored in `finally`), with a single explicit exception for the
  pump: `fan N pump max <50-100>` (BIOS curve with the points above the cap reduced; the BIOS
  curve is stored in `settings.fans[N].bios_curve` and `pump_max` is reset at every boot because
  the BIOS reprograms it), `fan N pump <50-100>` (fixed speed, manual mode) and `fan N pump auto`
  (restores); never curves or steps on the pump by hand (the BIOS drove it to 100 % under load
  and it hummed). The kernel parameter `acpi_enforce_resources=lax` is set by `ryzenctl fan
  enable` (explicit user action, grubby), never by the package. The fake backend simulates the
  hwmon with real files under `$ROOT/sys/class/hwmon/hwmon0` and the physics in
  `Fake.after_fan_write`.

## Hardware invariants (non-negotiable)

- Strict SMU allowlist (`CMD` at the top of `ryzenctl`): CO MP1 0x35, PPT/TDC/EDC MP1
  0x3E/0x3C/0x3D, FMax RSMU 0x70/0x6E, Tjmax RSMU 0x59, Shaper RSMU 0xA6/0x84, CO get RSMU
  0xD5. No other ID is sent. Never MP1 0x58–0x6F (freezes the SMU on the 9800X3D) nor MP1
  0x10 (turns off the display). Never voltage commands, OC mode (RSMU 0x5D), fixed VID (0x61),
  PBO scalar (0x5B), `smn` writes, FCLK/memory.
- Gate: `codename` must be 23 (Granite Ridge), otherwise total refusal. (phase 5: codename in
  `FAMILIES`, each family with its own allowlist; outside the table total refusal)
- Every SMU transaction under `flock(/run/ryzenctl/lock)` (the driver's `smu_args` is global).
- Every write is followed by a readback; mismatch → one retry → restore of the baseline value →
  error. No automatic fallback to other IDs.
- Floors: PPT ≥ 45 W, TDC ≥ 30 A, EDC ≥ 45 A (PPT 0 locks the CPU at 606 MHz). CO/Shaper −50..+30,
  FMax 3000..baseline(+200 unlocked), Tjmax 60..min(baseline, 95). The constants live at the top
  of `ryzenctl` and are calibration knobs, not to be scattered around.
- PM table values read only if `pm_table_version>>16 == 0x62`; PM table absent →
  PPT/TDC/EDC/Tjmax refused (fail closed), CO/FMax/Shaper ok.
- Profile names only `[a-z0-9_-]{1,32}`, `baseline` reserved. State files written atomically
  (`write_atomic`).

## Workflow

- Local git repo, branches `main` (init only) and `dev` (development), no remote until the user
  names one.
- Step-by-step development following the plan's "Phases and commits" table: one commit per step,
  **only after verifying** the step (`make check` at least). Failed verification → fix it, no commit.
- Conventional prefix (`feat/fix/build/docs/chore/test`), message in English prose,
  `Co-Authored-By` line required by the environment.
- Tags `v0.1.0`, `v0.2.0`, … at the end of every phase verified on hardware; the tag version is
  the one of `VERSION` in the Makefile and of the RPM spec (keep them aligned).
- Deliberate simplifications with a known ceiling are marked with a `# ponytail:` comment.
