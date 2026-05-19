# 🍳 Rezepte – Home Assistant Integration

Eine Rezept-Verwaltung als Web-App direkt im Home Assistant Dashboard.  
Rezepte hinzufügen, bearbeiten, löschen – mit Kochmodus und Timer.

## Features

- 📋 Rezepte verwalten (hinzufügen, bearbeiten, löschen)
- ⚖️ Portionsscaler (Zutaten automatisch umrechnen)
- 👨‍🍳 Kochmodus mit Schritt-für-Schritt-Ansicht
- ⏱ Integrierte Timer pro Schritt (mit Vibration)
- 🔄 Geräteübergreifend (Daten auf dem HA-Server)
- 📱 Optimiert für Tablet und Companion App

---

## Installation

### Manuell

1. Repository herunterladen
2. Ordner `custom_components/rezepte/` nach `/config/custom_components/rezepte/` kopieren
3. Home Assistant neu starten

### Via HACS

1. HACS → Integrationen → ⋮ → Benutzerdefinierte Repositories
2. URL dieses Repositories eintragen, Kategorie: **Integration**
3. Integration **Rezepte** installieren
4. Home Assistant neu starten

---

## Einrichtung

### 1. Integration aktivieren

In `configuration.yaml` eintragen:

```yaml
rezepte:
```

HA neu starten. Die Integration:
- kopiert die Web-App automatisch nach `/config/www/rezepte/`
- registriert den Service `rezepte.save_recipes`
- fügt **Rezepte** als Eintrag in der Seitenleiste hinzu

### 2. Long-Lived Access Token erstellen

**HA → Profil → Sicherheit → Langlebige Zugriffstoken → Token erstellen**

Den Token beim ersten Start der App im Dialog eingeben.  
Er wird im Browser-Speicher des Geräts gespeichert.

### 3. Dashboard-Karte (optional)

Die App ist automatisch in der Seitenleiste verfügbar.  
Alternativ als Dashboard-Karte:

```yaml
type: webpage
url: /local/rezepte/index.html
aspect_ratio: "16:9"
```

---

## Rezeptformat

Rezepte werden in `/config/www/rezepte/recipes.json` gespeichert.

```json
[
  {
    "id": 1748000000000,
    "title": "Rezeptname",
    "subtitle": "z. B. Thermomix TM31",
    "emoji": "🍳",
    "category": "Hauptgericht",
    "description": "Kurzbeschreibung",
    "baseServings": 4,
    "servingLabel": "Portionen",
    "ingredients": [
      { "amount": 200, "unit": "g", "name": "Zutatname" }
    ],
    "steps": [
      { "text": "Schrittbeschreibung", "timerSec": 300 }
    ],
    "notes": ["Tipp oder Hinweis"]
  }
]
```

**Unterstützte Einheiten:** `g` `kg` `ml` `l` `TL` `EL` `Stk.` `Prise` `n.B.`  
**`timerSec`:** Zeit in Sekunden (0 = kein Timer)

---

## Struktur

```
custom_components/rezepte/
├── __init__.py          # Service-Registrierung, Panel, Datei-Setup
├── manifest.json        # Integration-Metadaten
├── services.yaml        # Service-Schema
└── www/
    ├── index.html       # Web-App
    └── recipes.json     # Initiale Beispieldaten
```

---

## Lizenz

MIT
