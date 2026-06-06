# 🍳 ha-rezepte

Rezeptverwaltung als Home Assistant Panel – direkt in der Seitenleiste, optimiert für Tablet und Smartphone.

## Features

- 📋 Rezepte anlegen, bearbeiten und löschen
- 🔍 Volltextsuche über Titel, Beschreibung, Kategorie und Zutaten
- 🏷️ Kategorie-Schnellfilter als Buttons
- 🔤 Alphabetische Sortierung und Gruppierung nach Kategorie
- 🍳 Kochmodus: Schritt-für-Schritt mit Fortschrittsbalken
- ⏱️ Timer pro Kochschritt mit Vibration bei Timer-Ende
- 📢 Timer-Ansagen auf Alexa Echo und anderen Lautsprechern
- ⚖️ Portionsscaler
- 📥 Rezept-Import via [ha-rezepte-import](https://github.com/Noack1978/ha-rezepte-import)

## Installation

### Via HACS

[![In HACS öffnen](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=Noack1978&repository=ha-rezepte&category=integration)

1. HACS → Integrationen → ⋮ → Benutzerdefinierte Repositories
2. URL: `https://github.com/Noack1978/ha-rezepte`, Kategorie: **Integration**
3. **ha-rezepte** installieren → HA neu starten

### Manuell

`custom_components/rezepte/` nach `/config/custom_components/rezepte/` kopieren, HA neu starten.

## Einrichtung

Einstellungen → Integrationen → + → **Rezepte**

### Timer-Ansagen konfigurieren

| Feld | Beschreibung |
|------|-------------|
| Alexa Echo-Geräte | Echo-Lautsprecher → Alexa Announce |
| Andere Lautsprecher | Sonos, TV, … → HA TTS |
| TTS-Engine | Standard: `tts.google_translate_de_de` (eingebaut, kostenlos) |

Geräte-Auswahl auch direkt im Kochmodus am Timer möglich (📢-Button).

**Einstellungen ändern:**
Integrationen → Rezepte → ⋮ → Neu konfigurieren

## Changelog

### v1.3.1
- 🎨 Icon und Logo hinzugefügt

### v1.3.0
- 🔍 Volltextsuche (Titel, Beschreibung, Kategorie, Zutaten)
- 🏷️ Kategorie-Schnellfilter als scrollbare Buttons
- 🔧 Timer-Ansagen Zuverlässigkeit verbessert

### v1.2.3
- 📢 Timer-Ansagen bei Timer-Ende
- Alexa Echo und HA TTS (Sonos, TV, …) gleichzeitig nutzbar
- Geräte-Auswahl im Kochmodus

### v1.2.0
- PDF-Import (via ha-rezepte-import)
- Sortierung und Gruppierung nach Kategorie

## Lizenz

MIT
