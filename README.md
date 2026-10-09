# Ryzen Control

Controllo stile Ryzen Master per AMD Ryzen 9000 (Granite Ridge) su Linux: Curve Optimizer e
Curve Shaper per core, limiti PPT/TDC/EDC, frequenza di boost (FMax), temperatura massima
(Tjmax), profilo energetico e ventole della scheda madre. Profili applicati all'avvio con
protezione dopo un crash.

> **Attenzione.** Software sperimentale che parla direttamente con l'SMU del processore.
> Sviluppato e provato su un solo sistema: Ryzen 7 9800X3D, ASUS ROG STRIX X870E-H, Fedora 44.
> Qualsiasi altra CPU viene rifiutata. Un Curve Optimizer troppo negativo può far riavviare il
> sistema (nessun danno, ma lavoro non salvato perso): leggere "Sicurezza" prima di usarlo.

Stato: **fase 1** — helper/CLI `ryzenctl`, servizi systemd, driver via DKMS, pacchetti RPM.
Ventole, GUI GTK4, calibrazioni e pacchetti deb/Arch seguono (vedi `docs/plans/`).

## Installazione

### Fedora (RPM)

```sh
make rpm                                   # richiede rpm-build, rpmdevtools, git
sudo dnf install dist/ryzen-control-*.rpm
```

Un solo pacchetto che fa tutto da solo: compila il modulo `ryzen_smu` via DKMS per ogni kernel
installato (`dkms.service` lo ricompila a ogni aggiornamento) e avvia il servizio, che carica
il modulo e legge la baseline (nessun profilo viene applicato).

**Secure Boot**: il modulo deve essere firmato con una chiave registrata in MOK. Se sul sistema
c'è già la chiave akmods registrata (tipico con i driver NVIDIA di RPM Fusion), DKMS la riusa
automaticamente: nessun passo manuale. Altrimenti il pacchetto lo dice a fine installazione e
serve una registrazione, una volta sola — è un limite di Secure Boot (richiede la conferma
fisica al riavvio), non aggirabile da software:

```sh
sudo mokutil --import /var/lib/dkms/mok.pub      # chiede una password temporanea
sudo reboot                                       # MOK Manager: Enroll MOK → Continue → password
```

Verifica (tutto automatico, reversibile, un paio di secondi):

```sh
sudo ryzenctl status                        # valori del BIOS, "Baseline di questo boot"
sudo ryzenctl hwtest                        # scrive e rilegge ogni comando vicino alla baseline, poi la ripristina
```

### Altre distribuzioni

Pacchetti deb e Arch sono previsti (`packaging/`). Nel frattempo, con `dkms`, gli header del
kernel, `python3 >= 3.9`, `polkit` e `systemd` installati:

```sh
sudo make install && sudo make dkms
sudo systemctl enable --now ryzenctl.service ryzenctl-resume.service
```

Per rimuovere: `sudo make uninstall`.

## Uso (CLI)

Tutti i comandi hanno la stessa grammatica da CLI, nei file profilo e nella GUI.

```sh
sudo ryzenctl status                 # stato attuale e baseline
sudo ryzenctl co 7 -15               # Curve Optimizer del core 7; `co all -10`; `co v0 … v7`
sudo ryzenctl ppt 120                # limiti: ppt (W), tdc (A), edc (A)
sudo ryzenctl fmax 5000              # frequenza massima di boost (MHz)
sudo ryzenctl tjmax 85               # temperatura massima (°C), mai sopra la baseline
sudo ryzenctl power balanced         # power-saver | balanced | performance
sudo ryzenctl default                # tutto ai valori di base (BIOS), avvio automatico off
sudo ryzenctl hwtest                 # prova reversibile di ogni comando con readback
```

Profili (`/etc/ryzenctl/profiles/<nome>.conf`, una riga per comando, `#` commenta):

```sh
sudo ryzenctl profile save quiet "co all -15" "ppt 88" "tdc 75" "edc 150" "fmax 4800" "power balanced"
sudo ryzenctl apply quiet            # applica ora
sudo ryzenctl use quiet && sudo ryzenctl autostart on     # applica a ogni avvio e dopo il resume
sudo ryzenctl profile list | show quiet | delete quiet
```

Oltre i valori di fabbrica (PPT fino a 230 W, TDC 160 A, EDC 230 A, FMax +200 MHz) solo dopo
`sudo ryzenctl unlock on`, che stampa un'avvertenza. Tjmax non supera mai la baseline.

### Ventole (scheda madre, chip Nuvoton nct67xx)

```sh
sudo ryzenctl fan enable             # carica nct6775 e lo rende permanente; se il chip non appare per un
                                     # conflitto ACPI aggiunge acpi_enforce_resources=lax (grubby) e chiede il riavvio
sudo ryzenctl fan status             # canali, giri, pwm, step, curva, ruolo
sudo ryzenctl fan autodetect         # ~30 s per canale sotto carico: assegna i ruoli ventola/pompa/non-controllabile
sudo ryzenctl fan 1 step 10000 5000  # ritardo di reazione della SmartFan (ms, salita/discesa): ignora i picchi brevi
sudo ryzenctl fan 1 curve 40:77 60:150 75:255   # punti temperatura:pwm (pwm >= 51, ultimo 255 entro 125 °C)
sudo ryzenctl fan identify 2         # 100 % per 5 s per riconoscere fisicamente il canale
sudo ryzenctl fan name 1 "radiatore alto"; sudo ryzenctl fan role 3 pompa   # a mano si può solo declassare
sudo ryzenctl fan disable
```

Si scrive solo su canali classificati **ventola** da `fan autodetect` (test fisico: canale al 40 %
per 20 s sotto carico, la pompa fa salire Tctl di gradi in secondi, una ventola no); la pompa e i
canali che non rispondono al PWM restano in sola lettura, `pwmN_enable` (modalità SmartFan del
BIOS) non viene mai cambiato fuori dai test. Nei profili: `fan <N> step …` e `fan <N> curve …`.

### Modalità e calibrazione automatica

Nella GUI (pagina Modalità) o da CLI. Preset fissi (nessun test): **Default** = valori BIOS,
**Quiet** = limiti ×0.55/0.63/0.83, FMax −400, Tjmax 80, ventole 10 s/5 s, **Performance** =
valori di fabbrica con energia al massimo. Modalità **calibrate sull'hardware** con test di
carico (**Eco**, **Auto**, **Boost**): la ricerca del limite di stabilità del CO per core è una
sola, condivisa e salvata (`/var/lib/ryzenctl/co_limits.json`, riusata dalle calibrazioni
successive); ogni modalità applica il proprio margine: Eco +5 (discreto), Auto e Boost +3.

```sh
sudo ryzenctl preset quiet|performance|eco|auto|boost   # crea il profilo dai valori di fabbrica (segnaposto)
sudo ryzenctl autotune estimate eco              # durata stimata (parallelo e core per core)
sudo ryzenctl autotune start eco|auto|boost [target=70 colimit=-40 margin=5 step=90 parallel=1 reuse=1]
sudo ryzenctl autotune step                      # un test alla volta; ripetere finché phase == done
sudo ryzenctl autotune status | abort            # abort interrompe subito anche un passo in corso
```

Dalla GUI: Modalità → "Calibra…" su Eco o Auto, poi "Automatica" (valori di default) o "Scegli i
valori…". Di default i core si provano **tutti insieme** a ogni livello di CO (un worker per
core, ~8× più veloce; `parallel=0` = un core alla volta, che attribuisce con certezza anche un
riavvio). Durante i test la GUI mostra il tempo rimanente stimato, la tensione reale misurata
per core a ogni livello e quanti mV vale un passo di CO su questa CPU.

- **Eco**: cerca il Curve Optimizer negativo stabile (passi di −5 fino a `colimit`, tre fasi di
  carico: pieno con verifica, 50 %, 10 %, più raffiche singole per il boost massimo; controllo
  errori MCE) e tiene l'ultimo stabile + `margin` (undervolt *discreto*); passata finale su tutti
  i core; poi, con i limiti eco già applicati, abbassa FMax di 100 MHz alla volta finché il 95°
  percentile dei picchi di Tctl sotto raffiche miste (tutti i core / un core) resta sotto
  `target`; scrive il profilo `eco` con limiti Quiet, ventole lente e curva dal target.
  Esito sul 9800X3D di sviluppo: tutti i core stabili fino a −25 → CO −20, ≈ 3,4 mV per passo
  (−69 mV reali a pieno carico), FMax invariata (picco 64 °C < 70 con il profilo eco).
- **Auto**: CO = limite + 3, poi il ginocchio prestazioni/watt: sweep di PPT (multi-thread) e
  FMax (single-thread) misurando bogo-ops/s di stress-ng e potenza RAPL, scegliendo il valore
  più basso che perde al massimo `loss` % (default 10) rispetto al massimo.
- **Boost**: CO = limite + 3, limiti e FMax ai tetti consentiti (fabbrica, o sblocco), energia
  al massimo; misura il guadagno MT/ST rispetto alla fabbrica.

**Attenzione**: un CO instabile può riavviare il PC durante la calibrazione (nessun danno,
lavoro non salvato perso). Lo stato è su disco: al riavvio il passo interrotto viene marcato
instabile e si riprende. Durata: Eco ~25–40 min, Auto di più.

**Curve Shaper**: sperimentale e di fatto disattivato. Sul 9800X3D con SMU 98.81.0 il comando
di scrittura (RSMU 0xA6) risponde OK ma quello di lettura (0x84) restituisce solo zeri o
l'argomento stesso, quindi nessuna scrittura è verificabile: `shaper` resta fuori da profili e
baseline (`shaper raw` / `shaper probe` servono solo a indagare). Il Curve Shaper va impostato
dal BIOS.

## Sicurezza

- Nessun comando di tensione, mai: niente SoC/VDDIO/VDDG, niente VID fisso, niente OC mode,
  niente PBO scalar, niente scritture SMN. Si inviano solo gli ID in allowlist (CO, limiti,
  FMax, Tjmax, Shaper, letture) e ogni valore è un *limite* che il firmware continua a far
  rispettare.
- La **baseline** (valori del BIOS) viene letta a ogni avvio prima di qualunque modifica ed è
  il tetto di ogni valore. Senza baseline di questo boot nessuna scrittura CPU è accettata.
- Ogni scrittura è verificata rileggendo il valore; se non corrisponde, una ripetizione, poi
  ripristino del valore di base ed errore.
- **Crash-guard**: `ryzenctl.service` scrive i marker `dirty` (boot in corso) e `active`
  (stato modificato) *prima* di toccare l'SMU e toglie `dirty` allo spegnimento pulito. Se al
  boot successivo entrambi esistono, il sistema è andato in crash: il profilo CPU **non viene
  riapplicato**, viene scritto `/var/lib/ryzenctl/crashed`, al login arriva una notifica e si
  decide (`ryzenctl crashed clear` + `autostart on` per riattivare, o restare sui valori BIOS).
- Via di fuga totale: al boot, in GRUB, `e` e aggiungere `ryzenctl.off` alla riga del kernel:
  il servizio non parte e il modulo non viene caricato (è in blacklist, lo carica solo il
  servizio).
- Tutto è volatile: un riavvio riporta ai valori del BIOS.

## Verifica su hardware (checklist fase 1)

1. `dkms status` installed; `modinfo -F signer ryzen_smu` (chiave akmods o DKMS registrata);
   `systemctl status ryzenctl` active; `cat /sys/kernel/ryzen_smu_drv/codename` = 23.
2. `sudo ryzenctl status` = valori BIOS; `sudo ryzenctl hwtest` con esito `ok` (ogni comando
   scritto, riletto e riportato alla baseline). Esito sul 9800X3D / SMU 98.81.0: CO, FMax,
   PPT, TDC, EDC, Tjmax ok; Curve Shaper non verificabile (vedi sopra).
3. Crash-guard: profilo innocuo (`ppt 150`) con autostart; `sync; echo b | sudo tee
   /proc/sysrq-trigger` → al boot `ryzenctl crashed` valorizzato, `status` = baseline,
   notifica al login; `systemctl restart ryzenctl` → baseline invariata; riavvio pulito →
   profilo applicato; suspend/resume → profilo ancora applicato; boot con `ryzenctl.off` →
   modulo non caricato.

## Sviluppo

```sh
make check          # selftest (backend finto), layout, unit systemd, desktop, metainfo
make driver-check   # compila il driver in una copia temporanea (kbuild non accetta spazi nel percorso)
make rpm            # tarball da HEAD + RPM in dist/
RYZENCTL_ROOT=/tmp/fake python3 ryzenctl boot   # CLI sul backend finto, nessun root
```

Piano, architettura e stato dei lavori: `docs/plans/2026-10-09-ryzen-control.md`.

## Licenza

GPL-3.0-or-later. Il driver vendorizzato in `ryzen_smu/` resta GPL-2.0 (incluso nello stesso
pacchetto, licenza RPM `GPL-3.0-or-later AND GPL-2.0-only`); vedi `ryzen_smu/UPSTREAM.md`. Riferimenti tecnici: ryzen_smu (amkillam),
ZenStates-Core (irusanov), gnr-smu (Kyworn, misure sul 9800X3D).
