# Ryzen Control — unica fonte del layout installato. I pacchetti (RPM, deb, Arch) chiamano
# `make install DESTDIR=…`; `install-cli` / `install-gui` / `install-dkms-src` sono i pezzi.
VERSION := 0.4.1
APPID := org.ryzencontrol.RyzenControl
PREFIX ?= /usr
DESTDIR ?=

BIN := $(DESTDIR)$(PREFIX)/bin
UNITDIR := $(DESTDIR)$(PREFIX)/lib/systemd/system
PRESETDIR := $(DESTDIR)$(PREFIX)/lib/systemd/system-preset
MODPROBEDIR := $(DESTDIR)$(PREFIX)/lib/modprobe.d
POLKITDIR := $(DESTDIR)$(PREFIX)/share/polkit-1/actions
APPDIR := $(DESTDIR)$(PREFIX)/share/applications
ICONDIR := $(DESTDIR)$(PREFIX)/share/icons/hicolor/scalable/apps
METADIR := $(DESTDIR)$(PREFIX)/share/metainfo
AUTOSTARTDIR := $(DESTDIR)/etc/xdg/autostart
ETCDIR := $(DESTDIR)/etc/ryzenctl
STATEDIR := $(DESTDIR)/var/lib/ryzenctl
DKMS_SRC := $(DESTDIR)$(PREFIX)/src/ryzen_smu-$(VERSION)
TMPROOT := $(or $(TMPDIR),/tmp)/ryzen-control-check

.PHONY: all install install-cli install-gui install-dkms-src dkms uninstall check driver-check dist rpm

all:
	@echo "Target: install [DESTDIR=…] (install-cli install-gui install-dkms-src), dkms, uninstall, check, driver-check, dist, rpm"

install: install-cli $(if $(wildcard ryzen-control),install-gui) install-dkms-src

install-cli:
	install -Dm755 ryzenctl $(BIN)/ryzenctl
	install -Dm644 -t $(UNITDIR) data/ryzenctl.service data/ryzenctl-resume.service
	install -Dm644 -t $(PRESETDIR) data/80-ryzen-control.preset
	install -Dm644 data/ryzen-control.modprobe.conf $(MODPROBEDIR)/ryzen-control.conf
	install -Dm644 -t $(POLKITDIR) data/$(APPID).policy
	install -Dm644 -t $(AUTOSTARTDIR) data/ryzenctl-notify.desktop
	install -dm755 $(ETCDIR)/profiles $(STATEDIR)

install-gui:
	install -Dm755 ryzen-control $(BIN)/ryzen-control
	install -Dm644 -t $(APPDIR) data/$(APPID).desktop
	install -Dm644 -t $(ICONDIR) data/$(APPID).svg
	install -Dm644 -t $(METADIR) data/$(APPID).metainfo.xml

# Sorgente del driver per DKMS (il pacchetto -dkms non contiene binari).
install-dkms-src:
	install -dm755 $(DKMS_SRC)
	install -m644 -t $(DKMS_SRC) ryzen_smu/drv.c ryzen_smu/smu.c ryzen_smu/smu.h ryzen_smu/Makefile
	sed -e 's/@VERSION@/$(VERSION)/' -e 's/@CFLGS@//' ryzen_smu/dkms.conf > $(DKMS_SRC)/dkms.conf

# Ultima spiaggia senza pacchetto: `sudo make install && sudo make dkms`.
dkms:
	dkms add ryzen_smu/$(VERSION) || true
	dkms build ryzen_smu/$(VERSION) && dkms install ryzen_smu/$(VERSION)

uninstall:
	-dkms remove ryzen_smu/$(VERSION) --all
	rm -rf $(DKMS_SRC)
	rm -f $(BIN)/ryzenctl $(BIN)/ryzen-control
	rm -f $(UNITDIR)/ryzenctl.service $(UNITDIR)/ryzenctl-resume.service $(PRESETDIR)/80-ryzen-control.preset
	rm -f $(MODPROBEDIR)/ryzen-control.conf $(POLKITDIR)/$(APPID).policy $(AUTOSTARTDIR)/ryzenctl-notify.desktop
	rm -f $(APPDIR)/$(APPID).desktop $(ICONDIR)/$(APPID).svg $(METADIR)/$(APPID).metainfo.xml

# Verifiche senza root né hardware: selftest, layout in una radice temporanea, unit, desktop, metainfo.
check:
	python3 ryzenctl selftest
	rm -rf "$(TMPROOT)" && $(MAKE) install DESTDIR="$(TMPROOT)" >/dev/null
	cd "$(TMPROOT)" && find . -type f | sort
	systemd-analyze --root="$(TMPROOT)" verify --recursive-errors=no ryzenctl.service ryzenctl-resume.service
	desktop-file-validate data/ryzenctl-notify.desktop data/$(APPID).desktop
	-appstreamcli validate --no-net data/$(APPID).metainfo.xml
	timeout 120 python3 ryzen-control --mock --smoke   # finestra di calibrazione su ogni stato del backend finto (serve un display)

# Tarball dal commit corrente (HEAD): i pacchetti si costruiscono da ciò che è versionato.
dist:
	mkdir -p dist
	git archive --format=tar.gz --prefix=ryzen-control-$(VERSION)/ -o dist/ryzen-control-$(VERSION).tar.gz HEAD

# RPM nell'albero standard ~/rpmbuild (niente spazi nei percorsi); risultato copiato in dist/.
rpm: dist
	rpmdev-setuptree
	cp dist/ryzen-control-$(VERSION).tar.gz "$$HOME/rpmbuild/SOURCES/"
	rpmbuild -ba packaging/ryzen-control.spec
	cp "$$HOME"/rpmbuild/RPMS/noarch/ryzen-control-$(VERSION)-*.rpm dist/
	ls -1 dist/

# kbuild non accetta spazi nel percorso: compila una copia del driver fuori dal repo.
driver-check:
	rm -rf "$(TMPROOT)-driver" && cp -r ryzen_smu "$(TMPROOT)-driver"
	$(MAKE) -C "$(TMPROOT)-driver" && modinfo -F vermagic "$(TMPROOT)-driver/ryzen_smu.ko"
