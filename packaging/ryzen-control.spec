Name:           ryzen-control
Version:        0.1.0
Release:        1%{?dist}
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
installato. Con Secure Boot attivo va registrata una volta la chiave DKMS:
mokutil --import /var/lib/dkms/mok.pub

%prep
%autosetup

%build
# Nessuna compilazione: script Python; il driver lo compila DKMS sul sistema.

%install
make install-cli install-dkms-src DESTDIR=%{buildroot} PREFIX=%{_prefix}

%post
%systemd_post ryzenctl.service ryzenctl-resume.service

%preun
%systemd_preun ryzenctl.service ryzenctl-resume.service

%postun
%systemd_postun ryzenctl.service ryzenctl-resume.service

%post -n ryzen-smu-dkms
dkms add -m ryzen_smu -v %{version} -q --rpm_safe_upgrade || :
dkms build -m ryzen_smu -v %{version} -q || :
dkms install -m ryzen_smu -v %{version} -q || :
if grep -qE '\[(integrity|confidentiality)\]' /sys/kernel/security/lockdown 2>/dev/null; then
    echo "ryzen-smu-dkms: Secure Boot attivo. Se non e' gia' registrata, importare la chiave DKMS"
    echo "  sudo mokutil --import /var/lib/dkms/mok.pub"
    echo "poi riavviare e confermare in MOK Manager; altrimenti il modulo ryzen_smu non si carica."
fi

%preun -n ryzen-smu-dkms
dkms remove -m ryzen_smu -v %{version} -q --all --rpm_safe_upgrade || :

%files
%license LICENSE
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

%changelog
* Fri Oct 09 2026 senseikiritof <tonifede98@gmail.com> - 0.1.0-1
- Prima versione: ryzenctl, servizi systemd, driver ryzen_smu via DKMS
