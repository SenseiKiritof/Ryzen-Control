# Piano: "Ryzen Control" — controllo stile Ryzen Master su Linux (9800X3D)

Copia nel progetto: `~/Documenti/Progetti/Personali/Ryzen Control/docs/plans/2026-10-09-ryzen-control.md`
Revisione 2 (2026-10-09): installazione via pacchetti (RPM + base cross-distro), niente `install.sh`.
Revisione 3 (2026-10-09): modalità Auto; repo git personale, sviluppo a passi con verifica e commit.
Revisione 4 (2026-10-09): revisione di sicurezza (crash-guard riscritto, cosa non si tocca mai,
protezione pompa); ventole prima della GUI.
Revisione 5 (2026-10-09): zero passi manuali dove possibile — il `%post` del pacchetto -dkms
riusa la chiave akmods se già registrata in MOK (drop-in dkms creato solo in quel caso,
`%ghost`), rebuild forzato, `ryzen-control` avvia il servizio all'installazione; `ryzenctl
hwtest` automatizza la verifica reversibile su hardware. Resta manuale solo ciò che Secure Boot
impone (registrazione MOK al riavvio, se nessuna chiave è già registrata) e il test di crash.
In fase 2 `ryzenctl fan enable` imposterà da sé il parametro kernel (grubby / /etc/default/grub)
con conferma esplicita, reversibile con `fan disable`.
Revisione 7 (2026-10-09): curva ventole per modalità (Quiet dal target, Auto step moderato).
Revisione 6 (2026-10-09): fase 1 verificata su hardware e taggata `v0.1.0`; un solo pacchetto
di installazione (driver DKMS dentro `ryzen-control`); nuova fase 6: icona nel vassoio di
sistema con comandi rapidi.

## Context

Obiettivo utente: gestire da Linux Curve Optimizer, Curve Shaper, limiti PBO, FMax/Tjmax e
ventole con una GUI completa, modalità Default/Quiet/Auto/Boost, calibrazione automatica e
auto-tuning CO. Bisogno principale: AIO più silenzioso (oggi Tctl sale di colpo e le ventole
vanno al massimo). Requisiti espliciti:
- dopo un crash il profilo NON si riapplica da solo: decide l'utente;
- Default = ritorno ai valori di base letti dalla CPU (baseline);
- limiti ≤ stock; oltre stock solo con sblocco esplicito e avvertenza;
- GTK4/libadwaita, compatibile con altre distro;
- modalità Auto = efficienza/prestazioni ottimizzate automaticamente; Boost = sola potenza
  bruta; Quiet = silenzio; Default = valori di fabbrica;
- installazione con pacchetto classico (RPM) e strada praticabile per ogni distro;
- niente che possa danneggiare l'hardware; ventole prima della GUI.

Sistema rilevato:
- Ryzen 7 9800X3D (Granite Ridge, fam 0x1A mod 0x44), 1 CCD, 8 core; `cpuN`/`cpuN+8` = core
  fisico N; core migliori (prefcore 196) 1 e 2, peggiore 7.
- ASUS ROG STRIX X870E-H GAMING WIFI7 **HATSUNE MIKU EDITION**, BIOS 0405, root complex `1022:14d8`.
- Fedora 44, kernel 7.2.8, **Secure Boot attivo**; chiave MOK akmods già registrata (NVIDIA).
  `dkms` 3.4.3 installato, `dkms.service` abilitato; `rpm-build` + `rpmdevtools` presenti.
- Root filesystem btrfs (commit ogni 30 s: i marker del crash-guard vanno `fsync`-ati).
- Sleep `deep` (S3). Profilo energetico attivo `performance`.
- Ventole: nessun hwmon fan/pwm. `nct6775` non elenca la scheda e il nome DMI con suffisso
  "HATSUNE MIKU EDITION" fa fallire anche `asus-ec-sensors`. Nessun AIO USB → pompa/ventole
  sugli header della scheda (Super I/O Nuvoton, curve SmartFan IV programmate dal BIOS).
- RAPL disponibile: `/sys/class/powercap/intel-rapl:0` (`package-0`, `core`), lettura solo root.
- Installati: Python 3.14, PyGObject 3.56, GTK 4.22, libadwaita 1.9. Non installati: stress-ng.

Ricerca fatta (sorgenti in scratchpad): driver `ryzen_smu` (amkillam, supporta Granite Ridge,
fix kernel 7.2+ in d298366); ZenStates-Core `Zen4Settings.cs`/`Zen5Settings.cs` (ID comandi SMU
di riferimento); gnr-smu (mappa PM table 0x620105 misurata su 9800X3D, ID MP1 pericolosi);
RyzenSMUDebug-LINUX (FMax 0x6E/0x70 testato su Granite Ridge). Nessun tool esistente copre
persistenza + crash-guard + limiti + Curve Shaper + ventole: si scrive un'app piccola, si
riusano solo i dati misurati.

## Verifica di sicurezza (rev. 4)

Domanda: può danneggiare l'hardware? No, per costruzione:
- I danni reali su AM5 vengono da tensioni fisse (SoC/VDDIO/VDDG, VID manuale in OC mode).
  Questo programma **non invia nessun comando di tensione** e non entra mai in OC mode: RSMU
  0x5D `EnableOcMode`, 0x61 `SetOverclockCpuVid`, 0x5B `SetPBOScalar`, le CLDO/SoC e il file
  `smn` restano fuori dall'allowlist. Non tocca FCLK/UCLK/memoria.
- Tutto ciò che scrive è un *limite* che il firmware continua a far rispettare: PPT/TDC/EDC e
  Tjmax solo ≤ baseline (sopra stock solo con sblocco esplicito, tetti 230 W/160 A/230 A e
  Tjmax comunque ≤ baseline → la protezione termica resta sempre attiva), FMax ≤ baseline
  (+200 MHz con sblocco, come "Boost Override" del BIOS), CO/Shaper −50..+30 (CO negativo =
  undervolt: può solo causare instabilità; positivo resta entro i limiti di tensione del
  firmware).
- Errori possibili: crash/riavvio per CO troppo negativo (gestito dal crash-guard), SMU che
  rifiuta (0xFD/0xFE, nessun effetto), congelamento SMU per ID sbagliato (escluso
  dall'allowlist; richiederebbe solo un riavvio).

Problemi trovati nella rev. 3 e corretti qui:
1. **Boot loop possibile**: `dirty` veniva creato *dopo* l'apply; un crash durante l'apply al
   boot non lasciava traccia → riapplicato a ogni boot. Ora i marker precedono ogni scrittura
   e sono `fsync`-ati (btrfs).
2. **Via di fuga incompleta**: il driver si autocarica via PCI ID anche con `ryzenctl.off`.
   Ora il pacchetto blacklista l'autoload e il modulo lo carica solo il servizio.
3. **Baseline corrotta** da `systemctl restart` a profilo attivo. Ora cattura una sola volta
   per boot e mai se `active` esiste.
4. **Pompa dell'AIO**: un canale pompa rallentato è l'unico vero rischio lato ventole. Linux
   vede solo `pwm1..N` senza nome e gli RPM da soli non distinguono (pompe 2000–3500, ventole
   500–3000). Ora il ruolo lo assegna un test fisico automatico (`fan autodetect`, vedi
   "Ventole"), l'utente può solo declassare un canale, mai promuoverlo a "ventola"; tutto ciò
   che non è "ventola" è in sola lettura.
5. **Readback fallito**: ora un tentativo di ripetizione, poi ripristino del valore baseline
   di quel parametro, poi errore (protegge da gare con altri tool SMU).
6. **PM table assente** (AGESA nuovo): baseline dei limiti impossibile → PPT/TDC/EDC/Tjmax
   rifiutati (fail closed), CO/FMax/Shaper ok (readback via RSMU).
7. Scritture di file di stato atomiche (`tmp` + `os.replace` + fsync): un crash non lascia
   JSON/profili corrotti; un profilo illeggibile non viene applicato.
8. Auto-tuning: aggiunta fase a carico basso (le instabilità CO si vedono soprattutto in
   idle), passata finale combinata, stress-ng eseguito come utente, avviso "salva tutto".

## Architettura (3 file di codice + driver vendorizzato + pacchetti)

```
ryzen-control (GUI GTK4/Adw, utente) ──pkexec──▶ ryzenctl serve (root, valida TUTTO)
                                                   ├─ /sys/kernel/ryzen_smu_drv/*  (SMU)
CLI: sudo ryzenctl …  ─────────────────────────────┤─ /sys/class/hwmon/nct67xx/*   (ventole)
systemd: ryzenctl.service (boot/stop), -resume ────┘─ /etc/ryzenctl, /var/lib/ryzenctl
```

- `ryzenctl` (Python stdlib, ~400 righe): unico punto privilegiato = confine di fiducia.
  Stessa grammatica comandi per CLI, file profilo e protocollo `serve` (una riga JSON-array per
  richiesta → una riga JSON di risposta, su pipe: solo il processo padre può parlargli).
- `ryzen-control` (Python + PyGObject GTK4/libadwaita ≥1.5, ~700 righe): gira come utente,
  avvia una sola volta `pkexec ryzenctl serve` (un prompt password per sessione). Legge
  direttamente (sola lettura) `crashed`, `settings.json`, profili, baseline; usa `serve` per
  scritture e letture SMU/RAPL. stress-ng lo lancia la GUI come utente; `serve` lo esegue
  solo dentro `fan autodetect`, con argomenti fissi.
- `ryzen_smu/`: driver upstream vendorizzato (`git subtree`, commit d298366) + una modifica
  locale in `smu.c`: dimensioni PM table 0x621101/0x621102 (0x724) e 0x621201/0x621202 (0x994)
  da ZenStates-Core `PowerTable.cs`, per AGESA più recenti.
- Nessun test framework: `ryzenctl selftest` con backend SMU finto (monkeypatch di 2 funzioni,
  path radice da env `RYZENCTL_ROOT`) copre codifiche, validazione, profili, baseline,
  crash-guard. `--mock` nella GUI usa lo stesso backend.

### Pacchettizzazione

`Makefile` = unica fonte del layout (`install`/`uninstall`/`dkms`, rispetta `DESTDIR`/`PREFIX`;
variabile `APPID=org.ryzencontrol.RyzenControl`). Ogni formato di pacchetto è un involucro
sottile che chiama `make install DESTDIR=…`.

Layout installato:
```
/usr/bin/ryzenctl, /usr/bin/ryzen-control
/usr/lib/systemd/system/ryzenctl.service, ryzenctl-resume.service
/usr/lib/modprobe.d/ryzen-control.conf              (blacklist ryzen_smu: niente autoload, lo carica il servizio)
/usr/share/polkit-1/actions/<APPID>.policy          (auth_admin_keep, exec.path=/usr/bin/ryzenctl)
/usr/share/applications/<APPID>.desktop
/usr/share/icons/hicolor/scalable/apps/<APPID>.svg
/usr/share/metainfo/<APPID>.metainfo.xml            (AppStream: visibile in Discover/GNOME Software)
/etc/xdg/autostart/ryzenctl-notify.desktop          (notifica crash al login)
/etc/ryzenctl/                                      (config, %config(noreplace))
/var/lib/ryzenctl/                                  (stato: baseline, dirty, active, crashed)
/usr/src/ryzen_smu-<ver>/                           (sorgente driver + dkms.conf, pacchetto -dkms)
```

1. **RPM — `packaging/ryzen-control.spec`** (Fedora/RHEL/openSUSE), `BuildArch: noarch`,
   un tarball dal repo, **un solo pacchetto** `ryzen-control` (rev. 6, richiesta utente;
   `License: GPL-3.0-or-later AND GPL-2.0-only` per il driver incluso; `Obsoletes/Provides:
   ryzen-smu-dkms` per chi ha installato la 0.1.0-1…4):
   - app: `Requires: python3 ≥ 3.9, python3-gobject, gtk4, libadwaita ≥ 1.5, polkit, systemd`;
     `Recommends: stress-ng, libnotify`. Preset systemd abilita i servizi (non applicano nulla
     senza autostart); `%post` avvia il servizio.
   - driver: copia `ryzen_smu/*.c *.h Makefile dkms.conf` in `%{_usrsrc}/ryzen_smu-%{version}`
     sostituendo `@VERSION@`/`@CFLGS@`; `Requires: dkms, kernel-devel, gcc, make`; `%post`:
     drop-in chiave akmods se registrata, `dkms add/build/install --force --rpm_safe_upgrade`
     (non fatale), avviso Secure Boot solo se nessuna chiave registrata; `%preun`: `dkms
     remove --all`.
   - Build: `make rpm` locale oppure COPR (spec COPR-ready: noarch, nessuna rete al build
     grazie al driver vendorizzato).
2. **Debian/Ubuntu — `packaging/debian/`**: `control` (1 binario), `rules` (`dh $@ --with
   dkms`), `ryzen-control.dkms`, `install`, `changelog`, `copyright`.
3. **Arch — `packaging/PKGBUILD`**: un solo `package()`, dkms via hook di pacman.
4. **Qualsiasi altra distro**: `sudo make install && sudo make dkms` (ultima spiaggia
   documentata nel README).

deb e PKGBUILD non sono testabili su questa macchina: involucri minimi marcati "non testati".

Secure Boot con DKMS 3.4.3: firma di default con `/var/lib/dkms/mok.key`/`mok.pub` (creati se
mancanti). Una sola registrazione: `mokutil --import /var/lib/dkms/mok.pub` + riavvio.
Alternativa su questa macchina (zero nuove MOK): drop-in `/etc/dkms/framework.conf.d/akmods.conf`
che punta alla chiave akmods — documentata, non imposta dal pacchetto.

### Comandi SMU (allowlist rigida, nient'altro può essere inviato)

| Funzione | Mailbox | ID | Argomento | Verifica (readback) |
|---|---|---|---|---|
| CO per core | MP1 | 0x35 | `core<<20 \| (m & 0xFFFF)` | RSMU 0xD5 arg0=`core<<20`, low16 signed |
| PPT / TDC / EDC | MP1 | 0x3E / 0x3C / 0x3D | W·1000 / A·1000 | PM d[2] / d[8] / d[63] |
| FMax | RSMU | 0x70 set, 0x6E get | MHz | 0x6E |
| Tjmax | RSMU | 0x59 | °C | PM d[10] |
| Curve Shaper | RSMU | 0xA6 set, 0x84 get | `hi<<24\|med<<16\|lo<<8\|0x80\|tier` | 0x84 (5 arg = 5 tier) |
| PM table | (driver) | — | file `pm_table` | — |

Fonti: CO 0x35 validato con readback su 9950X3D (stessa famiglia); PPT/TDC/EDC validati con
readback proprio su 9800X3D; FMax/Tjmax/Shaper da ZenStates-Core (Shaper mai provato su Linux:
solo il readback 0x84 lo conferma). MP1 0x58–0x6F congela l'SMU sul 9800X3D e MP1 0x10 spegne
il display: non sono mai inviati. RSMU 0x59/0x6E sono comandi di produzione ZenStates su
Zen 4/5 (il range "proibito" riguarda solo MP1).

Regole di transazione:
- Gate: `codename` = Granite Ridge, altrimenti rifiuto totale. Mai scritture su `smn`.
- Ogni transazione sotto `flock(/run/ryzenctl.lock)`: `smu_args` del driver è globale.
  Documentato: non usare altri tool SMU (gnr-smu, ryzen_monitor) in contemporanea.
- Ogni scrittura → readback. Discrepanza → una ripetizione → se ancora diversa, riscrive il
  valore baseline di quel parametro → errore. Risposta 0xFD (prerequisito) → suggerisce
  PBO = Advanced nel BIOS.
- Valori PM letti solo se `pm_table_version>>16 == 0x62` (`# ponytail:` euristica famiglia,
  mappa completa solo 0x620105). PM table assente → PPT/TDC/EDC/Tjmax rifiutati (nessuna
  baseline per loro), CO/FMax/Shaper ok.
- Se CO via MP1 0x35 non torna al readback → si valuta RSMU 0x6 (ZenStates), niente fallback
  automatico.
- Apply di un profilo: si ferma al primo errore (le righe già applicate sono singolarmente
  entro i limiti), riporta la riga fallita.

### Validazione (costanti in testa = manopole di calibrazione)

- CO e Shaper −50..+30. FMax 3000..baseline (+200 se sbloccato). Tjmax 60..baseline (max 95).
- PPT ≥45 W, TDC ≥30 A, EDC ≥45 A (mai 0: PPT 0 blocca a 606 MHz). Tetto = baseline (stock);
  con sblocco 230 W / 160 A / 230 A. Scrivere esattamente il valore di baseline è sempre ammesso.
- Senza baseline fresca di questo boot: nessuna scrittura CPU (fail closed).
- Sblocco: `ryzenctl unlock on` stampa avvertenza; in GUI switch + `Adw.AlertDialog`.
- Ventole: canale modificabile solo se `fan autodetect` lo ha classificato "ventola" in
  `settings.json` ("pompa", "non controllabile", "sconosciuto" → rifiuto; a mano si può solo
  declassare); step up/down 0..60000 ms; curva con temp crescenti, pwm non decrescenti, pwm
  minimo ≥ 77 (30 %), ultimo punto pwm 255 a ≤90 °C; `pwmN_enable` mai cambiato, tranne nei
  due test (`autodetect`, `identify`) che lo ripristinano in `finally`.
- Nomi profilo solo `[a-z0-9_-]`. File di stato scritti in modo atomico.

### Profili, baseline, modalità

- Profilo = file di righe-comando: `/etc/ryzenctl/profiles/<nome>.conf` (`co -15 -10 …`,
  `fmax 4800`, `ppt 88`, `power balanced`, `fan 2 step 10000 5000`, `fan 2 curve 40:60 …`).
  `apply` = esegui ogni riga. Salvataggio dalla GUI: ogni riga validata (dry-run) prima.
- `/etc/ryzenctl/settings.json`: profilo attivo, autostart, unlock, ruolo/nome canali ventola.
- Baseline `/var/lib/ryzenctl/baseline.conf` nello stesso formato: catturata **una volta per
  boot, prima di applicare** (SMU = valori BIOS), mai se `active` esiste; guardia
  `/run/ryzenctl/baseline-done`. Contiene CO, FMax, PPT/TDC/EDC/THM, Shaper, profilo
  energetico, impostazioni ventole. Segue eventuali modifiche al BIOS.
- Modalità (tutte statiche: il comportamento dinamico lo fa già PBO nell'SMU, nessun demone):
  - **Default**: `apply baseline`, rimuove `active`, disattiva autostart.
  - **Quiet**: FMax da calibrazione Quiet, PPT/TDC/EDC eco AMD 88/75/150, Tjmax = target+10
    (≤ baseline), CO da auto-tuning se presente, `power balanced`, ventole step up 10 s /
    down 5 s sui canali marcati "ventola". Obiettivo: temperatura/rumore.
  - **Auto**: PPT/TDC/EDC e FMax dalla calibrazione Auto (punto di ginocchio prestazioni/W di
    *questa* CPU), CO da auto-tuning, Tjmax baseline, `power balanced`. Finché non calibrata:
    preset eco AMD 105 W (142/110/170), FMax baseline. Obiettivo: prestazioni per watt.
  - **Boost**: limiti baseline (o tetti sbloccati), FMax massimo consentito, Tjmax baseline,
    CO da auto-tuning, `power performance`. Obiettivo: potenza bruta.
  - **Custom**: valori impostati a mano nelle pagine.
- `power`: profilo energetico via D-Bus `net.hadess.PowerProfiles` (`busctl`, funziona con
  power-profiles-daemon e tuned-ppd); se assente, scrittura EPP in sysfs.

### Crash-guard (requisito esplicito) — macchina a stati

Marker in `/var/lib/ryzenctl/`, ognuno scritto con `fsync` di file e directory:
- `dirty`: "questo boot non è ancora terminato in modo pulito".
- `active`: "in questo boot è stato scritto uno stato CPU diverso dalla baseline".
- `crashed`: `{ora, profilo}` — il boot precedente è finito male con un profilo attivo.

```
ryzenctl boot   (ryzenctl.service, oneshot RemainAfterExit, After=dkms.service,
                 ExecStartPre=-/sbin/modprobe ryzen_smu, ConditionKernelCommandLine=!ryzenctl.off)
  1. se dirty ∧ active            → scrive crashed {ora, profilo}
  2. rm active
  3. scrive dirty                 (PRIMA di qualunque scrittura SMU)
  4. baseline: solo se manca /run/ryzenctl/baseline-done; fallita → niente scritture CPU
  5. ventole: applica la parte fan del profilo se autostart (non possono causare crash)
  6. CPU: solo se autostart ∧ ¬crashed; ogni riga non-baseline scrive active (fsync) e POI l'SMU

ryzenctl shutdown (ExecStop, spegnimento/riavvio puliti)      → rm dirty
scrittura runtime (CLI o serve) di un valore non-baseline      → active prima dell'SMU
ryzenctl-resume.service (After=/WantedBy= dei target di sleep) → riapplica se autostart ∧ ¬crashed
Default                                                        → apply baseline, rm active, autostart off
GUI "Riattiva"                                                 → rm crashed, autostart on, apply
GUI "Resta su Default"                                         → rm crashed, autostart off
```

Scenari verificati sulla macchina a stati:
- Crash a regime con profilo attivo → dirty ∧ active → `crashed`, niente apply, notifica al
  login (`ryzenctl notify` da autostart XDG), banner `Adw.Banner` nella GUI con
  **Riattiva** / **Resta su Default**.
- Crash *durante* l'apply al boot (CO instabile all'avvio) → dirty già scritto → al boot
  successivo `crashed`. Nessun loop: ogni nuovo tentativo richiede un clic su "Riattiva".
- Crash in un boot in cui nulla era applicato (profilo disattivato, o `crashed` già presente)
  → `active` assente → non segnalato come colpa nostra; `crashed` precedente resta finché
  l'utente non decide.
- Crash prima che il servizio parta (altra causa) → dirty del boot precedente → falso
  positivo nella direzione sicura (profilo non applicato, un clic per riattivare).
- Spegnimento con tasto power / reset → trattato come crash → direzione sicura.
- Suspend: con S3 le impostazioni SMU tornano a quelle BIOS → `-resume` riapplica; resume
  fallito → reset → dirty ∧ active → `crashed`.
- `systemctl restart ryzenctl` a profilo attivo → baseline non ricatturata (guardia /run +
  `active`), nessuna corruzione del tetto.
- Via di fuga totale: in GRUB `e` + `ryzenctl.off` → il servizio non parte e, grazie alla
  blacklist, il modulo non viene caricato affatto. Il `dirty` rimasto fa scattare `crashed`
  al boot normale successivo.
- Crash durante l'auto-tuning: il valore in prova è scritto (fsync) nello stato GUI prima
  dell'SMU; `active` è impostato → `crashed`; la GUI incrocia `crashed.ora` con il proprio
  stato e marca il passo come instabile.
- Driver che non compila per un kernel nuovo → `boot` salta la parte CPU con messaggio, le
  ventole si applicano comunque; non fallisce.
- Avvertenza unica nelle finestre di auto-tuning e sblocco: possibili riavvii improvvisi,
  salvare il lavoro (perdita dati, non danni).

### GUI `ryzen-control` (Adw.ViewStack, 5 pagine)

1. **Monitor** (polling 1 s, comando `telemetry`): Tctl/Tccd1 (k10temp) + grafico 60 s
   (cairo), PPT/TDC valore vs limite (LevelBar), MHz e CO per core, temp per core (solo
   0x620105), RPM ventole.
2. **Modalità**: Default/Quiet/Auto/Boost/Custom, switch "Applica all'avvio", switch sblocco,
   banner crash, pulsanti **Calibra Quiet**, **Calibra Auto** (slider perdita max %) e
   **Auto-tuning CO** con progresso, log e tabella risultati.
3. **CPU**: PPT/TDC/EDC, FMax, Tjmax, profilo energetico (Adw.SpinRow limitati ai tetti).
4. **Curve**: CO per core (8 SpinRow + "tutti"), Curve Shaper 5 tier × 3 temperature.
5. **Ventole**: pulsante **Rileva ruoli** (autodetect, con progresso e motivazione per
   canale: ΔT, RPM), canali con RPM, ruolo e nome, step up/down, punti curva (spin +
   anteprima) solo sui canali "ventola", Identifica; se nct6775 assente → istruzioni con
   comandi pronti (parametro kernel + `ryzenctl fan enable`).
Ogni pagina: **Applica ora** (runtime) e **Salva nel profilo** (menu profili).

### Ventole da Linux (scelta utente; fase 2, prima della GUI)

- Fattibilità prima di toccare il boot: `sudo modprobe nct6775; sudo dmesg | grep -i nct`
  (atteso: chip trovato + conflitto risorse ACPI).
- Se il chip c'è: parametro kernel `acpi_enforce_resources=lax` (passo manuale: Fedora
  `grubby --update-kernel=ALL --args=…`, altre distro `GRUB_CMDLINE_LINUX_DEFAULT`) +
  `ryzenctl fan enable` (scrive `/etc/modules-load.d/nct6775.conf`, carica il modulo).
  Rischio: accessi concorrenti al Super I/O con ACPI; scritture minime, solo all'apply.
- Prima cosa dopo il rilevamento: `ryzenctl fan autodetect` assegna i ruoli con un test
  fisico, senza intervento umano. Sotto carico moderato e stabile (`stress-ng --cpu 4`,
  argomenti fissi), per ogni canale con RPM > 0: mediana di Tctl e RPM su 5 s → canale al
  40 % per 20 s → nuova mediana → ripristino. Classificazione:
  - RPM varia < 5 % → **non controllabile** (ventola 3 pin o pompa a 12 V fissi) → protetto;
  - Tctl sale ≥ 2 °C **oppure** RPM al 40 % ancora ≥ 1500 → **pompa** → protetto;
  - Tctl sale < 1 °C e RPM cala → **ventola** → scrivibile;
  - altrimenti **sconosciuto** → protetto.
  Base fisica: meno flusso nel blocco alza Tctl di gradi in pochi secondi; meno aria sul
  radiatore scalda ~400 g di liquido lentamente (~0,5 °C in 20 s): separazione ≥ 5×. Guardie:
  abort e ripristino immediato se Tctl > 80 °C o ΔT > 8 °C, massimo 20 s per canale,
  ripristino in `finally`, Tjmax sempre attivo. Soglie = costanti in testa al file
  (`# ponytail:` tarate su un AIO 360; ritoccare se un radiatore piccolo le sfiora).
  Senza stress-ng o senza test eseguito: nessun canale scrivibile (fail closed).
  `ryzenctl fan role N pompa|sconosciuto` serve solo a declassare; "ventola" a mano non esiste.
  `ryzenctl fan identify N` (100 % per 5 s) resta come aiuto per riconoscere fisicamente
  quale ventola del case è quale, non assegna ruoli.
- Controllo = curva hardware SmartFan IV già programmata dal BIOS: si cambiano solo
  `pwmN_step_up_time`/`step_down_time` (ignora i picchi brevi: causa vera del rumore) e, se
  richiesto, `pwmN_auto_point*`. Niente demone: se l'app muore, il chip continua da solo.
  La CPU resta protetta da Tjmax qualunque cosa facciano le ventole.

### Calibrazione Quiet (in GUI, sicura: abbassa solo limiti)

Target Tctl (default 70 °C). Applica baseline + CO corrente; poi da FMax baseline scende a
passi di 100 MHz (minimo 4000): per ogni passo 12 cicli `stress-ng --cpu 2 -t 2s` + 3 s pausa,
campiona solo k10temp a 20 Hz (niente letture PM durante la misura: scaldano il die), prende il
p95 dei picchi; primo FMax con p95 ≤ target → profilo Quiet. `# ponytail:` euristica, la
temperatura del liquido deriva nel tempo.

Ventole nelle modalità (rev. 7, solo canali classificati "ventola"; pompa mai toccata):
- **Quiet**: curva ricavata dal target: pwm minimo della curva BIOS fino a `target − 10 °C`,
  salita lineare al 100 % a `Tjmax − 5 °C`; step 10 s / 5 s.
- **Auto**: curva del BIOS, step 3 s / 2 s (toglie i picchi senza ritardare troppo).
- **Boost / Default**: curva e step del BIOS.

### Calibrazione Auto (in GUI, sicura: abbassa solo limiti)

Trova il punto in cui *questa* CPU rende di più per watt. Parametro unico esposto come slider:
**perdita massima di prestazioni** rispetto a Boost (default 10 %). Prima applica Boost + CO
corrente. Misure: prestazioni = bogo-ops/s di `stress-ng --metrics -Y`; potenza = energia RAPL
(`intel-rapl:0/energy_uj`, via `ryzenctl`) / durata; fallback PM d[3].
1. Sweep multi-thread: PPT da baseline a −10 % per passo fino al 50 % (TDC/EDC scalati con lo
   stesso rapporto, floor rispettati); a ogni punto 5 s di assestamento + 15 s
   `stress-ng --cpu 0 --cpu-method matrixprod`. Scelta: PPT più basso con prestazioni
   ≥ (100 − perdita) % del massimo misurato.
2. Sweep single-thread: FMax da baseline a passi di −100 MHz fino a −800; `stress-ng --cpu 1
   --taskset <core migliore>`; stessa regola di scelta.
Risultato salvato nel profilo Auto con la tabella misurata (W, ops/s, ops/W per punto).
Durata ~5 min. `# ponytail:` una misura per punto, ripetere se la differenza fra punti
adiacenti è sotto il rumore (~2 %).

### Auto-tuning CO (in GUI, rischio crash gestito)

Avvertenza + conferma ("salva tutto: possibili riavvii improvvisi"). Stato in
`~/.local/state/ryzen-control/autotune.json` (fsync prima di ogni passo). Per core 0..7, gli
altri core a baseline (così un crash è attribuibile): da 0 scende a passi di −5 fino al limite
(default −40); ogni passo N minuti (default 3) in tre fasi: pieno carico `stress-ng --cpu 1
--taskset c --cpu-method all --verify`, carico variabile `--cpu-load 50`, carico basso
`--cpu-load 10` (le instabilità CO emergono soprattutto in idle). Fallimento = exit
stress-ng ≠ 0 o nuovi errori MCE (`ryzenctl mce-since`, root legge il log kernel). Risultato
core = ultimo stabile + 3 di margine. Passata finale con tutti i core ai valori trovati
(10 min, tre fasi): se fallisce, +3 a tutti e ripetizione. Crash/blocco → al riavvio `crashed`
+ stato "core c a v": la GUI marca v instabile e chiede se continuare da v+5. Fine: CO salvato
in Quiet/Auto/Boost.

## File (in `~/Documenti/Progetti/Personali/Ryzen Control/`)

- `ryzenctl` — helper/CLI root + selftest
- `ryzen-control` — GUI GTK4/libadwaita
- `Makefile` — install/uninstall/dkms (DESTDIR/PREFIX/APPID)
- `data/` — unit systemd, modprobe.d, policy polkit, .desktop, icona SVG, metainfo, autostart
- `ryzen_smu/` — driver vendorizzato (subtree d298366 + patch PM table 0x6211xx)
- `packaging/ryzen-control.spec`, `packaging/debian/`, `packaging/PKGBUILD`
- `README.md` — installazione per distro, Secure Boot (MOK dkms o drop-in akmods), ventole,
  avvertenze
- `CLAUDE.md` — da allineare a questa revisione all'inizio dell'implementazione (ordine fasi,
  blacklist modulo, ordine marker, FMax +200 con sblocco, ruoli ventola)

## Git e flusso di lavoro

- Repo git personale in `~/Documenti/Progetti/Personali/Ryzen Control` (`git init`, branch
  `main`, nessun remote finché non lo indichi tu). Driver upstream con `git subtree add
  --prefix ryzen_smu https://github.com/amkillam/ryzen_smu d298366 --squash`.
- Un commit per passo **solo dopo la sua verifica**: le verifiche eseguibili senza root
  (selftest, compilazione driver, `make install DESTDIR`, `rpmbuild`, `systemd-analyze
  verify`, `desktop-file-validate`, GUI in `--mock`) le faccio io prima del commit; quelle su
  hardware/root le esegui tu (`! comando` nel prompt) e committo dopo il tuo esito. Verifica
  fallita → si corregge, niente commit.
- Messaggi in prosa italiana, prefisso convenzionale (`feat/fix/build/docs/chore/test`), con
  riga `Co-Authored-By` richiesta dall'ambiente. Tag `v0.1.0`, `v0.2.0`… a fine di ogni fase
  verificata su hardware; la versione del tag è quella della spec RPM.

## Fasi e commit (ogni fase verificata su hardware prima della successiva)

### Fase 1 — fondamenta e pacchetto RPM → tag `v0.1.0`
| # | Commit | Verifica prima del commit |
|---|---|---|
| 1 | `chore: init repo, plan, README stub` | — |
| 2 | `build: vendor ryzen_smu d298366 (subtree)` + `fix(driver): PM table 0x6211xx sizes` | `make -C ryzen_smu` compila con gli header del kernel 7.2.8 |
| 3 | `feat(ryzenctl): SMU transport, lock, status` | `ryzenctl selftest` (backend finto) |
| 4 | `feat(ryzenctl): co/ppt/tdc/edc/fmax/tjmax/shaper + validazione, readback, sblocco` | selftest: codifiche, range, tetti, ripristino su readback fallito |
| 5 | `feat(ryzenctl): profili, baseline, boot/shutdown, crash-guard, serve` | selftest: tutti gli scenari della macchina a stati |
| 6 | `build: Makefile, unit systemd, modprobe.d, policy polkit, desktop, metainfo, icona` | `make install DESTDIR=/tmp/x` = layout atteso; `systemd-analyze verify`; `desktop-file-validate`; `appstreamcli validate` se presente |
| 7 | `build(rpm): spec ryzen-control + ryzen-smu-dkms` | `rpmbuild -ba` pulito |
| 8 | `docs: installazione Fedora, Secure Boot, verifica hardware` | **tu**: `dnf install`, `mokutil --import`, riavvio, `dkms status`, `lsmod` senza servizio = modulo non caricato, `ryzenctl status`, scritture reversibili, test crash (Verifica 2-5) |

### Fase 2 — ventole (CLI) → `v0.2.0`
| # | Commit | Verifica |
|---|---|---|
| 9 | `feat(ryzenctl): fan status/autodetect/identify/role/step/curve/enable` | selftest su hwmon finto (classificatore con serie Tctl/RPM sintetiche, abort); **tu**: `modprobe nct6775` + `dmesg`, parametro kernel, `sensors`, `fan autodetect` individua la pompa |
| 10 | `feat(ryzenctl): parte fan nel profilo e nel boot` | **tu**: Verifica 7 (step up 10 s: un picco di 2 s non alza gli RPM; pompa invariata) |

### Fase 3 — GUI → `v0.3.0`
| # | Commit | Verifica |
|---|---|---|
| 11 | `feat(gui): scheletro Adw, client pkexec/serve, --mock` | avvio in `--mock`, un solo prompt pkexec su hardware |
| 12 | `feat(gui): pagina Monitor` | valori coerenti con `sensors`/`ryzenctl status` |
| 13 | `feat(gui): pagine CPU, Curve, Ventole` | Applica/Salva → `ryzenctl status` e file profilo cambiano |
| 14 | `feat(gui): pagina Modalità (Default/Auto/Boost/Custom, sblocco, banner crash)` | **tu**: banner dopo test crash, Riattiva/Resta |

### Fase 4 — calibrazioni → `v0.4.0`
| # | Commit | Verifica |
|---|---|---|
| 15 | `feat: calibrazione Quiet` | **tu**: Verifica 8 (p95 sotto target) |
| 16 | `feat: calibrazione Auto (sweep PPT/FMax, RAPL)` | **tu**: tabella monotona, scelta ≤ slider |
| 17 | `feat: auto-tuning CO con ripresa dopo crash` | **tu**: prova su 1 core con passi da 1 min |

### Fase 5 — altre distro → `v0.5.0`
| # | Commit | Verifica |
|---|---|---|
| 18 | `build(deb): packaging/debian` | `dpkg-buildpackage` se disponibile, altrimenti marcato non testato |
| 19 | `build(arch): PKGBUILD` | `namcap` se disponibile, altrimenti marcato non testato |

### Fase 6 — icona nel vassoio di sistema (in basso a destra, stile Telegram) → `v0.6.0`
Richiesta utente (rev. 6). Icona `StatusNotifierItem` (protocollo nativo di KDE Plasma, su
GNOME serve l'estensione AppIndicator) con menu `com.canonical.dbusmenu`, implementati
direttamente su D-Bus con `Gio` di PyGObject: nessuna dipendenza nuova, funziona su Wayland
(GTK4 non ha più la StatusIcon). È lo stesso processo `ryzen-control` avviato con `--tray`
dall'autostart al login (finestra nascosta, un solo processo: l'autostart `ryzenctl-notify`
viene assorbito, il banner crash diventa voce del menu).
- Menu rapido: modalità **Default / Quiet / Auto / Boost** (spunta su quella attiva),
  **Applica all'avvio** on/off, **Apri Ryzen Control**, **Esci**; dopo un crash in testa la voce
  "Profilo disattivato dopo un crash: Riattiva / Resta su Default".
- Tooltip e icona di stato: Tctl e PPT attuali aggiornati ogni 2 s (icona normale /
  attenzione se Tctl > target Quiet); nessun polling SMU senza `serve` attivo: finché non
  si fa un'azione privilegiata si legge solo k10temp.
- Prima azione privilegiata della sessione → un solo prompt pkexec (come la GUI).
| # | Commit | Verifica |
|---|---|---|
| 20 | `feat(tray): StatusNotifierItem + dbusmenu via Gio, --tray, autostart` | `--mock --tray`: icona in Plasma, menu, spunta modalità; **tu**: cambio modalità dal menu → `ryzenctl status` cambia; prompt pkexec una sola volta |

## Verifica

1. `python3 ryzenctl selftest` (senza hardware): codifiche CO/Shaper, validazione e tetti,
   parse profili, baseline/Default, readback fallito → ripristino, macchina a stati del
   crash-guard (tutti gli scenari elencati), ordine marker (dirty e active prima della
   scrittura SMU finta).
2. Pacchetti: `rpmbuild -ba packaging/ryzen-control.spec` pulito; `sudo dnf install` dei due
   RPM → `dkms status` = `ryzen_smu/<ver>, <kernel>: installed`; `modinfo -F signer` = chiave
   dkms (o akmods con drop-in); dopo `mokutil --import` + riavvio: `lsmod | grep ryzen_smu`
   vuoto finché il servizio non parte (blacklist), `systemctl start ryzenctl` → modulo
   caricato, `/sys/kernel/ryzen_smu_drv/codename` = 23; `dnf remove` rimuove tutto.
3. `sudo ryzenctl status` = valori BIOS (CO, FMax ~5200, PPT/TDC/EDC 162/120/180 o PBO scheda).
4. Scritture minime reversibili con readback: `co 7 -3`→`co 7 0`; `ppt 150`→baseline;
   `fmax 5000` (sotto carico ≤5000 MHz)→baseline; `tjmax 85`→baseline; `shaper 4 -2 -2 -2`→0.
5. Crash-guard: profilo innocuo (es. `ppt 150`) con autostart; `sync; echo b >
   /proc/sysrq-trigger` → al boot `crashed` presente, `ryzenctl status` = baseline, notifica
   al login; `systemctl restart ryzenctl` → baseline invariata; riavvio pulito → apply
   normale; suspend/resume → status = profilo; boot con `ryzenctl.off` → modulo non caricato,
   nulla applicato; kernel update → `dkms.service` ricompila, servizio parte dopo.
6. GUI: avvio da menu (voce in Discover grazie al metainfo), un solo prompt pkexec, monitor
   aggiornato, Applica/Salva funzionano, banner crash con Riattiva/Resta.
7. Ventole: `sensors` mostra nct67xx; `fan autodetect` classifica la pompa come "pompa"
   (ΔT riportato) e le ventole del radiatore come "ventola"; `fan role N ventola` non esiste;
   canale pompa rifiutato in scrittura; step up 10 s → un picco di carico di 2 s non alza gli
   RPM; pompa a RPM invariati per tutta la prova.
8. Calibrazione: Quiet riduce p95 picchi Tctl sotto target; Auto produce una tabella
   monotona (W ↓ ⇒ ops/s ↓) e sceglie PPT/FMax con perdita ≤ slider, ops/W del punto scelto
   > ops/W di Boost; auto-tuning su 1 core con passi da 1 min per prova rapida.
