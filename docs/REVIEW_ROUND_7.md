# Korrekturrunde 7 – letzter F05-Blocker

Basis: `review/korrekturrunde-6`, Commit
`016a1af901ad364404b0b2133c069d294f1b9266`.
Remote-Head vor Arbeitsbeginn exakt geprüft; Arbeitsbaum sauber.
Arbeitsbranch: `review/korrekturrunde-7`.

## Ursache und technische Änderung

Die temporäre Quellenunterbrechung rief dieselbe destruktive Engine-Suspendierung
wie ein tatsächlicher Quellenwechsel auf. Dadurch wurden bestätigte
Slow-/Low-/High-Monitoring-Intervalle bei jedem unavailable/unknown/ungültigen
Flow verworfen. Regelmäßige kurze Ausfälle konnten die Detektion dauerhaft
verhindern, obwohl genügend tatsächliche Flow-Evidenz vorhanden war.

Ein neuer, kleiner Engine-Hilfspfad `pause_source_evidence()` trennt diese Semantik.
Der Manager verwendet ihn ausschließlich für die temporäre Unterbrechung:

- Slow/Low/High behalten Monitoring-Start und bestätigten Fortschritt.
- `last_sample_at` bleibt erhalten. Der erste gültige Rückkehrreport besitzt null
  Evidenz; die unveränderte `sample()`-Logik verschiebt Monitoring-Starts genau
  einmal um die gesamte nicht bestätigte Zeit. Kein Offline-Zeitbonus.
- Quiet-Fenster und vorherige Flow-/Rate-Evidenz werden verworfen.
- Ein unbestätigter Burst-Kandidat wird verworfen; ACTIVE Burst bleibt aktiv.
- Bestätigte Leaks und Shutoff-Anforderungen bleiben erhalten.
- Der vorhandene destruktive Pfad und `rebind_sources()` bleiben unverändert:
  ein tatsächlicher Quellenwechsel verwirft unbestätigte Evidenz der alten Quelle.

Eine Quellenunterbrechung ist keine Messung von 0 L/h. Tatsächlich gemessene
Rückkehrwerte durchlaufen weiterhin alle bisherigen Detektorregeln: Slow kann
bei 0 sofort sein Monitoring beenden; Low/High beginnen ihr normales Quiet-Fenster
und setzen nach den unveränderten Resetzeiten zurück. Quiet-Zeit über unavailable
zählt niemals mit. README und Konfigurationsdokumentation beschreiben diese Trennung.

## Exakte Regression und weitere Abdeckung

Für Slow, Low und High: Detektionsschwelle 3600 Sekunden, 29 × 120 Sekunden
passender Flow ergeben 3480 Sekunden. Nach beobachteter Unterbrechung und Rückkehr
bleiben exakt 3480 Sekunden erhalten. Der Rückkehrreport zählt null; der nächste
120-Sekunden-Abstand ergibt exakt 3600 und aktiviert den Event.

Dieser Test läuft für unavailable, unknown, negative Werte, NaN, Infinity und
nicht normalisierbaren Flow, jeweils mit 10 Minuten und 30 Tagen Unterbrechung.
Interne Ausfall-Ticks ändern weder Messzeit noch Evidenz. Wiederholtes Lesen nach
Rückkehr verschiebt den Start nicht doppelt. Weitere Tests unterbrechen die Quelle
bereits nach jedem einzelnen bestätigten 120-Sekunden-Abstand: auch viele frühe
Ausfälle können die reguläre Aktivierung nicht verhindern.

Zusätzlich geprüft: tatsächliche ruhige Rückkehrwerte und unveränderte Resetzeiten,
aktive Slow-/Low-/High-/Burst-Leaks mit laufender Quiet-Zeit und Shutoff,
verworfenes Burst-Monitoring, unterbrochene Rapid-Rise-Historie sowie echte
Source-Rebinds ohne Übertragung des alten Monitoring-Fortschritts.

## Prüfergebnisse

| Prüfung | Ergebnis |
| --- | --- |
| Gesamte pytest-Suite | **713 bestanden**: 662 bisherige Fälle + 51 neue |
| Runde-7-F05 separat | **51 bestanden** |
| Runde-6-F05 vollständig | **75 bestanden** |
| F15-/Learning vollständig (`-k 'f15 or test_learning'`) | **66 bestanden** |
| Safety-Auswahl | **108 bestanden** |
| Routing-/Restore-/Release-Auswahl | **208 bestanden** |
| Ruff | bestanden |
| Hassfest, alle Validierungsplugins | 1 Integration, 0 ungültig |
| Python-Kompilierung | 44 Dateien gültig |
| JSON | 4 Dateien gültig |
| YAML | 7 Dateien gültig |
| Bash-Syntax | 10 Workflow-Blöcke und Release-Skript gültig |
| `git diff --check` | bestanden |
| AST-/Bytevergleich | bestanden |

Safety-Auswahl: `safety or bypass or ack or negative or invalid_flow or
invalid_source or lower or new_event or unavailability`.
Routing-/Restore-/Release-Auswahl: `routing or restore or release`.
pytest meldet lediglich die bestehende Home-Assistant/aiohttp-DeprecationWarning.

90 bestehende Dateien bleiben bytegleich, einschließlich `learning.py`, aller
F15-spezifischen Tests, `evidence.py`, Config Flow, Notification Routing,
Control Plane, Übersetzungen und Release-Workflow. 211 bestehende
Produktionsfunktionen/-methoden sowie 268 bestehende Test-/Hilfsfunktionen sind
unverändert. Alle vier `_sample_*`, `DetectorSettings`, Rapid Rise fachlich,
Totalzählerlogik und Alarm-Restore bleiben unverändert.

Ein zusätzlicher exakter Dateivergleich bestätigt: Entfernen allein der neuen
Engine-Hilfsfunktion stellt die ursprüngliche Engine-Datei vollständig wieder
her; Rücktausch allein des Manager-Ausfallaufrufs stellt dessen Datei vollständig
wieder her. Bei bisherigen Tests wurde ausschließlich eine F05-Phasenerwartung
angepasst (MONITORING bleibt bei Ausfall erhalten statt IDLE). Alle übrigen Bytes
der bestehenden Testdateien sind identisch. Experten-Max-Gap und das
deterministische Runde-6-Evidenzmodell bleiben unverändert.

## Verbleibende Grenzen

Der Erhalt gilt für temporäre Ausfälle derselben Quelle innerhalb der laufenden
Sitzung. Echte Quellenwechsel und die bestehende Restart-/Restore-Semantik werden
nicht verändert. Die vorhandene aktive Event-Dauer bleibt ebenfalls unverändert;
sie ist von der bestätigten Monitoring-Evidenz zu unterscheiden.

Ohne explizites Max-Gap-Limit bleiben stille Kommunikationsausfälle zwischen zwei
gültigen Reports von einer legitimen langsamen Meldekadenz ununterscheidbar.
Endpunktwerte beweisen keine kontinuierliche physische Strömung. F02/F04/F08 und
die fachliche Rapid-Rise-Definition bleiben außerhalb dieser Runde.

F15 bleibt VERIFIED. Kein Merge, PR, Tag, Release oder Wiki-Publish.
