# Korrekturrunde 6 – F05

Basis: `review/korrekturrunde-5`,
`e3cb3d9570afc86c46926a24cf9cadcf6cdd8b31`.
Der Remote-Head wurde vor Arbeitsbeginn exakt geprüft; der lokale Ausgangsstand
war identisch und sauber. Arbeitsbranch: `review/korrekturrunde-6`.

## Ursache und Änderung

Die automatische Kadenzklassifikation machte die Evidenzanrechnung von der
Reporthistorie abhängig. Wiederkehrende, legitime Abstände konnten dauerhaft
unqualifiziert bleiben; zusätzliche Meldungen konnten die Qualifikation und damit
spätere Zeitgutschriften verändern. Diese Heuristik ist vollständig entfernt:
keine Cluster, Kandidaten, Qualifikationsfenster, Mindestanteile, erlernten Modi
oder daraus abgeleiteten Ausfallgrenzen.

Im Automatikbetrieb (`source_max_age_seconds = 0`) zählt das abgeschlossene
monotonic Intervall zwischen zwei frischen, gültigen Flow-Reports. Es wird erst
beim zweiten Report angerechnet. Interne Ticks rufen keine Detektorprobe auf und
tragen immer null Evidenz bei. Auch sehr langsame und wechselnde Meldefolgen
benötigen keine Reifung mehr.

Eine explizit beobachtete ungültige, unknown oder unavailable Quelle unterbricht
die Messkette. Der erste gültige Report danach trägt null Zeit bei. Ein kleiner
technischer Pausenpfad bewahrt den bisherigen Monitoring-Fortschritt; die bereits
vorhandene Zeitdarstellung verschiebt dessen Start um nicht angerechnete Zeit.
Quiet-/Rate-Evidenz überquert die Unterbrechung nicht. Bestätigte Leaks bleiben
aktiv. Die vier `_sample_*`-Funktionen, fachlichen Resetregeln, Schwellen und
`DetectorSettings` sind unverändert.

Ein positiver Expertenwert begrenzt ausschließlich anrechenbare Reportintervalle.
Bei Grenze 60 zählen 30 und genau 60 Sekunden; 61 Sekunden tragen null bei.
Eine solche Lücke löscht keine frühere bestätigte Monitoring-Zeit. Folgende
zulässige Intervalle zählen wieder. Es gibt keine automatisch ermittelte Grenze.
README, Konfigurationsdokumentation und beide Einstellungsbezeichnungen erklären
den neuen Vertrag.

## Reproduktionen und Monotonie

- `120,120,120,120,600`, wiederholt über 30 Stunden: vollständiger Fortschritt
  und Erkennung; kein permanentes Monitoring wegen Kadenzqualifikation.
- `8 × 120,600,3 × 120,600,17 × 120,650`: jeder gültige Abstand zählt im
  Automatikbetrieb. Mit expliziter Grenze 120 tragen die langen Abstände null bei;
  der bereits bestätigte Fortschritt bleibt erhalten.
- Zusätzlicher echter Report nach 90 Sekunden: Bei Evidenzschwelle 3500 Sekunden
  beobachtet eine 120-Sekunden-Folge die Überschreitung bei 3600 Sekunden; eine
  zusätzliche Meldung bei 3570 beobachtet sie bereits dort. Das ist eine frühere
  tatsächliche Beobachtung einer schon erreichten Schwelle. Beide Folgen besitzen
  am ursprünglichen Endpunkt 3600 dieselbe bestätigte Evidenz, ohne künstliche
  Beschleunigung oder historische Umklassifikation.
- Zwölf deterministische Varianten teilen Messintervalle durch zusätzliche
  gültige Reports: an sämtlichen ursprünglichen Endpunkten bleibt die bestätigte
  Zeit exakt gleich. Die Invariante bezieht sich auf den Automatikbetrieb;
  ein bewusst gesetztes Expertenlimit bewertet die tatsächlichen Teilabstände.

## Prüfergebnisse

| Prüfung | Ergebnis |
| --- | --- |
| Gesamte pytest-Suite | **629 bestanden**: 587 bestehende Fälle und 42 neue Fälle |
| Neue Runde-6-F05-Tests separat | **42 bestanden** |
| F15-/Learning-Auswahl, unverändert (`-k 'f15 or test_learning'`) | **66 bestanden** |
| Explizite F15-Auswahl (`-k f15`) | **58 bestanden** |
| Lern- und Runde-4/5-Clock-Testdateien separat | **52 bestanden** |
| Safety-Auswahl | **114 bestanden** |
| Ruff | bestanden |
| Python-Kompilierung | 43 Dateien gültig |
| JSON | 4 Dateien gültig |
| YAML | 7 Dateien gültig |
| Bash-Syntax | 10 Workflow-Blöcke und Release-Skript gültig |
| Hassfest, alle Validierungsplugins | 1 Integration, 0 ungültige Integrationen |
| `git diff --check` | bestanden |
| AST-/Bytevergleich zur Basis | bestanden |

Die neuen Fälle umfassen konstante Abstände 5/30/60/120/600/901/1800/3600/86400
Sekunden, sechs variable Folgen einschließlich fünf verschiedener Abstände,
die exakten Review-Reproduktionen, eingefrorene hohe und Nullzustände, sechs
ungültige Quellenzustände, Wiederkehr, aktive Leaks und Quiet-Timer während
Ausfällen sowie die inklusive Experten-Grenze und Wiederaufnahme danach.

Nur bestehende F05-Tests mit Abhängigkeit von der entfernten Kadenzheuristik
wurden angepasst. 226 bestehende Test-/Hilfsfunktionen außerhalb F05 bleiben
AST- und quelltextgleich. 210 bestehende Produktionsfunktionen/-methoden sind
unverändert; lediglich zwei Manager-Methoden wurden angepasst und ein technischer
Engine-Pausenpfad ergänzt. 80 bestehende Dateien sind bytegleich, insbesondere
`learning.py`, sämtliche F15-spezifischen Testdateien, Notification Routing,
Control Plane und Release-Workflow. Totalzähler-, Alarm-Restore-, Rapid-Rise- und
fachliche Detektorimplementierungen bleiben unverändert. Die Übersetzungen
ändern ausschließlich die Max-Gap-Bezeichnung.

pytest meldet eine bestehende Home-Assistant/aiohttp-DeprecationWarning;
keine Tests schlagen fehl.

## Verbleibende technische Grenze

Ohne explizites Max-Gap-Limit kann die Integration einen stillen
Kommunikationsausfall zwischen zwei frischen Reports nicht von einer legitimen
langsamen Meldekadenz unterscheiden. Endpunktmessungen beweisen keine lückenlose
physische Strömung. Zwischen Reports entsteht trotzdem keinerlei Tick-Evidenz.
Nutzer mit möglicherweise still einfrierenden Sensoren können ein positives
technisches Limit setzen. Die vorhandene Volumenintegrationsbegrenzung und alle
fachlichen Detektorregeln bleiben erhalten.

F15 und sein samplespezifischer Clock-Rollback-Kontext sind VERIFIED und wurden
nicht geändert. Kein Merge, PR, Tag, Release oder Wiki-Publish gehört zu dieser Runde.
