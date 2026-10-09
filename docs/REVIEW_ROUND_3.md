# Abschlussbericht – Korrekturrunde 3

Stand: 2026-10-09. Basis: `review/korrekturrunde-2`, Commit `b7769fc29537ce746494357ee635c78826228860`. Arbeits- und Bereitstellungsbranch: `review/korrekturrunde-3`.

Bearbeitet wurden ausschließlich die beauftragten Restfehler in F05, F12, F06, F07, F15, F16 und F20, ihre Regressionstests und die zugehörige Dokumentation. F02, F04, F08 und die fachliche Rapid-Rise-Definition bleiben unverändert. Es wurden keine Leckageklassen, Detektionsschwellen oder fachlichen Erkennungszeiten geändert. Die physische Ventilsteuerung bleibt außerhalb der Integration in Home-Assistant-Automationen.

## F05 – Mess-Evidenz und wechselnde Kadenzen

**Ursache:** Kadenzqualifikation und Detektionszeit waren gekoppelt. Eine neu gelernte längere Lücke konnte ältere Zeit nachträglich legitimieren; wechselnde lange und kurze Intervalle konnten sich gegenseitig immer wieder verwerfen.

**Lösung:** Kadenzlernen und anrechenbare Intervallzeit sind getrennt. `SourceEvidence` entscheidet die Evidenzgutschrift ausschließlich anhand der vor dem aktuellen Report vorhandenen Qualifikation. Das lernende Intervall selbst bleibt unbekannt und erhält keine Zeitgutschrift. Zwei vergleichbare längere Intervalle innerhalb von vier Reports qualifizieren eine neue Kadenz für zukünftige Reports. Bis zu zwanzig qualifizierte Intervalle halten wechselnde Modi verfügbar. Eine seltene Lücke zwischen vielen normalen Reports qualifiziert dadurch keinen neuen Meldetakt.

Die Verfügbarkeitsgrenze (1,5 × längster qualifizierter Abstand) berechtigt ausdrücklich nicht zur Gutschrift von Detektionszeit. Automatische Evidenz benötigt einen zuvor qualifizierten Modus mit 25 % Kadenz-Toleranz oder ein kürzeres frisches Intervall. Nur beim noch unqualifizierten Anlauf können Intervalle bis zum internen Zehn-Sekunden-Tick direkt qualifizieren. Ein ausgelassener Fünf-Sekunden-Report wird deshalb nicht als vermeintlich gültiges Zehn-Sekunden-Anlaufintervall behandelt. Positive explizite Experten-Grenzen bleiben als bewusst konfigurierte zulässige Report-Abstände erhalten.

Die Engine erhält die ausdrücklich bestätigte Intervallzeit. Unbekannte Lücken verwerfen weiterhin unbestätigte Monitoring-/Quiet-Fenster und können die Erkennung verzögern; bestätigte Events bleiben aktiv. Bei langen Ausfällen werden auch Kadenzqualifikationen verworfen. Interne Ticks liefern niemals neue Mess-Evidenz und werden nicht nachträglich durch spätere Reports bestätigt.

**Tests:** `tests/test_round3_measurements.py`: konstante 5/30/60/120/600 Sekunden; alternierende 60/120 und 600/120 Sekunden über vier Stunden; 5 Sekunden gefolgt von einer 240-Sekunden-Lücke; wiederholte, aber seltene Lücken; ausgelassene Reports, einschließlich 5 → 10 und qualifizierte 60/120 → unbekannte 180 Sekunden; lange Kommunikationslücke und Wiederkehr; eingefrorene hohe und Null-States; identische frische Reports. Die entsprechenden Runde-1-/Runde-2-Tests bestehen ebenfalls.

**Dateien:** `evidence.py`, `engine.py`, `manager.py`, README, Changelog und Betriebsdokumentation.

**Grenzen:** Kadenzqualifikation ist eine konservative Interpretation von Report-Endpunkten, kein physischer Beweis durchgehenden Flusses. Anlauf und unbestätigte Lücken können die Erkennung verzögern. Sehr lange oder unregelmäßige Quellen können eine explizite Experten-Grenze benötigen. Die fachlichen Detektorregeln selbst bleiben unverändert.

## F12 – Steuerung unabhängig von neuer Mess-Evidenz

**Ursache:** Der frühe Return bei einem unveränderten State verhinderte auch ausdrücklich angeforderte Steuerungsänderungen.

**Lösung:** `DetectionEngine.apply_controls()` verarbeitet die bestehenden Regeln für deaktivierte Slow-/Low-Detektoren und aktiven High-Flow-Bypass ohne Flow-Sample. Der Manager wendet diese Steuerung vor der Frischeprüfung und unmittelbar bei Optionsänderungen an. Entsprechende End- und Shutoff-Übergänge nutzen die bestehenden Pfade. Empfängeränderungen starten den Notification-Abgleich sofort. Bypass-Ende oder neue Optionen erzeugen dagegen kein Event aus einem alten Messwert; dafür bleibt ein frischer Report erforderlich.

**Tests:** `tests/test_round3_measurements.py`: eingefrorene Quelle, aktives Slow/Low → deaktivieren; aktives High → Bypass aktivieren; Bypass ohne Report wieder ausschalten; Empfänger ändern; Detektoroption ändern. `tests/test_round3_notifications.py` prüft zusätzlich den tatsächlichen Versand über einen neuen Service ohne neuen Flow-Report.

**Dateien:** `engine.py`, `manager.py`, README und Betriebsdokumentation.

**Grenzen:** Explizites Deaktivieren und Bypass setzen nur die dafür bereits vorgesehenen Zustände zurück. Quittierung bleibt davon getrennt. Neue Mess-Evidenz wird durch eine Konfigurationsänderung nicht erfunden.

## F06 – Versandstatus gehört zum konkreten Versandweg

**Ursache:** `interrupted` war nur dem Empfänger zugeordnet und konnte dadurch einen noch nie verwendeten neuen Notify-Service sperren.

**Lösung:** Stabile Route-Identität aus Empfänger-ID und tatsächlich verwendetem Notify-Service. Persistierte `route_states` und laufende Tasks verwenden Event-ID plus Route. `accepted` und `interrupted` gelten nur für diesen Weg. Ein Servicewechsel kann einen neuen Dispatch starten; parallele Doppel-Dispatches derselben Route bleiben ausgeschlossen. Bereits laufende alte Wege können ihren tatsächlichen Abschluss unabhängig dokumentieren. Returning Home entfernt nur die erneuerbare Annahme der aktuellen Route und überträgt keine alte Sperre auf einen neuen Service. Globale und lokale Quittierungen bleiben wirksam.

Runde-1-/Runde-2-Annahme-Keys werden kompatibel auf bekannte Service-Routen übertragen. Runde 2 hat bei einer unterbrochenen, zuvor nie erfolgreich angenommenen Übergabe keinen Service gespeichert. Solche fehlende Herkunft bleibt ausdrücklich als unbekannte Alt-Route erhalten, statt dem aktuellen, möglicherweise neuen Service zugeordnet zu werden. Ein berechtigter aktueller Versandweg bleibt nutzbar.

**Tests:** `tests/test_round3_notifications.py`: interrupted/accepted jeweils gleicher/neuer Service, live und nach Restore/Unload; Empfängeränderung; Returning Home; globale Quittierung; neuer Service während alter Service noch läuft; echte Legacy-Store-Migration ohne Route-Herkunft. Pro Route werden Mehrfachanläufe und Persistenz geprüft.

**Dateien:** `notifications.py`, README und Betriebsdokumentation.

**Grenzen:** Bei Altdaten ohne Service-Herkunft ist die alte Route nicht rekonstruierbar. War der jetzt verwendete Service auch die unbekannte alte Route, kann beim Upgrade eine Doppelmeldung entstehen. Neue Stores enthalten die Route eindeutig. Wie bisher garantiert ein normaler HA-Service-Return die Übergabe an den konfigurierten Home-Assistant-Notify-Service, nicht die physische Zustellung auf dem Telefon. Unterbrochene bekannte Routen bleiben wegen ihrer unklaren Wirkung ohne blinde automatische Wiederholung.

## F06 – Dispatch-Tasks beim Event-Ende

**Ursache:** Das Entfernen der Event-/Quittierungsdaten ließ bereits laufende Dispatch-Tasks bestehen.

**Lösung:** Der End-Listener entfernt zunächst das Event und seine Quittierung, cancelt anschließend ausschließlich die zu diesem Event gehörenden Worker und wartet auf deren Ende. Auch vor ihrem ersten Lauf abgebrochene Tasks werden aus beiden Registrierungen entfernt. Ein Service-Return darf keine beendete Quittierungsstruktur wieder einsetzen. Unload bereinigt die Task-Registrierungen ebenfalls vollständig. Andere Events bleiben unberührt.

**Tests:** `tests/test_round3_notifications.py`: hängender Service mit einem oder mehreren Empfängern; zwei parallele Events, nur eines endet; Event-Ende vor Worker-Start sowie unmittelbar um den Service-Return; keine verbleibenden Event-/Task-Referenzen. Bestehende Unload-/Timeout-Tests bestehen weiterhin.

**Dateien:** `notifications.py`, README und Betriebsdokumentation.

**Grenzen:** Bereinigt werden die integrationseigenen Worker. Ein bereits an Home Assistant übergebener Notify-Aufruf kann dort intern weiterlaufen und naturgemäß nicht zurückgerufen werden.

## F07 – Verworfene Totals benötigen neue Total-Evidenz

**Ursache:** Ein unplausibler Sprung wurde später allein durch anwachsende Flow-Integration akzeptiert, obwohl der Totalwert eingefroren blieb. Der Faktor 1,5 erlaubte außerdem einen deutlich vorgreifenden Mengenalarm.

**Lösung:** Der Manager verfolgt Total-State-Identität und tatsächliche identische Wiederholungsreports unabhängig von Flow-Reports. Die Engine prüft einen verworfenen Wert nur bei neuer Total-Evidenz: echtem Wertfortschritt oder ausdrücklich frischem identischem Report. Der konservative API-Standard `total_fresh=False` verhindert auch bei direkten Engine-Aufrufen eine stillschweigende Bestätigung identischer Totals.

Der Mengenrahmen enthält keinen Faktor 1,5 und keinen festen Literzuschlag mehr. Er akkumuliert bestätigte Intervalle mit dem tatsächlich aktuellen Flow statt dem Maximum aus altem und neuem Flow. Akzeptierte Zählerfortschritte verbrauchen nur ihre Menge; ungenutzte Flow-Evidenz bleibt für folgende Quantensprünge erhalten. Ein eingefrorener verdächtiger Totalwert wird dadurch nicht allein durch Flow-Aufholen gültig. Reset, Rücksprung, Ausfall und Wiederkehr behalten das sichere Rebasing. Die Flow-Integration bleibt unabhängig nutzbar.

**Tests:** `tests/test_round3_measurements.py`: verworfener Sprung mit eingefrorenem Wert; explizit neuer identischer Totalreport; späterer weiterer Quantensprung; konservativer direkter Engine-Aufruf; echter Manager mit unterschiedlichen Flow-/Total-Reports; 1/10/100-Liter-Quantisierung bei 5/60/120-Sekunden-Total-Kadenzen; Reset/Rücksprung und Ausfall. Bestehende Ausfall-/Wiederkehr- und Plausibilitätstests laufen unverändert mit, soweit ihre fachliche Erwartung nicht gerade der beauftragte Fehler war.

**Dateien:** `engine.py`, `manager.py`, README, Betriebsdokumentation; zwei bestehende F07-Testfälle wurden verschärft (Details unten).

**Grenzen:** Die Prüfung belegt Konsistenz mit bestätigter Flow-Evidenz, nicht die Richtigkeit eines defekten Messgeräts. Ein frischer identischer Totalreport darf nach ausreichender Flow-Evidenz ausdrücklich bestätigen. Die vorhandene Begrenzung sehr langer einzelner Flow-Integrationsintervalle bleibt unverändert; der Total-Plausibilitätsrahmen berücksichtigt das vollständige bestätigte Intervall, niemals eine unbestätigte Kommunikationslücke.

## F15 – Lernhistorie mit realer UTC

**Ursache:** Der Learner erhielt die synthetische Prozesszeitachse auch für persistierte historische Zeitstempel. Nach UTC-Rückstellung konnten dadurch Samples bei Restore als vermeintliche Zukunftsdaten verschwinden.

**Lösung:** Im Produktionspfad erhält der Learner zwei getrennte Zeiten: tatsächliche UTC für Aufnahmezeitpunkt, Historie, Pruning und Rolling Window; monotone Prozesszeit für Episode-/Quiet-Intervalle. Adaptive Referenzen und Lern-Snapshots verwenden reale UTC. Laufende Detektor-, Quiet- und Bypass-Timer behalten die monotone Zeitbasis. Die Rapid-Rise-Definition wurde nicht geändert.

**Tests:** `tests/test_round3_measurements.py`: UTC −1/+1 Stunde sowie mehrere Korrekturen; Episode danach abschließen; gespeicherter Zeitstempel entspricht realer UTC; sauberer Unload und Store-Restore behalten das Sample; Rolling Window 29/31 Tage; Uhrkorrektur während laufendem Lern-Quiet-Timer ohne vorzeitigen Abschluss. Die bisherigen Zeitbasis-, Bypass-, Active-Duration- und queued-State-Tests bestehen weiterhin.

**Dateien:** `learning.py`, `manager.py`, README und Betriebsdokumentation.

**Grenzen:** Historische UTC und Kalenderfenster folgen bewusst der korrigierten realen Uhr. Offline-Zeit liefert weiterhin keine bestätigte Laufzeit. Eine Uhrkorrektur während eines unkontrollierten Ausfalls lässt sich aus alten absoluten Zeitpunkten allein nicht vollständig rekonstruieren.

## F16 – Klassenunabhängiger fail-safe Restore

**Ursache:** Die Rekonstruktion bei beschädigter Phase und ID verlangte einen Burst-spezifischen `reason` und eine positive Menge.

**Lösung:** Einheitliche Regel für Slow, Low, High und Burst: explizit aktive Phase, redundantes `confirmed_active=True` oder robuste verbleibende Bestätigungsinformationen erhalten das aktive Ereignis. Legacy-Daten mit beschädigter/Idle-Phase können insbesondere anhand gültiger Detektions- und Startzeit rekonstruiert werden; gültige Event-Identität plus Detektionszeit bleibt eine weitere Bestätigung. `reason` und positive Menge sind nicht erforderlich. Neues redundantes Feld, alte Stores weiterhin kompatibel; keine Versionsmigration nötig. Quiet-Evidenz wird nicht restauriert. Unbestätigtes Monitoring bleibt verwerfbar.

**Tests:** `tests/test_round3_restore.py`: jede Klasse, Legacy und neues Format, einzeln beschädigte Phase, ID, Detektionszeit, optionaler Grund, Menge; Phase + ID und weitere Kombinationen. Zusätzlich echte Store-/Manager-Setup-Abläufe für jede Klasse und sieben Schadensvarianten. Aktiver Zustand und eingeschaltete Shutoff-Anforderung bleiben bestehen; beschädigtes Monitoring erzeugt keinen Alarm.

**Dateien:** `engine.py`, README und Betriebsdokumentation.

**Grenzen:** Wenn in einem Legacy-Store sämtliche belastbaren Bestätigungsinformationen verloren sind, lässt sich daraus kein bestätigter Leak erfinden. Das neue redundante Feld verbessert die Rekonstruktion bei mehreren beschädigten Teilfeldern, ohne allgemeine Speicherintegrität zu garantieren.

## F16 – Aktionssichere Event-IDs

**Ursache:** Persistierte IDs konnten den Action-Trenner `|`, Leer-/Sonderzeichen oder überlange Inhalte enthalten und die Notification-Aktionen unbrauchbar machen.

**Lösung:** Restore erlaubt 1–128 ASCII-Buchstaben, Ziffern, Unterstriche und Bindestriche. Ungültige IDs werden durch den bestehenden sicheren Generator ersetzt. Aktive Sicherheitslage bleibt erhalten. Die neue ID übernimmt keine Quittierung der alten ID; die vorhandene aktive-ID-Filterung entfernt verwaiste Quittierungen. Zulässige bestehende IDs bleiben unverändert.

**Tests:** `tests/test_round3_restore.py`: `broken|id`, leere/Whitespace-IDs, Unicode, Zeilenumbruch, Listen/None, überlange ID; gültige Legacy-IDs und Länge 128. Echte Store-Restores prüfen erhaltenen Shutoff, keine übernommene alte Quittierung und wieder parsebare Action-IDs.

**Dateien:** `engine.py`, README und Betriebsdokumentation. Action-Parser und Quittierungsautorisierung selbst bleiben unverändert.

**Grenzen:** Ein ersetztes Event kann neu benachrichtigt werden; das ist sicherer als eine ungeprüft übernommene Quittierung oder eine unparsebare Aktion.

## F20 – Release-SHA und Tag-Rennen

**Ursache:** Zwischen Tag-Prüfung und Release-Erstellung konnte ein konkurrierender Lauf einen Tag erzeugen oder ein externer Akteur ihn bewegen.

**Lösung:** Gemeinsames Skript für 1.0.1 und 1.0.2 erzeugt fehlende GitHub-Refs atomar per Git References API auf `GITHUB_SHA`, ohne vorhandene Refs zu ändern. Erfolg und Kollisionsfehler werden durch erneutes Lesen und vollständiges Auflösen auf den Commit verifiziert; annotierte und verschachtelte annotierte Tags werden vollständig gepeelt. Weitere Prüfung unmittelbar vor Release-Erstellung, Erstellung mit `--verify-tag` und festem SHA, danach Prüfung des Release-Tag-Namens und erneut des Tag-Commits. Ein konkurrierend schon erstellter Release wird nur nach derselben vollständigen Prüfung akzeptiert. Remote-Fehler führen zum Abbruch. Beide Workflows serialisieren Läufe über eine Concurrency-Gruppe je Release-Tag mit `cancel-in-progress: false`.

**Tests:** `tests/test_round3_release.py`: atomar geteiltes API-Modell mit zwei gleichzeitig gestarteten Skriptprozessen; Tag-Kollision mit gleichem/anderem SHA; vorhandener/fehlender Release; Lightweight/annotierte Tags; Re-Run; Tagbewegung vor/während Erstellung ohne falschen Erfolg; Remote-Fehler; falscher Release-Tag-Name und Workflow-Concurrency. Zusätzlich sechs Tests mit echten Git-Objekten in temporären Repositories für Lightweight, annotierte und verschachtelte annotierte Tags, jeweils richtiger/falscher Commit. Keine realen GitHub-Tags oder Releases werden in den Tests veröffentlicht.

**Dateien:** `.github/release_checked_commit.sh`, beide Release-Workflows, `docs/RELEASING.md`.

**Grenzen:** Für die vollständige SHA-Garantie müssen Release-Tags über **GitHub Rulesets / Tag Protection gegen Verschieben geschützt sein**. Ein Client-Skript kann einen externen Berechtigten nicht daran hindern, den Tag nach einer erfolgreichen Prüfung zu bewegen. Das Skript schließt die vermeidbaren Erstellungsrennen und erkennt beobachtete Bewegungen; es kann eine externe Mutation oder einen bereits erstellten Release nicht rückwirkend verhindern. Rulesets wurden auftragsgemäß nicht extern verändert; kein Veröffentlichungsworkflow wurde ausgelöst.

## Prüfungen

| Prüfung | Ergebnis |
|---|---|
| Gesamte pytest-Suite | **490 bestanden**, einschließlich aller 272 bisherigen Fälle |
| Neue Runde-3-Suite separat | **218 bestanden** |
| Safety-Auswahl | **76 bestanden**, 414 abgewählt |
| Ruff 0.16.10 | bestanden |
| Python-Kompilierung | 38 Dateien bestanden; Kompilate außerhalb des Repositorys |
| JSON | 4 Dateien gültig |
| Workflow-YAML | 6 Dateien lesbar |
| Bash-Syntax | 10 Workflow-Run-Blöcke und gemeinsames Release-Skript bestanden |
| Hassfest, HA Core 2026.9.4 | 1 Integration, 0 ungültige Integrationen |
| Schutz-Diff | 30 geprüfte Funktionen AST-identisch; `DetectorSettings` identisch |
| Zusätzlicher Dateiabgleich | Config Flow, Konstanten, Integration-Setup/Unload und Einheiten bytegleich |
| Whitespace | `git diff --check` bestanden; erneut vor Commit geprüft |

Umgebung: Python 3.14.2, Home Assistant 2026.9.4, pytest 9.1.1. Eine bekannte DeprecationWarning stammt aus Home Assistants HTTP-Abhängigkeit.

Die Safety-Auswahl und die Gesamtsuite sichern Quittierung ohne Leak-/Shutoff-Ende, Burst trotz High-Flow-Bypass, negative/unknown/unavailable Quellen ohne Entwarnung, erhaltene aktive niedrigere Klassen und neue Events ohne alte Quittierung. VERIFIED F01, F03, F09, F10, F11, F13, F14, F18 und F22 bleiben geschützt. Insbesondere die vier `_sample_*`-Erkennungsfunktionen inklusive Rapid Rise, Persistenzplanung, Quittierungsautorisierung, Quellenvalidierung, Config-Navigation und Setup-/Unload-/Reload-Funktionen sind gegenüber Runde 2 unverändert.

### Bestehende Tests wurden nicht zum Erhalt fehlerhaften Verhaltens umgeschrieben

Alle 272 bisherigen Testfälle sind weiterhin vorhanden und bestehen. Zwei F07-Erwartungen wurden ausdrücklich verschärft:

- `test_high_flow_detects_by_total_volume_before_duration` verlangt jetzt zunächst Ablehnung des 100-Liter-Sprungs bei nur 66,7 Litern Flow-Evidenz; die ursprüngliche Aktivierungsprüfung erfolgt erst bei ausreichender Evidenz und frischem Totalreport.
- `test_f07_pending_quantum_keeps_common_reference_until_flow_supports_it` verlangt zusätzlich, dass der eingefrorene alte Sprung auch nach Flow-Aufholen abgelehnt bleibt, bevor ein ausdrücklich neuer Report bestätigt.

Im bestehenden Release-Test wurden nur die CLI-Testprogramme um atomare Ref-Erstellung und Release-Metadaten erweitert. Die bisherigen Erfolgs-/Fehler-Szenarien und Assertions bleiben erhalten. Alle übrigen bestehenden Testdateien bleiben unverändert. Die neue Suite umfasst 41 Mess-/Steuerungs-/Lernfälle, 17 Notification-Fälle, 127 Restore-Fälle und 33 Release-Fälle.

### Prüfgrenzen und Bereitstellung

Runtime-Tests nutzen reale HA-States, Eventbus, Services, Registries, ConfigEntries und Store-Dateien. Einzelne Plattformgrenzen bleiben gemockt. Der bestehende Executor-Test-Harness arbeitet synchron; er wurde nicht geändert. Hassfest verwendet wegen Sandbox-Einschränkungen einen seriellen Pool, führt aber alle Integration-Validatoren aus. Die Release-Tests prüfen echte Bash-Abläufe mit kontrollierten APIs und zusätzlich echten temporären Git-Objekten, nicht eine tatsächliche GitHub-Veröffentlichung. Ein realer Gerätebetrieb und physische Mobilzustellung werden nicht behauptet.

README, Changelog und lokale Betriebs-/Release-Dokumentation sind abgestimmt; Version bleibt 1.0.2 und diese Korrekturrunde ist unveröffentlicht. Bereitstellung ausschließlich als Commit auf `review/korrekturrunde-3`; genauer SHA in der Abschlussmeldung. Kein main-Update, Merge, Pull Request, Tag, Release oder Wiki-Publishing.
