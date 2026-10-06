# Adaptives Lernen und Hydraulik

## Ziel

Haushalte unterscheiden sich stark.

Ein statischer High-Flow-Grenzwert kann deshalb entweder:

- zu viele Fehlalarme erzeugen oder
- bei sehr hohem normalem Verbrauch zu unempfindlich sein

Der Wasserwächter kombiniert daher:

- konservative feste Basisgrenzen
- kontinuierliches Lernmodell
- optional manuell bekanntes Maximum
- hydraulische Plausibilitätsgrenzen

Das Lernmodell beeinflusst **High Flow** und **Burst Leak**.

Slow Leak und Low Flow bleiben bewusst fachlich statisch.

---

# 1. Was wird gelernt?

Es werden nicht einzelne Sekundenwerte als „normal“ gespeichert.

Stattdessen lernt das System **abgeschlossene normale Wasserverbrauchsepisoden**.

Eine Episode:

- beginnt ab etwa 1 L/h
- verfolgt ihren maximalen Durchfluss
- gilt erst nach 120 Sekunden sehr niedrigen Durchflusses als abgeschlossen

Erst dann kann ihr Peak als Lernwert aufgenommen werden.

---

# 2. Was wird nicht gelernt?

Eine Episode wird ausgeschlossen, sobald sie als verdächtig gilt.

Insbesondere ausgeschlossen:

- aktiver Leckalarm
- High-Flow-Monitoring
- Burst-Leak-Monitoring
- Zeit mit aktivem High-Flow-Bypass

## Warum auch High/Burst-Monitoring?

Das Lernmodell darf nicht warten, bis ein außergewöhnlicher Wert schon zum bestätigten Alarm geworden ist.

Sonst könnte ein knapp vor der Bestätigung endendes gefährliches Ereignis als „normal“ gespeichert werden.

## Warum Bypass-Zeiten nicht lernen?

Poolbefüllung ist ein gutes Beispiel.

Der Benutzer sagt mit dem Bypass:

> Dieser hohe Verbrauch ist gerade bewusst erlaubt.

Er sagt nicht:

> Dieser Verbrauch soll künftig die normale Haushaltsgrenze definieren.

Darum ist Bypass-Verbrauch kein Lernmaterial.

---

# 3. Rolling Window

Standard:

**30 Tage**

Zulässiger Expertenbereich:

typischerweise 7–90 Tage.

Alte Lernwerte außerhalb des Fensters werden entfernt.

Dadurch passt sich das Modell kontinuierlich an saisonale oder dauerhafte Verhaltensänderungen an.

---

# 4. Kurz- und Langzeitreferenz

Aus den zugelassenen Episoden werden robuste 95%-Referenzen berechnet.

### Langzeit

95. Perzentil des gesamten aktuellen Lernfensters.

### Kurzzeit

95. Perzentil der letzten bis zu 7 Tage.

### Kombinierte Lernreferenz

Wenn beide vorhanden sind:

`0,65 × Kurzzeit + 0,35 × Langzeit`

Zusätzlich darf die kombinierte Referenz nicht unter:

`0,85 × Langzeit`

fallen.

## Begründung

Die Kurzzeitreferenz sorgt für Anpassungsfähigkeit.

Die Langzeitreferenz verhindert, dass wenige ruhige Tage die Erwartung zu schnell absenken.

---

# 5. Confidence

Das Lernmodell zeigt offen, wie vertrauenswürdig seine Datenbasis ist.

## Insufficient

Wenn:

- weniger als 5 Lernwerte oder
- weniger als 3 abgedeckte Tage

Dann darf das gelernte Maximum die Schutzgrenzen **nicht nach oben anheben**.

## Learning

Ab ausreichender Mindestdatenbasis, aber noch nicht zuverlässig.

Voraussetzung für Reliable ist noch nicht erfüllt.

In dieser Phase fließt nur:

`85 % des gelernten Maximums`

in die Normalreferenz ein.

## Reliable

Bei mindestens:

- 20 Lernwerten und
- ausreichend abgedeckten Tagen

Die erforderlichen Tage entsprechen:

`min(14; max(7; Lernfenster / 2))`

Dann darf die vollständige gelernte Referenz verwendet werden.

---

# 6. Manuell bekanntes Maximum

Optional kann ein manuell bekanntes normales Maximum angegeben werden.

Ist es > 0, wird es unabhängig vom Lernstatus als Referenz berücksichtigt.

Die Normalreferenz ist dann das Maximum aus:

- manuellem Wert
- confidence-gewichteter Lernreferenz

---

# 7. Adaptive High-Grenze

Basis:

**600 L/h**

Kandidat:

`max(Basis; Normalreferenz × 1,20)`

Diese Grenze darf aber nicht beliebig wachsen.

Sie wird durch die hydraulische Plausibilität nach oben begrenzt.

---

# 8. Adaptive Burst-Grenze

Basis:

**2000 L/h**

Kandidat:

`max(Basis; Normalreferenz × 1,80)`

Zusätzlich gilt:

- hydraulische Obergrenze
- Burst soll nach Möglichkeit mindestens 10 % oberhalb der effektiven High-Grenze liegen

---

# 9. Hydraulisches Plausibilitätsmodell

Eingaben:

- Nennweite / Rohrdurchmesser
- statischer Druck

Referenzstandard:

- DN25
- 3,5 bar

Das Modell berechnet aus Querschnitt und einer druckskalierten praxisnahen Fließgeschwindigkeit einen Referenzdurchfluss.

Die Geschwindigkeit wird bewusst begrenzt.

## Ganz wichtig

Diese Berechnung ist **kein exaktes physikalisches Maximum**.

Der tatsächliche Durchfluss hängt zusätzlich ab von:

- Wasserzähler
- Druckminderer
- dynamischem Druck
- Rohrlänge
- Bögen und Armaturen
- Hausnetz
- vorgelagertem Versorgungsnetz

Deshalb heißt die Funktion bewusst **Plausibilitätsmodell**.

---

# 10. Warum eine hydraulische Obergrenze?

Ein rein selbstlernendes System könnte sich theoretisch durch wiederholt hohe Verbräuche immer unempfindlicher machen.

Die hydraulische Hülle verhindert:

> „Sehr hoch wurde oft gesehen, also muss noch viel höher erst gefährlich sein.“

Die adaptive High-Grenze reserviert außerdem Abstand zum Burst-Bereich.

---

# 11. Sensoren für Transparenz

Home Assistant zeigt unter anderem:

- Gelernter Maximaldurchfluss
- Lernzuverlässigkeit
- Lernabdeckung
- Hydraulischer Referenzdurchfluss
- Effektive High-Flow-Grenze
- Effektive Burst-Leak-Grenze

Das adaptive Verhalten soll dadurch nachvollziehbar bleiben und keine Blackbox sein.

---

# 12. Lernmodell zurücksetzen

Aktion:

`water_leak_detection.reset_learning`

Sie löscht zugelassene Lernwerte.

Nicht zurückgesetzt werden dadurch:

- aktive Leckereignisse
- Detector-Einstellungen
- aktuelle physische Alarmbedingungen

Ein Reset des Lernmodells ist keine Alarmquittierung.
