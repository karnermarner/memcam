#!/usr/bin/env bash
#
# setup.sh - MemCam kornyezet beuzemelese Linuxon.
#
# Barmikor ujrafuttathato. Minden lepes eloszor megnezi, hogy kesz van-e,
# es csak akkor csinal barmit, ha kell. Kernelfrissites utan pont ezert
# hasznos: a v4l2loopback modult ujra kell forditani es alairni, a tobbit
# viszont bekeni hagyja.
#
#   ./setup.sh              teljes beuzemeles
#   ./setup.sh --check      csak allapotjelentes, semmit nem valtoztat
#   ./setup.sh --no-phone   scrcpy lepes kihagyasa (ha van igazi webkamerad)
#
# Amit NEM csinal a hatad mogott: nem kapcsol ki Secure Bootot, nem tolt
# le semmit a rendszerbe kerdes nelkul, es nem indit ujra. Ahol reboot
# kell, ott megall es szol.

set -euo pipefail

# ─────────────────────────────────────────────────────────── beallitasok

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="$PROJECT_DIR/.venv"

V4L2_SRC="$HOME/v4l2loopback"
SCRCPY_SRC="$HOME/scrcpy"

MOK_KEY="/root/MOK.priv"
MOK_CERT="/root/MOK.der"

# Ket loopback eszkoz: a PhoneCam-be ir a scrcpy, a MemCam-bol olvas a
# hivoprogram. Tombkent, nem stringkent: stringbol az idezojelek szo
# szerint atmennenek a modprobe-nak, es a cimke literalisan "MemCam"
# lenne, idezojelekkel egyutt. Szokoz nincs a nevekben, igy nem is kell.
# shellcheck disable=SC2054  # a vesszok a modprobe ertekein belul vannak
LOOPBACK_OPTS=(
  devices=2
  video_nr=10,11
  card_label=MemCam,PhoneCam
  exclusive_caps=1,1
)

PIP_PACKAGES=(
  opencv-python mediapipe pyvirtualcam numpy pillow scikit-learn joblib
)

APT_BUILD_DEPS=(
  build-essential git "linux-headers-$(uname -r)" mokutil openssl
  v4l-utils libgl1 libglib2.0-0
)

APT_SCRCPY_DEPS=(
  ffmpeg libsdl2-2.0-0 libsdl2-dev adb wget pkg-config meson ninja-build
  libavcodec-dev libavdevice-dev libavformat-dev libavutil-dev
  libswresample-dev libusb-1.0-0 libusb-1.0-0-dev
)

CHECK_ONLY=0
SKIP_PHONE=0

# ────────────────────────────────────────────────────────────── kimenet

if [[ -t 1 ]]; then
  C_OK=$'\033[32m'; C_WARN=$'\033[33m'; C_ERR=$'\033[31m'
  C_DIM=$'\033[2m'; C_BOLD=$'\033[1m'; C_OFF=$'\033[0m'
else
  C_OK=""; C_WARN=""; C_ERR=""; C_DIM=""; C_BOLD=""; C_OFF=""
fi

step()  { printf '\n%s▸ %s%s\n' "$C_BOLD" "$1" "$C_OFF"; }
ok()    { printf '  %s✓%s %s\n' "$C_OK" "$C_OFF" "$1"; }
warn()  { printf '  %s!%s %s\n' "$C_WARN" "$C_OFF" "$1"; }
fail()  { printf '  %s✗%s %s\n' "$C_ERR" "$C_OFF" "$1"; }
info()  { printf '  %s%s%s\n' "$C_DIM" "$1" "$C_OFF"; }

die() { printf '\n%s✗ %s%s\n\n' "$C_ERR" "$1" "$C_OFF" >&2; exit 1; }

# Csak akkor csinal valamit, ha nem --check modban vagyunk.
would() {
  if (( CHECK_ONLY )); then
    info "[--check] kimarad: $*"
    return 1
  fi
  return 0
}

ask() {
  (( CHECK_ONLY )) && return 1
  local reply
  read -rp "  $1 [i/N] " reply
  [[ "$reply" =~ ^[iyIY]$ ]]
}

# ───────────────────────────────────────────────────────── argumentumok

for arg in "$@"; do
  case "$arg" in
    --check)     CHECK_ONLY=1 ;;
    --no-phone)  SKIP_PHONE=1 ;;
    -h|--help)   sed -n '3,17p' "${BASH_SOURCE[0]}" | sed 's/^# \?//'; exit 0 ;;
    *)           die "ismeretlen kapcsolo: $arg" ;;
  esac
done

(( CHECK_ONLY )) && printf '%s--check mod: semmit nem valtoztatok%s\n' "$C_DIM" "$C_OFF"

# ══════════════════════════════════════════════════════ 1. rendszercsomagok

step "Rendszercsomagok"

missing_apt=()
for pkg in "${APT_BUILD_DEPS[@]}"; do
  dpkg -s "$pkg" &>/dev/null || missing_apt+=("$pkg")
done

if (( ${#missing_apt[@]} == 0 )); then
  ok "minden build-fuggoseg megvan"
else
  warn "hianyzik: ${missing_apt[*]}"
  if would "apt install"; then
    sudo apt update
    sudo apt install -y "${missing_apt[@]}"
    ok "telepitve"
  fi
fi

# ═════════════════════════════════════════════════════════ 2. python venv

step "Python kornyezet"

if [[ -x "$VENV_DIR/bin/python" ]]; then
  ok "venv megvan: $VENV_DIR"
else
  warn "nincs venv"
  if would "venv letrehozasa"; then
    python3 -m venv "$VENV_DIR"
    ok "letrehozva"
  fi
fi

if [[ -x "$VENV_DIR/bin/python" ]]; then
  pyver="$("$VENV_DIR/bin/python" -c 'import sys; print("%d.%d" % sys.version_info[:2])')"
  info "python $pyver"

  # a mediapipe 3.13-ra sokaig nem adott wheelt; ha nincs, ez a leggyakoribb ok
  if [[ "$pyver" == "3.13" ]]; then
    warn "python 3.13 - ha a mediapipe nem talalhato, ez az oka. Telepits 3.12-t melle."
  fi

  missing_pip=()
  for pkg in "${PIP_PACKAGES[@]}"; do
    modname="${pkg//-/_}"
    case "$pkg" in
      opencv-python) modname=cv2 ;;
      pillow)        modname=PIL ;;
      scikit-learn)  modname=sklearn ;;
    esac
    "$VENV_DIR/bin/python" -c "import $modname" &>/dev/null || missing_pip+=("$pkg")
  done

  if (( ${#missing_pip[@]} == 0 )); then
    ok "minden python csomag megvan"
  else
    warn "hianyzik: ${missing_pip[*]}"
    if would "pip install"; then
      "$VENV_DIR/bin/python" -m pip install --upgrade pip
      "$VENV_DIR/bin/python" -m pip install "${missing_pip[@]}"
      ok "telepitve"
    fi
  fi
fi

# ═══════════════════════════════════════════════ 3. MOK kulcs (Secure Boot)

step "Secure Boot / modulalairas"

SECURE_BOOT=0
if command -v mokutil &>/dev/null && mokutil --sb-state 2>/dev/null | grep -i enabled >/dev/null; then
  SECURE_BOOT=1
fi

MOK_READY=0
if (( SECURE_BOOT )); then
  info "Secure Boot bekapcsolva - a sajat forditasu modult ala kell irni"

  if ! sudo test -f "$MOK_CERT"; then
    warn "nincs MOK kulcs"
    if would "MOK kulcs generalasa"; then
      sudo openssl req -new -x509 -newkey rsa:2048 \
        -keyout "$MOK_KEY" -outform DER -out "$MOK_CERT" \
        -nodes -days 36500 -subj "/CN=$(hostname) local modules/"
      ok "kulcs letrehozva"
    fi
  else
    ok "MOK kulcs megvan"
  fi

  if sudo test -f "$MOK_CERT"; then
    if sudo mokutil --test-key "$MOK_CERT" 2>/dev/null | grep -i "already enrolled" >/dev/null; then
      ok "kulcs beiktatva"
      MOK_READY=1
    else
      warn "a kulcs NINCS beiktatva"
      if would "beiktatas kerelmezese"; then
        printf '\n  A kovetkezo lepes jelszot ker. Jegyezd meg: ujrainditaskor\n'
        printf '  ezt kell beirni a kek MOK Manager kepernyon.\n\n'
        sudo mokutil --import "$MOK_CERT"
        printf '\n%s  ══ UJRAINDITAS KELL ══%s\n' "$C_BOLD" "$C_OFF"
        printf '  Boot kozben a kek kepernyon:\n'
        printf '    Enroll MOK → Continue → Yes → jelszo → Reboot\n\n'
        printf '  Az a kepernyo par masodperc utan magatol tovabbmegy,\n'
        printf '  ezert szokott kimaradni. Utana futtasd ujra ezt a scriptet.\n\n'
        exit 0
      fi
    fi
  fi
else
  ok "Secure Boot nincs bekapcsolva - alairas nem kell"
  MOK_READY=1
fi

# ═══════════════════════════════════════════════════════ 4. v4l2loopback

step "v4l2loopback"

# /proc/modules-bol olvasunk grep-q-val: az egy FAJL, nincs mogotte elo
# folyamat, amit a korai lezaras SIGPIPE-elne. "lsmod | grep -q ..." lattato-
# lag ugyanezt csinalja, de set -o pipefail mellett idonkent hamisan hibazik:
# a grep -q az elso talalat utan azonnal bezarja a csovet, az lsmod ekkor
# SIGPIPE-ot kap es nemnulla kodal ter vissza, a pipefail pedig ezt hibanak
# szamitja - meg akkor is, ha a grep tenylegesen megtalalta, amit keresett.
module_loaded() { grep -q '^v4l2loopback ' /proc/modules; }
module_file() { modinfo -n v4l2loopback 2>/dev/null || true; }
module_signed() { modinfo v4l2loopback 2>/dev/null | grep '^signer:' >/dev/null; }

build_v4l2loopback() {
  if [[ ! -d "$V4L2_SRC/.git" ]]; then
    info "forras klonozasa -> $V4L2_SRC"
    git clone https://github.com/umlaeute/v4l2loopback.git "$V4L2_SRC"
  else
    info "forras frissitese"
    git -C "$V4L2_SRC" pull --ff-only || warn "pull nem ment, a meglevo forrast hasznalom"
  fi

  info "forditas"
  make -C "$V4L2_SRC" clean >/dev/null 2>&1 || true
  make -C "$V4L2_SRC"
  sudo make -C "$V4L2_SRC" install
  sudo depmod -a
}

sign_module() {
  local mod; mod="$(module_file)"
  [[ -n "$mod" ]] || die "nem talalom a lefordult modult"

  # tomoritett modult nem lehet alairni: a kernel eloszor kicsomagol, es
  # az alairasnak a tomorites ALATT kell lennie
  if [[ "$mod" == *.zst ]]; then
    info "kicsomagolas (alairni csak tomorites nelkul lehet)"
    sudo unzstd --rm "$mod"
    mod="${mod%.zst}"
  elif [[ "$mod" == *.xz ]]; then
    info "kicsomagolas"
    sudo unxz "$mod"
    mod="${mod%.xz}"
  fi

  info "alairas: $mod"
  sudo "/usr/src/linux-headers-$(uname -r)/scripts/sign-file" sha256 \
    "$MOK_KEY" "$MOK_CERT" "$mod"
  sudo depmod -a
}

needs_build=0
if [[ -z "$(module_file)" ]]; then
  warn "nincs v4l2loopback modul ehhez a kernelhez ($(uname -r))"
  needs_build=1
elif (( SECURE_BOOT )) && ! module_signed; then
  warn "a modul nincs alairva, Secure Boot mellett nem fog betoltodni"
else
  ok "modul megvan: $(module_file)"
fi

if (( needs_build )); then
  if would "v4l2loopback forditasa forrasbol"; then
    build_v4l2loopback
    ok "leforditva"
  fi
fi

if (( SECURE_BOOT )) && [[ -n "$(module_file)" ]] && ! module_signed; then
  if would "modul alairasa"; then
    sign_module
    module_signed && ok "alairva" || fail "az alairas nem lathato a modinfo-ban"
  fi
fi

# betoltes
if module_loaded; then
  ok "modul betoltve"
else
  warn "modul nincs betoltve"
  if would "modprobe"; then
    if (( MOK_READY )); then
      sudo modprobe v4l2loopback "${LOOPBACK_OPTS[@]}" && ok "betoltve" \
        || fail "a betoltes nem sikerult - lasd: dmesg | tail"
    else
      fail "elobb a MOK kulcsot kell beiktatni (reboot)"
    fi
  fi
fi

if command -v v4l2-ctl &>/dev/null && module_loaded; then
  # a "Cannot open device /dev/videoN" sor normalis, ha nincs fizikai kamera
  v4l2-ctl --list-devices 2>/dev/null | grep -E '^(MemCam|PhoneCam)' | while read -r line; do
    info "$line"
  done
fi

# ═════════════════════════════════════════════════════ 5. boot utani allapot

step "Boot utani betoltes"

MODULES_CONF="/etc/modules-load.d/v4l2loopback.conf"
OPTIONS_CONF="/etc/modprobe.d/v4l2loopback.conf"

if [[ -f "$MODULES_CONF" && -f "$OPTIONS_CONF" ]]; then
  ok "beallitva"
else
  warn "ujrainditas utan nem toltodne be magatol"
  if would "beallitas"; then
    echo v4l2loopback | sudo tee "$MODULES_CONF" >/dev/null
    echo "options v4l2loopback ${LOOPBACK_OPTS[*]}" | sudo tee "$OPTIONS_CONF" >/dev/null
    ok "beallitva"
  fi
fi

# ══════════════════════════════════════════════════════════════ 6. scrcpy

if (( SKIP_PHONE )); then
  step "scrcpy (kihagyva: --no-phone)"
else
  step "scrcpy (telefon webkamerakent)"

  scrcpy_version() {
    command -v scrcpy &>/dev/null || return 1
    scrcpy --version 2>/dev/null | head -1 | grep -oP '\d+\.\d+(\.\d+)?' | head -1
  }

  # a --video-source=camera a 2.2-tol letezik
  version_ok() {
    local v="$1"
    local major minor
    major="${v%%.*}"
    minor="$(cut -d. -f2 <<<"$v")"
    (( major > 2 )) || { (( major == 2 )) && (( minor >= 2 )); }
  }

  build_scrcpy() {
    info "build-fuggosegek"
    local missing=()
    for pkg in "${APT_SCRCPY_DEPS[@]}"; do
      dpkg -s "$pkg" &>/dev/null || missing+=("$pkg")
    done
    (( ${#missing[@]} )) && sudo apt install -y "${missing[@]}"

    if [[ ! -d "$SCRCPY_SRC/.git" ]]; then
      git clone https://github.com/Genymobile/scrcpy "$SCRCPY_SRC"
    fi
    git -C "$SCRCPY_SRC" fetch --tags --quiet

    # A 4.x mar SDL3-at var, ami az Ubuntu 24.04-ben nincs. A 3-as ag
    # SDL2-vel epul, es a kameraforrast mar tudja.
    local tag
    tag="$(git -C "$SCRCPY_SRC" tag -l 'v3*' | sort -V | tail -1)"
    [[ -n "$tag" ]] || die "nem talaltam v3 taget a scrcpy repoban"
    info "verzio: $tag (a 4.x SDL3-at igenyel, ami itt nincs)"

    git -C "$SCRCPY_SRC" checkout --quiet "$tag"
    rm -rf "$SCRCPY_SRC/build-auto"
    ( cd "$SCRCPY_SRC" && ./install_release.sh )
    hash -r
  }

  if ver="$(scrcpy_version)" && version_ok "$ver"; then
    ok "scrcpy $ver"
  elif [[ -n "${ver:-}" ]]; then
    warn "scrcpy $ver tul regi (a --video-source=camera a 2.2-tol van)"
    if would "forditas forrasbol" && ask "leforditsam?"; then
      build_scrcpy
      ok "scrcpy $(scrcpy_version)"
    fi
  else
    warn "nincs scrcpy"
    if would "forditas forrasbol" && ask "leforditsam?"; then
      build_scrcpy
      ok "scrcpy $(scrcpy_version)"
    fi
  fi

  if command -v adb &>/dev/null; then
    devices="$(adb devices 2>/dev/null | awk 'NR>1 && $2=="device" {print $1}')"
    if [[ -n "$devices" ]]; then
      ok "adb eszkoz: $devices"
    else
      info "nincs csatlakoztatott adb eszkoz (parositas: adb pair IP:PORT)"
    fi
  fi
fi

# ══════════════════════════════════════════════════════════════ 7. projekt

step "Projektfajlok"

for f in memcam.py gesture_features.py collect_gestures.py train_gestures.py; do
  [[ -f "$PROJECT_DIR/$f" ]] && ok "$f" || fail "$f hianyzik"
done

if [[ -f "$PROJECT_DIR/gesture_model.pkl" ]]; then
  ok "gesture_model.pkl (sajat gesztusok)"
else
  info "nincs gesture_model.pkl - csak a het beepitett gesztus menne"
fi

if [[ -d "$PROJECT_DIR/memes" ]]; then
  count="$(find "$PROJECT_DIR/memes" -maxdepth 1 -type f \
    \( -iname '*.png' -o -iname '*.jpg' -o -iname '*.jpeg' \
       -o -iname '*.gif' -o -iname '*.webp' \) | wc -l)"
  ok "memes/ ($count kep)"
else
  info "nincs memes/ mappa - szoveges plakatok lesznek"
fi

# ════════════════════════════════════════════════════════════════ osszegzes

printf '\n%s─────────────────────────────────────────────%s\n' "$C_DIM" "$C_OFF"

if (( CHECK_ONLY )); then
  printf '\nAllapotjelentes kesz. Valtoztatashoz futtasd kapcsolo nelkul.\n\n'
  exit 0
fi

cat <<EOF

Inditas:

  ${C_BOLD}telefon kamerakent${C_OFF} (kulon terminal, hagyd futni)
    scrcpy --video-source=camera --camera-facing=front \\
      --camera-size=1280x720 --no-audio --no-playback \\
      --v4l2-sink=/dev/video11

  ${C_BOLD}MemCam${C_OFF}
    source .venv/bin/activate
    python memcam.py --camera 11 --preview

  ${C_BOLD}adatgyujtes uj gesztushoz${C_OFF}
    python collect_gestures.py
    python train_gestures.py

${C_DIM}Kernelfrissites utan futtasd ujra ezt a scriptet: a v4l2loopback
modult ujra kell forditani es alairni. A MOK kulcs beiktatva marad,
azt nem kell ujra.${C_OFF}

EOF
