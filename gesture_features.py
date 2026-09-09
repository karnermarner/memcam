#!/usr/bin/env python3
"""
gesture_features.py - a jellemzovektor egyetlen forrasa.

A collect_gestures.py es a memcam.py ugyanezt a szamitast hasznalja. Ha a
ketto elcsuszna egymastol, a modell csendben rosszul mukodne: a tanitas
egy jelentesu szamokon menne, a felismeres masikon, es semmi nem jelezne
a hibat. Ezert van kulon fajlban.

VEKTOR FELEPITESE (92 szam)

  kezenkent 45, ket kezre 90:
    0-41   alak:  a 21 landmark a csuklohoz kepest, kezmerettel leosztva.
                  Szandekosan forgasfuggo - a szalutalasnal a doles az
                  egyetlen dolog, ami megkulonbozteti a nyitott tenyertol.
    42-43  hely:  a kez kozeppontja az arc kozeppontjahoz kepest, az arc
                  szelessegeben merve.
    44     meret: kezmeret / arcszelesseg.

  utolso ketto:
    90     hany kez latszik (0, 1 vagy 2)
    91     a ket kez tavolsaga az arc szelessegeben merve

  A kezeket kepen balrol jobbra rendezzuk, hogy ne szamitson, melyiket
  talalta meg eloszor a detektor. Hianyzo kez helyen nullak allnak.

  Arc nelkul nincs ertelmes vektor: a hely es a meret is az archoz
  viszonyul. A hivo dolga eldonteni, mit csinal ilyenkor.
"""

import numpy as np

PER_HAND_DIM = 45
FEATURE_DIM = 2 * PER_HAND_DIM + 2          # 92
FACE_GRACE = 0.5                            # mp, ameddig az utolso arc ervenyes


def hand_features(lm_px, face):
    """Egy kez 45 szama.

    lm_px: (21, 2) tomb pixelben
    face:  (cx, cy, w, h) pixelben
    Visszaad: (45 hosszu vektor, a kez kozeppontja)
    """
    fcx, fcy, fw, _ = face
    wrist = lm_px[0]

    # kezmeret proxy: csuklo -> kozepso ujj tokize. Robusztusabb, mint a
    # bounding box, mert nem fugg attol, hany ujj van kinyujtva.
    scale = np.linalg.norm(lm_px[9] - wrist)
    if scale < 1e-3:
        scale = 1.0

    shape = ((lm_px - wrist) / scale).ravel()           # 42
    center = lm_px.mean(axis=0)
    pos = (center - np.array([fcx, fcy])) / fw          # 2
    rel_size = np.array([scale / fw])                   # 1
    return np.concatenate([shape, pos, rel_size]), center


def build_features(hands_px, face):
    """Fix hosszu vektor legfeljebb ket kezbol.

    hands_px: lista (21, 2) tombokbol, pixelben
    face:     (cx, cy, w, h) pixelben
    """
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


def landmarks_to_pixels(hand_landmarks, width, height):
    """MediaPipe normalizalt landmarkjaibol pixel tombok."""
    return [np.array([[p.x * width, p.y * height] for p in lm], dtype=np.float32)
            for lm in hand_landmarks]
