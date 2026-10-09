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
sudo dnf install dist/ryzen-smu-dkms-*.rpm dist/ryzen-control-*.rpm
```

Il pacchetto `ryzen-smu-dkms` compila il modulo `ryzen_smu` per ogni kernel installato
(`dkms.service` lo ricompila a ogni aggiornamento). Con **Secure Boot** attivo il modulo deve
essere firmato con una chiave registrata; DKMS lo firma da solo con la sua chiave, da
registrare una volta sola:

```sh
sudo mokutil --import /var/lib/dkms/mok.pub      # chiede una password temporanea
sudo reboot                                       # MOK Manager: Enroll MOK → Continue → password
```

Alternativa se la chiave akmods è già registrata (sistemi con driver NVIDIA/akmods): far
firmare DKMS con quella, senza nuove registrazioni:

```sh
sudo tee /etc/dkms/framework.conf.d/akmods.conf <<'EOF'
mok_signing_key=/etc/pki/akmods/private/private_key.priv
mok_certificate=/etc/pki/akmods/certs/public_key.der
EOF
sudo dkms build ryzen_smu/0.1.0 --force && sudo dkms install ryzen_smu/0.1.0 --force
```

Verifica:

```sh
dkms status                                 # ryzen_smu/0.1.0, <kernel>: installed
systemctl status ryzenctl                   # active (exited); carica il modulo e cattura la baseline
cat /sys/kernel/ryzen_smu_drv/codename      # 23 = Granite Ridge
sudo ryzenctl status                        # valori del BIOS, "Baseline di questo boot"
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
sudo ryzenctl shaper 4 -10 -10 -5    # Curve Shaper: tier 0-4, margini a bassa/media/alta temperatura
sudo ryzenctl power balanced         # power-saver | balanced | performance
sudo ryzenctl default                # tutto ai valori di base (BIOS), avvio automatico off
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

1. `dkms status`, `modinfo -F signer ryzen_smu` (chiave dkms o akmods), `lsmod | grep ryzen_smu`
   vuoto prima di `systemctl start ryzenctl`, pieno dopo; `codename` = 23.
2. `sudo ryzenctl status` = valori BIOS; `baseline show` coerente.
3. Scritture minime reversibili: `co 7 -3` → `co 7 0`; `ppt 150` → `ppt 162`; `fmax 5000`
   (sotto carico `grep MHz /proc/cpuinfo` ≤ 5000) → valore base; `tjmax 85` → base;
   `shaper 4 -2 -2 -2` → `shaper 4 0 0 0`.
4. Crash-guard: profilo innocuo (`ppt 150`) con autostart; `sync; echo b | sudo tee
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

GPL-3.0-or-later. Il driver vendorizzato in `ryzen_smu/` resta GPL-2.0 (pacchetto
`ryzen-smu-dkms`); vedi `ryzen_smu/UPSTREAM.md`. Riferimenti tecnici: ryzen_smu (amkillam),
ZenStates-Core (irusanov), gnr-smu (Kyworn, misure sul 9800X3D).
