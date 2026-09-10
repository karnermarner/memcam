#!/usr/bin/env python3
"""
collect_gestures.py - tanitoadat gyujtese sajat gesztusokhoz.

Webkamerabol figyeli a kezed es az arcod, kiszamol egy jellemzovektort, es
CSV-be irja a valasztott cimkevel. A kimenet kozvetlenul a train_gestures.py
bemenete.

--------------------------------------------------------------------------
MIERT NEM ELEG A PUSZTA LANDMARK

  A "szalutalas" ujjallasa azonos a nyitott tenyerevel. Ami megkulonbozteti,
  az a helye (halantek) es a dolese - nem az ujjak. Ha a landmarkokat a
  csuklohoz normalizaljuk es kezmerettel leosztjuk, pont ez az informacio
  vesz el.

  Ezert a jellemzovektor haromfele dolgot tartalmaz kezenkent:
    - alak:    a 21 pont a csuklohoz kepest, kezmerettel leosztva (42 dim)
               ez forgasfuggo, mert a doles itt szamit
    - hely:    a kez kozeppontja az arc kozeppontjahoz kepest, az arc
               szelessegeben merve (2 dim)
    - meret:   kezmeret / arcszelesseg (1 dim)
  plusz ket globalis:
    - hany kez latszik
    - a ket kez tavolsaga az arc szelessegeben merve

  Osszesen 92 szam. Arc nelkul nincs minta - a relativ jellemzok nem
  szamolhatok. Mindket celgesztus amugy is az arcnal van.

--------------------------------------------------------------------------
HASZNALAT

  pip install opencv-python mediapipe numpy
  python collect_gestures.py

  A CLASSES listat lentebb allitsd be a sajat gesztusaidra.

  Billentyuk az elonezeti ablakban:
    1..9    cimke valasztasa
    SPACE   felvetel indit / megallit
    u       az utolso 30 minta visszavonasa
    s       mentes most (kilepeskor is ment)
    q       kilepes

--------------------------------------------------------------------------
MENNYI ADAT KELL

  Gesztusonkent 400-600 minta, de ne egyhelyben allva. Kozben mozogj:
  fordulj el kicsit, gyere kozelebb-tavolabb, csinald bal es jobb kezzel,
  valtoztass a megvilagitason. Az adat valtozatossaga szamit, nem a
  mennyisege - 2000 egyforma minta rosszabb, mint 300 valtozatos.

  A None osztaly kotelezo, es legyen belole a legtobb (1000+). Ide az megy,
  amikor NEM csinalsz semmit: gepelsz, iszol, vakarod a fejed, integetsz,
  beszelsz. Enelkul a modell mindenre a legkozelebbi gesztust fogja mondani,
  es folyamatosan tuzelni fog.
--------------------------------------------------------------------------
"""

import csv
import os
import sys
import time
import urllib.request

import cv2
import numpy as np

# ══════════════════════════════════════════════════════════════════════
# ITT ALLITS. A nev lesz a cimke, es kesobb a memes/ mappaban a fajlnev.
# A None-t hagyd a helyen es hagyd elsonek.
# ══════════════════════════════════════════════════════════════════════
CLASSES = [
    "None",
    "Prayer",
    "Salute",
    "FingerGuns",
    "MiddleFinger",
    "Telephone",
    "Okay",
]

OUT_CSV = "gestures.csv"

HAND_MODEL = ("hand_landmarker.task",
              "https://storage.googleapis.com/mediapipe-models/hand_landmarker/"
              "hand_landmarker/float16/1/hand_landmarker.task")
FACE_MODEL = ("blaze_face_short_range.tflite",
              "https://storage.googleapis.com/mediapipe-models/face_detector/"
              "blaze_face_short_range/float16/1/blaze_face_short_range.tflite")

IS_WINDOWS = sys.platform.startswith("win")

PER_HAND_DIM = 45
FEATURE_DIM = 2 * PER_HAND_DIM + 2          # 92
FACE_GRACE = 0.5                            # mp, ameddig az utolso arc ervenyes


def ensure_model(spec):
    fname, url = spec
    if not os.path.exists(fname):
        print(f"modell letoltese -> {fname}", flush=True)
        urllib.request.urlretrieve(url, fname)
    return fname


# ------------------------------------------------------------- jellemzok

def hand_features(lm_px, face):
    """Egy kez 45 szama. lm_px: (21,2) pixelben. face: (cx, cy, w, h)."""
    fcx, fcy, fw, _ = face
    wrist = lm_px[0]
    # kezmeret proxy: csuklo -> kozepso ujj tokize. Robusztusabb, mint a
    # bounding box, mert nem fugg attol, hany ujj van kinyujtva.
    scale = np.linalg.norm(lm_px[9] - wrist)
    if scale < 1e-3:
        scale = 1.0

    shape = ((lm_px - wrist) / scale).ravel()          # 42, forgasfuggo
    center = lm_px.mean(axis=0)
    pos = (center - np.array([fcx, fcy])) / fw          # 2, archoz kepest
    rel_size = np.array([scale / fw])                   # 1
    return np.concatenate([shape, pos, rel_size]), center


def build_features(hands_px, face):
    """Fix hosszu vektor legfeljebb ket kezbol. A kezeket kepen balrol jobbra
    rendezzuk, hogy ne szamitson, melyiket talalta meg eloszor a detektor."""
    vec = np.zeros(FEATURE_DIM, dtype=np.float32)
    if not hands_px:
        return vec

    ordered = sorted(hands_px, key=lambda h: h[:, 0].mean())[:2]
    centers = []
    for i, lm in enumerate(ordered):
        feat, center = hand_features(lm, face)
        vec[i * PER_HAND_DIM:(i + 1) * PER_HAND_DIM] = feat
        centers.append(center)

    vec[-2] = len(ordered)
    if len(centers) == 2:
        vec[-1] = np.linalg.norm(centers[0] - centers[1]) / face[2]
    return vec


# ------------------------------------------------------------------ main

def main():
    hand_model = ensure_model(HAND_MODEL)
    face_model = ensure_model(FACE_MODEL)

    import mediapipe as mp
    from mediapipe.tasks import python as mp_python
    from mediapipe.tasks.python import vision

    landmarker = vision.HandLandmarker.create_from_options(
        vision.HandLandmarkerOptions(
            base_options=mp_python.BaseOptions(model_asset_path=hand_model),
            running_mode=vision.RunningMode.VIDEO,
            num_hands=2,
        )
    )
    face_detector = vision.FaceDetector.create_from_options(
        vision.FaceDetectorOptions(
            base_options=mp_python.BaseOptions(model_asset_path=face_model),
            running_mode=vision.RunningMode.VIDEO,
        )
    )

    cap = cv2.VideoCapture(11, cv2.CAP_V4L2)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
    if not cap.isOpened():
        sys.exit("nem nyilt meg a kamera")

    # meglevo CSV folytatasa, ne irjuk felul a delelotti munkat
    rows = []
    if os.path.exists(OUT_CSV):
        with open(OUT_CSV, newline="") as fh:
            reader = csv.reader(fh)
            next(reader, None)
            rows = [r for r in reader]
        print(f"meglevo {OUT_CSV} folytatasa: {len(rows)} minta")

    counts = {c: 0 for c in CLASSES}
    for r in rows:
        if r[0] in counts:
            counts[r[0]] += 1

    label_idx = 0
    recording = False
    last_face = None
    last_face_at = 0.0
    t0 = time.monotonic()

    print("\nSPACE = felvetel, 1..9 = cimke, u = utolso 30 vissza, s = mentes, q = kilepes\n")

    try:
        while True:
            ok, frame = cap.read()
            if not ok:
                continue
            h, w = frame.shape[:2]

            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
            ts = int((time.monotonic() - t0) * 1000)

            hres = landmarker.detect_for_video(image, ts)
            fres = face_detector.detect_for_video(image, ts)

            now = time.monotonic()
            if fres.detections:
                bb = max(fres.detections, key=lambda d: d.bounding_box.width).bounding_box
                last_face = (bb.origin_x + bb.width / 2, bb.origin_y + bb.height / 2,
                             float(bb.width), float(bb.height))
                last_face_at = now
            # az imadkozo poz eltakarhatja az arc also feleit; rovid ideig
            # elfogadjuk az utolso ismert arcot, kulonben kiesnenek a mintak
            face = last_face if (now - last_face_at) < FACE_GRACE else None

            hands_px = []
            for lm in hres.hand_landmarks:
                hands_px.append(np.array([[p.x * w, p.y * h] for p in lm], dtype=np.float32))

            usable = face is not None
            if recording and usable:
                vec = build_features(hands_px, face)
                label = CLASSES[label_idx]
                rows.append([label] + [f"{v:.5f}" for v in vec])
                counts[label] += 1

            # ---------------- kijelzo ----------------
            view = cv2.flip(frame, 1)
            for lm in hands_px:
                for p in lm:
                    cv2.circle(view, (int(w - p[0]), int(p[1])), 3, (60, 220, 60), -1)
            if face:
                fcx, fcy, fwid, fhei = face
                cv2.rectangle(view,
                              (int(w - fcx - fwid / 2), int(fcy - fhei / 2)),
                              (int(w - fcx + fwid / 2), int(fcy + fhei / 2)),
                              (255, 180, 60), 2)

            banner = (0, 0, 220) if recording else (60, 60, 60)
            cv2.rectangle(view, (0, 0), (w, 96), banner, -1)
            state = "FELVETEL" if recording else "all"
            cv2.putText(view, f"[{state}]  {CLASSES[label_idx]}", (14, 38),
                        cv2.FONT_HERSHEY_SIMPLEX, 1.0, (255, 255, 255), 2, cv2.LINE_AA)
            tally = "   ".join(f"{i+1}:{c}={counts[c]}" for i, c in enumerate(CLASSES))
            cv2.putText(view, tally, (14, 74),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (235, 235, 235), 1, cv2.LINE_AA)
            if not usable:
                cv2.putText(view, "nincs arc - a minta kimarad", (14, h - 24),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.8, (60, 60, 255), 2, cv2.LINE_AA)

            cv2.imshow("gyujtes", view)

            # ---------------- billentyuk ----------------
            key = cv2.waitKey(1) & 0xFF
            if key == ord("q"):
                break
            elif key == ord(" "):
                recording = not recording
            elif key == ord("u"):
                removed = 0
                while rows and removed < 30:
                    counts[rows.pop()[0]] -= 1
                    removed += 1
                print(f"  {removed} minta visszavonva")
            elif key == ord("s"):
                save(rows)
            elif ord("1") <= key <= ord("9"):
                idx = key - ord("1")
                if idx < len(CLASSES):
                    label_idx = idx
                    recording = False       # cimkevaltasnal ne folytassa vakon

    finally:
        cap.release()
        cv2.destroyAllWindows()
        landmarker.close()
        face_detector.close()
        save(rows)
        print("\nvegso allas:")
        for c in CLASSES:
            print(f"  {c:12s} {counts[c]}")


def save(rows):
    header = ["label"] + [f"f{i}" for i in range(FEATURE_DIM)]
    with open(OUT_CSV, "w", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(header)
        writer.writerows(rows)
    print(f"  mentve: {OUT_CSV} ({len(rows)} minta)")


if __name__ == "__main__":
    main()
