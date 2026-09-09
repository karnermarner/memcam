#!/usr/bin/env python3
"""
train_gestures.py - osztalyozo tanitasa a collect_gestures.py CSV-jebol.

  pip install scikit-learn numpy joblib
  python train_gestures.py

Kimenet: gesture_model.pkl, amit a memcam.py be tud tolteni.

--------------------------------------------------------------------------
GPU-RA NINCS SZUKSEG

  92 bemenet es par ezer minta. CPU-n masodpercek. A CUDA inicializalasa
  tovabb tartana, mint maga a tanitas.

--------------------------------------------------------------------------
MIT NEZZ MEG A VEGEN

  A confusion matrix a lenyeg, nem a pontossag. Ha a Salute sorban a
  hibak a None oszlopba esnek, az kezelheto: emeld a kuszobot. Ha ket
  valodi gesztus keveredik egymassal, az adat a hibas - gyujts tobbet
  abbol a kettobol, jobban elvalaszthato pozokkal.

  A None osztaly szandekosan tulsulyos, ezert a class_weight="balanced".
  Enelkul a modell megtanulna, hogy mindig None-t mondani eleg jo.
--------------------------------------------------------------------------
"""

import sys

import numpy as np

try:
    import joblib
    from sklearn.model_selection import train_test_split
    from sklearn.neural_network import MLPClassifier
    from sklearn.preprocessing import StandardScaler
    from sklearn.pipeline import make_pipeline
    from sklearn.metrics import classification_report, confusion_matrix
    from sklearn.utils.class_weight import compute_sample_weight
except ImportError:
    sys.exit("kell: pip install scikit-learn joblib numpy")

CSV_PATH = "gestures.csv"
OUT_PATH = "gesture_model.pkl"


def main():
    try:
        raw = np.genfromtxt(CSV_PATH, delimiter=",", dtype=str, skip_header=1)
    except OSError:
        sys.exit(f"nincs meg a {CSV_PATH} - futtasd eloszor a collect_gestures.py-t")

    if raw.ndim == 1:
        raw = raw.reshape(1, -1)

    labels = raw[:, 0]
    X = raw[:, 1:].astype(np.float32)

    classes, counts = np.unique(labels, return_counts=True)
    print(f"{len(labels)} minta, {len(classes)} osztaly")
    for c, n in zip(classes, counts):
        print(f"  {c:12s} {n}")

    thin = [c for c, n in zip(classes, counts) if n < 100]
    if thin:
        print(f"\nfigyelem: keves minta ehhez: {', '.join(thin)}. "
              f"200 alatt a modell nem lesz megbizhato.")

    X_tr, X_te, y_tr, y_te = train_test_split(
        X, labels, test_size=0.2, random_state=0, stratify=labels)

    model = make_pipeline(
        StandardScaler(),
        MLPClassifier(hidden_layer_sizes=(128, 64), max_iter=800,
                      early_stopping=True, n_iter_no_change=25,
                      random_state=0),
    )

    # a None tulsulyat itt egyenlitjuk ki
    weights = compute_sample_weight("balanced", y_tr)
    try:
        model.fit(X_tr, y_tr, mlpclassifier__sample_weight=weights)
    except TypeError:
        # az MLPClassifier nem minden verzioban vesz at sample_weight-et;
        # ilyenkor kezzel ritkitunk a tulsulyos osztalybol
        print("(sample_weight nem tamogatott - alulmintavetelezes helyette)")
        X_tr, y_tr = undersample(X_tr, y_tr)
        model.fit(X_tr, y_tr)

    pred = model.predict(X_te)
    print("\n" + classification_report(y_te, pred, digits=3))

    order = sorted(set(labels))
    cm = confusion_matrix(y_te, pred, labels=order)
    width = max(len(c) for c in order) + 2
    print("confusion matrix (sor = valodi, oszlop = josolt)")
    print(" " * width + "".join(f"{c[:8]:>10s}" for c in order))
    for name, row in zip(order, cm):
        print(f"{name:<{width}s}" + "".join(f"{v:>10d}" for v in row))

    joblib.dump({"model": model, "classes": sorted(set(labels)),
                 "feature_dim": X.shape[1]}, OUT_PATH)
    print(f"\nmentve: {OUT_PATH}")


def undersample(X, y):
    """A legkisebb osztaly meretere vagja a tobbit."""
    classes, counts = np.unique(y, return_counts=True)
    target = counts.min()
    rng = np.random.default_rng(0)
    keep = np.concatenate([
        rng.choice(np.flatnonzero(y == c), target, replace=False) for c in classes])
    rng.shuffle(keep)
    return X[keep], y[keep]


if __name__ == "__main__":
    main()
