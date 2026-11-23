# WHOOP Insights 2.0 — persönliches Performance Lab

Die Web-App ist eine **private WHOOP-Datenansicht** auf Basis von Python/FastAPI und der offiziellen WHOOP Developer API v2. Sie zeigt aktuelle, bereits verarbeitete Daten; keine Sekundentakt-Rohdaten.

## Vier eigenständige Bereiche

1. **Cockpit** — Recovery, HRV, Ruhepuls, Schlafdauer, 7-Tage-Trends, letzte Werte.
2. **Schlaflabor** — Schlafdauer, Performance, Effizienz, Schlafphasen, Einschlafzeit und Hauptschlaf-Tabelle.
3. **Trainingsanalyse** — Einheiten, Trainingszeit, Aktivitätsmix, Herzfrequenzzonen, Workout-Historie inklusive Strain und mittlerer HF.
4. **Zusammenhänge** — Training → nächste Hauptschlafphase → Recovery am Morgen, eigene Filter für Aktivität, Trainingsmerkmal (Strain / Dauer / Abstand bis zum Schlafbeginn) und Folgemesswert, Streudiagramme sowie Training-/Ruhetag-Vergleiche.

## Wie die Zusammenhänge berechnet werden

- Die Zuordnung erfolgt anhand der **tatsächlichen Uhrzeiten** der WHOOP-Workouts und des Schlafbeginns. Ein Workout zählt, wenn es spätestens 24 Stunden vor Beginn der nächsten erfassten Hauptschlafphase beendet wurde. Workouts während des Schlafs werden nicht zugeordnet.
- **Analyseeinheit ist die Nacht**. Gibt es zwei oder mehr Workouts vor einer Nacht, zählt die Nacht nur einmal: Als Sportart wird die *zuletzt absolvierte Aktivität* gezeigt; als Intensitätsvariable verwenden wir den *höchsten Workout-Strain* in diesem 24-Stunden-Fenster (nicht die Summe der nicht-additiven Strain-Werte). Die Workout-Anzahl ist sichtbar.
- Der Recovery-/HRV-Folgewert wird ausschließlich über die von WHOOP gelieferte **sleep_id** mit der Schlafphase verknüpft. Wenn WHOOP keinen Recovery-Wert liefert, bleibt er leer.
- Nächte ohne Workout in den letzten 24 Stunden sind die Vergleichsgruppe, **nur wenn der Workout-Endpunkt erfolgreich abrufbar** war. Beim Fehler dieses Endpunkts wird die gesamte Korrelationsanalyse deaktiviert, statt trainingsfreie Nächte zu erfinden.
- Pearson-Korrelationen werden erst ab **acht vollständigen Paaren** angezeigt. Die Streupunkte dürfen bei weniger Paaren angezeigt werden, aber keine Korrelationszahl. Unterschiede zwischen Trainings- und Ruhetagen sollen bei weniger als vier Nächten in einer Gruppe nicht interpretiert werden.
- Diese Berechnungen sind **explorativ** und belegen **keine Kausalität**. Sie korrigieren nicht für Schlafzeiten, Belastung anderer Tage, Erkrankungen, Stress, Reisen oder Unterschiede in der WHOOP-Messgenauigkeit. Klinische Schlussfolgerungen sind damit nicht möglich.
- Ein WHOOP-Workout-Fehler kann dazu führen, dass zunächst keine Korrelationen sichtbar sind. Die Diagnoseausgabe zeigt dann den HTTP-Status, ohne Geheimnisse zu protokollieren.

## Update der bestehenden Render-App

1. Das Projekt hat dieselbe Datei- und Ordnerstruktur wie V1; `render.yaml` und die vorhandenen Render-Secrets bleiben unverändert.
2. In GitHub `flux2209/ben-whoop-insights` die **Inhalte des entpackten Projekts** auf `main` hochladen und bestehende Dateien ersetzen. Wenn ein ZIP direkt hochgeladen wird, wird es nicht von Render als Code ausgeführt; **vorher entpacken**.
3. Die Änderungen betreffen `app.py`, `analytics.py`, `static/js/app.js`, `static/css/style.css`, `templates/index.html`, `tests/test_app.py` und diese `README.md`. Für einen möglichst kleinen Upload gibt es separat ein Update-ZIP mit ausschließlich diesen Dateien.
4. Das bestehende Render-Hosting baut die neue Commit-Version mit Auto-Deploy neu. **Keine** WHOOP-Client-ID, Client-Secret oder private Gesundheitsdaten in GitHub speichern.
5. Im Dashboard die Seite aktualisieren (gegebenenfalls Browser mit `Strg+F5`), anschließend die vier Bereiche öffnen.

## Datenschutz und Betrieb

- OAuth 2.0: `read:recovery`, `read:cycles`, `read:sleep`, `read:workout` sowie `offline` für Refresh-Token.
- HttpOnly/Secure-Cookie für verschlüsselte WHOOP-Token, die Server-Schlüsselvariable `APP_SECRET` liegt ausschließlich in Render.
- Kein dauerhaftes WHOOP-Datenspeichern auf Render, nur ein temporärer Arbeitsspeicher-Cache (5 Minuten) nach Zugangstoken und Zeitfenster.
- Abfrage beim Laden und alle 5 Minuten bei geöffnetem Browser; bei Render Free kann die Anwendung nach Inaktivität schlafen.
- Das GitHub-Repository kann öffentlich sein, solange **keine** geheimen Werte oder WHOOP-Messdaten hochgeladen werden.
- Achtung: Die App bietet keine eigenständige Nutzer-Zugangssperre vor dem WHOOP-Login. Sie ist technisch über ihre Webadresse erreichbar. Eine zusätzliche Zugriffsschranke wäre für sensible oder gemeinsame Nutzung sinnvoll.

## Lokal

```bash
pip install -r requirements.txt
pytest -q
uvicorn app:app --reload --port 8000
```

Die Demo befindet sich unter `http://localhost:8000/?demo=1` (nur erfundene Beispieldaten).

## Dokumentation

- [WHOOP Developer API v2](https://developer.whoop.com/api/)
- [WHOOP Workout-Datenmodell](https://developer.whoop.com/docs/developing/user-data/workout/)
- [WHOOP OAuth 2.0](https://developer.whoop.com/docs/developing/oauth/)
