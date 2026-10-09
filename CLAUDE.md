# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Stato del progetto

"Ryzen Control": controllo stile Ryzen Master (Curve Optimizer, Curve Shaper, PBO, FMax/Tjmax,
ventole) per un Ryzen 7 9800X3D su Linux, GUI GTK4/libadwaita + helper root, pacchetti RPM/deb/Arch.

Il codice non esiste ancora. La fonte di verità è il piano
`docs/plans/2026-10-09-ryzen-control.md` (rev. 3): architettura, tabella comandi SMU, range di
validazione, formato profili, crash-guard, fasi e commit previsti. Leggerlo prima di toccare
qualcosa; questo file ne riassume solo l'essenziale. I piani futuri vanno nella stessa cartella
(`docs/plans/YYYY-MM-DD-<argomento>.md`). Lingua di piano, README e messaggi di commit: italiano.

## Layout previsto

- `ryzenctl` — Python stdlib, unico punto privilegiato (CLI, `serve`, `selftest`), ~350 righe.
- `ryzen-control` — GUI Python/PyGObject (GTK4, libadwaita ≥ 1.5), gira come utente, ~700 righe.
- `ryzen_smu/` — driver upstream vendorizzato con `git subtree` (amkillam/ryzen_smu, commit
  d298366) + patch locale in `smu.c` (dimensioni PM table 0x6211xx/0x6212xx).
- `Makefile` — unica fonte del layout installato (`install`/`uninstall`/`dkms`, `DESTDIR`,
  `PREFIX`, `APPID=org.ryzencontrol.RyzenControl`). Ogni pacchetto è un involucro che chiama
  `make install DESTDIR=…`, mai un layout duplicato.
- `data/` — unit systemd, policy polkit, .desktop, icona, metainfo, autostart.
- `packaging/ryzen-control.spec` (RPM, due sottopacchetti `ryzen-control` e `ryzen-smu-dkms`),
  `packaging/debian/`, `packaging/PKGBUILD`.

Vincoli di compatibilità: sintassi Python ≥ 3.9 (nessuna feature più recente), libadwaita ≥ 1.5,
niente dipendenze Python oltre PyGObject, nessun framework di test.

## Comandi

Senza hardware né root (si eseguono prima di ogni commit):

```sh
python3 ryzenctl selftest                       # backend SMU finto; copre codifiche, validazione, profili, baseline, crash-guard
RYZENCTL_ROOT=/tmp/fake python3 ryzenctl status # CLI sul backend finto (stesso del selftest)
python3 ryzen-control --mock                    # GUI senza driver né pkexec
make -C ryzen_smu                               # compila il driver con gli header del kernel corrente
make install DESTDIR=/tmp/x && find /tmp/x      # verifica il layout installato
systemd-analyze verify data/*.service
desktop-file-validate data/*.desktop
appstreamcli validate data/*.metainfo.xml
rpmbuild -ba packaging/ryzen-control.spec       # rpmdevtools presente; rpmlint NON installato
```

Su hardware (li esegue l'utente, con `! comando`; si committa dopo il suo esito):

```sh
sudo ryzenctl status                            # deve coincidere con i valori BIOS
sudo ryzenctl co 7 -3 && sudo ryzenctl co 7 0   # scrittura minima reversibile con readback
dkms status; modinfo -F signer ryzen_smu
cat /sys/kernel/ryzen_smu_drv/codename          # 23 = Granite Ridge
```

Non testabili su questa macchina: `dpkg-buildpackage`, `namcap`, `stress-ng` (mancanti).
I pacchetti deb/Arch vanno marcati "non testati" nel README.

## Architettura

```
ryzen-control (GUI, utente) ──pkexec──▶ ryzenctl serve (root, valida TUTTO)
                                          ├─ /sys/kernel/ryzen_smu_drv/*   (SMU)
CLI: sudo ryzenctl …  ────────────────────┤─ /sys/class/hwmon/nct67xx/*    (ventole)
systemd: ryzenctl.service, -resume ───────┘─ /etc/ryzenctl, /var/lib/ryzenctl
```

- **Una sola grammatica di comandi** (`co 7 -3`, `ppt 88`, `fmax 4800`, `fan 2 step 10000 5000`,
  …) usata identica da CLI, righe dei file profilo e protocollo `serve` (una riga JSON-array per
  richiesta, una riga JSON di risposta). Un nuovo comando si aggiunge in un solo posto.
- **`ryzenctl` è il confine di fiducia**: la GUI non valida nulla di definitivo, invia e mostra
  gli errori. `serve` viene avviato una volta per sessione (un solo prompt pkexec).
- **Backend finto condiviso**: `selftest`, `RYZENCTL_ROOT` e `--mock` usano lo stesso backend
  (monkeypatch di due funzioni + radice filesystem da env). Nuova logica = caso nel selftest.
- **Baseline** (`/var/lib/ryzenctl/baseline.conf`, stesso formato dei profili): catturata a ogni
  boot prima di applicare qualsiasi cosa. "Default" = `apply baseline` + autostart off. Tetto di
  ogni valore = baseline, salvo sblocco esplicito (`unlock on`, con avvertenza).
- **Crash-guard** (requisito esplicito dell'utente): `boot` trova `dirty` **e** `active` →
  scrive `crashed`, NON riapplica la parte CPU (ventole sì); `shutdown` pulito rimuove `dirty`;
  `active` nasce da qualsiasi scrittura non-baseline. Via di fuga: parametro kernel `ryzenctl.off`.
- **Modalità** statiche (nessun demone, il dinamismo lo fa PBO): Default / Quiet / Auto / Boost /
  Custom. Quiet e Auto si ottengono da calibrazioni in GUI che abbassano solo limiti.
- **Ventole**: nessun demone; si cambiano solo `pwmN_step_up_time`/`step_down_time` (e punti
  curva se richiesto) della SmartFan già programmata dal BIOS. `pwmN_enable` non si tocca mai
  (eccezione "Identifica", ripristino in `finally`). Il parametro kernel
  `acpi_enforce_resources=lax` è un passo manuale mostrato in GUI: il pacchetto non tocca il
  bootloader.

## Invarianti hardware (non negoziabili)

- Allowlist SMU rigida (tabella nel piano): CO MP1 0x35, PPT/TDC/EDC MP1 0x3E/0x3C/0x3D, FMax
  RSMU 0x70/0x6E, Tjmax RSMU 0x59, Shaper RSMU 0xA6/0x84. Nessun altro ID viene inviato.
  Mai MP1 0x58–0x6F (congela l'SMU sul 9800X3D) né MP1 0x10 (spegne il display).
- Gate: `codename` deve essere Granite Ridge, altrimenti rifiuto totale.
- Ogni transazione SMU sotto `flock(/run/ryzenctl.lock)` (`smu_args` del driver è globale).
- Ogni scrittura è seguita da readback; discrepanza = errore, nessun fallback automatico.
- Floor: PPT ≥ 45 W, TDC ≥ 30 A, EDC ≥ 45 A (PPT 0 blocca la CPU a 606 MHz). CO/Shaper −50..+30,
  FMax 3000..baseline, Tjmax 60..baseline. Le costanti di validazione stanno in testa a
  `ryzenctl` e sono manopole di calibrazione, non da sparpagliare.
- Valori dalla PM table letti solo se `pm_table_version>>16 == 0x62`.
- Nomi profilo solo `[a-z0-9_-]`.

## Flusso di lavoro

- Repo git personale locale, branch `main`, nessun remote finché l'utente non ne indica uno.
  Oggi il repo non è ancora inizializzato: il primo commit previsto è `chore: init repo, plan,
  README stub`.
- Sviluppo a passi seguendo la tabella "Fasi e commit" del piano: un commit per passo, **solo
  dopo la verifica** del passo. Verifica fallita → si corregge, niente commit.
- Prefisso convenzionale (`feat/fix/build/docs/chore/test`), messaggio in prosa italiana.
- Tag `v0.1.0`, `v0.2.0`, … a fine di ogni fase verificata su hardware; la versione del tag è
  quella della spec RPM.
- Le semplificazioni deliberate con un tetto noto si marcano con un commento `# ponytail:`
  (già previsti nel piano: euristica famiglia PM table, calibrazioni a misura singola).
