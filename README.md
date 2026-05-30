# MY_APP – Persönliche Punkte-Tracking App

## Projektübersicht

Eine vollständige SwiftUI iOS-App mit einem flexiblen Punkte-System zur Ernährungsverfolgung (basierend auf Nährwerten).

---

## Funktionen

| # | Feature | Implementiert |
| 1 | **Persönliche Daten & Punkteberechnung** | Geschlecht, Alter, Größe, Gewicht, Aktivität, Ziel → automatische Tagespunkte |
| 2 | **Lebensmittel-Datenbank** | 80+ vorgeladene Lebensmittel mit Punkte-Bewertung, Nährwerten, Zero-Punkte-Status |
| 3 | **Rezepte & eigene Lebensmittel** | Rezepte mit Zutaten, Portionen, automatische Punkt-Berechnung; eigene Lebensmittel hinzufügen/bearbeiten/löschen |
| 4 | **Ziele & Statistiken** | Sterne je 5 kg abgenommen ⭐, Fortschrittsbalken, % zum Ziel, Wochen-Auswertung |
| 5 | **Apple Health** | Gewicht, Schritte, aktive Kalorien synchronisieren; Gewichtsverlauf-Chart |

---

## Punkte-Berechnung (Basis: Alter, Gewicht, Aktivität)

```
Basis:      Frau = 7 Pkt.  |  Mann = 15 Pkt.
Alter:      18–20 = +5  |  21–35 = +4  |  36–50 = +3  |  51–65 = +2  |  66+ = +1
Größe:      < 160 cm = +1  |  ≥ 160 cm = +2
Gewicht:    Gewicht ÷ 10 (abgerundet)
Aktivität:  kaum = +0  |  wenig = +2  |  viel = +4  |  täglich viel = +6
Ziel:       Halten = +4  |  Abnehmen = +0
```

## Pläne

| Plan | 0-Punkte-Lebensmittel |
|------|-----------|
| 🔴 Restriktiv | Obst, Gemüse |
| 🔵 Ausgewogen | Obst, Gemüse, Hülsenfrüchte, Eier, mageres Fleisch |
| 🟡 Liberal | Obst, Gemüse, Vollkornprodukte, Fisch, Kartoffeln, Eier |

---

## Dateistruktur

```
Sources/MY_APP/
├── MY_APP.swift                  ← App-Einstiegspunkt
├── ContentView.swift             ← Routing: Onboarding ↔ Haupt-App
├── Models/
│   ├── UserProfile.swift         ← Profil, Geschlecht, Plan, Aktivität
│   ├── FoodItem.swift            ← Lebensmittel, Nährwerte, 0-Punkte-Flags
│   ├── Recipe.swift              ← Rezepte mit Zutaten
│   └── DailyLog.swift            ← Tagesprotokoll, Gewichtseinträge
├── Services/
│   ├── PointsCalculator.swift    ← Punkte-Berechnung + Statistik-Helfer
│   ├── HealthKitService.swift    ← Apple Health (Gewicht, Schritte, Kalorien)
│   └── DataStore.swift           ← Persistenz (UserDefaults + JSON)
├── Resources/
│   └── PreloadedFoods.swift      ← 80+ vorgeladene Lebensmittel
└── Views/
    ├── OnboardingView.swift       ← 5-Schritt Onboarding
    ├── MainTabView.swift          ← Tab-Navigation
    ├── DashboardView.swift        ← Heute: Punkte-Ring, Mahlzeiten, Wasser
    ├── FoodDatabaseView.swift     ← Suche, Kategorien, Hinzufügen/Bearbeiten
    ├── RecipesView.swift          ← Rezepte erstellen und verwalten
    ├── StatisticsView.swift       ← Sterne, Fortschritt, Chart, Protokoll
    └── SettingsView.swift         ← Profil, Plan, HealthKit, Punkte-Aufschlüsselung
```

---

## Xcode-Setup

### 1. Neues Projekt erstellen

1. Xcode öffnen → **File → New → Project**
2. **iOS App** wählen → Name: `MY_APP`
3. Interface: **SwiftUI**, Language: **Swift**

### 2. Dateien hinzufügen

Alle `.swift`-Dateien aus `Sources/MY_APP/` in das Xcode-Projekt ziehen (Struktur beibehalten).

### 3. HealthKit aktivieren

1. Xcode → Target → **Signing & Capabilities**
2. **+ Capability** → **HealthKit** hinzufügen
3. In `Info.plist` eintragen:

```xml
<key>NSHealthShareUsageDescription</key>
<string>Liest Gewicht, Schritte und aktive Kalorien aus Apple Health.</string>
<key>NSHealthUpdateUsageDescription</key>
<string>Speichert Gewichtseinträge in Apple Health.</string>
```

### 4. Deployment Target

Mindestens **iOS 17.0** (für SwiftUI-Features wie `.searchable`, `NavigationStack`).

---

## Bedienung

1. **Onboarding** (einmalig): Name → Körperdaten → Aktivität → Plan wählen
2. **Dashboard**: Lebensmittel per `+` hinzufügen, per Wischen löschen/bearbeiten
3. **Lebensmittel**: Suchen, nach Kategorie filtern, eigene anlegen
4. **Rezepte**: Zutaten kombinieren → Punkte pro Portion automatisch berechnet
5. **Statistik**: Gewicht eintragen → Sterne & Fortschritt werden automatisch aktualisiert
6. **Einstellungen**: Plan, Aktivität, Zielgewicht jederzeit ändern

---

*Erstellt mit GitHub Copilot – Punkte-Tracking für private Nutzung.*

---

## Windows-Version (ohne HealthKit)

Diese Repo enthaelt zusaetzlich eine Windows-lauffaehige Version als lokale Web-App:

- Ordner: `windows_app/`
- Startskript: `windows_app/run_windows.bat`
- Ohne Apple Health / HealthKit

### Start unter Windows

1. In den Ordner `windows_app` wechseln
2. `run_windows.bat` starten
3. Im Browser die angezeigte lokale URL oeffnen (meist `http://localhost:8501`)

### Enthaltene Funktionen

- Profil und Tagespunkte-Berechnung
- Lebensmittel-Datenbank mit eigenen Lebensmitteln
- Tageslog (Mahlzeiten, Punkte, Wasser, Bonus)
- Gewichtsprotokoll und einfache Statistik
