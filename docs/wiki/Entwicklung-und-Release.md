# Entwicklung, Tests und Release

## Repository

`BeGiBue/homeassistant-water-leak-detection`

Technische Domain:

`water_leak_detection`

Der sichtbare Name darf geändert bzw. übersetzt werden, die Domain sollte nach Veröffentlichung stabil bleiben.

---

# 1. Entwicklungsmodell

Änderungen werden auf Feature-/Fix-Branches entwickelt.

Vor Merge nach `main` werden je nach Änderung geprüft:

- JSON
- Python Compile
- Ruff
- Pytest
- Hassfest
- HACS-Validator

---

# 2. Tests

Die Tests sind bewusst deterministisch und decken unter anderem ab:

- Detektor-Zustandsautomaten
- Resetverhalten
- High-Flow-Bypass
- Burst-Unabhängigkeit vom Bypass
- Rapid-Rise-Burst
- Lernmodell
- Confidence
- saisonale Anpassung
- hydraulische Grenzen
- Config Flow
- Benachrichtigungen
- Home-/Away-Quittierung
- Rückkehr-nach-Hause
- Übersetzungs-/UI-Metadaten

Der Stand vor dem ersten 0.3.0-Release wurde mit **94 Tests** erfolgreich geprüft. Die Release-Metadaten werden zusätzlich darauf geprüft, dass die Integration **nicht** als Home-Assistant-Helfer klassifiziert ist.

---

# 3. Hassfest

Hassfest prüft Home-Assistant-spezifische Metadaten und Strukturen.

Der dokumentierte Stand wurde mit:

`Invalid integrations: 0`

validiert.

---

# 4. GitHub Actions

Die Projekt-Workflows sind absichtlich **manual-only** über `workflow_dispatch`.

Grund:

Automatische Checks auf jeden Push/PR erzeugten unnötig viele Benachrichtigungen.

Automatische Trigger sollen nicht ohne bewusste Entscheidung wieder aktiviert werden.

Workflows:

- Validate
- Hassfest
- HACS
- Publish 1.0.2

---

# 5. HACS

Für HACS wichtig:

- öffentliches Repository
- `hacs.json`
- gültiges `manifest.json`
- README
- Topics
- lokale Brand-Assets
- veröffentlichter GitHub Release für Release-Versionierung

Der HACS-Anzeigename ist:

**Water Leak Guard**

Deutsch wird erst innerhalb Home Assistant zu:

**Wasserwächter**

---

# 6. Release 1.0.2

Das Repository enthält:

- `CHANGELOG.md`
- `RELEASE_NOTES_1.0.2.md`
- manuellen Publish-Workflow

Der Release-Workflow prüft die Manifest-Version **und** `integration_type: "service"` und erzeugt den GitHub Release `1.0.2`.

Der veröffentlichte 0.3.0-Tag enthielt noch `integration_type: "helper"`. Das wurde erst nach dem Tag auf `main` korrigiert. 1.0.0 war deshalb der erste stabile Release, der von Home Assistant als normale Integration und nicht als Helfer einsortiert wird.

---

# 7. Versionsphilosophie

## 0.1

Kern-Detektion und HA-Backend.

## 0.2

Companion-Benachrichtigungen und gerätebasierte Quittierung.

## 0.3

Adaptives Lernen, Confidence, Hydraulik und Rapid-Rise-Burst.

---

# 8. Nicht verhandelbare Regressionen

Änderungen dürfen insbesondere nicht dazu führen, dass:

- High-Flow-Bypass Burst deaktiviert
- Quittierung einen Detektor beendet
- Quittierung Shut Off löscht
- `unknown` als 0 gewertet wird
- verdächtige Episoden das Lernmodell erhöhen
- ein Away-Gerät global quittieren kann
- Slow und Low nur noch gemeinsam abschaltbar sind
- die Integration im Manifest wieder als `helper` statt als normale `service`-Integration klassifiziert wird

Diese Punkte sollten bei Änderungen an Engine, Manager oder Notifications immer als Regressionstests erhalten bleiben.


## 1.0.1

Version 1.0.1 verbessert die Verwaltung mehrerer Benachrichtigungsempfänger: Bereits eingerichtete Geräte werden während Einrichtung, Hinzufügen, Bearbeiten und Entfernen gemeinsam angezeigt. Sichtbar sind Anzeigename, Companion-Benachrichtigungsdienst und Device Tracker; interne IDs und Action-Tokens bleiben verborgen.


## 1.0.2

Version 1.0.2 behebt die Navigation im Home-Assistant-Konfigurator. Speichern beendet den Options-Flow nicht mehr, sondern führt zurück zum passenden Menü. Das Empfänger-Untermenü besitzt zusätzlich **Zurück zur Konfiguration**. Außerdem wurden sichtbare `\n\n`-Escape-Sequenzen in der Empfängerübersicht korrigiert und die Übersicht auf kompakte Anzeigenamen reduziert.
