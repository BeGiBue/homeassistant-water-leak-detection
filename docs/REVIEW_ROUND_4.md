# Abschlussbericht – Korrekturrunde 4

Basis: `review/korrekturrunde-3`, `bd7e161957968cd87a308db61e8d88c33c71f223`.
Der Remote-Head wurde exakt geprüft. Arbeitsbranch: `review/korrekturrunde-4`.
Bearbeitet wurden ausschließlich F05 und F15 sowie ihre Regressionstests.

## F05 – Wechselnde Report-Modi

**Ursache:** Nach Qualifikation von 120 Sekunden schrumpfte die Grenze zum
Verwerfen der Kadenzhistorie auf 540 Sekunden. Jeder folgende 600-Sekunden-Report
löschte damit auch die Kandidaten, bevor der längere Modus qualifizieren konnte.

**Änderung:** Die automatische Grenze zum Verwerfen der Kadenzhistorie fällt
nicht mehr unter den bisherigen Anlaufwert von 900 Sekunden. Qualifizierte
kurze Modi und wiederkehrende längere Kandidaten bleiben dadurch parallel
erhalten. Die Evidenzentscheidung bleibt unverändert: Zwei vergleichbare
unbekannte Intervalle innerhalb von vier Reports qualifizieren einen Modus
erst für zukünftige Intervalle. Beide lernenden Lücken erhalten null Sekunden.
Explizit konfigurierte Grenzen, Verfügbarkeitsprüfung und Detektorregeln bleiben
unverändert; echte lange Ausfälle löschen weiterhin die Kadenzhistorie.

**Tests:** Sechs Stunden 120/600 und 600/120, jeweils mit und ohne acht vorherige
120-Sekunden-Intervalle; 60/120 in beiden Reihenfolgen; interner Tick ohne Evidenz;
einzelne/seltene 600-Sekunden-Ausreißer; keine rückwirkende Zeitgutschrift;
7200-Sekunden-Ausfall und erneute Qualifikation; explizite Ausfallgrenze.

**Grenzen:** Report-Endpunkte beweisen keinen durchgehenden physischen Fluss.
Unbekannte Intervalle unterbrechen weiterhin Monitoring/Quiet und können die
Erkennung verzögern. Automatisches Lernen bleibt auf wiederkehrende Muster
innerhalb der bestehenden Kandidaten- und Ausfallgrenzen beschränkt.

## F15 – Bereits gültige Historie nach UTC-Rückstellung

**Ursache:** Restore verwarf jedes Sample oberhalb der aktuellen UTC, auch wenn
es vor einer später beobachteten Rückstellung gültig aufgenommen worden war.

**Änderung:** Der Learner vergleicht beobachtete UTC mit dem monotonen
Zeitfortschritt. Bei einer Rückstellung dokumentiert er die obere UTC-Grenze
bereits zugelassener Samples. Beim Speichern wird ein begrenzter
`clock_rollback`-Kontext mit Speicher-UTC und dieser Grenze persistiert.
Restore akzeptiert zukünftige Samples ausschließlich innerhalb eines gültigen
Kontexts mit höchstens 24 Stunden Zukunftsdifferenz. Fehlender/beschädigter
Kontext, eine weitere unbewiesene Offline-Rückstellung und Zeitstempel jenseits
der dokumentierten Grenze bleiben ausgeschlossen. Die ursprünglichen realen
UTC-Samplezeitstempel werden unverändert gespeichert; Rolling Window bleibt UTC.
Episode-, Quiet-, Detektor- und Bypass-Zeitbasis bleiben monotonic.

**Tests:** Sample zuerst abschließen, anschließend UTC −1/−2/+1 Stunde oder
mehrere Korrekturen, jeweils mit/ohne weiteren Report; echter sauberer
Unload/Store-Restore und erneuter Restart; 29/31-Tage-Fenster; beschädigte
Future-Samples und Clock-Kontexte; fehlender Korrekturbeleg; Offline-Rückstellung;
24-Stunden-Grenze; unveränderte laufende Episode/Quiet. Bestehende Detektor- und
Bypass-Uhrkorrekturtests bestehen ebenfalls.

**Grenzen:** Ohne beobachteten/persistierten Korrekturkontext werden Future-Samples
weiterhin verworfen. Bei mehr als 24 Stunden verbleibender Zukunftsdifferenz
beim Speichern greift die konservative Behandlung ebenfalls.

## Prüfergebnisse

Umgebung: Python 3.14.2, Home Assistant 2026.9.4, pytest 9.1.1, Ruff 0.17.0.

| Prüfung | Ergebnis |
|---|---|
| Gesamte pytest-Suite | 517 bestanden: alle 490 bisherigen + 27 neue |
| Runde-4-Tests separat | 27 bestanden |
| Safety-Auswahl | 106 bestanden, 411 abgewählt |
| Ruff | bestanden |
| Python-Kompilierung | 40 Dateien bestanden; Kompilate außerhalb des Repositorys |
| JSON | 4 Dateien gültig |
| YAML | 6 Workflows und services.yaml gültig |
| Bash-Syntax | 10 Workflow-Run-Blöcke und Release-Skript bestanden |
| Hassfest, HA Core 2026.9.4 | alle Integrationsprüfungen, 1 Integration, 0 ungültig |
| AST-Vergleich | 46 bestehende Methoden der geänderten Dateien identisch |
| Zusätzlicher AST-Schutz | Evidenzentscheidung, übrige Serialisierung, Episode/Quiet identisch |
| Dateivergleich | 83 bestehende Dateien bytegleich; alle bestehenden Tests unverändert |
| git diff --check | bestanden |

Safety-Aufruf: `pytest -q -k 'safety or bypass or ack or negative or invalid_flow or invalid_source or lower or new_event or unavailability'`.
Hassfest lief wegen der lokalen Forkserver-Sandboxgrenze mit Multiprocessing
`fork` und zwei Prozessen; keine Plugins/Prüfungen wurden übersprungen.
pytest meldet eine bekannte DeprecationWarning aus Home Assistants HTTP-Abhängigkeit.

Engine einschließlich `_sample_slow`, `_sample_low`, `_sample_high`, `_sample_burst`,
Rapid Rise, `DetectorSettings`, Totalzähler- und Alarm-Restore-Logik ist bytegleich.
Notification Routing, Control Plane, Setup/Unload/Restore im Manager sowie
Release-Workflows sind unverändert. Der einzige Manager-Diff übergibt die beiden
Zeitachsen an die Lernhistorien-Serialisierung.
