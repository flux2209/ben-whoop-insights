# WHOOP Insights — Private Performance Dashboard

Eine responsive private Web-App mit echten WHOOP-Daten via offizieller **WHOOP Developer API v2**. Kein Tracking, keine externe Diagrammbibliothek, kein persistentes Speichern persönlicher Gesundheitsdaten auf dem App-Server.

## Funktionen

- OAuth-2.0-Verbindung mit WHOOP, ausschließlich lesende Berechtigungen
- Recovery, HRV (RMSSD, ms), nächtlicher Ruhepuls, Schlafdauer, täglicher Strain
- Schlafphasen (Leicht-/Tief-/REM-Schlaf), Schlafperformance, Workout-Historie
- 7, 30, 90 oder 365 Tage; automatisch aktualisierte Daten beim Öffnen und bei geöffnetem Tab alle 5 Minuten
- Vergleich letzte 7 vs. vorherige 7 Tage; keine medizinischen Diagnosen, keine erfundenen Messwerte
- Datenschutz: verschlüsselte HttpOnly-Sitzungscookies, kurzlebiger In-Memory-Cache, keine Datenbank
- Demo-Modus ohne WHOOP-Konto zur UI-Vorschau: `/?demo=1`

**Wichtig:** Dies ist keine sekundengenaue Live-Herzfrequenzanzeige. Die offizielle API liefert aktuelle, bereits durch WHOOP verarbeitete Messwerte. Sie ist keine Quelle kontinuierlicher Herzfrequenz-Rohdaten.

## Schnellstart: Veröffentlichung mit GitHub + Render

Du brauchst einmalig ein **privates GitHub-Repository**, einen **Render-Account** und eine WHOOP-Developer-Anwendung. Lass die gesamte Datei-/Ordnerstruktur in GitHub unverändert. Diese erste Version verwendet **FastAPI** und braucht außer den angegebenen Python-Abhängigkeiten keine externe JavaScript-Bibliothek.

1. Lade diesen Projektordner in ein neues **privates** GitHub-Repository hoch (niemals `.env` oder Zugangsschlüssel einchecken).
2. Öffne [Render](https://dashboard.render.com/) und verbinde das GitHub-Repository über **New > Blueprint** (Render liest `render.yaml`). Der Dienst heißt im Blueprint `whoop-insights-private`; bei Namenskollision einen verfügbaren Namen wählen. Kostenloser Dienst ist für einen Test ausreichend, hat jedoch Ruhezeiten und ist nicht für anspruchsvolle Produktivnutzung gedacht.
3. Für Render unter **Environment** konfigurieren:
   - `APP_SECRET`: wird durch das Blueprint automatisch generiert; **nicht** verändern, sonst verfallen bestehende Sitzungen.
   - `WHOOP_CLIENT_ID`: aus deiner WHOOP-Developer-Anwendung.
   - `WHOOP_CLIENT_SECRET`: aus deiner WHOOP-Developer-Anwendung. **Nur** direkt im Render-Secretfeld eingeben; niemals im Chat oder Repository.
   - `PUBLIC_BASE_URL`: die vollständige Render-Adresse, z. B. `https://whoop-insights-private.onrender.com`, **ohne** abschließenden Schrägstrich.
4. In [WHOOP Developer Dashboard](https://developer-dashboard.whoop.com/) eine neue App anlegen. Als **Redirect URI** exakt `https://DEINE-RENDER-ADRESSE/auth/callback` registrieren. Berechtigungen `read:recovery`, `read:sleep`, `read:cycles`, `read:workout` und `offline` (für Refresh Tokens) vorsehen.
5. Auf Render die Einstellungen speichern / deployen, dann deine Web-App öffnen und **WHOOP sicher verbinden** anklicken. WHOOP zeigt die Freigabe direkt bei WHOOP an.

**Reihenfolge-Tipp:** Falls WHOOP beim Erstellen der App eine Redirect-URL verlangt, zuerst Render deployen (temporär Platzhalter in den Secretfeldern), dann dessen öffentliche URL bei WHOOP registrieren und abschließend echte Client-ID und Client-Secret in Render eintragen.

**Zu prüfende WHOOP-Felder:** Die Plattform kann weitere Angaben zu Appname, Website, Datenverwendung und Datenschutz verlangen. Beispiel: Name `WHOOP Insights Private`, Verwendung `Private Eigenanalyse meiner WHOOP Daten`, Website die Render-URL. Datenschutzrichtlinie und ggf. Veröffentlichungsregeln für öffentliche Anwendungen müssen bei Bedarf zusätzlich geklärt werden. Diese App ist für private Eigenverwendung konzipiert.

## Lokal starten

Voraussetzungen: Python 3.11+.

```bash
python -m venv .venv
source .venv/bin/activate    # Windows: .venv\\Scripts\\activate
pip install -r requirements.txt
cp .env.example .env        # Nur als lokale Vorlage; die App lädt .env NICHT automatisch
export PUBLIC_BASE_URL="http://localhost:8000"
export APP_SECRET="ein-zufallswert-mit-mindestens-32-zeichen"
export WHOOP_CLIENT_ID="..."
export WHOOP_CLIENT_SECRET="..."
uvicorn app:app --reload --port 8000
```

Dann `http://localhost:8000/?demo=1`. Für echten WHOOP-Login muss die lokale Redirect-URL ebenfalls als gültige URI bei WHOOP registriert sein; wenn WHOOP HTTPS erzwingt, stattdessen eine gehostete HTTPS-URL verwenden.

## Konfiguration

| Schlüssel | Zweck |
|---|---|
| `WHOOP_CLIENT_ID` | WHOOP OAuth2 Client-ID |
| `WHOOP_CLIENT_SECRET` | OAuth2 Client-Secret, niemals veröffentlichen |
| `PUBLIC_BASE_URL` | Kanonische HTTPS-Adresse für OAuth-Callback und Origin-Prüfung |
| `APP_SECRET` | Langer zufälliger Wert für die Cookie-Verschlüsselung; dauerhaft stabil halten |

Alle WHOOP-API-Zugriffe laufen serverseitig; Browser-JavaScript bekommt nur aggregierte Messwerte. Zugriffs- und Refresh-Tokens stehen verschlüsselt im Browser-Cookie; der Entschlüsselungsschlüssel bleibt auf dem Server. Im Browser ist das Cookie nicht für JavaScript lesbar. Kein permanentes Speichern der WHOOP-Daten auf dem Hosting-Server. Alle API-Antworten haben `Cache-Control: no-store`.

Beim Trennen versucht die Anwendung die WHOOP-Freigabe auch serverseitig zu widerrufen und löscht in jedem Fall das lokale Cookie. Falls WHOOP nicht erreichbar ist, kann die Freigabe zusätzlich im WHOOP-Konto widerrufen werden.

## Tests

```bash
pytest -q
```

## Begrenzungen dieser ersten Version

- Kein eigenständiges Hintergrund-Synchronisieren bei geschlossener Web-App. Öffnen/Aktualisieren löst einen Abruf aus; bei offener App alle 5 Minuten.
- Es gibt keine dauerhafte Datenspeicherung. WHOOP-Historie wird auf Abruf geladen (mit temporärem Speicher für 5 Minuten); 365 Tage können länger dauern.
- Die WHOOP-API unterstützt keine kontinuierlichen Herzfrequenz-Rohdaten über die öffentliche API.
- Der Refresh-Token wird bei WHOOP rotiert. Verlorene Cookies, mehrere gleichzeitig veraltete Browser-Sitzungen oder ein neuer APP_SECRET können erneute Autorisierung erfordern.
- Das API-Scope `offline` ist vorgesehen, aber ohne Benutzer-Interaktion bei WHOOP kann die Verbindung nicht erstellt werden.
- Das kostenlose Render-Hosting schläft nach Inaktivität ein; erster Aufruf kann langsam sein. Daten werden dort nicht dauerhaft gehalten, deshalb keine SQLite-Datenbank.
- Die gesamte Anwendung ist privat ausgelegt und ersetzt keine medizinische Beratung.

Die WHOOP-Daten wurden ohne persönliche WHOOP-OAuth-Freigabe nicht live getestet. Automatisierte Tests prüfen API-Routen, Dashboard-Datenstrukturen und OAuth-Parameter. Die private Benutzung ist nicht mit WHOOP offiziell verbunden.

## Technische Referenzen

- [WHOOP API v2](https://developer.whoop.com/api/)
- [WHOOP OAuth 2.0](https://developer.whoop.com/docs/developing/oauth/)
- [WHOOP API-Pagination](https://developer.whoop.com/docs/developing/pagination/)
- [WHOOP Developer Dashboard](https://developer-dashboard.whoop.com/)
- [Render Free Plan](https://render.com/docs/free)
