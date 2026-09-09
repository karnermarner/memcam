# MemCam

Gesztusvezérelt mém-overlay virtuális kameraként. Megfogja a webkamerát,
figyeli a kezed, és amikor felismer egy gesztust, ráteszi a hozzá tartozó
képet a videóra. A kimenet egy virtuális kameraeszköz, amit a Teams, a
Discord és a Meet is kiválaszthat — így a hívás másik végén is látszik.

Minden helyben fut, semmilyen kép nem megy ki a gépről.

---

## Mit tud

- 7 beépített kézgesztus felismerése (MediaPipe Gesture Recognizer)
- Saját PNG/JPG mémek gesztusonként
- Három elhelyezési mód: kéz fölé, arcra (fejkövetéssel), vagy képközépre
- Állítható érzékenység, tartási idő és méret
- Windows és Linux ugyanabból a fájlból

---

## Telepítés

### Windows

**1. OBS Studio**

<https://obsproject.com> — a 28-as verziótól a virtuális kamera alapból
települ vele. Az OBS-t **nem kell futtatni**, csak telepítve legyen: ő
regisztrálja a DirectShow-eszközt, amibe a script ír.

Régebbi OBS-nél, ha a script nem találja: nyisd meg egyszer, *Start Virtual
Camera*, majd *Stop*. Ezzel biztosan regisztrál.

**2. Python 3.10–3.12**

A mediapipe 3.13-ra nem ad hivatalos wheelt. Ellenőrzés: `python --version`.
Ha 3.13 van, telepítsd mellé a 3.12-t a python.org-ról (elférnek egymás
mellett), és a telepítőben pipáld be az *Add python.exe to PATH* opciót.

**3. Függőségek**

```cmd
mkdir C:\memcam
cd C:\memcam
python -m venv .venv
.venv\Scripts\activate
python -m pip install opencv-python mediapipe pyvirtualcam numpy
```

PowerShellben az aktiválás `.\.venv\Scripts\Activate.ps1`.

**4. Indítás**

```cmd
python memcam.py --preview
```

Első indításkor letölti a modellfájlokat (pár MB).

### Linux (Ubuntu)

**1. Kernelmodul**

```bash
sudo apt install v4l2loopback-dkms v4l2loopback-utils
sudo modprobe v4l2loopback devices=1 video_nr=10 card_label="MemCam" exclusive_caps=1
```

Az `exclusive_caps=1` nem opcionális: nélküle a Chrome/Chromium — és így a
webes Teams — ki sem listázza az eszközt.

Hogy újraindítás után is meglegyen:

```bash
echo v4l2loopback | sudo tee /etc/modules-load.d/v4l2loopback.conf
echo 'options v4l2loopback devices=1 video_nr=10 card_label="MemCam" exclusive_caps=1' \
  | sudo tee /etc/modprobe.d/v4l2loopback.conf
```

**2. Függőségek és indítás**

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install opencv-python mediapipe pyvirtualcam numpy
python3 memcam.py --preview
```

---

## Használat

Indítás után válaszd ki a virtuális kamerát a hívóprogramban:

- **Discord** — Beállítások → Hang és videó → Kamera
- **Teams (böngésző)** — a hívás eszközbeállításainál
- **Meet** — fogaskerék → Videó

A `--preview` egy helyi ellenőrző ablakot nyit. Kilépés: `Ctrl-C`, vagy `q`
az előnézeti ablakban. **Az ablak X gombja nem működik** — az OpenCV nem
kezeli a keretet, csak billentyűre figyel.

A kimenő kép szándékosan nincs tükrözve. A hívások a saját előnézetedet
tükrözik, de a kimenő adást nem — így látják helyesen a többiek. Ezért
tükröz a `--preview` ablak, és nem tükröz a virtuális kamera.

---

## Gesztusok

A beépített modell hét pózt ismer. A mémek fájlneve pontosan ez legyen:

| Fájlnév | Gesztus |
|---|---|
| `Thumb_Up.png` | hüvelykujj fel, többi ujj zárva |
| `Thumb_Down.png` | hüvelykujj le |
| `Victory.png` | mutató + középső ujj (V) |
| `Open_Palm.png` | nyitott tenyér, mind az öt ujj |
| `Closed_Fist.png` | zárt ököl |
| `Pointing_Up.png` | csak a mutatóujj felfelé |
| `ILoveYou.png` | hüvelyk + mutató + kisujj ki, középső és gyűrűs behajtva |

A `Closed_Fist` és a `Thumb_Up` összekeverhető, ha nem nyújtod ki rendesen a
hüvelyket — `--threshold 0.75` segít. Az `ILoveYou` a legnehezebb, egyenesen
a kamerába mutasd, ne oldalról.

---

## Saját mémek

Csinálj egy `memes/` mappát a script mellé, és tedd bele a képeket a fenti
nevekkel. Amelyik gesztushoz nincs kép, ott sárga szöveges plakát jelenik meg
— ez jó a beüzemeléshez, mert látod, működik-e a felismerés.

Átlátszó hátterű PNG a legjobb, különösen `--anchor face` mellett, mert ott
a JPG fehér téglalapja nagyon látszik.

---

## Kapcsolók

| Kapcsoló | Alap | Mit csinál |
|---|---|---|
| `--threshold` | 0.62 | felismerési küszöb 0–1; lejjebb = engedékenyebb |
| `--hold` | 5 | ennyi egymást követő frame-en kell tartani a gesztust |
| `--duration` | 2.2 | meddig marad a képen, másodpercben |
| `--anchor` | hand | `hand` \| `face` \| `center` |
| `--size` | 0.34 | mém szélessége a frame arányában (hand/center) |
| `--face-scale` | 1.6 | arcra rakva: az arc szélességének hányszorosa |
| `--face-offset` | 0.0 | arcra rakva: függőleges eltolás; negatív = feljebb |
| `--camera` | 0 | valódi webkamera indexe |
| `--width` `--height` | 1280×720 | felbontás |
| `--fps` | 30 | képfrissítés |
| `--memes` | `memes` | mém mappa útvonala |
| `--output` | | Linuxon a v4l2loopback eszköz; Windowson üresen hagyni |
| `--preview` | ki | helyi ellenőrző ablak |

Ha csak azt akarod állítani, mennyire ugrálós, a `--threshold` és a `--hold`
a két lényeges csúszka.

### Elhelyezési módok

**`hand`** — a kéz fölé. A pozíció a kioldás pillanatában rögzül, utána nem
mozog.

**`face`** — az arcodra, és követi a fejed: minden frame-ben újraszámolja a
helyet és a méretet az arc bounding boxából. Ha közelebb hajolsz, együtt nő
veled. Ha elveszik a detekció (elfordulsz, kitakarod), az utolsó ismert
helyen marad, nem ugrik el.

Fejbuborék-hatáshoz told feljebb:

```
python memcam.py --anchor face --face-scale 1.2 --face-offset -0.9 --preview
```

**`center`** — fix a kép közepén.

### Gyorsindító

Ha sokat variálsz a kapcsolókkal, csinálj egy `start.bat`-ot:

```bat
@echo off
call .venv\Scripts\activate
python memcam.py --anchor face --face-scale 1.3 --threshold 0.7 --preview
```

---

## Hibakeresés

**`'py' is not recognized`** — nincs fent a Python Launcher. Nem baj, a
`python -m venv` ugyanazt tudja. Ha a `python` sincs meg, zárd be és nyisd
újra a cmd ablakot: a PATH-t induláskor olvassa be.

**`where python` egy `WindowsApps\python.exe`-t mutat** — az a Microsoft
Store átirányító stubja, nem valódi Python. Beállítások → Alkalmazások →
Alkalmazás-aliasok, kapcsold ki a `python.exe` és `python3.exe` aliast.

**`pip.exe was blocked by your organization's Device Guard policy`** —
a venv által generált `pip.exe` aláíratlan. Használd helyette:
`python -m pip install ...` — ez az aláírt `python.exe`-n keresztül fut.

**`Could not find a version that satisfies the requirement mediapipe`** —
Python 3.13-on vagy. Kell a 3.12.

**`nem nyílt meg a virtuális kamera`** — Windowson nincs telepítve az OBS.
Linuxon nincs betöltve a `v4l2loopback` modul.

**A Discord nem listázza az eszközt** — Linuxon szinte biztos, hogy hiányzik
az `exclusive_caps=1`. Töltsd újra a modult vele.

**A hívóprogram nem találja a valódi webkamerát** — ez normális. Amíg a
`memcam.py` fut, ő fogja a fizikai kamerát, egyszerre csak egy program
tudja megnyitni.

**Akadozik** — két modell fut frame-enként (`--anchor face` esetén). Vidd
lejjebb: `--width 960 --height 540`.

---

## Hogyan működik

```
webkamera ──► OpenCV ──► MediaPipe ──► Trigger ──► overlay ──► pyvirtualcam
                          gesztus +    állapotgép   alfa-      virtuális
                          arc bbox                  blend      kamera
```

A lényegi rész a `Trigger` osztály. Egy gesztus akkor lő, ha `hold` egymást
követő frame-en látszik a küszöb fölött — utána le van tiltva addig, amíg a
kezed el nem hagyja azt a pózt. Enélkül egy kitartott hüvelykujj
másodpercenként harmincszor szólna.

Az arckövetéshez egy második modell fut (BlazeFace). Mivel az arc mérete
frame-enként változik, a `SpriteCache` teszi el a már kiszámolt
átméretezéseket, 8 pixelre kerekített szélességgel — különben minden apró
fejmozdulás új `cv2.resize`-t szülne.

---

## Továbbfejlesztés

**Saját gesztus tanítása.** A beépített hét póz nem bővíthető, de mellé lehet
tanítani sajátot. A recept: `HandLandmarker`-rel gyűjtesz landmarkokat CSV-be
(gesztusonként 300–500 minta, változatos szögből és távolságból),
normalizálod a csuklóponthoz képest, aztán MediaPipe Model Makerrel tanítasz.
Az eredmény egy `.task` fájl, amit a script változtatás nélkül betölt — csak
a modellfájl nevét kell átírni, a `Trigger` és az overlay marad.

A normalizálás nem opcionális: nyers koordinátákon a modell azt tanulja meg,
hol álltál a kamerához képest, nem azt, milyen a póz.

GPU-ra nincs szükség hozzá. 63 bemenet és pár ezer minta CPU-n is másodpercek
alatt tanul.

**Két kéz.** A `num_hands=1` átírható, de akkor a `Trigger`-ből is kettő kell,
kezenként egy — különben a két kéz felváltva reseteli egymást.

**Ismétlődő trigger.** Ha azt akarod, hogy kitartott póz mellett újra és újra
szóljon, a `Trigger.update()`-ben az `armed_for` mellé kell egy időzítés.

---

## Ami nincs benne

- Konfigfájl — minden kapcsolóból megy
- Hang
- Mozdulatsorok (csak statikus pózok). Ahhoz a `Trigger` mellé kellene egy
  állapotgép, ami két póz közti átmenetet ismer fel.
- Képernyő-overlay más alkalmazások fölé. Ez virtuális kamera: csak a
  videóhívás képébe kerül bele, a képernyődre nem rajzol.
