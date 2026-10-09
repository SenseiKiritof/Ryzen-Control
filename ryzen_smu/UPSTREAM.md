# Driver ryzen_smu — copia vendorizzata

- Origine: https://github.com/amkillam/ryzen_smu
- Commit: d2983668300dd2a598e5a7dc40e71ce0678cc270 (2026-08-15, "Fix cpuid include on 7.2+ kernels")
- File copiati: `drv.c`, `smu.c`, `smu.h`, `Makefile`, `dkms.conf`, `LICENSE`, `README.md`,
  `docs/rsmu_commands.md`. Esclusi: `lib/`, `userspace/`, `scripts/`, `pics/` (non servono al modulo).

## Modifiche locali

- `smu.c`, `smu_update_pmtable_size()`, blocco `CODENAME_GRANITERIDGE`: aggiunte le versioni
  PM table 0x621101/0x621102 (0x724 byte) e 0x621201/0x621202 (0x994 byte) degli AGESA più
  recenti, dimensioni da ZenStates-Core `Hardware/PowerTable.cs`. Senza, il driver carica ma
  disabilita `pm_table` su quei firmware.

## Aggiornamento

```sh
git clone https://github.com/amkillam/ryzen_smu /tmp/ryzen_smu && cd /tmp/ryzen_smu && git checkout <nuovo-commit>
diff -ru --exclude=UPSTREAM.md "<repo>/ryzen_smu" /tmp/ryzen_smu   # rivedere, poi ricopiare e riapplicare le modifiche locali
```

Nota: kbuild non accetta spazi nel percorso, quindi `make -C ryzen_smu` fallisce dentro questo
repo. Per compilare usare `make driver-check` (copia in una directory temporanea).
