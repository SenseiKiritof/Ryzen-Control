Name:           ryzen-control
Version:        0.1.0
Release:        8%{?dist}
Summary:        Curve Optimizer, limiti PBO, boost e ventole per Ryzen 9000 (Granite Ridge)
# App GPL-3.0-or-later; driver ryzen_smu incluso (ryzen_smu/) GPL-2.0-only.
License:        GPL-3.0-or-later AND GPL-2.0-only
Source0:        %{name}-%{version}.tar.gz
BuildArch:      noarch

BuildRequires:  make
BuildRequires:  systemd-rpm-macros
Requires:       python3 >= 3.9
Requires:       polkit
Requires:       systemd
Requires:       dkms
Requires:       kernel-devel
Requires:       gcc
Requires:       make
Requires(post): dkms
Requires(preun): dkms
Recommends:     stress-ng
Recommends:     libnotify
# Fino alla 0.1.0-4 il driver era un sottopacchetto separato.
Obsoletes:      ryzen-smu-dkms < 0.1.0-5
Provides:       ryzen-smu-dkms = %{version}-%{release}
%{?systemd_requires}

%description
Controllo stile Ryzen Master per AMD Ryzen 9000 (Granite Ridge) su Linux:
Curve Optimizer e Curve Shaper per core, limiti PPT/TDC/EDC, frequenza di
boost e temperatura massima, profilo energetico e ventole della scheda madre.
Profili applicati all'avvio con protezione dopo un crash: il profilo non
viene riapplicato finché non lo decide l'utente.

Un solo pacchetto: l'helper privilegiato ryzenctl (CLI), i servizi systemd e
il sorgente del modulo kernel ryzen_smu (amkillam/ryzen_smu, con dimensioni
PM table aggiuntive per Granite Ridge), compilato da DKMS per ogni kernel
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
# 1. Driver. Secure Boot senza passi manuali: se la chiave akmods (NVIDIA ecc.) esiste ed e'
#    gia' registrata in MOK, DKMS firma con quella. Il drop-in vale per ogni modulo DKMS.
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
    echo "ryzen-control: Secure Boot attivo e chiave DKMS non registrata. Una volta sola:"
    echo "  sudo mokutil --import /var/lib/dkms/mok.pub   (poi riavvio, MOK Manager -> Enroll MOK)"
    echo "Fino ad allora il modulo ryzen_smu non puo' essere caricato."
fi
# 2. Servizi: preset li abilita; avvio subito (carica il modulo, cattura la baseline, nessun
#    profilo applicato).
%systemd_post ryzenctl.service ryzenctl-resume.service
if [ -d /run/systemd/system ]; then
    systemctl start ryzenctl.service >/dev/null 2>&1 || :
fi

%preun
%systemd_preun ryzenctl.service ryzenctl-resume.service
dkms remove -m ryzen_smu -v %{version} -q --all --rpm_safe_upgrade || :

%postun
%systemd_postun ryzenctl.service ryzenctl-resume.service

%files
%license LICENSE ryzen_smu/LICENSE
%doc README.md ryzen_smu/UPSTREAM.md
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
%{_usrsrc}/ryzen_smu-%{version}/
%ghost %config(noreplace) %{_sysconfdir}/dkms/framework.conf.d/ryzen-smu-akmods.conf

%changelog
* Fri Oct 09 2026 senseikiritof <tonifede98@gmail.com> - 0.1.0-8
- Curve ventole: pwm minimo 51 (20 %%) come le curve BIOS

* Fri Oct 09 2026 senseikiritof <tonifede98@gmail.com> - 0.1.0-7
- Autodetect ventole con pwm di prova relativo al valore attuale; curve con ultimo punto fino a 125 °C

* Fri Oct 09 2026 senseikiritof <tonifede98@gmail.com> - 0.1.0-6
- Ventole: fan status/enable/autodetect/step/curve/identify/role/name, righe fan nei profili

* Fri Oct 09 2026 senseikiritof <tonifede98@gmail.com> - 0.1.0-5
- Un solo pacchetto: il driver DKMS entra in ryzen-control (obsoleta ryzen-smu-dkms)

* Fri Oct 09 2026 senseikiritof <tonifede98@gmail.com> - 0.1.0-4
- La baseline di una versione precedente con righe shaper viene applicata ignorandole;
  sonda shaper con 0x84 per tier

* Fri Oct 09 2026 senseikiritof <tonifede98@gmail.com> - 0.1.0-3
- Readback dei limiti con attesa (la PM table si aggiorna col passo dell'SMU), Curve Shaper
  sperimentale fuori da profili e hwtest, nessuna eccezione non gestita (ABRT)

* Fri Oct 09 2026 senseikiritof <tonifede98@gmail.com> - 0.1.0-2
- Firma automatica con la chiave akmods se registrata, rebuild forzato, avvio del servizio
  all'installazione, comando hwtest

* Fri Oct 09 2026 senseikiritof <tonifede98@gmail.com> - 0.1.0-1
- Prima versione: ryzenctl, servizi systemd, driver ryzen_smu via DKMS
