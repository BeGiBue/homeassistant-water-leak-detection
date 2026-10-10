# Korrekturrunde 6 – ausschließlich F05

Ausgangspunkt: `review/korrekturrunde-5`, Commit
`e3cb3d9570afc86c46926a24cf9cadcf6cdd8b31`. Der Remote-Head wurde vor dem
Checkout per `git ls-remote` exakt bestätigt. Zielbranch: `review/korrekturrunde-6`.

Beim Push-Vorabcheck existierte der Zielbranch bereits bei
`834d8296c53da413f14886156a7fac0295a04cde` (ebenfalls direkt auf dem vorgegebenen
Runde-5-Commit). Sein Commit bleibt erhalten. Der geprüfte finale Dateistand wird
als weiterer Commit per Fast-Forward angehängt, ohne Force-Push oder Merge.
Dabei entfällt auch dessen zusätzliche Engine-Methode `pause_measurements`;
der finale Engine-Dateistand ist wieder vollständig bytegleich zu Runde 5.
Sämtliche Schutzvergleiche dieses Berichts beziehen sich auf den vorgeschriebenen
Runde-5-Ausgangscommit, nicht auf den bereits vorhandenen Runde-6-Zwischenstand.

## Entfernte Kadenzheuristik

`SourceEvidence` enthält keine Kandidatenhistorie, Intervallfenster,
Kadenzqualifikation, statistische Unterstützung, Cluster oder Toleranz mehr.
Automatisch abgeleitete Ablauf-/Ausfallgrenzen sind ebenfalls entfernt.
Die Integration bewertet frische gültige Flow-Meldungen, statt die Meldekadenz
des Sensors statistisch zu erraten.

## Deterministischer Mess-Evidenz-Vertrag

Ein erster gültiger Report beginnt eine Messkette mit null Evidenz. Erst ein
zweiter tatsächlicher frischer gültiger Report bestätigt das abgeschlossene
Intervall zwischen beiden Reports. Dessen monotone Empfangszeit ist die
anrechenbare Zeit. Vorher wird nichts fortgeschrieben. Interne Ticks erzeugen
immer null Evidenz und nehmen auch noch nicht verarbeitete Reports nicht selbst
als Detektorsample an; die Reportverarbeitung bleibt unabhängig davon zuständig.
Identische erneut gemeldete Werte bleiben frische Reports.

Die vorhandene Engine bildet akkumulierte bestätigte Monitoring-Zeit bereits
ab: Nicht angerechnete Zeit verschiebt `started_at` nach vorn, sodass
`now - started_at` ausschließlich bisher bestätigte Zeit enthält. Null-Evidenz
verändert deren Summe nicht. Diese vorhandene Repräsentation wird weiterverwendet;
die Engine musste dafür nicht geändert werden. Fachliche Bandwechsel-/Quiet-/
Resetregeln bleiben unverändert.

Beobachtetes `unknown`, `unavailable`, negative, nichtendliche oder anderweitig
ungültige Flow-Werte erzeugen weder Leak- noch Ruhe-Evidenz und brechen die
Messkette. Die bestehenden Quellen-Ausfallregeln verwerfen unbestätigtes
Monitoring und laufende Quiet-Fenster; bestätigte Leaks bleiben aktiv. Der erste
gültige Report nach Wiederkehr beginnt mit null Evidenz eine neue Messkette.
Die Zeit über die beobachtete Unterbrechung hinweg wird nie angerechnet.
Ein eingefrorener gültiger State ohne neue Reports aktiviert und beendet keinen
Leak; im Automatikbetrieb verändert ein Tick auch keinen laufenden Quiet-Timer.

## Optionale Experten-Grenze

„Maximal anrechenbarer Abstand zwischen zwei Messwertmeldungen“ verwendet die
bestehende Einstellung `source_max_age_seconds`:

- 0 / automatisch: keine künstliche Grenze, kein Lernen einer Grenze.
- Positiv: Gleichheit zählt. Bei Grenze 60 s zählen 30 s und 60 s; 61 s zählt nicht.
- Ein ausgeschlossenes Intervall fügt nur null hinzu. Bereits akkumulierte
  bestätigte Monitoring-Zeit bleibt erhalten; weitere normale Reports zählen sofort.
- Bei expliziter Überschreitung bleibt die bestehende Unterbrechung eines Quiet-
  Fensters erhalten. Bestätigte Leaks werden dadurch nicht beendet.

Der bestehende Einstellbereich 0–3600 und die Migration des historischen,
nicht explizit gespeicherten 30-s-Defaults bleiben unverändert.

## Abnahme und Monotonie

Neue Manager-Abnahmetests prüfen Slow/Low/High zeitbasiert bei konstanten
5/30/60/120/600/901/1800/3600/86400 Sekunden sowie 60↔120, 120↔600, 120↔901,
120,120,120,120,600, 120→300→600 und fünf regelmäßig wiederkehrenden Abständen.
Jedes abgeschlossene Intervall zählt unmittelbar; jeder Tick davor zählt null.
Die fachliche Burst-/Rapid-Rise-Definition wird nicht verändert.

Die exakten bisherigen Fehlerfolgen werden erneut geprüft:

1. `120,120,120,120,600` über 30 Stunden: alle 108000 Sekunden werden beim
   jeweiligen zweiten Report angerechnet; eine 3600-s-Zeitschwelle wird bei
   Sekunde 3600 beobachtet. Keine dauerhafte Nichterkennung.
2. `8 × 120, 600, 3 × 120, 600, 17 × 120, 650`: jede Gutschrift entspricht exakt
   dem aktuellen Intervall. Die 650-s-Lücke bekommt keine besondere Lernwirkung;
   eine 3600-s-Schwelle wird ebenfalls bei Sekunde 3600 beobachtet.
3. Konstant 120 s gegenüber genau einem zusätzlichen Report nach 90 s:
   `[120]` wird zu `[90,30]`. An allen ursprünglichen Reportzeitpunkten ist die
   akkumulierte Evidenz identisch. Zusätzlich werden wiederholte Unterteilungen
   und zwölf zufällig erzeugte Unterteilungen derselben 120-s-Intervalle geprüft.

Ein zusätzlicher echter Report kann eine schon erreichte Schwelle früher
**beobachtbar** machen: Bei konstantem Flow und 90-s-Zeitschwelle beobachtet der
zusätzliche Report bei t=90 die erreichten 90 Sekunden; ohne ihn findet die
nächste Beobachtung erst bei t=120 statt. Für eine 100-s-Schwelle alarmieren beide
Folgen bei t=120, für 3600 s beide bei t=3600. Auch eine wiederholte Unterteilung
kann eine 3690-s-Schwelle bei t=3690 statt t=3720 sichtbar machen. Das ist frühere
tatsächliche Beobachtung, keine künstliche Beschleunigung: Kein Alarm liegt vor
der bestätigten Evidenzschwelle, keine zusätzliche Zeit wird erfunden und die
Evidenz an den gemeinsamen Reportzeitpunkten bleibt identisch.

Weitere Tests prüfen eingefrorene hohe/ruhige States, unknown/unavailable,
negative/ungültige/nichtendliche Werte, Wiederkehr, aktive Leaks während Ausfall,
laufende Quiet-Timer sowie 30/60/61 s bei expliziter 60-s-Grenze mit und ohne
zwischenzeitlichen Tick. Die ausgeschlossene 61-s-Lücke erhält den bisherigen
90-s-Monitoring-Fortschritt; weitere 30 s erreichen regulär die 120-s-Schwelle.

## Schutz der übrigen Findings und F15

`learning.py`, `engine.py` einschließlich `_sample_slow`, `_sample_low`,
`_sample_high`, `_sample_burst`, Rapid Rise, `DetectorSettings`, Totalzähler und
Alarm-Restore sind vollständig bytegleich zum Ausgangscommit. Notification
Routing, Konfigurations-/Control-Plane-Regeln und alle Release-Workflows bleiben
unverändert. Insbesondere wurde kein samplespezifischer F15-Clock-Rollback-Kontext
verändert.

`docs/verify_round6_scope.py` vergleicht sämtliche bestehenden Dateien außerhalb
der ausdrücklich erlaubten F05-Dateien byteweise. Im Manager bleiben alle
Methoden außer Tick-/Frischeprüfung, Messketten-Unterbrechung und dem Gap-
Docstring byte-/AST-identisch. Die geschützte tatsächliche Reportverarbeitung
ab Flow-Normalisierung, einschließlich Total, Learning und Clock-Kontext, ist
auch innerhalb `async_refresh` bytegleich. Der Rückbau ausschließlich der vier
zulässigen Methodenspannen ergibt wieder die komplette ursprüngliche Managerdatei.
Übersetzungen ändern ausschließlich das F05-Gap-Label.

Alle bestehenden Testfunktionen und Helfer außerhalb `test_f05_*` bleiben
byte-/AST-identisch, einschließlich Dekoratoren und Safety-Assertions. Geänderte
alte F05-Tests betrafen ausschließlich entfernte Kadenzqualifikation/-Ablaufgrenzen
und deren bisherige Evidenzlöschung. Vorhandene explizite Ablaufprüfungen nutzen
jetzt eine explizite Experten-Grenze. 80 von 92 vorhandenen Dateien sind bytegleich.

## Prüfungen

Umgebung: Python 3.14.2, Home Assistant Core 2026.9.4, pytest 9.1.1, Ruff 0.17.0.

| Prüfung | Ergebnis |
|---|---|
| Gesamte pytest-Suite | 662 bestanden: 587 bisherige + 75 neue F05-Abnahmen |
| Neue Runde-6-F05-Tests separat | 75 bestanden |
| Gesamte F15-Auswahl `pytest -q -k f15` | 58 bestanden; Testquellen unverändert |
| Runde-4-/Runde-5-F15-Dateien separat | 45 bestanden, vollständig bytegleich |
| Identische Safety-Auswahl wie Runde 5 | 108 bestanden |
| Erweiterte Findings-/Safety-/Routing-/Restore-/Release-Auswahl | 346 bestanden |
| AST-/Byte-Schutzprüfung | alle drei Bereichsprüfungen bestanden |
| Ruff | bestanden |
| Python-Kompilierung | bestanden |
| JSON | 4 Dateien gültig |
| YAML | 6 Workflows und services.yaml gültig |
| Bash-Syntax | 10 Workflow-Run-Blöcke und Release-Skript bestanden |
| Hassfest, HA Core 2026.9.4 | 1 Integration, 0 ungültig; keine Prüfplugins ausgelassen |
| git diff --check | bestanden |

Scope-Prüfung: `python docs/verify_round6_scope.py` (benötigt den Ausgangscommit
in der lokalen Git-Historie; bewusst kein Bestandteil der regulären pytest-Suite,
damit ein flacher CI-Checkout keine Git-Historie für funktionale Tests benötigt).
Safety: `pytest -q -k 'safety or bypass or ack or negative or invalid_flow or invalid_source or lower or new_event or unavailability'`.
Hassfest verwendet wie Runde 5 wegen der lokalen Forkserver-Sandboxgrenze
Multiprocessing `fork` mit zwei Prozessen. pytest meldet ausschließlich die
bekannte DeprecationWarning aus Home Assistants HTTP-Komponente.

## Verbleibende technische Grenze

Ohne explizite Max-Gap-Einstellung kann die Integration nicht unterscheiden,
ob ein langer Abstand eine legitime langsame Meldekadenz oder ein stiller
Kommunikationsausfall war. Ein späterer gültiger Report kann deshalb ein langes
Intervall bestätigen. Zwei Endpunktmeldungen beweisen keinen ununterbrochenen
physischen Flow zwischen ihnen. Diese Grenze ist im README, in der
Konfigurationsdokumentation und im lokalen Wiki-Quelltext ausdrücklich beschrieben.
Die fachlichen Findings F02/F04/F08 und Rapid Rise bleiben unverändert offen.

Keine Änderung an main, kein Merge, PR, Tag, Release oder Wiki-Publishing.

Aktueller Nachtrag F02: Die statische High-Flow-Schwelle schließt F02.
F04, F08 und Rapid Rise bleiben offen; die damalige Review-Aussage ist historisch.
