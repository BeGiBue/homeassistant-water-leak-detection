# Architektur und Datenfluss

## Überblick

Der Wasserwächter ist bewusst als Backend-Integration aufgebaut. Die eigentliche Sicherheitslogik liegt nicht in einer Lovelace-Karte, sondern vollständig in Home Assistant.

Vereinfachter Datenfluss:

```text
Durchflusssensor ─┐
                  ├─> Normalisierung ─> Manager ─> Detection Engine
Gesamtverbrauch ──┘                       │              │
                                         │              ├─> Leck-Events
                                         │              ├─> Alarmstatus
                                         │              └─> Shut-Off-Request
                                         │
                                         ├─> Adaptive Learner
                                         ├─> Hydraulikmodell
                                         ├─> Notification Controller
                                         ├─> HA-Entitäten
                                         └─> Persistenter Store
```

## 1. Manager

Der `WaterLeakManager` ist die Laufzeitkoordination einer eingerichteten Instanz.

Er übernimmt:

- Lesen der Home-Assistant-Quellzustände
- Normalisierung der Messwerte
- Ausführung der Detektoren
- Berechnung adaptiver High-/Burst-Grenzen
- Übergabe sicherer Episoden an das Lernmodell
- Erzeugen von Home-Assistant-Events
- Verwaltung des High-Flow-Bypass
- Speichern und Wiederherstellen des Laufzeitzustands
- Aktualisierung der bereitgestellten Entitäten

### Ausführungszeitpunkte

Die Auswertung erfolgt:

- bei Zustandsänderung eines konfigurierten Quellsensors
- zusätzlich zyklisch alle **10 Sekunden**

Dadurch laufen Zeitbedingungen weiter, auch wenn der Quellsensor bei konstantem Durchfluss nicht fortlaufend neue Zustände erzeugt.

## 2. Detection Engine

Die Detection Engine ist weitgehend Home-Assistant-unabhängig und bildet vier getrennte Zustandsautomaten ab:

- Slow Leak
- Low Flow
- High Flow
- Burst Leak

Jeder Automat kennt die Phasen:

- `idle`
- `monitoring`
- `active`

### Monitoring vs. Active

`monitoring` bedeutet:

> Es liegen verdächtige Messwerte vor, aber die zeitliche bzw. mengenmäßige Bestätigung ist noch nicht erfüllt.

`active` bedeutet:

> Der Detektor hat seine Erkennungsbedingung bestätigt und erzeugt ein Ereignis mit eigener Event-ID.

Diese Trennung verhindert, dass ein kurzer normaler Wasserverbrauch sofort als Leckage gemeldet wird.

## 3. Event-IDs

Beim Übergang auf `active` erzeugt jeder Detektor eine eindeutige Ereignis-ID.

Sinngemäß:

`slow_leak_20261006T123456_a1b2c3`

Quittierungen sind immer an genau diese Event-ID gebunden.

Endet die physische Situation und tritt später erneut auf, entsteht eine neue Event-ID und damit ein vollständig neuer Alarmzyklus.

## 4. Messwertnormalisierung

Der Kern arbeitet unabhängig von der Einheit des Quellsensors.

Intern:

- Durchfluss: **L/h**
- Volumen: **L**

Negative Durchflusswerte werden für die Detektion auf 0 begrenzt.

## 5. Verhalten bei Sensorausfall

Wenn der Durchflusssensor `unknown`, `unavailable` oder nicht sinnvoll konvertierbar ist:

- wird die Quelle als nicht verfügbar markiert
- laufende, noch unbestätigte `monitoring`-Phasen werden verworfen
- laufende Quiet-/Reset-Zeitfenster werden verworfen
- bereits bestätigte `active`-Ereignisse bleiben aus Sicherheitsgründen aktiv
- die aktuelle unvollständige Lern-Episode wird verworfen

Grund:

> Fehlende Messwerte sind kein Beweis für 0 L/h.

## 6. Volumenberechnung

Wenn ein kumulierter Gesamtverbrauchssensor vorhanden ist, wird das Ereignisvolumen bevorzugt aus dessen Differenz berechnet.

Falls nicht, integriert die Engine den Durchfluss über die Zeit.

Nach längeren HA-Ausfallzeiten wird nicht beliebig viel Volumen rückwirkend integriert; große Zeitlücken werden begrenzt.

## 7. Adaptive Grenzwerte

Slow und Low verwenden bewusst statische fachliche Bänder.

High und Burst können dagegen adaptive Grenzwerte verwenden.

Dadurch wird vermieden, dass ein gelerntes hohes Haushaltsmaximum den Low-Flow-Bereich ungewollt nach oben verschiebt.

## 8. Notification Controller

Der Notification Controller ist von der Detection Engine getrennt.

Er verwaltet:

- konfigurierbare Companion-Empfänger
- pro Ereignis persönliche Mutes
- globale Quittierung
- Home-Zone-Prüfung
- Re-Notification beim Heimkommen
- Critical-Payload für Burst

Er kann einen Detektor nicht zurücksetzen.

## 9. Water-Shut-Off-Schicht

Die Engine berechnet aus allen **aktiven** Detektoren und deren konfigurierter Zuordnung eine unabhängige boolesche Absperranforderung.

Diese wird als Home-Assistant-Binary-Sensor bereitgestellt.

Die physische Ventilsteuerung erfolgt in der aktuellen Version bewusst außerhalb der Integration über eine Home-Assistant-Automation.

## 10. Persistenz

Persistiert werden unter anderem:

- Detector-Runtime
- Event-ID und Startzeit
- Quittierungszustände
- High-Flow-Bypass-Endzeit
- zugelassene Lernwerte

Nicht persistiert wird eine noch unvollständige Lern-Episode. Eine vor einem Neustart nur teilweise beobachtete Episode ist keine vertrauenswürdige Grundlage für „normales Verhalten“.
