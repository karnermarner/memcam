#!/usr/bin/env python3
"""
MemCam - gesztusvezerelt mem-overlay virtualis kamerakent.

Megfogja az igazi webkamerat, raszamol ket gesztusfelismerovel, a talalt
gesztushoz tartozo kepet rakomponalja a frame-re, es az egeszet kiirja egy
virtualis kameraba. Teams / Discord / Meet a kamerak kozott latja, es a
hivas masik vegen is latszik a mem.

Ugyanez a fajl fut Windowson es Linuxon, a kulonbseg csak az, hogy mi adja
a virtualis kameraeszkozt.

==========================================================================
KET MODELL, EGY DONTES

  MediaPipe (beepitett)   het altalanos kezforma: Thumb_Up, Thumb_Down,
                          Victory, Open_Palm, Closed_Fist, Pointing_Up,
                          ILoveYou. Tobb tizezer emberen tanitva, barki
                          kezen mukodik. Csak az ujjak allasat nezi.

  gesture_model.pkl       a sajat, betanitott modelled. Archoz viszonyitva
  (ha ott van)            lat, ezert olyat is meg tud kulonboztetni, amit
                          a MediaPipe szerkezetileg nem: pl. szalutalast a
                          nyitott tenyertol, mert ott a hely es a doles
                          szamit, nem az ujjak.

  Ha mindketto mond valamit ugyanarra a frame-re, a SAJAT modell nyer.
  Ennek oka van: a tiednek van None osztalya, tehat kepzett arra, hogy
  megmondja, mikor NEM gesztus valami. A MediaPipe-nak nincs ilyen
  fogalma a te pozaidrol.

  A sajat modell nelkul is elindul minden, csak a het beepitett megy.

==========================================================================
HOVA KERUL A MEM  (--anchor)

  hand    a kez fole. A pozicio a kioldas pillanataban rogzul.
  face    az arcodra, koveti a fejed, egyutt no veled. A merethez a
          --face-scale valo, a --size ilyenkor nem szamit.
  center  fix a kep kozepen.

==========================================================================
MEM FORMATUMOK

  PNG / JPG / WebP     allokep. Atlatszo hattereru PNG a legjobb.
  GIF / animalt WebP   animalt, sajat idozitessel, a --duration vegeig
                       ciklusban. Ehhez Pillow kell.
  A fajlnev a gesztus neve legyen, kiterjesztes barmi:
    memes/Thumb_Up.png  memes/Salute.gif  memes/FingerGuns.webp

==========================================================================
TELEPITES

  Windows:  OBS Studio (a virtualis kamerat o regisztralja), Python
            3.10-3.12, majd
              python -m pip install opencv-python mediapipe pyvirtualcam \\
                numpy pillow scikit-learn joblib

  Linux:    sudo modprobe v4l2loopback devices=1 video_nr=10 \\
              card_label="MemCam" exclusive_caps=1
            pip install opencv-python mediapipe pyvirtualcam numpy pillow \\
              scikit-learn joblib

  Kilepes: Ctrl-C, vagy a preview ablakban q. Az ablak X-e nem mukodik,
  az OpenCV nem kezeli a keretet.
==========================================================================
"""

import argparse
import os
import sys
import time
import urllib.request

import cv2
import numpy as np

from gesture_features import (FACE_GRACE, FEATURE_DIM, build_features,
                              landmarks_to_pixels)

try:
    from PIL import Image, ImageSequence
    HAS_PIL = True
except ImportError:
    HAS_PIL = False

IS_WINDOWS = sys.platform.startswith("win")

GESTURE_MODEL = ("gesture_recognizer.task",
                 "https://storage.googleapis.com/mediapipe-models/gesture_recognizer/"
                 "gesture_recognizer/float16/1/gesture_recognizer.task")
FACE_MODEL = ("blaze_face_short_range.tflite",
              "https://storage.googleapis.com/mediapipe-models/face_detector/"
              "blaze_face_short_range/float16/1/blaze_face_short_range.tflite")
CUSTOM_MODEL = "gesture_model_v3.1.pkl"

STATIC_EXT = (".png", ".jpg", ".jpeg", ".bmp")
ANIMATED_EXT = (".gif", ".webp", ".apng")

# a het beepitett gesztus -> tartalek felirat, ha nincs kep a memes/ mappaban
BUILTIN_CAPTION = {
    "Thumb_Up":    "KIVALO",
    "Thumb_Down":  "HAT EZ NEM",
    "Victory":     "MEGLEPVE",
    "Open_Palm":   "ALLJ",
    "Closed_Fist": "TUZ",
    "Pointing_Up": "VALOJABAN",
    "ILoveYou":    "SZIVEM",
}


# ----------------------------------------------------------------- betoltes

def ensure_model(spec):
    fname, url = spec
    if not os.path.exists(fname):
        print(f"modell letoltese -> {fname}", flush=True)
        urllib.request.urlretrieve(url, fname)
    return fname


class Sprite:
    """Egy mem. Allokepnel egy kocka, animaltnal tobb, sajat idozitessel.
    A `frames` mindig BGRA, a `durations` masodpercben."""

    def __init__(self, frames, durations):
        self.frames = frames
        self.durations = durations
        self.cumulative = np.cumsum(durations)
        self.total = float(self.cumulative[-1])

    @property
    def animated(self):
        return len(self.frames) > 1

    def frame_index(self, elapsed):
        """Melyik kocka latszik `elapsed` masodperccel a kioldas utan.
        A vegen ujrakezdi, igy hosszabb --duration mellett ciklusban megy."""
        if not self.animated:
            return 0
        return int(np.searchsorted(self.cumulative, elapsed % self.total, side="right"))


def load_sprite_file(path):
    """Beolvas egy mem fajlt Sprite-kent. Animalt formatumhoz Pillow kell."""
    ext = os.path.splitext(path)[1].lower()

    if ext in ANIMATED_EXT:
        if not HAS_PIL:
            print(f"  kihagyva (Pillow kell hozza): {os.path.basename(path)}",
                  file=sys.stderr)
            return None
        with Image.open(path) as im:
            frames, durations = [], []
            for page in ImageSequence.Iterator(im):
                rgba = np.array(page.convert("RGBA"))
                frames.append(cv2.cvtColor(rgba, cv2.COLOR_RGBA2BGRA))
                # a GIF nem mindig ad idozitest; 80 ms ertelmes alapertelmezes
                ms = page.info.get("duration") or 80
                durations.append(max(20, ms) / 1000.0)
        return Sprite(frames, durations) if frames else None

    if ext in STATIC_EXT:
        img = cv2.imread(path, cv2.IMREAD_UNCHANGED)
        if img is None:
            return None
        if img.ndim == 2:                                   # szurkearnyalatos
            img = cv2.cvtColor(img, cv2.COLOR_GRAY2BGRA)
        elif img.shape[2] == 3:                             # nincs alfa
            alpha = np.full(img.shape[:2] + (1,), 255, dtype=img.dtype)
            img = np.concatenate([img, alpha], axis=2)
        return Sprite([img], [1.0])

    return None


def load_memes(folder):
    """Beolvassa a memes/ mappat. Sprite-ot ad vissza gesztusnevenkent."""
    memes = {}
    if not os.path.isdir(folder):
        return memes
    for fname in sorted(os.listdir(folder)):
        stem, ext = os.path.splitext(fname)
        if ext.lower() not in STATIC_EXT + ANIMATED_EXT:
            continue
        sprite = load_sprite_file(os.path.join(folder, fname))
        if sprite is None:
            continue
        h, w = sprite.frames[0].shape[:2]
        kind = (f"{len(sprite.frames)} kocka, {sprite.total:.1f}s"
                if sprite.animated else "allokep")
        memes[stem] = sprite
        print(f"  mem betoltve: {stem} ({w}x{h}, {kind})")
    return memes


def make_placeholder(text, width=420):
    """Szoveges plakat, ha egy gesztushoz nincs sajat kep."""
    font, scale, thick = cv2.FONT_HERSHEY_DUPLEX, 1.6, 3
    (tw, th), base = cv2.getTextSize(text, font, scale, thick)
    pad = 26
    w, h = max(width, tw + 2 * pad), th + base + 2 * pad
    card = np.zeros((h, w, 4), dtype=np.uint8)
    card[:, :] = (63, 210, 255, 235)                     # BGRA, sarga
    cv2.putText(card, text, ((w - tw) // 2, pad + th),
                font, scale, (29, 23, 21, 255), thick, cv2.LINE_AA)
    return Sprite([card], [1.0])


# ------------------------------------------------------------ kompozitalas

def overlay(frame, sprite_img, cx, cy):
    """Alfa-blendeli a kepet a frame-re, kozeppont (cx, cy) pixelben.
    A frame szelen automatikusan vag, nem dob hibat."""
    sh, sw = sprite_img.shape[:2]
    fh, fw = frame.shape[:2]

    x0, y0 = int(cx - sw / 2), int(cy - sh / 2)
    x1, y1 = x0 + sw, y0 + sh

    sx0, sy0 = max(0, -x0), max(0, -y0)
    sx1, sy1 = sw - max(0, x1 - fw), sh - max(0, y1 - fh)
    x0, y0 = max(0, x0), max(0, y0)
    x1, y1 = min(fw, x1), min(fh, y1)

    if x1 <= x0 or y1 <= y0:
        return

    patch = sprite_img[sy0:sy1, sx0:sx1]
    alpha = patch[:, :, 3:4].astype(np.float32) / 255.0
    roi = frame[y0:y1, x0:x1].astype(np.float32)
    frame[y0:y1, x0:x1] = (patch[:, :, :3] * alpha + roi * (1 - alpha)).astype(np.uint8)


class SpriteCache:
    """Arckovetes mellett a kivant szelesseg minden frame-ben mas lehet, es
    animalt memnel a kockak is valtoznak - ezert a mar kiszamolt
    atmeretezeseket eltesszuk (nev, szelesseg, kocka) kulccsal. A szelesseget
    8 pixelre kerekitjuk, kulonben minden apro fejmozdulas uj resize-t szulne."""

    MAX_ENTRIES = 400

    def __init__(self, sprites):
        self.sprites = sprites
        self.cache = {}

    def get(self, name, target_w, elapsed=0.0):
        sprite = self.sprites[name]
        idx = sprite.frame_index(elapsed)
        target_w = max(16, int(round(target_w / 8) * 8))

        key = (name, target_w, idx)
        hit = self.cache.get(key)
        if hit is None:
            src = sprite.frames[idx]
            scale = target_w / src.shape[1]
            hit = cv2.resize(src, (target_w, max(1, int(src.shape[0] * scale))),
                             interpolation=cv2.INTER_AREA)
            if len(self.cache) > self.MAX_ENTRIES:
                self.cache.clear()
            self.cache[key] = hit
        return hit


# ------------------------------------------------------------ allapotgep

class Trigger:
    """Akkor lo, ha `hold` egymas utani frame-en ugyanaz a gesztus van a
    kuszob folott. Utana le van tiltva addig, amig a kez el nem hagyja azt
    a pozt - igy egy kitartott huvelykujj egyszer szol, nem negyvenszer."""

    def __init__(self, hold, threshold):
        self.hold = hold
        self.threshold = threshold
        self.candidate = None
        self.streak = 0
        self.armed_for = None

    def update(self, name, score):
        current = name if (name and name != "None" and score >= self.threshold) else None

        if current != self.candidate:
            self.candidate = current
            self.streak = 0
        self.streak += 1

        if current != self.armed_for:
            self.armed_for = None                       # poz elengedve -> ujra eles

        if current and self.streak >= self.hold and self.armed_for != current:
            self.armed_for = current
            return current
        return None


class CustomClassifier:
    """A betanitott sajat modell. Nem kotelezo - ha nincs pkl, ez None marad
    es minden megy a beepitettel."""

    def __init__(self, path):
        import joblib
        bundle = joblib.load(path)
        self.model = bundle["model"]
        self.classes = bundle["classes"]
        dim = bundle.get("feature_dim", FEATURE_DIM)
        if dim != FEATURE_DIM:
            raise ValueError(
                f"a modell {dim} jellemzore tanult, a kod {FEATURE_DIM}-t szamol. "
                f"Ugyanazzal a gesture_features.py-jal tanitsd ujra.")
        self.gestures = [c for c in self.classes if c != "None"]

    def predict(self, hands_px, face):
        """(nev, valoszinuseg) vagy (None, 0). Arc nelkul nincs josolhato
        vektor - a jellemzok az archoz viszonyulnak."""
        if face is None or not hands_px:
            return None, 0.0
        vec = build_features(hands_px, face).reshape(1, -1)
        proba = self.model.predict_proba(vec)[0]
        idx = int(np.argmax(proba))
        return self.model.classes_[idx], float(proba[idx])


# --------------------------------------------------------------- kamerak

def open_capture(index, width, height, fps):
    """Windowson DirectShow, Linuxon V4L2. Egyik esetben sem hagyjuk az
    OpenCV-re a backend valasztasat: a visszaeses az FFMPEG-esre sajat,
    rovidebb eszkozlistat hasznal, es v4l2loopback eszkozt nem talal meg."""
    backend = cv2.CAP_DSHOW if IS_WINDOWS else cv2.CAP_V4L2
    cap = cv2.VideoCapture(index, backend)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
    cap.set(cv2.CAP_PROP_FPS, fps)
    return cap


def open_virtual_camera(pyvirtualcam, width, height, fps, device):
    kwargs = dict(width=width, height=height, fps=fps,
                  fmt=pyvirtualcam.PixelFormat.BGR)
    if device:
        kwargs["device"] = device
    try:
        return pyvirtualcam.Camera(**kwargs)
    except RuntimeError as exc:
        if IS_WINDOWS:
            sys.exit(f"nem nyilt meg a virtualis kamera: {exc}\n"
                     f"telepitve van az OBS Studio? a virtualis kamerajat o regisztralja.")
        sys.exit(f"nem nyilt meg a virtualis kamera: {exc}\n"
                 f"betoltotted a modult? sudo modprobe v4l2loopback "
                 f"devices=1 video_nr=10 card_label=\"MemCam\" exclusive_caps=1")


# ------------------------------------------------------------------- main

def main():
    ap = argparse.ArgumentParser(description="Gesztusvezerelt mem-overlay virtualis kameraba.")
    ap.add_argument("--camera", type=int, default=0, help="valodi webkamera indexe")
    ap.add_argument("--output", default=None,
                    help="Linuxon a v4l2loopback eszkoz (default /dev/video10). "
                         "Windowson hagyd uresen.")
    ap.add_argument("--width", type=int, default=1280)
    ap.add_argument("--height", type=int, default=720)
    ap.add_argument("--fps", type=int, default=30)
    ap.add_argument("--memes", default="memes", help="mem mappa")
    ap.add_argument("--custom-model", default=CUSTOM_MODEL,
                    help="a sajat betanitott modell. Ha nincs meg, csak a "
                         "het beepitett gesztus mukodik.")
    ap.add_argument("--no-custom", action="store_true",
                    help="a sajat modell kihagyasa, csak a beepitettek")
    ap.add_argument("--anchor", choices=["hand", "face", "center"], default="hand")
    ap.add_argument("--face-scale", type=float, default=1.6,
                    help="--anchor face: a kep szelessege az arc szelessegenek "
                         "hanyszorosa")
    ap.add_argument("--face-offset", type=float, default=0.0,
                    help="--anchor face: fuggoleges eltolas az arc magassaganak "
                         "aranyaban. Negativ = feljebb")
    ap.add_argument("--hold", type=int, default=5, help="ennyi frame-ig tartani kell")
    ap.add_argument("--threshold", type=float, default=0.62,
                    help="a beepitett MediaPipe kuszobe")
    ap.add_argument("--custom-threshold", type=float, default=0.75,
                    help="a sajat modell kuszobe. Magasabb, mert a sajat "
                         "modell magabiztosabb szokott lenni.")
    ap.add_argument("--duration", type=float, default=0,
                    help="0 = animalt memnel egy vegigjatszas, allokepnel 2.2 mp")
    ap.add_argument("--size", type=float, default=0.34,
                    help="hand/center horgony: a mem szelessege a frame aranyaban")
    ap.add_argument("--preview", action="store_true", help="helyi elonezeti ablak")
    args = ap.parse_args()

    device = args.output
    if device is None and not IS_WINDOWS:
        device = "/dev/video10"

    # ---------------- sajat modell ----------------
    custom = None
    if not args.no_custom:
        if os.path.exists(args.custom_model):
            try:
                custom = CustomClassifier(args.custom_model)
                print(f"sajat modell: {args.custom_model} "
                      f"({', '.join(custom.gestures)})")
            except Exception as exc:
                print(f"a sajat modell nem toltodott be: {exc}", file=sys.stderr)
        else:
            print(f"(nincs {args.custom_model} - csak a het beepitett gesztus megy)")

    gesture_model = ensure_model(GESTURE_MODEL)
    # arc kell a sajat modellhez is, nem csak a face horgonyhoz
    need_face = custom is not None or args.anchor == "face"
    face_model = ensure_model(FACE_MODEL) if need_face else None

    import mediapipe as mp
    from mediapipe.tasks import python as mp_python
    from mediapipe.tasks.python import vision
    import pyvirtualcam

    print("memek keresese...")
    if not HAS_PIL:
        print("  (Pillow nincs telepitve - GIF es animalt WebP kimarad)")
    memes = load_memes(args.memes)
    if not memes:
        print(f"  (a {args.memes}/ mappa ures vagy nincs meg - szoveges plakatok lesznek)")

    cap = open_capture(args.camera, args.width, args.height, args.fps)
    if not cap.isOpened():
        hint = ("Beallitasok > Adatvedelem > Kamera, engedelyezd az asztali alkalmazasoknak."
                if IS_WINDOWS else
                "fut a forras? v4l2loopback eszkoz exclusive_caps mellett csak "
                "akkor capture, ha valaki ir ra.")
        sys.exit(f"nem nyilt meg a kamera (index {args.camera}). {hint}")

    ok, probe = cap.read()
    if not ok:
        sys.exit("a kamera megnyilt, de nem ad frame-et.")
    height, width = probe.shape[:2]

    # ket kez kell: a FingerGuns es a Prayer ketkezes
    recognizer = vision.GestureRecognizer.create_from_options(
        vision.GestureRecognizerOptions(
            base_options=mp_python.BaseOptions(model_asset_path=gesture_model),
            running_mode=vision.RunningMode.VIDEO,
            num_hands=2,
        )
    )

    face_detector = None
    if need_face:
        face_detector = vision.FaceDetector.create_from_options(
            vision.FaceDetectorOptions(
                base_options=mp_python.BaseOptions(model_asset_path=face_model),
                running_mode=vision.RunningMode.VIDEO,
            )
        )

    # sprite katalogus: beepitettek + a sajat modell osztalyai
    names = list(BUILTIN_CAPTION)
    if custom:
        names += [g for g in custom.gestures if g not in names]
    catalog = {}
    for name in names:
        sprite = memes.get(name)
        if sprite is None:
            sprite = make_placeholder(BUILTIN_CAPTION.get(name, name.upper()))
        catalog[name] = sprite
    sprites = SpriteCache(catalog)

    missing = [n for n in names if n not in memes]
    if missing:
        print(f"  (nincs kep ezekhez, plakat lesz: {', '.join(missing)})")

    def show_time(name):
        if args.duration > 0:
            return args.duration
        s = catalog[name]
        return s.total if s.animated else 2.2

    trigger = Trigger(args.hold, args.threshold)
    active = None          # (nev, kezdet, lejarat, cx, cy)
    last_face = None
    last_face_at = 0.0
    t_start = time.monotonic()

    with open_virtual_camera(pyvirtualcam, width, height, args.fps, device) as vcam:
        print(f"\nvirtualis kamera el: {vcam.device}  ({width}x{height} @ {args.fps})")
        print(f"horgony: {args.anchor}")
        print("valaszd ki Teamsben / Discordban a virtualis kamerat. Ctrl-C a kilepeshez.\n")

        try:
            while True:
                ok, frame = cap.read()
                if not ok:
                    print("frame kimaradt", file=sys.stderr)
                    continue

                rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
                ts = int((time.monotonic() - t_start) * 1000)
                now = time.monotonic()

                result = recognizer.recognize_for_video(mp_image, ts)

                if face_detector is not None:
                    faces = face_detector.detect_for_video(mp_image, ts).detections
                    if faces:
                        bb = max(faces, key=lambda d: d.bounding_box.width).bounding_box
                        last_face = (bb.origin_x + bb.width / 2,
                                     bb.origin_y + bb.height / 2,
                                     float(bb.width), float(bb.height))
                        last_face_at = now
                # a Prayer eltakarhatja az arc also feleit; rovid ideig
                # elfogadjuk az utolso ismert arcot
                face = last_face if (now - last_face_at) < FACE_GRACE else None

                hands_px = landmarks_to_pixels(result.hand_landmarks, width, height)

                # ---- beepitett ----
                name, score = None, 0.0
                if result.gestures:
                    top = result.gestures[0][0]
                    name, score = top.category_name, top.score

                # ---- sajat, es a dontes ----
                # A sajatnak van None osztalya, tehat kepzett arra, hogy
                # megmondja, mikor NEM gesztus valami. Ha az biztos a
                # dolgaban, felulirja a beepitettet.
                if custom is not None:
                    cname, cscore = custom.predict(hands_px, face)
                    if cname and cname != "None" and cscore >= args.custom_threshold:
                        name, score = cname, cscore

                fired = trigger.update(name, score)

                if fired:
                    cx, cy = width * 0.5, height * 0.35
                    if args.anchor == "center":
                        cx, cy = width * 0.5, height * 0.5
                    elif args.anchor == "hand" and hands_px:
                        # tobb kez eseten a kozos kozeppont
                        allpts = np.concatenate(hands_px, axis=0)
                        sprite_h = sprites.get(fired, width * args.size).shape[0]
                        cx = float(np.clip(allpts[:, 0].mean() / width, 0.2, 0.8)) * width
                        cy = allpts[:, 1].min() - sprite_h * 0.6
                        cy = float(np.clip(cy, sprite_h * 0.55, height - sprite_h * 0.55))
                    active = (fired, now, now + show_time(fired), cx, cy)
                    print(f"  {fired}  ({score:.2f})")

                if active:
                    gname, started, expires, cx, cy = active
                    if now >= expires:
                        active = None
                    else:
                        elapsed = now - started
                        if args.anchor == "face":
                            if last_face:
                                fcx, fcy, fw, fh = last_face
                                img = sprites.get(gname, fw * args.face_scale, elapsed)
                                overlay(frame, img, fcx, fcy + fh * args.face_offset)
                        else:
                            img = sprites.get(gname, width * args.size, elapsed)
                            overlay(frame, img, cx, cy)

                vcam.send(frame)
                vcam.sleep_until_next_frame()

                if args.preview:
                    cv2.imshow("MemCam (elonezet)", cv2.flip(frame, 1))
                    if cv2.waitKey(1) & 0xFF == ord("q"):
                        break

        except KeyboardInterrupt:
            print("\nleallitas")
        finally:
            cap.release()
            recognizer.close()
            if face_detector is not None:
                face_detector.close()
            if args.preview:
                cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
