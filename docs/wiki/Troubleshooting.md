# Fehlerbilder und Troubleshooting

## 1. Integration erscheint nach HACS-Installation nicht

Prüfen:

1. HACS hat das Repository als **Integration** installiert.
2. Home Assistant wurde vollständig neu gestartet.
3. Verzeichnis vorhanden:
   `<config>/custom_components/water_leak_detection`
4. Home-Assistant-Logs nach `water_leak_detection` durchsuchen.

---

# 2. Alte Vorabversion war als Helfer sichtbar

Eine frühe Vorabversion war fälschlich als Helper klassifiziert.

Dadurch konnte ein alter Config Entry unter **Helfer** statt unter **Integrationen** erscheinen und die neue Einrichtung derselben Domain blockieren.

Saubere Bereinigung:

1. alten Wasserwächter-/Water-Leak-Eintrag unter Helfer löschen
2. dadurch verschwinden auch alle zu diesem Config Entry gehörenden Entitäten
3. Home Assistant neu starten
4. aktuelle Integration neu einrichten

Dass mehrere zugehörige „Helfer“ gemeinsam verschwinden, ist in diesem Sonderfall korrekt: Sie gehörten alle zum selben alten Config Entry.

Nicht eigenständig `.storage/core.config_entries` editieren, solange eine normale Entfernung über Home Assistant möglich ist.

---

# 3. Durchflusssensor wird abgelehnt

Der Sensor muss eine unterstützte Durchflusseinheit besitzen.

Typische Einheiten:

- L/h
- L/min
- L/s
- m³/h
- m³/min
- m³/s

Ein Sensor ohne interpretierbare Einheit wird nicht geraten.

---

# 4. Kein Gesamtverbrauchssensor vorhanden

Der Gesamtverbrauch ist optional.

Die Erkennung funktioniert weiterhin.

Das Ereignisvolumen kann dann aus Durchfluss und Zeit abgeschätzt werden.

---

# 5. Keine Benachrichtigungsempfänger auswählbar

Prüfen:

- Home Assistant Companion App ist eingerichtet
- ein `notify.mobile_app_*`-Dienst existiert
- ein passender `device_tracker.*` existiert

Empfänger können sowohl:

- bei der Ersteinrichtung als auch
- später unter **Konfigurieren → Benachrichtigungsempfänger**

verwaltet werden.

---

# 6. „Für alle quittieren“ fehlt

Der Button wird nur angezeigt, wenn:

- der Empfänger globale Quittierung erlaubt und
- sein Tracker aktuell `home` ist

Das Backend prüft dies beim Klick erneut.

---

# 7. Globale Quittierung wird abgelehnt

Prüfen:

- richtiger Tracker ausgewählt
- Trackerzustand exakt `home`
- Empfänger darf global quittieren
- Event ist noch aktiv
- Empfänger wurde nicht zwischenzeitlich aus der Integration entfernt

Ein Gerät außerhalb der Home-Zone kann weiterhin nur für sich selbst stummschalten.

---

# 8. Alarm ist quittiert, aber weiterhin rot/aktiv

Das ist beabsichtigt.

Quittierung beendet nur weitere Benachrichtigungen für den jeweiligen Scope.

Der Detektor bleibt aktiv, bis seine physische Resetbedingung erfüllt ist.

Siehe:

- [Leckageklassen und Erkennungslogik](Leckageklassen-und-Erkennungslogik)
- [Alarmstufen und Quittierung](Alarmstufen-und-Quittierung)

---

# 9. High-Flow-Bypass unterdrückt einen Alarm nicht

Der Bypass unterdrückt ausschließlich **High Flow**.

Nicht unterdrückt werden:

- Slow Leak
- Low Flow
- Burst Leak

Das ist eine Sicherheitsentscheidung und kein Fehler.

---

# 10. Burst wird trotz Bypass ausgelöst

Das ist ausdrücklich beabsichtigt.

Ein geplatzter Schlauch während einer Poolbefüllung soll weiterhin erkannt werden.

---

# 11. Gelernter Maximaldurchfluss wirkt unplausibel

Prüfen:

- Gelernter Maximaldurchfluss
- Lernzuverlässigkeit
- Lernabdeckung
- Effektive High-Grenze
- Effektive Burst-Grenze
- manuell bekanntes Maximum
- Rohrdurchmesser / Druck

Bei Bedarf kann das Lernmodell über:

`water_leak_detection.reset_learning`

zurückgesetzt werden.

---

# 12. Sensor wird unavailable

Unavailable wird **nicht** als 0 interpretiert.

Folge:

- Monitoring kann verworfen werden
- aktive Lecks bleiben bestehen
- Resetzeit läuft nicht auf unbekannter Evidenz weiter
- laufende Lern-Episode wird verworfen

---

# 13. Water Shut Off bleibt trotz Quittierung aktiv

Das ist korrekt.

Die Absperranforderung hängt von:

- aktiven Detektoren und
- deren Shut-Off-Zuordnung

ab.

Quittierung gehört zur Alarmierungsschicht und ändert diese Entscheidung nicht.

---

# 14. Debug-Logging

Temporär:

```yaml
logger:
  default: info
  logs:
    custom_components.water_leak_detection: debug
```

Nach der Fehlersuche Debug-Logging wieder entfernen.

---

# 15. Issue melden

Repository:

`https://github.com/BeGiBue/homeassistant-water-leak-detection/issues`

Hilfreiche Angaben:

- Home-Assistant-Version
- Wasserwächter-Version
- Quell-Entity-IDs und Einheiten
- relevante Einstellungen
- Logauszug
- reproduzierbare Schritte

Keine Zugangstokens oder Geheimnisse posten.
