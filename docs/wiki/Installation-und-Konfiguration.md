# Installation und Konfiguration

## Voraussetzungen

- Home Assistant 2026.9.0 oder neuer
- HACS empfohlen
- mindestens ein kompatibler Durchflusssensor
- optional ein kumulierter Gesamtverbrauchssensor
- für Benachrichtigungen: Home Assistant Companion App mit registriertem `notify.mobile_app_*`-Dienst

## Installation über HACS

Repository:

`https://github.com/BeGiBue/homeassistant-water-leak-detection`

Kategorie:

**Integration**

Nach der Installation:

1. Home Assistant neu starten.
2. **Einstellungen → Geräte & Dienste → Integration hinzufügen** öffnen.
3. Nach **Wasserwächter** suchen.
4. Einrichtung starten.

## Ersteinrichtung

### 1. Messquellen

Es gibt zwei Wege:

- einzelne Entitäten direkt auswählen
- ein Home-Assistant-Gerät auswählen und kompatible Sensoren daraus erkennen lassen

Erforderlich:

- Durchflusssensor

Optional:

- Gesamtverbrauchssensor

### 2. Benachrichtigungsempfänger

Bereits während der Installation können ein oder mehrere Companion-Geräte hinzugefügt werden.

Pro Gerät werden konfiguriert:

- Anzeigename
- `notify.mobile_app_*`
- passender `device_tracker.*`
- Critical-Burst-Alarm ja/nein
- globale Quittierung zuhause erlaubt ja/nein
- stationäres vertrauenswürdiges Home-Gerät ja/nein

Die Einrichtung kann auch ohne Empfänger abgeschlossen werden.

## Konfiguration später wieder öffnen

Die Konfiguration ist **nicht** auf die Installation beschränkt.

Unter:

**Einstellungen → Geräte & Dienste → Integrationen → Wasserwächter → Konfigurieren**

stehen drei Bereiche zur Verfügung:

### Messquellen

- Durchflusssensor ändern
- optionalen Gesamtverbrauch ändern

### Benachrichtigungsempfänger

- hinzufügen
- bearbeiten
- entfernen
- **Zurück zur Konfiguration** führt wieder ins Hauptmenü

Beim Speichern bleibt der Konfigurator geöffnet:

- Hinzufügen, Bearbeiten und Entfernen führen zurück zur Empfängerübersicht.
- Messquellen und Experteneinstellungen führen zurück zur Hauptübersicht.
- Das X oben links beendet den Options-Flow vollständig.

Die Empfängerübersicht zeigt bewusst nur die vergebenen Anzeigenamen. Technische `notify.*`- und `device_tracker.*`-IDs werden dort nicht mehr ausgeschrieben.

### Experteneinstellungen

Hier liegen unter anderem:

- Detektorgrenzen
- Erkennungszeiten
- Resetzeiten
- High-Flow-Bypass
- Lernfenster
- manuell bekanntes Normalmaximum
- Rohrdurchmesser
- statischer Druck
- adaptive Multiplikatoren
- Zuordnung der Detektoren zur Absperranforderung

Home Assistants separate Funktion **Neu konfigurieren** für Messquellen wird zusätzlich unterstützt.

## High-Flow-Bypass

Der High-Flow-Bypass ist für geplante hohe Verbräuche gedacht, z. B.:

- Pool befüllen
- längere Gartenbewässerung
- andere bewusst hohe Wasserentnahme

Er unterdrückt nur **High Flow**.

Er unterdrückt **nicht**:

- Slow Leak
- Low Flow
- Burst Leak

Der Bypass hat immer eine Ablaufzeit und kann nicht versehentlich dauerhaft aktiv bleiben.

## Sprache

Die Integration folgt der Home-Assistant-Sprache.

Bei `de` werden unter anderem deutsch dargestellt:

- Integrationstitel **Wasserwächter**
- Gerätename
- Entitätsnamen
- Zustände
- Konfigurationsdialoge
- Aktionen
- Companion-Pushtexte

Englischer Fallback ist **Water Leak Guard**.

## Wichtiger Hinweis nach Änderungen

Änderungen über die Konfiguration führen zu einem Reload der Integration.

Bei einer HACS-Aktualisierung sollte Home Assistant vollständig neu gestartet werden, wenn HACS dies anfordert.
