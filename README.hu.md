# MemCam

[English](README.md) · **Magyar**

Élő kamera-overlay, ami mémeket vág az arcodra, amikor kézmozdulatot csinálsz.
Virtuális webkameraként jelenik meg, szóval a Discord, a Teams és a Meet is
látja — a hívás másik végén is látszanak a mémek, nem csak nálad.

Minden helyben fut, egyetlen képkocka sem hagyja el a gépet.

A MediaPipe hét beépített gesztusán túl sajátot is taníthatsz. A mellékelt
gyűjtő és tanító scripttel pár perc a kamera előtt elég egy működő
osztályozóhoz.

---

## Hogyan működik

```
webkamera ──► OpenCV ──► MediaPipe ──────────┐
                         (7 beépített)       │
                         kéz-landmarkok      ├──► Trigger ──► overlay ──► pyvirtualcam
                         arc bounding box    │    állapot-    alfa-       virtuális
                                             │    gép         blend       kamera
                         saját modell ───────┘
                         (saját gesztusok)
```

Minden képkockán két osztályozó fut:

**A MediaPipe** hét általános kézformát ismer — hüvelykujj fel/le, győzelem,
nyitott tenyér, ököl, felfelé mutatás, ILY. Több tízezer emberen tanították,
így bárki kezén működik. Csak az ujjak állását nézi.

**A saját modelled** (`gesture_model.pkl`, nem kötelező) az *archoz
viszonyítva* látja a kezet. Ezért olyat is meg tud különböztetni, amit a
MediaPipe szerkezetileg nem: a szalutálás ujjállása azonos a nyitott
tenyérével, és attól lesz szalutálás, hogy a halántékodnál van és meg van
döntve.

Ha mindkettő mond valamit ugyanarra a képkockára, a tiéd nyer. Neki van `None`
osztálya, tehát képzett arra, hogy megmondja, mikor *nem* gesztus valami. A
MediaPipe-nak nincs ilyen fogalma a te pózaidról.

Saját modell nélkül is elindul minden, csak a hét beépítettel.

### A trigger

Egy gesztus akkor lő, ha `--hold` egymást követő képkockán látszott a küszöb
fölött. Utána le van tiltva addig, amíg a kezed el nem hagyja a pózt. Enélkül
egy kitartott hüvelykujj harmincszor szólna másodpercenként.

### A jellemzővektor

Ez az a rész, amitől a saját gesztusok működnek. 92 szám képkockánként:

| Tartomány | Mi | Miért |
|---|---|---|
| 0–41 | 21 landmark a csuklóhoz képest, kézmérettel leosztva | Alak. Szándékosan **forgásfüggő** — a döntés az, ami elválasztja a szalutálást a nyitott tenyértől. |
| 42–43 | Kézközéppont az arc közepéhez képest, arcszélességben | Hely. Pont ezt dobja el a MediaPipe. |
| 44 | Kézméret / arcszélesség | Mennyire vagy közel. |
| 45–89 | Ugyanez a három blokk egy második kézre | Kétkezes pózok. |
| 90 | Hány kéz látszik | Egykezes és kétkezes pózok elválasztása. |
| 91 | A két kéz távolsága arcszélességben | Össze vannak-e téve vagy sem. |

A kezeket balról jobbra rendezzük, hogy ne számítson, melyiket találta meg
előbb a detektor. Hiányzó kéz helyén nullák. **Arc nélkül nincs vektor** — a
hely és a méret is az archoz viszonyul.

A szokásos tanács gesztusmodellekhez az, hogy normalizálj a csuklóhoz és ossz
le kézmérettel. Ez ujjformákhoz helyes, itt viszont hibás: pont azt az
információt dobja el, amitől a szalutálás szalutálás. A
`gesture_features.py` ezért külön modul — ha a gyűjtő és a felismerő máshogy
számolná a vektort, a modell csendben rosszul működne, és semmi nem jelezné,
miért.

---

## Telepítés

### Linux

```bash
git clone git@github.com:karnermarner/memcam.git
cd memcam
chmod +x setup.sh start.sh
./setup.sh --check     # csak jelentés, semmit nem változtat
./setup.sh             # tényleges beüzemelés
```

A `setup.sh` idempotens — minden lépés előbb megnézi, kész van-e. Kezeli a
virtualenvet, lefordítja és aláírja a `v4l2loopback` kernelmodult,
ellenőrzi a scrcpy verzióját, és beállítja a boot utáni betöltést.

Kernelfrissítés után futtasd újra: a modult újra kell fordítani és aláírni az
új kernelhez. A MOK kulcs beiktatva marad.

**Secure Boot:** ha be van kapcsolva, a saját fordítású kernelmodul csak
aláírva töltődik be. A `setup.sh` generál MOK kulcsot, aláírja a modult és
kérelmezi a beiktatást — aztán megáll és szól, hogy indíts újra. A beiktatás a
boot közbeni kék MOK Manager képernyőn történik, futó rendszerből nem lehet.

### Windows

Telepítsd az [OBS Studiót](https://obsproject.com) — futtatni nem kell, csak ő
regisztrálja azt a DirectShow eszközt, amibe a `pyvirtualcam` ír. Aztán:

```cmd
python -m venv .venv
.venv\Scripts\activate
python -m pip install opencv-python mediapipe pyvirtualcam numpy pillow scikit-learn joblib
python memcam.py --preview
```

Python 3.10–3.12. A mediapipe-nak nincs hivatalos 3.13-as wheelje.

---

## Használat

```bash
./start.sh                    # telefon kameraként, scrcpy-n át
./start.sh --local            # beépített webkamera
./start.sh -- --anchor hand   # egyszeri felülbírálás a memcam.py-nak
```

A `start.sh` háttérben indítja a scrcpy-t, megvárja, amíg a loopback eszköz
tényleg élő lesz, aztán futtatja a MemCamet — kilépéskor pedig leállítja a
scrcpy-t, hogy ne maradjon árván. A gyakran állított beállítások a fájl
tetején vannak változóként.

Vagy közvetlenül:

```bash
python memcam.py --camera 0 --anchor face --preview
```

Aztán válaszd ki a virtuális kamerát a hívóprogramban: **Discord** →
Beállítások → Hang és videó → Kamera; **Teams (böngésző)** → a hívás
eszközbeállításainál.

Kilépés `Ctrl-C`, vagy `q` az előnézeti ablakban. Az ablak X gombja nem
működik — az OpenCV nem kezeli a keretet, csak billentyűre figyel.

A kimenet szándékosan nincs tükrözve. A hívóprogramok a saját előnézetedet
tükrözik, a kimenő adást nem — így látják helyesen a többiek.

### Kapcsolók

| Kapcsoló | Alap | Mit csinál |
|---|---|---|
| `--camera` | `0` | Kamera indexe |
| `--anchor` | `hand` | `hand` \| `face` \| `center` |
| `--threshold` | `0.62` | A MediaPipe küszöbe |
| `--custom-threshold` | `0.75` | A saját modell küszöbe |
| `--hold` | `5` | Ennyi képkockán kell tartani |
| `--duration` | `0` | Másodperc a képen. `0` = animáltnál egy végigjátszás, állóképnél 2,2 mp |
| `--size` | `0.34` | Mém szélessége a képkocka arányában (hand/center) |
| `--face-scale` | `1.6` | Arc-horgony: az arc szélességének hányszorosa |
| `--face-offset` | `0.0` | Arc-horgony: függőleges eltolás arcmagasságban. Negatív = feljebb |
| `--no-custom` | ki | Saját modell kihagyása, csak a beépítettek |
| `--preview` | ki | Helyi előnézeti ablak |
| `--output` | | Linux: v4l2loopback eszköz. Windowson hagyd üresen |

### Horgonyok

**`hand`** — a kéz fölé. A pozíció a kioldás pillanatában rögzül.

**`face`** — az arcodra, követi a fejed. A helyet és a méretet minden
képkockán újraszámolja az arc bounding boxából, szóval ha közelebb hajolsz,
együtt nő veled. Ha elveszik a detekció, az utolsó ismert helyen marad, nem
ugrik el. Gondolatbuborék-hatáshoz told feljebb:

```bash
python memcam.py --anchor face --face-scale 1.2 --face-offset -0.9
```

**`center`** — fixen a kép közepén.

---

## Mémek

Tedd a képeket a `memes/` mappába, a gesztus nevével:

```
memes/Thumb_Up.gif
memes/Salute.png
memes/FingerGuns.webp
```

Állókép: `.png .jpg .jpeg .bmp` · Animált: `.gif .webp .apng` (Pillow kell
hozzá). Az animált fájlok a saját kockaidőzítésükkel játszanak, és a
`--duration` végéig ismételnek.

Amelyik gesztushoz nincs kép, ott sárga szöveges plakát jelenik meg — ez jó a
beüzemeléshez, mert megmutatja, működik-e a felismerés.

Átlátszó hátterű PNG a legjobb, különösen `--anchor face` mellett, ahol a JPEG
fehér téglalapja nagyon látszik. A GIF csak bináris átlátszóságot tud; ha
tiszta kivágás kell, animált WebP vagy APNG a jobb.

Tartsd a fájlokat 300–400 px szélesség körül. Egy 500×500-as, 60 kockás GIF
BGRA-ban kicsomagolva nagyjából 60 MB, plusz az átméretezési gyorsítótár.

### Beépített gesztusnevek

`Thumb_Up` · `Thumb_Down` · `Victory` · `Open_Palm` · `Closed_Fist` ·
`Pointing_Up` · `ILoveYou`

---

## Saját gesztus tanítása

```bash
python collect_gestures.py    # 1/2/3 címke, SPACE felvétel, u visszavon 30-at, q ment+kilép
python train_gestures.py      # kiírja a gesture_model.pkl-t
```

Előbb írd át a `CLASSES` listát a `collect_gestures.py` tetején. A `None`
maradjon elsőnek, az kötelező.

A repóban lévő `gestures.csv` működő példa: 5387 minta öt osztályban. A gyűjtő
hozzáfűz a meglévő fájlhoz, szóval több menetben is gyűjthetsz.

**Ami tényleg eldönti a minőséget:**

**Változatosság, nem mennyiség.** 300 változatos minta többet ér, mint 2000
egyforma. Mozogj felvétel közben — fordulj el, gyere közelebb-távolabb, csináld
mindkét kézzel, változtass a megvilágításon.

**A `None` a legfontosabb osztály.** Minden, amit csinálsz, ami *nem* gesztus:
gépelsz, iszol, vakarod a fejed, integetsz. Nagy és változatos `None` nélkül a
modell mindent a legközelebbi gesztushoz sorol, és folyamatosan tüzel.

**Egyezzen a használati körülményekkel.** Kamera szemmagasságban, nagyjából
ott, ahol a képernyőd lenne. Ha az asztalon fekvő kamerával gyűjtesz, olyan
szögből tanítasz, amit a valódi webkamera sosem fog látni.

**Gyűjts a hibás esetekből.** Ez számít a legtöbbet, és ez a
legkevésbé magától értetődő. Fejlesztés közben a `Prayer` bármilyen két
összetett kézre bejött, bárhol — a modell az *alakot* tanulta meg, nem a
*helyet*, mert minden tanítómintája arcmagasságban készült. A confusion
matrix ebből semmit nem mutatott. A javítás nem több adat és nem
küszöbállítás volt, hanem pár száz célzott `None` minta arról, hogy a kezek
össze vannak téve, de *nem* az arcnál. A hamis triggerek gyakoriról 601-ből
2-re estek.

A confusion matrixot olvasd, ne a pontosságot. A pontosság félrevezet, amikor
a `None` túlsúlyban van.

```
                FingerGu  MiddleFi      None    Prayer    Salute
FingerGuns            79         0         1         0         0
MiddleFinger           0        94        11         0         0
None                   0         0       598         2         1
Prayer                 0         0        20       188         0
Salute                 0         0         1         0        83
```

A `None` **oszlopába** eső hibák azt jelentik, hogy a gesztust néha nem veszi
észre — kezelhető, a `--custom-threshold` és a `--hold` állítja. A `None`
**sorában** lévők hamis triggerek. Ha két valódi gesztus keveredik egymással,
az adat nem tudja őket elválasztani.

A `gesture_model.pkl` nincs a repóban. A pickle betöltéskor tetszőleges kódot
futtat, ezért publikálni rossz szokás — a CSV-ből amúgy is másodpercek alatt
előáll.

---

## Hibakeresés

**`Key was rejected by service` modprobe-nál** — a Secure Boot elutasít egy
aláíratlan modult. Futtasd a `./setup.sh`-t; kezeli a kulcsgenerálást, az
aláírást és a beiktatást.

**A modult nem lehet aláírni / `.ko.zst`** — tömörített modult nem lehet
közvetlenül aláírni. A kernel előbb kicsomagol, utána ellenőriz, tehát az
aláírásnak a tömörítés *alatt* kell lennie. Csomagold ki, írd alá, hagyd
tömörítetlenül.

**A Discord nem listázza az eszközt (Linux)** — szinte mindig a hiányzó
`exclusive_caps=1`. A Chromium-alapú alkalmazások csak capture eszközöket
mutatnak.

**`Not a video capture device` / `can't open camera by index`** —
`exclusive_caps=1` mellett a loopback eszköz addig nem capture eszköz, amíg
valaki nem ír rá. Ellenőrizd, hogy a scrcpy (vagy ami táplálja) még fut-e.

**Az OpenCV rossz backendet választ** — a `cv2.CAP_ANY` átcsúszhat az FFMPEG
backendre, ami saját, rövidebb eszközlistát használ, és nem találja meg a
v4l2loopback eszközt. A `memcam.py` kifejezetten `CAP_V4L2`-t kér Linuxon és
`CAP_DSHOW`-t Windowson.

**`pip.exe was blocked by your organization's Device Guard policy`** — a venv
által generált `pip.exe` aláíratlan. Használd helyette a `python -m pip
install ...` alakot, az az aláírt `python.exe`-n keresztül fut.

**`Could not find a version that satisfies the requirement mediapipe`** —
Python 3.13-on vagy. Telepíts mellé 3.12-t.

**scrcpy: `Dependency "sdl3" not found`** — a scrcpy 4.x SDL3-at igényel, ami
az Ubuntu 24.04-ben nincs. Válts a legfrissebb `v3` tagre; az SDL2-vel épül, és
a kameraforrást már tudja.

**scrcpy: `unrecognized option '--video-source=camera'`** — 2.2-nél régebbi
verzió. Az apt-os általában az.

**A hívóprogram nem találja a valódi webkamerát** — ez normális. Amíg a MemCam
fut, ő fogja a fizikai kamerát; egyszerre csak egy folyamat nyithatja meg.

**Akadozik** — `--anchor face` mellett két modell fut képkockánként. Próbáld:
`--width 960 --height 540`.

---

## Ami nincs benne

- Nincs konfigfájl — minden kapcsolóból megy
- Nincs hang
- Csak statikus pózok. Mozdulatsorokhoz a `Trigger` mellé kellene egy
  állapotgép, ami a pózok közti átmenetet ismeri fel
- Nincs képernyő-overlay. Ez virtuális kamera: csak a videóhívás képébe kerül
  bele, a képernyődre nem rajzol

---

## Követelmények

Python 3.10–3.12 · opencv-python · mediapipe · pyvirtualcam · numpy · pillow
(animált mémek) · scikit-learn + joblib (saját gesztusok)

Linux: `v4l2loopback`, plusz `scrcpy` és `adb`, ha telefont akarsz kameraként
használni. Windows: OBS Studio.

A modellfájlok első indításkor maguktól letöltődnek.
