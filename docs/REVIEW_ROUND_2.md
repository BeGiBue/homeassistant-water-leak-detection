# Abschlussbericht – Korrekturrunde 2

Basis: `review/korrekturrunde-1`, Commit `96d5128503d33fe44d6a17232749a35ad672ca28`.
Arbeits- und Review-Branch: `review/korrekturrunde-2`.

Bearbeitet wurden ausschließlich F05, F06, F07, F15 (Zeitbasis), F16 und F20 sowie zugehörige Tests und Dokumentation. F02, F04, F08 und die fachliche Rapid-Rise-Definition bleiben unverändert. Keine neuen Leckageklassen, Erkennungsschwellen oder Erkennungszeiten. Die physische Ventilsteuerung verbleibt bei Home-Assistant-Automationen.

## F05 – Kadenzverträglichkeit und frische Mess-Evidenz

**Ursache:** Ein pauschales 30-Sekunden-Ablaufmodell unterbrach reguläre langsamere Sensoren. Wiederholtes Lesen eines gespeicherten States konnte dagegen unbestätigte Messzeit liefern.

**Änderung:** `SourceEvidence` unterscheidet tatsächlich neue Reports anhand State-Identität und HA-Report-Informationen. Identische, erneut gemeldete Werte werden über Home Assistants `state_reported`-Helper erfasst. Interne Ticks liefern keine Erkennungs- oder Ruhe-Evidenz. Eingefrorene hohe Werte aktivieren deshalb keinen Leak; eingefrorene Nullwerte beenden keinen aktiven Leak. Die automatische Kadenz nutzt nach zwei beobachteten Intervallen das 1,5-Fache des größten der letzten fünf Intervalle. Anlauf und längere Lücken verwerfen unbestätigte Zeit; außergewöhnliche Lücken werden nicht sofort als Normalbetrieb gelernt. Wiederholt bestätigte langsame Anlaufintervalle können auch jenseits der anfänglichen 300-Sekunden-Beobachtungsgrenze eine Kadenz etablieren.

Der Standard ist `0 = automatisch`. Der in Runde 1 gegebenenfalls mitgespeicherte Standardwert 30 wird ohne neue explizite Auswahlmarkierung automatisch behandelt. Andere positive Altwerte bleiben erhalten; eine absichtlich gewünschte 30-Sekunden-Grenze kann erneut gespeichert werden.

**Regressionstests:** `tests/test_round2_measurements.py`: 5/30/exakt 30/60/120 Sekunden, zusätzlich 600 Sekunden; alle vier Leckageklassen, interne Ticks, identische frische Reports, eingefrorene hohe und Null-States, Wiederkehr nach Ausfall, ausgelassene reguläre Reports, Upgrade und explizite Expertenoptionen.

**Dateien:** `evidence.py`, `manager.py`, `const.py`, `config_flow.py`, Übersetzungen, README und Konfigurations-/Betriebsdokumentation.

**Grenzen:** Unbekannte Zeit wird konservativ verworfen; das kann die erstmalige Bestätigung nach Anlauf oder Ausfall verzögern. Der alte Optionswert allein verrät nicht, ob 30 Sekunden früher ausdrücklich beabsichtigt waren; diese Grenze muss gegebenenfalls erneut gespeichert werden. Frische Reports belegen eine erneute HA-Meldung, nicht die physische Messrichtigkeit des Geräts.

## F06 – Benachrichtigungen und Timeout-Verhalten

**Ursache:** Serieller Versand und ein Fünf-Sekunden-Timeout konnten andere Empfänger blockieren beziehungsweise nach bereits ausgelöstem Push einen automatischen Doppelversand erzeugen. Ein normaler Service-Return wurde zu weitgehend als Zustellung interpretiert.

**Änderung:** Unabhängige Tasks je Event/Empfänger, ohne lokalen Fünf-Sekunden-Abbruch. Kein zweiter gleichzeitiger Dispatch derselben Kombination. Persistierte Zustände unterscheiden `not_dispatched`, `in_flight`, `accepted`, `failed` und `interrupted`. Fehlende Dienste bleiben offen; echte lokale Exceptions werden isoliert und über reguläre Ticks erneut versucht. Normaler Return bedeutet ausschließlich erfolgreiche Übergabe an den HA-Notify-Service. Alte persistierte `delivered_recipients` werden kompatibel als akzeptierte Übergaben gelesen. Quittierung wird unmittelbar vor dem Serviceaufruf erneut geprüft. Laufende Tasks werden beim Unload abgebrochen und abgewartet; eine bereits begonnene, dadurch unklare Übergabe wird nicht blind automatisch wiederholt.

**Regressionstests:** `tests/test_round2_notifications.py`: Service über fünf Sekunden, hängender und schneller Empfänger, gleichzeitige Retry-Anläufe, Quittierung vor beziehungsweise während Übergabe, Unload, Restore akzeptierter und unterbrochener Übergaben, Migration/beschädigte Statusfelder, Event-Ende vor Worker-Start sowie intern abgefangener Remote-Push-Fehler. Bestehende Tests für fehlenden Dienst, Exception-Isolation und nie dispatchte restaurierte Events bleiben erfolgreich.

**Dateien:** `notifications.py`, README und Betriebsdokumentation.

**Grenzen:** Die Integration garantiert die Übergabe an den konfigurierten Home-Assistant-Notify-Service, nicht die physische Zustellung auf dem Telefon. Ein bereits übergebener Aufruf kann nicht zurückgerufen werden. Bei unterbrochener Übergabe ist die tatsächliche Wirkung unbekannt und erfordert Prüfung. Ein Prozessabsturz zwischen Service-Return und Persistenz kann weiterhin keine exakt-einmalige Übergabe garantieren. Ein dauerhaft hängender Service bleibt bis zum Unload offen, blockiert aber andere Empfänger nicht.

## F07 – Plausibilisierung von Totalzählern

**Ursache:** Der Vergleich mit einem kurzen Einzelintervall und einem festen Literzuschlag war für grob quantisierte Zähler ungeeignet. Ein unveränderter Totalwert konnte unabhängige Flow-Mengen entwerten.

**Änderung:** Gemeinsame Referenz seit dem letzten akzeptierten Zählerfortschritt; Flow-Evidenz wird über alle Zwischenreports akkumuliert. Positive Fortschritte werden gegen diesen akkumulierten Rahmen geprüft (Faktor 1,5, ohne festen Literzuschlag). Noch nicht gestützte Quantensprünge bleiben aus der Alarmmenge ausgeschlossen, ohne die gemeinsame Referenz nach jedem verworfenen Sprung zurückzusetzen. Reset, Rücksprung sowie Ausfall/Wiederkehr basieren den Zähler neu, ohne aktive Sicherheitszustände zu löschen. Auch Total-Ausfälle zwischen Flow-Reports werden erfasst. Eingefrorene Totalwerte vetoieren die Flow-Integration nicht.

**Regressionstests:** `tests/test_round2_measurements.py`: kontinuierliche Zähler und 1/10/100-Liter-Quantisierung bei unterschiedlichen Flow-/Total-Kadenzen; eingefrorene Werte; Reset auf 0; negativer Sprung; unrealistischer positiver Sprung; zunächst ungestützter später plausibler Quantensprung; Ausfall und Wiederkehr einschließlich `unknown`, `unavailable`, ungültiger und negativer Totalwerte.

**Dateien:** `engine.py`, `manager.py`, README und Betriebsdokumentation.

**Grenzen:** Plausibilisierung ist weiterhin eine konservative Konsistenzprüfung zweier Messquellen, keine Garantie der Zählergenauigkeit. Ein erster großer Quantensprung bleibt bis zu ausreichender Flow-Evidenz unberücksichtigt. Die bestehende Begrenzung langer einzelner Flow-Integrationsintervalle bleibt unverändert und kann sehr langsame Quellen konservativ unterschätzen.

## F15 – Monotone Laufzeit statt UTC-Ordnungsannahmen

**Ursache:** UTC-Vergleiche konnten nach Zeitkorrekturen neue Reports verwerfen und Laufzeit-/Quiet-/Bypass-Dauern springen lassen.

**Änderung:** Prozessinterne Intervalle verwenden eine monotone Zeitachse. Neue/überholte HA-Events werden anhand des aktuellen State-Objekts und der Report-Verarbeitung erkannt; UTC ist kein primäres Ordnungsmerkmal. Ereignis-Anzeige und persistierte absolute Zeitpunkte bleiben tatsächliche UTC-Werte. Aktive Laufzeit wird zusätzlich als verstrichene Dauer gespeichert. Bypass nutzt im Prozess eine monotone Deadline; die Persistenz projiziert die exakte verbleibende Dauer einschließlich Sekundenbruchteilen auf UTC. Die fachliche Rapid-Rise-Definition wurde nicht geändert.

**Regressionstests:** `tests/test_round2_measurements.py`: UTC +1/-1 Stunde; weitere identische Reports nach Rückstellung; sogar erneut gleicher UTC-Reportzeitpunkt; überholtes queued State-Event; aktiver Leak, laufender Quiet-Timer, Laufzeitsensor, Bypass und Restore/Reload nach Korrektur; reale UTC-Ereignislabels und fraktionale Bypass-Persistenz.

**Dateien:** `manager.py`, `engine.py`, `sensor.py`, `evidence.py`, README und Betriebsdokumentation.

**Grenzen:** Nicht beobachtete Offline-Zeit wird nicht als bestätigte Messzeit gezählt. Altdaten ohne gespeicherte monotone Laufzeit beginnen die wiederhergestellte Laufzeitanzeige konservativ bei null. Absolute Bypass-Restore-Zeit nach einem unkontrollierten Absturz und anschließender Uhrkorrektur bleibt grundsätzlich mehrdeutig. UTC-Anzeigezeitpunkte können nach Rückstellung zeitlich rückwärts erscheinen; sie steuern keine laufenden fachlichen Intervalle.

## F16 – Fail-safe Restore beschädigter Sicherheitsereignisse

**Ursache:** Ein ungültiges `phase`-Teilfeld konnte trotz übriger eindeutiger Eventinformationen zum vollständigen Reset führen.

**Änderung:** Explizit aktive oder aus konsistenten verbleibenden Angaben bestätigte Ereignisse bleiben aktiv. Event-ID, Detektionszeit und gegebenenfalls weitere bestätigende Runtime-Daten bilden die konservative Restore-Grundlage. Fehlende/beschädigte IDs werden bei ansonsten bestätigtem Event neu erzeugt. Ungültige optionale Gründe/Mengen werden bereinigt; Quiet-Evidenz wird nicht restauriert. Bedeutungsloses oder unbestätigtes Monitoring erzeugt keinen neuen Alarm. Aktive Safety-Zustände und daraus resultierende Shutoff-Anforderungen bleiben erhalten.

**Regressionstests:** `tests/test_round2_restore_release.py`: einzeln beschädigte Phase, ID, Detektionszeit, Grund, Menge, Quiet-Zeit sowie kombinierte Schäden; echte Store-/Manager-Setup-Abläufe; erhaltener aktiver Leak und Shutoff; leere/bedeutungslose Daten und beschädigtes Monitoring ohne erfundenen Alarm.

**Dateien:** `engine.py` sowie Betriebsdokumentation.

**Grenzen:** Wenn alle belastbaren Bestätigungsinformationen verloren sind, kann kein aktives Ereignis sicher rekonstruiert werden. Eine neu erzeugte Ersatz-ID übernimmt keine alte Quittierung und kann daher erneut benachrichtigt werden.

## F20 – Vorhandener Release-Tag ohne Release

**Ursache:** Die bisherigen Checks erfassten bereits existierende Releases, aber nicht ausreichend einen vorhandenen Tag ohne Release.

**Änderung:** Gemeinsames Bash-Skript für beide Release-Workflows. Vor Release-Erstellung wird der Remote-Tag gesucht und gegebenenfalls sein Commit einschließlich annotierter Tags aufgelöst. Nur exakt `GITHUB_SHA` ist zulässig. Fehler bei der Remote-Abfrage brechen geschlossen ab. Passender Tag ohne Release erlaubt die Fortsetzung; abweichender Tag bricht unabhängig vom Release-Zustand ab. Vorhandener Release wird nur nach erfolgreicher Tag/SHA-Prüfung übersprungen. Neue Erstellung verwendet ausdrücklich `--target GITHUB_SHA`. Checkout und vorgeschaltete Validation bleiben an denselben SHA gebunden.

**Regressionstests:** `tests/test_round2_restore_release.py` führt das tatsächliche gemeinsame Bash-Skript mit kontrollierten Git-/GH-Testprogrammen aus: kein Tag/kein Release; richtiger/falscher Tag ohne Release; richtiger/falscher Tag mit Release; Re-Run; fehlender Tag trotz Release; Remote-Abfragefehler – jeweils für 1.0.1 und 1.0.2. Es werden keine realen Tags oder Releases angelegt.

**Dateien:** `.github/release_checked_commit.sh`, beide Release-Workflows und `docs/RELEASING.md`.

**Grenzen:** Remote-Prüfung und Release-Erstellung sind keine atomare Serveroperation. Unveränderliche beziehungsweise geschützte Tags bleiben für den Betrieb sinnvoll. Ein echter GitHub-Release wurde auftragsgemäß nicht ausgeführt.

## Ergebnisse aller Prüfungen

| Prüfung | Ergebnis |
|---|---|
| Gesamte pytest-Suite | **272 bestanden**: ursprüngliche 179 + 93 neue Fälle |
| Neue Regressionstests separat | **93 bestanden** |
| Gezielte Sicherheitsauswahl | **65 bestanden**, 207 abgewählt |
| Ruff 0.16.10 | bestanden |
| Python-Kompilierung | 34 Dateien bestanden; Artefakte außerhalb des Repositorys |
| JSON | 4 Dateien gültig |
| Workflow-YAML / Bash | YAML lesbar; 10 Run-Blöcke und gemeinsames Release-Skript syntaxgeprüft |
| Hassfest, HA Core 2026.9.4 | 1 Integration, 0 ungültige Integrationen |
| Git-Diff-Whitespace | `git diff --check` bestanden |
| Ursprüngliche Testdateien | unverändert |
| Schutz-Diff | 21 gezielt geprüfte Funktionen gegenüber Runde 1 AST-identisch |

Getestet mit Python 3.14.2 und Home Assistant 2026.9.4. pytest meldet ausschließlich eine DeprecationWarning aus Home Assistants HTTP-Abhängigkeit.

Die Sicherheitsauswahl umfasst Quittierung ohne Leak-/Shutoff-Reset, Burst trotz High-Flow-Bypass, ungültige/negative Quellen ohne Entwarnung, Erhalt aktiver niedrigerer Klassen und neue Events ohne übernommene Quittierung. Zusätzlich läuft die gesamte ursprüngliche Suite unverändert mit.

Der Schutz-Diff prüft insbesondere `_sample_slow`, `_sample_low`, `_sample_high`, `_sample_burst`, Settings-/Quellenwechsel, aktive Eventauswahl, die bereits korrigierte Persistenzplanung, Quittierungsautorisierung, Quellenvalidierung, Navigation und Config-Entry-Setup/Unload/Options-Reload. Änderungen an gemeinsam genutzter Zeit-, Mengen-, Restore- und Dispatch-Infrastruktur sind den sechs beauftragten Findings zugeordnet; keine fachliche Rapid-Rise-Änderung.

## Prüfgrenzen und Bereitstellung

Die Runtime-Tests verwenden echte Home-Assistant-States, Eventbus, ServiceRegistry, Registries, ConfigEntries und Store-Dateien. Plattformgrenzen werden teilweise gemockt; der bestehende Test-Harness führt Executor-Arbeit synchron aus. Hassfest lief wegen Sandbox-Einschränkungen seriell statt mit einem Multiprocessing-Pool; alle eigentlichen Validatoren wurden ausgeführt. Ein realer HA-Gerätebetrieb, die physische Push-Zustellung und ein tatsächlicher GitHub-Release wurden nicht behauptet oder ausgeführt.

README, Konfigurations- und Betriebsdokumentation, Übersetzungen und Changelog sind auf das neue technische Verhalten abgestimmt. Wiki-Dateien wurden nur lokal bearbeitet, nicht veröffentlicht. Bereitstellung erfolgt ausschließlich als Commit auf dem Review-Branch; der genaue Commit-SHA steht in der Abschlussmeldung. Kein Merge, Pull Request, Tag oder Release.
