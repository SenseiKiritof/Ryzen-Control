# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Stato del progetto

"Ryzen Control": controllo stile Ryzen Master (Curve Optimizer, Curve Shaper, PBO, FMax/Tjmax,
ventole) per un Ryzen 7 9800X3D su Linux, GUI GTK4/libadwaita + helper root, pacchetti RPM/deb/Arch.

La fonte di verità è il piano `docs/plans/2026-10-09-ryzen-control.md` (rev. 4): architettura,
tabella comandi SMU, range di validazione, formato profili, crash-guard, fasi e commit previsti.
Leggerlo prima di toccare qualcosa; questo file ne riassume solo l'essenziale. I piani futuri
vanno nella stessa cartella (`docs/plans/YYYY-MM-DD-<argomento>.md`). Lingua di piano, README e
messaggi di commit: italiano.

Fatto: **fase 1** (`ryzenctl` completo per la parte CPU, unit systemd, driver vendorizzato,
spec RPM, README). Verificato su hardware (9800X3D, SMU 98.81.0, PM table 0x620105): driver
firmato automaticamente con la chiave akmods, `hwtest` ok per CO, FMax, PPT, TDC, EDC, Tjmax.
**Curve Shaper non verificabile**: RSMU 0xA6 risponde OK ma 0x84 restituisce zeri (o l'arg0
stesso) → `shaper` è sperimentale, fuori da profili/baseline/hwtest, il setter fallisce sempre
al readback (sicuro per costruzione). Crash-guard verificato su hardware (crash sysrq →
profilo disattivato + notifica, riattiva, restart, boot pulito, resume). Tag `v0.1.0` su `main`.
**Fase 2 (ventole) verificata su hardware** (NCT6799D, nessun conflitto ACPI, nessun parametro
kernel): `fan enable/status/autodetect/step/curve/identify` ok; autodetect ha dato pwm2 pompa
(2125→1898 giri al 21 %), pwm5/pwm6 ventola, pwm7 (100 %, senza tachimetro) non testabile e
protetto; step 10 s/5 s sui canali ventola elimina gli scatti sui picchi (3 s di carico pieno,
giri fermi). Il chip arrotonda gli step a ~200 ms. Tag `v0.2.0`.
**Fase 3 (GUI) e fase 4 (calibrazioni)** scritte e usate su hardware: `ryzen-control` (pagine
Monitor, Modalità con preset Quiet/Boost e calibrate Eco/Auto, CPU, Curve, Ventole; valori
colorati rispetto alla fabbrica; finestra di calibrazione ridimensionabile con avanzamento,
stime di durata, tensione misurata per core e mV per passo; interruzione immediata). `autotune`
in ryzenctl è una macchina a passi (`start/step/status/abort/estimate`, stato in
`/var/lib/ryzenctl/autotune.json`, ripresa dopo crash, parallelo di default). Eco verificata su
hardware (CO −20 su 8 core, ≈ 3,4 mV/passo, FMax invariata); Auto (ginocchio PPT/FMax con RAPL)
in verifica; Boost calibrata, pompa con tetto o velocità fissa, scelta a fine calibrazione (Annulla / Salva /
Salva e applica), `trust`, avvio al login, notifica cliccabile. Tag `v0.4.1` (VERSION 0.4.1). Poi: fase 5 supporto a tutti i Ryzen (tabella `FAMILIES` per
codename, `CORES` dinamico, gate fail closed), fase 6 icona nel vassoio (StatusNotifierItem +
dbusmenu via Gio, `ryzen-control --tray`, comandi rapidi), fase 7 deb/PKGBUILD.

Lezioni dall'hardware: la PM table riflette un nuovo limite dopo decine di ms → readback con
attesa (`READBACK_WAIT`); la baseline si ricattura solo al boot, quindi dopo un aggiornamento
che cambia il formato le righe non più ammesse vanno ignorate (`profile_lines("baseline")`);
il backend finto non deve mai avere effetti reali (es. `notify-send`) perché il selftest gira
nella sessione dell'utente. Calibrazione: `--cpu-method all` per 5 min non basta, fft a 16 thread
ha bloccato il sistema a −37 (limite per core −40) → la passata finale parte dal metodo più
pesante (`FINAL_HEAVY_SEC`); uno stress-ng che termina in anticipo o con codice ≠ 0 è
instabilità (`Unstable`), mai una metrica bassa; ogni fase con il CO finale applicato ha il marker
`in_progress` (`post`) così un crash viene attribuito alla combinazione (+3, finale ripetuta); le
combinazioni fallite restano in `co_limits.json` (`final_failures`) e non si riprovano;
l'attribuzione del crash (`at_attribute_crash`, senza SMU) avviene già in `boot`; il metodo pesante
è anche la prima fase della ricerca (file `co_limits` senza `method` non riusati). Il driver
nct6775 non riscrive uno step di 0 ms (registro minimo 1 = 400 ms): `FAN_STEP_MIN_MS`, altrimenti
`default` falliva sulle righe ventola della baseline. Un blocco
con riavvio dal pulsante può azzerare i file scritti negli ultimi secondi (btrfs): anche oggetti
git appena creati.

## Layout

- `ryzenctl` — Python stdlib, unico punto privilegiato (CLI, `serve`, `selftest`).
- `ryzen-control` — GUI Python/PyGObject (GTK4, libadwaita ≥ 1.5), gira come utente; un solo
  processo `pkexec ryzenctl serve` per sessione (Helper con lettore + FIFO: le richieste partono
  senza attendere le precedenti, le risposte arrivano in ordine); `--mock` usa il backend finto
  con app id separato (`…Mock`) per non attivare l'istanza installata.
- `ryzen_smu/` — driver upstream (amkillam/ryzen_smu, commit d298366) **copiato**, non subtree
  (git-subtree non è installato): origine, file esclusi, modifica locale a `smu.c` (PM table
  0x6211xx/0x6212xx) e procedura di aggiornamento in `ryzen_smu/UPSTREAM.md`.
- `Makefile` — unica fonte del layout installato (`install` = `install-cli` + `install-gui` se
  c'è + `install-dkms-src`; `DESTDIR`, `PREFIX`; `APPID` serve solo per i nomi dei file in
  `data/`, l'id `org.ryzencontrol.RyzenControl` è scritto nei file). Ogni pacchetto è un
  involucro che chiama il Makefile, mai un layout duplicato.
- `data/` — unit systemd (`ryzenctl.service`, `ryzenctl-resume.service`), preset, blacklist
  modprobe, policy polkit, .desktop, icona, metainfo, autostart notify.
- `packaging/ryzen-control.spec` (RPM: **un solo pacchetto** `ryzen-control`, noarch, con il
  sorgente DKMS del driver dentro; `Obsoletes: ryzen-smu-dkms` per le release 1-4). Il `%post`
  ricompila il modulo solo se manca per il kernel in uso o cambia la chiave: **quando cambia il
  sorgente in `ryzen_smu/` va bumpata `DRV_VERSION`** (Makefile) **= `%drv_version`** (spec), altrimenti
  dkms tiene il modulo vecchio; `VERSION` (app) non tocca il modulo, così una release non ricompila;
  `packaging/debian/` e `packaging/PKGBUILD` in fase 7.

Vincoli di compatibilità: sintassi Python ≥ 3.9 (nessuna feature più recente), libadwaita ≥ 1.5,
niente dipendenze Python oltre PyGObject, nessun framework di test.

## Comandi

Senza hardware né root (si eseguono prima di ogni commit):

```sh
python3 ryzenctl selftest       # backend finto; codifiche, validazione, tetti, profili, baseline, crash-guard, serve
make check                      # selftest + layout in radice temporanea + systemd-analyze verify + desktop-file-validate + appstreamcli
make driver-check               # compila il driver in una copia fuori dal repo (kbuild NON accetta spazi nel percorso: `make -C ryzen_smu` fallisce qui)
make rpm                        # tarball da HEAD (solo ciò che è committato) + RPM in dist/; rpmlint NON installato
RYZENCTL_ROOT=/tmp/fake python3 ryzenctl boot   # CLI sul backend finto (stato in $ROOT/fake_smu.json)
python3 ryzen-control --mock    # GUI senza driver né pkexec (fase 3)
```

Su hardware (li esegue l'utente, con `! comando`; si committa dopo il suo esito): checklist in
README "Verifica su hardware".

Non testabili su questa macchina: `dpkg-buildpackage`, `namcap`, `stress-ng` (mancanti).
I pacchetti deb/Arch vanno marcati "non testati" nel README.

## Architettura

```
ryzen-control (GUI, utente) ──pkexec──▶ ryzenctl serve (root, valida TUTTO)
                                          ├─ /sys/kernel/ryzen_smu_drv/*   (SMU)
CLI: sudo ryzenctl …  ────────────────────┤─ /sys/class/hwmon/nct67xx/*    (ventole, fase 2)
systemd: ryzenctl.service, -resume ───────┘─ /etc/ryzenctl, /var/lib/ryzenctl, /run/ryzenctl
```

- **Una sola grammatica di comandi** (`co 7 -3`, `ppt 88`, `fmax 4800`, `shaper 4 -5 -5 0`,
  `power balanced`, …) usata identica da CLI, righe dei file profilo e protocollo `serve` (una
  riga JSON-array per richiesta, una riga `{"ok":…}` di risposta; `boot/shutdown/resume/serve`
  negati via serve). Un nuovo comando = una funzione `cmd_*` + voce in `COMMANDS` (+ in
  `PROFILE_CMDS` se ammesso nei profili) + caso nel selftest.
- **`ryzenctl` è il confine di fiducia**: la GUI non valida nulla di definitivo, invia e mostra
  gli errori. `serve` viene avviato una volta per sessione (un solo prompt pkexec; `trust on` scrive una regola polkit in
  `/etc/polkit-1/rules.d/` per l'utente chiamante, `PKEXEC_UID`/`SUDO_USER`, e il prompt sparisce).
- **Backend finto** (`class Fake`, attivo con `RYZENCTL_ROOT`): simula SMU, PM table, k10temp,
  profilo energetico; `drop` ignora le prossime scritture (prova del readback), `log` registra
  quali marker esistevano a ogni scrittura (prova dell'ordine). Nuova logica = caso nel selftest.
- **Baseline** (`/var/lib/ryzenctl/baseline.conf`, stesso formato dei profili): catturata da
  `boot` una volta per boot (`/run/ryzenctl/booted`), mai se `active` esiste. Tetto di ogni
  valore; senza baseline di questo boot (`/run/ryzenctl/baseline-done`) nessuna scrittura CPU.
  Tjmax ≤ baseline sempre; PPT/TDC/EDC ≤ baseline e FMax ≤ baseline salvo `unlock on`
  (tetti 230 W / 160 A / 230 A, FMax +200 MHz, avvertenza stampata).
- **Crash-guard** (requisito esplicito dell'utente), marker in `/var/lib/ryzenctl` con fsync:
  `boot` → se `dirty` ∧ `active` scrive `crashed {ora, profilo}`; rimuove `active`; scrive
  `dirty`; cattura baseline; applica ventole; applica CPU solo se autostart ∧ ¬crashed. `active`
  viene scritto da `write_verify` **prima** della scrittura SMU di un valore ≠ baseline.
  `shutdown` (ExecStop) toglie `dirty`. Restart nello stesso boot (`booted` presente) rimette
  solo `dirty`. `boot` non solleva mai eccezioni (la unit deve restare attiva perché ExecStop
  giri). Via di fuga: parametro kernel `ryzenctl.off` + modulo in blacklist (lo carica solo il
  servizio con modprobe esplicito).
- **Modalità** statiche (nessun demone, il dinamismo lo fa PBO): Default / Quiet (preset) /
  Eco (calibrata) / Auto (calibrata) / Performance (preset) / Boost (calibrata) / Custom. `preset <nome>` genera i profili
  dalla baseline (rapporti in `PRESETS`); `autotune` li sostituisce con misure, ma solo su
  `autotune save [apply]`: a `phase == done` la CPU è a baseline e il profilo è proposto in
  `profile_lines` (la GUI chiede Annulla / Salva / Salva e applica; `abort` scarta). `serve` esegue
  le richieste in ordine su un thread e legge su un altro: `autotune abort` alza il flag
  `/run/ryzenctl/autotune-abort` e termina gli stress-ng registrati in `_children`.
- **Ventole** (fase 2): nessun demone; si cambiano solo `pwmN_step_up_time`/`step_down_time` (e
  punti curva se richiesto) della SmartFan già programmata dal BIOS. Ruoli assegnati da
  `fan autodetect` (test fisico: canale al 40 % per 20 s sotto carico, ΔTctl distingue la pompa);
  a mano si può solo declassare, mai promuovere a "ventola". `pwmN_enable` non si tocca mai
  fuori dai test (ripristino in `finally`), con una sola eccezione esplicita per la pompa: `fan N pump max <50-100>`
  (curva del BIOS con i punti sopra il tetto ridotti; la curva BIOS è memorizzata in
  `settings.fans[N].bios_curve` e `pump_max` viene azzerato a ogni boot perché il BIOS la
  riprogramma), `fan N pump <50-100>` (velocità fissa, modo manuale) e `fan N pump auto`
  (ripristina); mai curve o step sulla pompa a mano (il BIOS la portava al 100 % sotto carico e
  ronzava). Il parametro kernel `acpi_enforce_resources=lax` lo
  mette `ryzenctl fan enable` (azione esplicita dell'utente, grubby), mai il pacchetto.
  Il backend finto simula l'hwmon con file veri sotto `$ROOT/sys/class/hwmon/hwmon0` e la
  fisica in `Fake.after_fan_write`.

## Invarianti hardware (non negoziabili)

- Allowlist SMU rigida (`CMD` in testa a `ryzenctl`): CO MP1 0x35, PPT/TDC/EDC MP1
  0x3E/0x3C/0x3D, FMax RSMU 0x70/0x6E, Tjmax RSMU 0x59, Shaper RSMU 0xA6/0x84, CO get RSMU
  0xD5. Nessun altro ID viene inviato. Mai MP1 0x58–0x6F (congela l'SMU sul 9800X3D) né MP1
  0x10 (spegne il display). Mai comandi di tensione, OC mode (RSMU 0x5D), VID fisso (0x61),
  PBO scalar (0x5B), scritture `smn`, FCLK/memoria.
- Gate: `codename` deve essere 23 (Granite Ridge), altrimenti rifiuto totale. (fase 5: codename in
  `FAMILIES`, ogni famiglia con la sua allowlist; fuori tabella rifiuto totale)
- Ogni transazione SMU sotto `flock(/run/ryzenctl/lock)` (`smu_args` del driver è globale).
- Ogni scrittura è seguita da readback; discrepanza → una ripetizione → ripristino del valore
  baseline → errore. Nessun fallback automatico su altri ID.
- Floor: PPT ≥ 45 W, TDC ≥ 30 A, EDC ≥ 45 A (PPT 0 blocca la CPU a 606 MHz). CO/Shaper −50..+30,
  FMax 3000..baseline(+200 sbloccato), Tjmax 60..min(baseline, 95). Le costanti stanno in testa
  a `ryzenctl` e sono manopole di calibrazione, non da sparpagliare.
- Valori dalla PM table letti solo se `pm_table_version>>16 == 0x62`; PM table assente →
  PPT/TDC/EDC/Tjmax rifiutati (fail closed), CO/FMax/Shaper ok.
- Nomi profilo solo `[a-z0-9_-]{1,32}`, `baseline` riservato. File di stato scritti in modo
  atomico (`write_atomic`).

## Flusso di lavoro

- Repo git locale, branch `main` (solo init) e `dev` (sviluppo), nessun remote finché l'utente
  non ne indica uno.
- Sviluppo a passi seguendo la tabella "Fasi e commit" del piano: un commit per passo, **solo
  dopo la verifica** del passo (`make check` almeno). Verifica fallita → si corregge, niente commit.
- Prefisso convenzionale (`feat/fix/build/docs/chore/test`), messaggio in prosa italiana, riga
  `Co-Authored-By` richiesta dall'ambiente.
- Tag `v0.1.0`, `v0.2.0`, … a fine di ogni fase verificata su hardware; la versione del tag è
  quella di `VERSION` nel Makefile e della spec RPM (da tenere allineate).
- Le semplificazioni deliberate con un tetto noto si marcano con un commento `# ponytail:`.
