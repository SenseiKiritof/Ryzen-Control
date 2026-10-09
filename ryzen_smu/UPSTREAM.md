# Driver ryzen_smu — copia vendorizzata

- Origine: https://github.com/amkillam/ryzen_smu
- Commit: d2983668300dd2a598e5a7dc40e71ce0678cc270 (2026-08-15, "Fix cpuid include on 7.2+ kernels")
- File copiati: `drv.c`, `smu.c`, `smu.h`, `Makefile`, `dkms.conf`, `LICENSE`, `README.md`,
  `docs/rsmu_commands.md`. Esclusi: `lib/`, `userspace/`, `scripts/`, `pics/` (non servono al modulo).

## Modifiche locali

Nessuna (copia identica a monte).

## Aggiornamento

```sh
git clone https://github.com/amkillam/ryzen_smu /tmp/ryzen_smu && cd /tmp/ryzen_smu && git checkout <nuovo-commit>
diff -ru --exclude=UPSTREAM.md "<repo>/ryzen_smu" /tmp/ryzen_smu   # rivedere, poi ricopiare e riapplicare le modifiche locali
```

Nota: kbuild non accetta spazi nel percorso, quindi `make -C ryzen_smu` fallisce dentro questo
repo. Per compilare usare `make driver-check` (copia in una directory temporanea).
