# Abschlussbericht – Korrekturrunde 5

Basis: `review/korrekturrunde-4`, `9e7eba9a0400271b8bb42ff211dc305ff58c7357`.
Remote-Head, lokaler HEAD und sauberer Arbeitsbaum wurden vor Beginn geprüft.
Ergebnisbranch: `review/korrekturrunde-5`. Änderungen betreffen ausschließlich
F05/F15, deren Regressionstests und notwendige Testaufbauten für den neuen Anlauf.

## F05 – Kadenzprofil und Evidenz getrennt

**Ursache:** Eine lange Lücke löschte das gesamte Profil. Zwei ähnliche Ausreißer
innerhalb von vier Reports konnten zugleich einen Modus qualifizieren, dessen
späterer Ausreißer unberechtigt große Evidenz erhielt.

**Änderung:** Die letzten 20 positiven frischen Report-Intervalle bilden ein
begrenztes Unterstützungsfenster. Ein Modus benötigt mindestens zwei passende
Beobachtungen und mindestens 25 % Report-Anteil; die relative Ähnlichkeitstoleranz
bleibt 25 %. Unterstützung wird für das tatsächlich ankommende Intervall geprüft,
damit einzelne tolerierte Zwischenwerte keine größere Lücke durch Verkettung
legitimieren. Qualifikation und Zeitgutschrift bleiben getrennt: Erst nach der
Evidenzentscheidung wird der aktuelle Abstand zum Lernfenster hinzugefügt.
Das qualifizierende Intervall bekommt null Sekunden, ebenso jeder unbekannte
Abstand und jeder interne Tick. Auch 5-/10-Sekunden-Anlaufintervalle benötigen
vorherige Qualifikation; die alte unmittelbare Anlaufgutschrift wurde entfernt.

Keine Lückenlänge löscht mehr die gesamte Kadenzhistorie. Die bisherige
900-Sekunden-Ausfalldiagnose wurde nicht erhöht und hat keinen Einfluss auf
Lernen oder Zeitfreigabe. Regelmäßige Tages-/Wochenreports sind ebenfalls lernbar.
Ein Modus ohne ausreichende jüngere Unterstützung bekommt keine Evidenz allein
durch seine frühere Qualifikation. Lange unbekannte Lücken suspendieren weiterhin
unbestätigte Evidenz; kurze frische Anlaufreports liefern ebenfalls null Zeit,
ohne dafür einen Kommunikationsausfall zu behaupten. Explizite Experten-Grenzen
bleiben ein unabhängiger, bewusst konfigurierter Pfad.

**Tests:** Alle beauftragten konstanten Kadenzen 5/30/60/120/600/901/1800 Sekunden;
60/120, 120/600, 120/901 in beiden Startreihenfolgen; acht vorherige 120- bzw.
600-Sekunden-Intervalle; drei/vier Modi; langsame Drift; einzelne/zwei seltene
Ausreißer; exakte 600/650-Review-Sequenz; echte Ausfälle, unknown/unavailable und
Wiederkehr; eingefrorene hohe/Null-States; interne Ticks; Experten-Grenze.
Zusätzlich: Tages-/Wochenkadenz, unqualifizierter schneller Anlauf, keine
Toleranzverkettung und zwölf deterministisch variierte Invariantenfälle mit
eingefügten unqualifizierten kurzen/längeren Lücken ohne früheren Leak-Alarm.

Gegenprobe auf Runde 4: Die exakte Review-Sequenz mit einer im Test eingestellten
High-Detektionszeit von 2400 Sekunden erzeugt beim 650er einen Alarm bei 5210 s
und schreibt 650 s gut. Runde 5 schreibt diesem Abstand null Zeit gut und
alarmiert in dieser Sequenz nicht. Fachliche Produktionsschwellen sind unverändert.

**Grenzen:** Report-Endpunkte beweisen keinen kontinuierlichen physischen Fluss.
Qualifikation benötigt wiederkehrende jüngere Unterstützung; mehr als vier
gleich häufige Modi oder stark unregelmäßige Quellen können die 25-%-Regel
verfehlen und eine explizite Experten-Grenze benötigen. Unbekannte Zeit verzögert
die Erkennung, liefert aber keine Evidenz.

## F15 – Samplespezifischer Clock-Kontext

**Ursache:** Der alte Kontext legitimierte sämtliche Future-Samples in einem
Zeitbereich, einschließlich fremder/manipulierter Records. Eine Rückstellung
unter einer Sekunde wurde außerdem nicht erkannt.

**Änderung:** Beim beobachteten negativen UTC-Offset werden nur bereits
zugelassene, anschließend scheinbar zukünftige Samples freigegeben. SHA-256-
Fingerprints binden die Freigabe an UTC-Zeitstempel und normalisierten Peakwert,
also sämtliche aktuell gespeicherten semantischen Samplefelder. Restore benötigt
zusätzlich einen gültigen Clock-Kontext und die unveränderten bisherigen
Zeit-/Plausibilitätsschutzbedingungen. Ein Fingerprint legitimiert nur die
vorher gespeicherte Anzahl seiner Records; zusätzliche identische Kopien erhöhen
die Samplezahl nicht. Der Zeitbereich allein berechtigt kein Future-Sample mehr.

Eine technisch begründete 1-ms-Toleranz trennt Clock-Read-/Numerik-Jitter von
Rückstellungen und erkennt zuverlässig −0,5 s. Die bisherige 24-Stunden-Grenze
wurde nicht erweitert. Identitäten werden beim Einholen der UTC und beim Pruning
bereinigt; der Kontext enthält ausschließlich noch benötigte Sample-Identitäten
und wächst nicht unabhängig von der vorhandenen Historie. Neue gültige Samples
nach einer Rückstellung werden regulär aufgenommen und bei einer weiteren
beobachteten Rückstellung ebenfalls exakt gebunden. UTC-Zeitstempel werden weder
verschoben noch synthetisiert; Episode/Quiet/Detektor/Bypass bleiben monotonic.

**Tests:** −0,5 s/−1 h/−2 h/+1 h mit echtem sauberem Unload und drei Restarts;
mehrere Vor-/Rückstellungen; mehrere vorher gültige und neue nachher gültige
Samples; 29/31 Tage; fehlender/beschädigter Kontext; beliebige Future-Samples;
eingeschleustes 11:30-Sample im legitimen 11–12-Uhr-Bereich, auch 50.000 L/h;
veränderter Wert bei gleichem Timestamp und umgekehrt; Offline-Rückstellung;
UTC-Aufholen/Pruning; Jitter; zusätzliche identische Kopien; samplespezifische
Invariante. Bestehende Episode-/Quiet-/Detektor-/Bypass-Timerprüfungen bestehen.

Gegenprobe auf Runde 4: Das eingeschleuste 11:30-Sample mit 50.000 L/h wird neben
dem gültigen 12:00-Sample akzeptiert; nach −0,5 s bleibt kein Sample erhalten.
Runde 5 verwirft den fremden Record und erhält das zuvor gültige Sample.

**Grenzen:** Fehlender samplespezifischer Kontext, zusätzliche unbeobachtete
Offline-Rückstellungen und mehr als 24 Stunden verbleibende Zukunftsdifferenz
bleiben konservativ. Alte reine Zeitbereichskontexte ohne Fingerprints geben
keine Future-Samples frei. Fingerprints sind Identitätsbindungen, keine Signaturen
gegen koordinierte Manipulation sowohl der Samples als auch ihrer Freigabedaten.

## Regressionen und Prüfergebnisse

Alle 517 bisherigen Fälle bleiben enthalten; 70 neue Fälle prüfen ausschließlich
F05/F15. Alte F05-Erwartungen an gelöschte Profile/sofortige Anlaufgutschrift wurden
an den ausdrücklich beauftragten Wechsel angepasst. Der bisherige F15-Test mit
handgeschriebenem Zeitbereich erzeugt nun einen echten samplespezifischen Kontext.

Bestehende Safety-/Routing-/UTC-Timertests deklarieren bei Bedarf im Testaufbau
eine explizite 10-Sekunden-Kadenz, bevor ihr unveränderter fachlicher Prüfschritt
beginnt. Der F12-Test erfasst den Monitoring-Start unmittelbar vor der
Empfängeränderung statt vor dem nun längeren Kadenzanlauf. Keine bestehenden
Assertions außerhalb F05/F15 wurden geändert oder entfernt.

Umgebung: Python 3.14.2, HA Core 2026.9.4, pytest 9.1.1, Ruff 0.17.0.

| Prüfung | Ergebnis |
|---|---|
| Gesamte pytest-Suite | 587 bestanden: 517 bisherige + 70 neue |
| Runde-5-Tests separat | 70 bestanden |
| Safety-Auswahl | 108 bestanden, 479 abgewählt |
| Ruff | bestanden |
| Python-Kompilierung | 42 Dateien bestanden; Kompilate außerhalb des Repositorys |
| JSON | 4 Dateien gültig |
| YAML | 6 Workflows und services.yaml gültig |
| Bash-Syntax | 10 Workflow-Run-Blöcke und Release-Skript bestanden |
| Hassfest, HA Core 2026.9.4 | 1 Integration, 0 ungültig; keine Plugins ausgelassen |
| Bytevergleich | 81 bestehende Dateien unverändert; nur zwei Produktionsdateien geändert |
| AST-Produktionsvergleich | 208 bestehende Funktionen/Methoden identisch |
| AST-Testvergleich | 499 Assertions außerhalb F05/F15 identisch |
| git diff --check | bestanden |

Safety: `pytest -q -k 'safety or bypass or ack or negative or invalid_flow or invalid_source or lower or new_event or unavailability'`.
Hassfest verwendet wegen der lokalen Forkserver-Sandboxgrenze Multiprocessing
`fork` mit zwei Prozessen. pytest meldet eine bekannte DeprecationWarning aus HA HTTP.

Manager, Engine, `_sample_slow`, `_sample_low`, `_sample_high`, `_sample_burst`,
Rapid Rise, `DetectorSettings`, Notification Routing, Totalzähler, Alarm-Restore,
Control Plane und Release-Workflow sind gegenüber dem Ausgangscommit bytegleich.
Keine Änderungen an main, kein Merge, PR, Tag, Release oder Wiki-Publishing.
