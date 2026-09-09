#!/usr/bin/env bash
#
# start.sh - MemCam inditasa egy paranccsal.
#
# Elinditja a scrcpy-t hatterben (telefon kamerakent), megvarja amig a
# loopback eszkoz elo lesz, aztan futtatja a MemCamet. Kilepeskor a
# scrcpy-t is leallitja, hogy ne maradjon arvan.
#
#   ./start.sh                  telefonnal
#   ./start.sh --local          sajat webkameraval, scrcpy nelkul
#   ./start.sh -- --anchor hand egyeni kapcsolok a memcam.py-nak
#
# A gyakran allitott dolgok itt lent valtozokban vannak - azokat ird at,
# ne a parancssort gepeld ujra minden alkalommal.

set -euo pipefail

# ────────────────────────────────────────────────── ezeket allitgasd

ANCHOR="face"            # face | hand | center
FACE_SCALE="1.6"         # a kep szelessege az arc szelessegenek hanyszorosa
FACE_OFFSET="0.0"        # negativ = feljebb (-0.9 a fej fole)
CUSTOM_THRESHOLD="0.9"   # a sajat modell kuszobe
HOLD="5"                 # ennyi frame-ig kell tartani a gesztust
PREVIEW=1                # 1 = elonezeti ablak is nyiljon

PHONE_DEVICE="/dev/video11"   # ide ir a scrcpy
PHONE_INDEX="11"              # ezt olvassa a memcam
LOCAL_INDEX="0"               # sajat webkamera --local eseten
CAMERA_SIZE="1280x720"
CAMERA_FACING="front"         # front | back

# ─────────────────────────────────────────────────────────── belsok

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_PY="$PROJECT_DIR/.venv/bin/python"

USE_PHONE=1
EXTRA_ARGS=()

while (( $# )); do
  case "$1" in
    --local)   USE_PHONE=0; shift ;;
    --)        shift; EXTRA_ARGS=("$@"); break ;;
    -h|--help) sed -n '3,14p' "${BASH_SOURCE[0]}" | sed 's/^# \?//'; exit 0 ;;
    *)         EXTRA_ARGS+=("$1"); shift ;;
  esac
done

die() { printf '\n\033[31m%s\033[0m\n\n' "$1" >&2; exit 1; }

[[ -x "$VENV_PY" ]] || die "nincs venv. Futtasd eloszor: ./setup.sh"

SCRCPY_PID=""
cleanup() {
  if [[ -n "$SCRCPY_PID" ]] && kill -0 "$SCRCPY_PID" 2>/dev/null; then
    printf 'scrcpy leallitasa...\n'
    kill "$SCRCPY_PID" 2>/dev/null || true
    wait "$SCRCPY_PID" 2>/dev/null || true
  fi
}
trap cleanup EXIT INT TERM

# ───────────────────────────────────────────────────────────── scrcpy

CAMERA_INDEX="$LOCAL_INDEX"

if (( USE_PHONE )); then
  command -v scrcpy &>/dev/null || die "nincs scrcpy. Futtasd: ./setup.sh"

  if ! adb devices 2>/dev/null | awk 'NR>1 && $2=="device"' | grep -q .; then
    die "nincs csatlakoztatott adb eszkoz.
  Kapcsold be a telefonon a vezetek nelkuli hibakeresest, majd:
    adb connect IP:PORT
  Ha meg nincs parositva:
    adb pair IP:PARITASI_PORT"
  fi

  lsmod | grep -q '^v4l2loopback' || die "a v4l2loopback nincs betoltve. Futtasd: ./setup.sh"

  printf 'scrcpy inditasa -> %s\n' "$PHONE_DEVICE"
  scrcpy \
    --video-source=camera \
    --camera-facing="$CAMERA_FACING" \
    --camera-size="$CAMERA_SIZE" \
    --no-audio \
    --no-playback \
    --v4l2-sink="$PHONE_DEVICE" \
    >/tmp/memcam-scrcpy.log 2>&1 &
  SCRCPY_PID=$!

  # Az exclusive_caps miatt az eszkoz csak akkor lesz capture, ha mar ir
  # ra valaki. Ezert varunk, nem indulunk azonnal.
  printf 'varakozas a kamerakepre'
  for _ in $(seq 40); do
    if ! kill -0 "$SCRCPY_PID" 2>/dev/null; then
      printf '\n'
      tail -20 /tmp/memcam-scrcpy.log >&2
      die "a scrcpy kilepett. A teljes log: /tmp/memcam-scrcpy.log"
    fi
    if grep -q 'v4l2 sink started' /tmp/memcam-scrcpy.log 2>/dev/null; then
      printf ' kesz\n'
      break
    fi
    printf '.'
    sleep 0.25
  done

  grep -q 'v4l2 sink started' /tmp/memcam-scrcpy.log 2>/dev/null \
    || die "a scrcpy nem nyitotta meg a sinket 10 masodperc alatt.
  Log: /tmp/memcam-scrcpy.log"

  CAMERA_INDEX="$PHONE_INDEX"
fi

# ───────────────────────────────────────────────────────────── memcam

ARGS=(
  --camera "$CAMERA_INDEX"
  --anchor "$ANCHOR"
  --face-scale "$FACE_SCALE"
  --face-offset "$FACE_OFFSET"
  --custom-threshold "$CUSTOM_THRESHOLD"
  --hold "$HOLD"
)
(( PREVIEW )) && ARGS+=(--preview)
(( ${#EXTRA_ARGS[@]} )) && ARGS+=("${EXTRA_ARGS[@]}")

printf '\n'
cd "$PROJECT_DIR"
"$VENV_PY" memcam.py "${ARGS[@]}"
