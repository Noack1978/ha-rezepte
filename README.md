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
- 🛒 Zutaten direkt zur Einkaufsliste hinzufügen (Bring! & andere todo-Listen)
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

### Zugriffstoken

Das Panel läuft als iFrame und benötigt beim ersten Öffnen einen **Long-Lived Access Token**:

1. HA → Profil (unten links) → **Langlebige Zugriffstoken** → Token erstellen
2. Token beim ersten Öffnen des Panels eingeben → wird im Browser gespeichert

> **Hinweis:** Das Token wird pro Browser/Gerät gespeichert. Außerhalb des Heimnetzwerks (z. B. über Nabu Casa) kann der Token-Flow Probleme bereiten – die App funktioniert zuverlässig im lokalen WLAN.

### Einkaufsliste

Im Rezept auf 🛒 tippen → Zutaten per Checkbox auswählen → Einkaufsliste wählen → Hinzufügen.

Mengen werden automatisch an den aktuellen Portionsscaler angepasst. Kompatibel mit Bring! und allen anderen `todo`-Entities in Home Assistant.

## Changelog

### v1.7.0
- 🍳 Airfryer-Einstellungen pro Rezeptschritt: Temperatur (°C) und Zeit
  (Min) lassen sich im Schritt-Formular hinterlegen
- Im Kochmodus erscheint bei entsprechenden Schritten ein Airfryer-Block
  mit **„Werte senden"** (überträgt Temperatur/Zeit an die konfigurierten
  Entities) und optional **„Starten"** als bewusst getrennter zweiter
  Schritt – kein automatischer Start beim Werte-Senden
- Neue Konfigurationsfelder in der Integration (Einstellungen → Geräte
  & Dienste → Rezepte → Konfigurieren): Airfryer Temperatur-Entity
  (`number.*`), Airfryer Zeit-Entity (`number.*`), Airfryer Start-Button
  (`button.*`) – alle optional

### v1.6.1
- 🆕 Neue Entity `sensor.rezepte_kochtimer_restlaufzeit` – zeigt die
  verbleibende Zeit in Sekunden, zählt live jede Sekunde herunter
  solange der Timer läuft. Geräteklasse „Dauer", nutzbar in Karten mit
  automatischer Zeitformatierung (z. B. Entities-Karte, Gauge, Bar-Karte).

### v1.6.0
- 🥕 Zutatenliste im Kochmodus erscheint jetzt als feste Spalte rechts
  neben der Schrittanzeige – klappt nicht mehr ungewollt ein beim Klick
  auf Timer, Weiter oder Zurück (vorher: Overlay-Sidebar blockierte Klicks)
- Auf schmalen Bildschirmen (< 700px) erscheint die Zutatenliste unterhalb
  der Schrittanzeige statt daneben
- 🔤 Neue Schriftgrößen-Einstellung im Kochmodus (80–160 %, über 🔤-Button
  im Header). Einstellung wird geräteweise gespeichert und bleibt auch
  beim nächsten Rezept erhalten

### v1.5.1
- 🐛 Bugfix: `sensor.rezepte_kochtimer` zeigte immer „Unbekannt" statt
  des Timer-Status. Ursache: Die Sensor-Klasse erbte von der generischen
  `Entity` statt von `SensorEntity` – nur Letztere übernimmt `native_value`
  automatisch als angezeigten Zustand.

### v1.5.0
- 🆕 Neue Entity `sensor.rezepte_kochtimer` – zeigt den Timer-Status
  (Inaktiv/Läuft/Pausiert) mit Attributen `step_num`, `remaining_seconds`
  und `finishes_at`. Kann auf beliebigen Dashboards, in Automationen oder
  Benachrichtigungen genutzt werden – unabhängig von der Rezepte-Karte
  und dem Kochmodus.

### v1.4.1
- 🐛 Bugfix: Timer stoppte bei Wiederherstellung des Kochmodus (z. B. nach
  App-Neustart) statt fortgesetzt zu werden. `renderCookStep()` rief
  intern immer `stopTimer()` auf – auch beim reinen Wiederherstellen.
  Automatischer Abbruch entfernt; Timer werden weiterhin korrekt gestoppt,
  wenn bewusst ein neuer Schritt gestartet wird (Start, Weiter, Zurück).

### v1.4.0
- ⏱️ Timer läuft jetzt server-seitig in Home Assistant (`async_call_later`)
  – unabhängig vom Browser, übersteht Dashboard-Wechsel und App-Neustart
- Neue interne Services: `rezepte.timer_start`, `rezepte.timer_pause`,
  `rezepte.timer_resume`, `rezepte.timer_cancel`
- Timer-Status wird in `timer_state.json` gespeichert und vom Frontend
  gepollt (kein HA-Token für den Status nötig)
- Ansage an Alexa/TTS wird automatisch von HA gesendet, sobald der Timer
  abläuft – auch wenn kein Browser offen ist
- Kochmodus-Wiederherstellung liest den Timer-Status direkt aus HA

### v1.3.3
- Kochmodus wird nach HA-Seitenneuladen automatisch wiederhergestellt
  (letzter Schritt, Timer-Stand inkl. verstrichener Zeit)
- Navigationsschutz: Zurück-Geste/Browser-Zurück verlässt den
  Kochmodus nicht mehr ungewollt
- Beenden-Button im Kochmodus deutlich präsenter gestaltet
- Einkaufsliste: Zutaten im Format „Mehl (250 g)"

### v1.3.2
- 🛒 Zutaten zur Einkaufsliste hinzufügen (Checkbox-Auswahl + todo-Listen-Auswahl)

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
