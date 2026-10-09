Name:           ryzen-control
Version:        0.1.0
Release:        3%{?dist}
Summary:        Curve Optimizer, limiti PBO, boost e ventole per Ryzen 9000 (Granite Ridge)
License:        GPL-3.0-or-later
Source0:        %{name}-%{version}.tar.gz
BuildArch:      noarch

BuildRequires:  make
BuildRequires:  systemd-rpm-macros
Requires:       python3 >= 3.9
Requires:       polkit
Requires:       systemd
Requires:       ryzen-smu-dkms = %{version}-%{release}
Recommends:     stress-ng
Recommends:     libnotify
%{?systemd_requires}

%description
Controllo stile Ryzen Master per AMD Ryzen 9000 (Granite Ridge) su Linux:
Curve Optimizer e Curve Shaper per core, limiti PPT/TDC/EDC, frequenza di
boost e temperatura massima, profilo energetico e ventole della scheda madre.
Profili applicati all'avvio con protezione dopo un crash: il profilo non
viene riapplicato finché non lo decide l'utente. Questo pacchetto contiene
l'helper privilegiato ryzenctl (CLI) e i servizi systemd.

%package -n ryzen-smu-dkms
Summary:        Driver ryzen_smu (accesso SMU dei Ryzen) in forma DKMS
License:        GPL-2.0-only
BuildArch:      noarch
Requires:       dkms
Requires:       kernel-devel
Requires:       gcc
Requires:       make
Requires(post): dkms
Requires(preun): dkms

%description -n ryzen-smu-dkms
Sorgente del modulo kernel ryzen_smu (amkillam/ryzen_smu, con dimensioni
PM table aggiuntive per Granite Ridge) compilato da DKMS per ogni kernel
installato. Con Secure Boot attivo il modulo viene firmato con la chiave
akmods se e' gia' registrata in MOK, altrimenti con la chiave DKMS, da
registrare una volta: mokutil --import /var/lib/dkms/mok.pub

%prep
%autosetup

%build
# Nessuna compilazione: script Python; il driver lo compila DKMS sul sistema.

%install
make install-cli install-dkms-src DESTDIR=%{buildroot} PREFIX=%{_prefix}
# Creato dal %%post solo quando la chiave akmods e' registrata; qui solo per tracciarlo (%%ghost).
install -dm755 %{buildroot}%{_sysconfdir}/dkms/framework.conf.d
touch %{buildroot}%{_sysconfdir}/dkms/framework.conf.d/ryzen-smu-akmods.conf

%post
%systemd_post ryzenctl.service ryzenctl-resume.service
# Avvio subito: carica il modulo e cattura la baseline. Non applica alcun profilo.
if [ -d /run/systemd/system ]; then
    systemctl start ryzenctl.service >/dev/null 2>&1 || :
fi

%preun
%systemd_preun ryzenctl.service ryzenctl-resume.service

%postun
%systemd_postun ryzenctl.service ryzenctl-resume.service

%post -n ryzen-smu-dkms
# Secure Boot senza passi manuali: se la chiave akmods (NVIDIA ecc.) esiste ed e' gia'
# registrata in MOK, DKMS firma con quella. Il drop-in vale per ogni modulo DKMS del sistema.
AKMODS_KEY=/etc/pki/akmods/private/private_key.priv
AKMODS_CERT=/etc/pki/akmods/certs/public_key.der
DROPIN=%{_sysconfdir}/dkms/framework.conf.d/ryzen-smu-akmods.conf
if [ ! -s "$DROPIN" ] && [ -f "$AKMODS_KEY" ] && [ -f "$AKMODS_CERT" ] \
   && mokutil --test-key "$AKMODS_CERT" 2>/dev/null | grep -q 'already enrolled'; then
    printf 'mok_signing_key=%%s\nmok_certificate=%%s\n' "$AKMODS_KEY" "$AKMODS_CERT" > "$DROPIN"
fi
dkms add -m ryzen_smu -v %{version} -q --rpm_safe_upgrade || :
dkms build -m ryzen_smu -v %{version} -q --force || :
dkms install -m ryzen_smu -v %{version} -q --force || :
if [ ! -s "$DROPIN" ] && grep -qE '\[(integrity|confidentiality)\]' /sys/kernel/security/lockdown 2>/dev/null \
   && ! mokutil --test-key /var/lib/dkms/mok.pub 2>/dev/null | grep -q 'already enrolled'; then
    echo "ryzen-smu-dkms: Secure Boot attivo e chiave DKMS non registrata. Una volta sola:"
    echo "  sudo mokutil --import /var/lib/dkms/mok.pub   (poi riavvio, MOK Manager -> Enroll MOK)"
    echo "Fino ad allora il modulo ryzen_smu non puo' essere caricato."
fi

%preun -n ryzen-smu-dkms
dkms remove -m ryzen_smu -v %{version} -q --all --rpm_safe_upgrade || :

%files
%license LICENSE
%doc README.md
%{_bindir}/ryzenctl
%{_unitdir}/ryzenctl.service
%{_unitdir}/ryzenctl-resume.service
%{_presetdir}/80-ryzen-control.preset
%{_modprobedir}/ryzen-control.conf
%{_datadir}/polkit-1/actions/org.ryzencontrol.RyzenControl.policy
%config(noreplace) %{_sysconfdir}/xdg/autostart/ryzenctl-notify.desktop
%dir %{_sysconfdir}/ryzenctl
%dir %{_sysconfdir}/ryzenctl/profiles
%dir %{_sharedstatedir}/ryzenctl

%files -n ryzen-smu-dkms
%license ryzen_smu/LICENSE
%doc ryzen_smu/README.md ryzen_smu/UPSTREAM.md
%{_usrsrc}/ryzen_smu-%{version}/
%ghost %config(noreplace) %{_sysconfdir}/dkms/framework.conf.d/ryzen-smu-akmods.conf

%changelog
* Fri Oct 09 2026 senseikiritof <tonifede98@gmail.com> - 0.1.0-3
- Readback dei limiti con attesa (la PM table si aggiorna col passo dell'SMU), Curve Shaper
  sperimentale fuori da profili e hwtest, nessuna eccezione non gestita (ABRT)

* Fri Oct 09 2026 senseikiritof <tonifede98@gmail.com> - 0.1.0-2
- Firma automatica con la chiave akmods se registrata, rebuild forzato, avvio del servizio
  all'installazione, comando hwtest

* Fri Oct 09 2026 senseikiritof <tonifede98@gmail.com> - 0.1.0-1
- Prima versione: ryzenctl, servizi systemd, driver ryzen_smu via DKMS
