# Persistenz und Neustartverhalten

## Ziel

Ein Home-Assistant-Neustart darf einen aktiven Wasserfehler nicht stillschweigend in einen unkritischen Ausgangszustand verwandeln.

Gleichzeitig dürfen unsichere, unvollständige Beobachtungen nicht nach einem Neustart als sichere Evidenz weitergerechnet werden.

---

# 1. Persistenter Store

Jeder Config Entry verwendet einen eigenen Home-Assistant-Store.

Schlüssel sinngemäß:

`water_leak_detection.runtime.<entry_id>`

Gespeichert werden unter anderem:

- Detection-Engine-Runtime
- High-Flow-Bypass-Endzeit
- Quittierungszustände
- zugelassene Lernwerte

---

# 2. Aktive Detektoren

Bestätigte `active`-Zustände werden persistiert.

Dazu gehören unter anderem:

- Phase
- Startzeit
- Erkennungszeit
- Event-ID
- Volumenbezug
- Reset-/Quiet-Kontext
- Burst-Grund

Damit bleibt ein ernstes Ereignis über einen Neustart erhalten.

---

# 3. Monitoring-Zustände

Die Engine kann Runtime-Zustände speichern, behandelt fehlende Messwerte aber konservativ.

Wenn die Quelle nicht verfügbar ist:

- noch unbestätigte Monitoring-Evidenz wird verworfen
- laufende Quiet-/Resetintervalle werden verworfen

Warum?

> Zeit ohne Messwert darf weder als Leck-Beweis noch als Null-Durchfluss-Beweis zählen.

---

# 4. Aktive Alarme bei Quellenverlust

Bereits bestätigte aktive Ereignisse bleiben aktiv.

Ein unbekannter Sensorzustand darf kein aktives Ereignis zurücksetzen.

Das ist die Konsequenz des Grundsatzes:

**unknown != 0 L/h**

---

# 5. High-Flow-Bypass

Gespeichert wird der absolute Endzeitpunkt.

Nach einem Neustart:

- liegt der Zeitpunkt noch in der Zukunft → Bypass wird wiederhergestellt
- ist er bereits abgelaufen → Bypass bleibt aus

Dadurch kann ein Neustart einen Bypass nicht unbegrenzt verlängern.

---

# 6. Quittierungen

Der Quittierungszustand wird pro Event-ID gespeichert.

Gespeichert werden:

- globale Quittierung
- welches Gerät global quittiert hat
- Zeitpunkt
- persönliche Mutes

Beim physischen Event-Ende wird der Quittierungszustand dieser Event-ID entfernt.

---

# 7. Lernmodell

Persistiert werden ausschließlich bereits zugelassene, abgeschlossene normale Episoden.

Nicht gespeichert wird:

- eine gerade laufende, noch nicht abgeschlossene Lern-Episode

## Warum?

Eine Episode, die direkt vor einem Neustart oder Sensorausfall abbricht, kann nicht zuverlässig als normal bewertet werden.

Darum wird sie verworfen statt nachträglich „fertiggedacht“.

---

# 8. Volumen nach Ausfallzeiten

Wenn kein Gesamtverbrauchssensor zur Verfügung steht, wird Volumen aus Durchfluss und Zeit integriert.

Nach einer großen Zeitlücke wird die rückwirkende Integration begrenzt.

Damit wird nicht angenommen, dass der letzte bekannte Durchfluss während einer beliebig langen HA-Ausfallzeit unverändert weiterlief.

---

# 9. Betriebszustand nach Reload

Bei einem Konfigurations-Reload:

1. alter Manager wird sauber entladen
2. aktueller Store wird gespeichert
3. neuer Manager lädt den Zustand
4. Quellenlistener und 10-Sekunden-Tick werden neu registriert
5. aktuelle Quellen werden sofort neu ausgewertet

---

# 10. Sicherheitsfolgen

Persistenz soll zwei gegensätzliche Fehler vermeiden:

### Falsch negative Entwarnung

Ein aktiver Burst darf nach Neustart nicht einfach verschwinden.

### Falsch positive Evidenz

Ein unvollständig beobachteter Messzeitraum darf nicht als vollständiger Leak- oder Lernbeweis gelten.

Darum sind aktive Events langlebig, unbestätigte Zeitfenster bei fehlender Evidenz dagegen konservativ.

## Korrekturrunde 1 (unveröffentlicht)

Sicherheitsübergänge werden mit einer festen Frist von 1 s gespeichert; Mess-/Lernupdates
mit 10 s ab dem ersten vorgemerkten Update. Weitere Samples verschieben die Frist nicht.
Event-Loop-Blockaden und Speicherfehler können diese Fristen überschreiten.
Pro Event und Empfänger wird die erfolgreiche Annahme durch den Notify-Service persistiert.
Nicht verfügbare/fehlgeschlagene Dienste werden erneut versucht; Quittierungen bleiben wirksam.
Ein Absturz zwischen Versand und Speicherung kann eine doppelte Meldung verursachen.

Negative, nicht endliche und überalterte Messungen sind keine Ruhe-Evidenz.
`last_reported` unterscheidet neue identische Meldungen von eingefrorenen Zuständen;
standardmäßig beträgt das maximale Alter 30 s (konfigurierbar). Laufzeitintervalle
verwenden eine monotone Uhr; Neustarts setzen unbestätigte Intervalle zurück.
Zählerreset, unplausibler Sprung und Quellenwechsel lösen den alten Volumenbezug.
Aktive Leckage und Absperranforderung bleiben dabei erhalten. Eingefrorene oder fehlende
Totalwerte werden durch Durchflussintegration ersetzt. Die fachlichen Findings
F02/F04/F08 und die Rapid-Rise-Definition bleiben für eine separate Spezifikation offen.
