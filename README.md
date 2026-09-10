# MemCam

**English** · [Magyar](README.hu.md)

A live camera overlay that drops memes on your face when you make a hand
gesture. It exposes itself as a virtual webcam, so Discord, Teams and Meet can
pick it up — the people on the call see the memes too, not just you.

Everything runs locally. No frames leave the machine.

Beyond the seven gestures MediaPipe ships with, you can train your own. The
included collector and trainer turn a few minutes in front of the camera into
a working classifier.

---

## How it works

```
webcam ──► OpenCV ──► MediaPipe ────────────┐
                      (7 built-in gestures) │
                      hand landmarks        ├──► Trigger ──► overlay ──► pyvirtualcam
                      face bounding box     │    state       alpha       virtual
                                            │    machine     blend       camera
                      your model ───────────┘
                      (custom gestures)
```

Two classifiers run on every frame:

**MediaPipe** recognises seven general hand shapes — thumbs up/down, victory,
open palm, closed fist, pointing up, and the ILY sign. It was trained on tens
of thousands of people, so it works on anyone's hands. It only looks at finger
configuration.

**Your model** (`gesture_model.pkl`, optional) sees hands *relative to your
face*. That lets it distinguish things MediaPipe structurally cannot — a
salute has the same finger configuration as an open palm; what makes it a
salute is that it's at your temple and tilted.

When both fire on the same frame, yours wins. It has a `None` class, so it has
been trained to say when something *isn't* a gesture. MediaPipe has no such
concept of your poses.

Without a custom model everything still runs, just with the seven built-ins.

### The trigger

A gesture fires only after it has been seen on `--hold` consecutive frames
above the confidence threshold. It's then disarmed until your hand leaves the
pose. Without this, a held thumbs-up would fire thirty times a second.

### The feature vector

This is the part that makes custom gestures work. 92 numbers per frame:

| Range | What | Why |
|---|---|---|
| 0–41 | 21 landmarks relative to the wrist, divided by hand size | Shape. Deliberately **rotation-sensitive** — tilt is what separates a salute from an open palm. |
| 42–43 | Hand centre relative to face centre, in face widths | Position. This is what MediaPipe throws away. |
| 44 | Hand size / face width | How close you are. |
| 45–89 | Same three blocks for a second hand | Two-handed poses. |
| 90 | Number of hands visible | Separates one-handed from two-handed poses. |
| 91 | Distance between hands, in face widths | Whether they're together or apart. |

Hands are sorted left-to-right so it doesn't matter which one the detector
found first. Missing hands are zeros. **No face means no vector** — position
and size are both measured against the face.

The usual advice for gesture models is to normalise landmarks to the wrist and
scale by hand size. That's right for finger shapes and wrong here: it discards
exactly the information that makes a salute a salute. `gesture_features.py` is
a separate module for this reason — if the collector and the recogniser
computed the vector differently, the model would silently misbehave with
nothing to indicate why.

---

## Install

### Linux

```bash
git clone git@github.com:karnermarner/memcam.git
cd memcam
chmod +x setup.sh start.sh
./setup.sh --check     # report only, changes nothing
./setup.sh             # actually set things up
```

`setup.sh` is idempotent — every step checks whether it's already done. It
handles the virtualenv, builds and signs the `v4l2loopback` kernel module,
checks the scrcpy version, and sets up boot persistence.

Run it again after a kernel upgrade: the module has to be rebuilt and
re-signed for the new kernel. Your MOK key stays enrolled.

**Secure Boot:** if it's on, a self-built kernel module won't load unless it's
signed. `setup.sh` generates a MOK key, signs the module and requests
enrolment — then stops and tells you to reboot. Enrolment happens on the blue
MOK Manager screen during boot and cannot be done from a running system.

### Windows

Install [OBS Studio](https://obsproject.com) — you don't need to run it, it
just registers the DirectShow device that `pyvirtualcam` writes to. Then:

```cmd
python -m venv .venv
.venv\Scripts\activate
python -m pip install opencv-python mediapipe pyvirtualcam numpy pillow scikit-learn joblib
python memcam.py --preview
```

Python 3.10–3.12. MediaPipe has no official 3.13 wheel.

---

## Usage

```bash
./start.sh                    # phone as camera via scrcpy
./start.sh --local            # built-in webcam
./start.sh -- --anchor hand   # one-off overrides passed to memcam.py
```

`start.sh` launches scrcpy in the background, waits for the loopback device to
actually go live, then runs MemCam — and kills scrcpy on exit so it doesn't
linger. Frequently changed settings are variables at the top of the file.

Or run it directly:

```bash
python memcam.py --camera 0 --anchor face --preview
```

Then select the virtual camera in your call app: **Discord** → Settings →
Voice & Video → Camera; **Teams (browser)** → device settings in the call.

Quit with `Ctrl-C`, or `q` in the preview window. The window's X button does
nothing — OpenCV doesn't handle the frame, only keys.

The output is deliberately not mirrored. Call apps mirror your self-view but
not the outgoing stream, so this is what other people see correctly.

### Options

| Flag | Default | What it does |
|---|---|---|
| `--camera` | `0` | Camera index |
| `--anchor` | `hand` | `hand` \| `face` \| `center` |
| `--threshold` | `0.62` | MediaPipe confidence threshold |
| `--custom-threshold` | `0.75` | Your model's threshold |
| `--hold` | `5` | Consecutive frames before firing |
| `--duration` | `0` | Seconds on screen. `0` = one full play for animated, 2.2s for stills |
| `--size` | `0.34` | Meme width as a fraction of the frame (hand/center) |
| `--face-scale` | `1.6` | Face anchor: width as a multiple of face width |
| `--face-offset` | `0.0` | Face anchor: vertical offset in face heights. Negative = higher |
| `--no-custom` | off | Skip the custom model, built-ins only |
| `--preview` | off | Local preview window |
| `--output` | | Linux: v4l2loopback device. Leave empty on Windows |

### Anchors

**`hand`** — above the hand. Position freezes at trigger time.

**`face`** — on your face, tracking your head. Position and size are
recalculated every frame from the face bounding box, so it grows as you lean
in. If detection is lost it stays at the last known position rather than
jumping away. For a thought-bubble effect, push it up:

```bash
python memcam.py --anchor face --face-scale 1.2 --face-offset -0.9
```

**`center`** — fixed at the centre of the frame.

---

## Memes

Drop images in `memes/`, named after the gesture:

```
memes/Thumb_Up.gif
memes/Salute.png
memes/FingerGuns.webp
```

Stills: `.png .jpg .jpeg .bmp` · Animated: `.gif .webp .apng` (needs Pillow).
Animated files play at their own frame timings and loop until `--duration`
elapses.

Any gesture without an image gets a plain yellow text card — useful while
setting up, since it tells you recognition is working.

Transparent PNG is best, especially with `--anchor face`, where a JPEG's white
rectangle is very visible. GIF only supports binary transparency; use animated
WebP or APNG if you need clean edges.

Keep files around 300–400px wide. A 500×500, 60-frame GIF is roughly 60MB
decoded to BGRA, and the resize cache adds more on top.

### Built-in gesture names

`Thumb_Up` · `Thumb_Down` · `Victory` · `Open_Palm` · `Closed_Fist` ·
`Pointing_Up` · `ILoveYou`

---

## Training your own gestures

```bash
python collect_gestures.py    # 1/2/3 label, SPACE record, u undo 30, q save+quit
python train_gestures.py      # writes gesture_model.pkl
```

Edit the `CLASSES` list at the top of `collect_gestures.py` first. Keep `None`
first — it's mandatory.

`gestures.csv` in this repo is a working example: 5387 samples across five
classes. The collector appends to an existing file, so you can collect across
several sessions.

**What actually determines quality:**

**Variety beats volume.** 300 varied samples beat 2000 identical ones. Move
while recording — turn, lean in and out, use both hands, change the lighting.

**`None` is the most important class.** Everything you do that *isn't* a
gesture: typing, drinking, scratching your head, waving. Without a large,
varied `None`, the model assigns everything to the nearest gesture and fires
constantly.

**Match your deployment conditions.** Camera at eye level, roughly where your
screen would be. If you collect with the camera on the desk looking up, you're
training on angles the real webcam will never see.

**Collect from your failure cases.** This is the one that matters most, and
it's counterintuitive. In development, the `Prayer` gesture fired on any two
hands pressed together, anywhere — the model had learned the *shape*, not the
*position*, because every training sample had been at face level. Nothing in
the confusion matrix showed it. The fix wasn't more data or threshold tuning;
it was a few hundred targeted `None` samples of hands together *away* from the
face. False positives went from frequent to 2 in 601.

Read the confusion matrix, not the accuracy. Accuracy is misleading when
`None` dominates.

```
                FingerGu  MiddleFi      None    Prayer    Salute
FingerGuns            79         0         1         0         0
MiddleFinger           0        94        11         0         0
None                   0         0       598         2         1
Prayer                 0         0        20       188         0
Salute                 0         0         1         0        83
```

Errors landing in the `None` column mean the gesture is sometimes missed —
manageable, tune with `--custom-threshold` and `--hold`. Errors in the `None`
*row* mean false triggers. Two real gestures confusing each other means your
data can't separate them.

`gesture_model.pkl` is not in this repo. Pickle executes arbitrary code on
load, so publishing one is a bad habit — and it rebuilds from the CSV in
seconds.

---

## Troubleshooting

**`Key was rejected by service` on modprobe** — Secure Boot rejecting an
unsigned module. Run `./setup.sh`; it handles key generation, signing and
enrolment.

**Module won't sign / `.ko.zst`** — compressed modules can't be signed
directly. The kernel decompresses first and verifies after, so the signature
has to be *under* the compression. Decompress, sign, leave it uncompressed.

**Discord doesn't list the device (Linux)** — almost always a missing
`exclusive_caps=1`. Chromium-based apps filter for capture-only devices.

**`Not a video capture device` / `can't open camera by index`** — with
`exclusive_caps=1` a loopback device isn't a capture device until something
writes to it. Check that scrcpy (or whatever feeds it) is still running.

**OpenCV picks the wrong backend** — passing `cv2.CAP_ANY` can fall through to
the FFMPEG backend, which keeps its own shorter device list and won't find a
v4l2loopback device. `memcam.py` requests `CAP_V4L2` on Linux and `CAP_DSHOW`
on Windows explicitly.

**`pip.exe was blocked by your organization's Device Guard policy`** — the
generated `pip.exe` shim is unsigned. Use `python -m pip install ...` instead;
it runs through the signed `python.exe`.

**`Could not find a version that satisfies the requirement mediapipe`** —
you're on Python 3.13. Install 3.12 alongside it.

**scrcpy: `Dependency "sdl3" not found`** — scrcpy 4.x requires SDL3, which
Ubuntu 24.04 doesn't have. Check out the latest `v3` tag; it builds against
SDL2 and already supports camera capture.

**scrcpy: `unrecognized option '--video-source=camera'`** — version older than
2.2. The one in apt usually is.

**Your call app can't find the real webcam** — expected. While MemCam is
running it holds the physical camera; only one process can open it.

**Choppy** — two models run per frame with `--anchor face`. Try
`--width 960 --height 540`.

---

## Not included

- No config file — everything is flags
- No audio
- Static poses only. Motion sequences would need a state machine alongside
  `Trigger` to recognise transitions between poses
- No screen overlay. This is a virtual camera: it only appears in the video
  call, it doesn't draw on your desktop

---

## Requirements

Python 3.10–3.12 · opencv-python · mediapipe · pyvirtualcam · numpy · pillow
(animated memes) · scikit-learn + joblib (custom gestures)

Linux: `v4l2loopback`, plus `scrcpy` and `adb` if you want to use a phone as
the camera. Windows: OBS Studio.

Model files download themselves on first run.

---

## Notes

Built with AI assistance (Claude) for the implementation. The architecture
decisions, debugging, training data and the diagnosis behind the feature
vector design are mine.

