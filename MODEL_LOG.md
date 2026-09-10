# Modell-changelog

A `gesture_model.pkl` verziótörténete. Minden bejegyzés: mi változott az
adatban, mi lett az eredmény, mit érdemes tudni róla. A `.pkl` fájlok maguk
nincsenek verziókezelve (lásd README — pickle, nem publikálandó), ez a napló
a helyi `gesture_model_vX.pkl` másolatokhoz tartozik.

Legújabb felül.

---

## v3.1 — 12 583 minta, 7 osztály

```
FingerGuns 1256 · MiddleFinger 1269 · None 5543 · Okay 1394 · Prayer 1095 · Salute 1138 · Telephone 888
```

**Változás:** +344 `Okay` minta, +286 `None` minta a v3.0-hoz képest.

**Eredmény:** `Okay` recall 0,950 (v3.0-hoz képest kismértékben esett, valószínűleg
a nagyobb változatosság miatt — ez rendben van, nem visszalépés). `Telephone`
recall tovább esett: 0,898 (v3.0: 0,916; v2.6, Okay előtt: 0,916).

**Nyitott kérdés:** a `Telephone` recall monoton esik minden kör óta, amióta
az `Okay` bekerült (0,916 → 0,898), és a hibák szinte mind a `None` felé
mennek (17/178, egy híján mindegyik). Két lehetséges ok, tesztelésre vár:

1. Anatómiailag a `Telephone` póz kevéssé variálható, ezért a tanítómintái
   túl hasonlóak egymáshoz — a modell a "pontosan pózolt" verziót tanulta
   meg, nem a hétköznapi, kevésbé feszes tartást.
2. Az `Okay` és a `Telephone` jellemzőtérben közelebb kerülhettek egymáshoz,
   ahogy az `Okay` mintaszáma nőtt — ezt a mátrix nem mutatja egyértelműen
   (nincs Telephone↔Okay keveredés), inkább az első magyarázat valószínű.

**Következő lépés, ha javítod:** célzott, *lazán* tartott `Telephone` minták
felvétele (nem pózolva, ahogy éles használatban tartanád), a `Prayer`
javításánál bevált recepttel — lásd a v2.1–v2.2 bejegyzéseket lejjebb.

---

## v3.0 — 11 953 minta, 7 osztály (Okay bevezetve)

```
FingerGuns 1256 · MiddleFinger 1269 · None 5257 · Okay 1050 · Prayer 1095 · Salute 1138 · Telephone 888
```

**Változás:** új osztály, `Okay` (1050 minta), a `None` és a többi változatlan
maradt a v2.6-hoz képest.

**Eredmény:** `Okay` recall 0,976 — tisztán elválik a többitől, semmilyen
keresztirányú tévesztés nem jelenik meg vele kapcsolatban a mátrixban.
`Telephone` recall 0,916, ugyanaz, mint v2.6-nál — az `Okay` bevezetése
önmagában nem rontott rajta ezen a ponton, a romlás csak a v3.1-es körben
jelentkezett.

---

## v2.6 — 10 903 minta, 6 osztály

```
FingerGuns 1256 · MiddleFinger 1269 · None 5257 · Prayer 1095 · Salute 1138 · Telephone 888
```

**Változás:** +237 `None` minta a v2.5-höz képest.

**Eredmény:** `MiddleFinger` és `Prayer` recall 0,969 → 0,986 javult.
`FingerGuns` 0,956-on stagnál. Ez volt az utolsó tisztán 6-osztályos kör az
`Okay` bevezetése előtt.

---

## v2.5 — 10 666 minta, 6 osztály

```
FingerGuns 1256 · MiddleFinger 1269 · None 5020 · Prayer 1095 · Salute 1138 · Telephone 888
```

**Változás:** +349 `None` minta a v2.4-hez képest.

**Eredmény:** stabil, minden osztály 0,96 recall fölött. A `None`-bővítés
sorozat (v2.1 óta) ezen a ponton már inkább finomhangolás, mint érdemi
javítás — a nagy ugrások a korábbi köröknél történtek.

---

## v2.4 — 10 317 minta, 6 osztály

```
FingerGuns 1256 · MiddleFinger 1269 · None 4671 · Prayer 1095 · Salute 1138 · Telephone 888
```

**Változás:** +619 `None` minta a v2.3-hoz képest.

**Eredmény:** `Prayer` recall visszaesett 0,977-ről 0,959-re (később, v2.5-nél
helyreállt) — egyetlen köri ingadozás, nem tartós trend.

---

## v2.3 — 9698 minta, 6 osztály (Telephone stabilizálva)

```
FingerGuns 1256 · MiddleFinger 1269 · None 4052 · Prayer 1095 · Salute 1138 · Telephone 888
```

**Változás:** +366 `None` minta a `Telephone` bevezetése (9332 minta,
nem mentett köztes állapot) óta.

**Eredmény:** `Telephone` recall 0,916 → 0,944 javult a plusz `None`-tól —
ez volt az első jele, hogy a `Telephone`↔`None` határ `None`-oldali
bővítéssel javítható. A v3.1-es visszaesés fényében ez a javulás csak
részleges és nem tartós volt.

---

## v2.2 — 8444 minta, 5 osztály

```
FingerGuns 1256 · MiddleFinger 1269 · None 3686 · Prayer 1095 · Salute 1138
```

**Változás:** +837 `None` minta a v2.1-hez képest. Ez után került be a
`Telephone` osztály (9332 mintás, nem mentett köztes tanítás).

**Eredmény:** `None` recall 0,993, továbbra sem keveredik semelyik gesztussal.

---

## v2.1 — 7607 minta, 5 osztály

```
FingerGuns 1256 · MiddleFinger 1269 · None 2849 · Prayer 1095 · Salute 1138
```

**Változás:** +553 `None` minta a v2-höz képest — célzottan olyan pózokból,
amik korábban (a mai adatgyűjtés előtti, régi modellnél) hamis triggert
okoztak: kéz összetéve, de nem az arcnál; egy kéz döntve az arc közelében.
Ugyanaz a recept, ami a `Prayer` eredeti hibáját javította (lásd README,
"Collect from your failure cases").

**Eredmény:** minden osztály 0,96 fölé javult, `None` precision 0,944 → 0,958.

---

## v2 — 7054 minta, 5 osztály (friss adatgyűjtés)

```
FingerGuns 1256 · MiddleFinger 1269 · None 2296 · Prayer 1095 · Salute 1138
```

**Változás:** a `gestures.csv` teljesen újragyűjtve nulláról (a régi,
felhalmozott adat `gestures_v1.csv` néven megmaradt referenciának). A cél a
korábbi modellben (v1) tapasztalt inkonzisztenciák kiküszöbölése volt tiszta,
egységes gyűjtéssel.

**Eredmény:** kereszttévesztés nulla minden gesztuspár között. `None`
precision 0,948, ez volt a fő gyengepont — innen indult a v2.1–v2.6-os
`None`-bővítő sorozat.

---

## v1 — 5387 minta, 4 osztály (a Prayer-hiba javítása után)

```
FingerGuns 402 · MiddleFinger 523 · None 3003 · Prayer 1041 · Salute 418
```

Ez a modell előzi meg a mai teljes adat-újragyűjtést. A `Prayer` itt már a
javított verzió — eredetileg bármilyen két összetett kézre triggerelt,
helytől függetlenül, mert a modell alakot tanult, nem pozíciót. A javítás
célzott negatív mintákkal történt (lásd README). Innen a `gestures_v1.csv`
őrzi az adatot, ha vissza kellene nyúlni hozzá.

---

## Tanulságok, amik minden körben visszaköszöntek

**A `None`-bővítés önmagában nem old meg mindent.** v2.1–v2.6 hat kör alatt
+2961 `None` mintát adott hozzá, és a hozam köronként csökkent — az első pár
kör (v2.1, v2.2) hozta a nagy javulást, utána inkább finomhangolás volt.

**Új osztály bevezetése megmozgatja a szomszédait.** A `Telephone` recall-ja
minden alkalommal érzékenyen reagált, amikor másik osztály (előbb saját
`None`-bővítés, majd az `Okay` bevezetése) változott mellette — ez arra utal,
hogy a `Telephone` a jellemzőtérben szűkebb, kevésbé védett régiót foglal el,
mint a többi gesztus.

**A confusion matrix a saját gyűjtési szokásaidat is méri, nem csak a
modellt.** Ha egy gesztusnak anatómiailag kevés a természetes variánsa,
a teszthalmaz is homogénebb lesz, és a validáció optimistább lehet, mint
amit élesben tapasztalsz. Erre a `Telephone` a példa — érdemes élő teszttel
is megerősíteni, nem csak a számra hagyatkozni.
