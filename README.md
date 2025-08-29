[![Quality Gate Status](https://sonarcloud.io/api/project_badges/measure?project=cwhde_organizr-api&metric=alert_status&token=84681f1b724cc905c5711ff62744b85c201afe3d)](https://sonarcloud.io/summary/new_code?id=cwhde_organizr-api) [![Coverage](https://sonarcloud.io/api/project_badges/measure?project=cwhde_organizr-api&metric=coverage&token=84681f1b724cc905c5711ff62744b85c201afe3d)](https://sonarcloud.io/summary/new_code?id=cwhde_organizr-api) [![Bugs](https://sonarcloud.io/api/project_badges/measure?project=cwhde_organizr-api&metric=bugs&token=84681f1b724cc905c5711ff62744b85c201afe3d)](https://sonarcloud.io/summary/new_code?id=cwhde_organizr-api) [![Code Smells](https://sonarcloud.io/api/project_badges/measure?project=cwhde_organizr-api&metric=code_smells&token=84681f1b724cc905c5711ff62744b85c201afe3d)](https://sonarcloud.io/summary/new_code?id=cwhde_organizr-api) [![Duplicated Lines (%)](https://sonarcloud.io/api/project_badges/measure?project=cwhde_organizr-api&metric=duplicated_lines_density&token=84681f1b724cc905c5711ff62744b85c201afe3d)](https://sonarcloud.io/summary/new_code?id=cwhde_organizr-api) [![Lines of Code](https://sonarcloud.io/api/project_badges/measure?project=cwhde_organizr-api&metric=ncloc&token=84681f1b724cc905c5711ff62744b85c201afe3d)](https://sonarcloud.io/summary/new_code?id=cwhde_organizr-api)

# Organizr-API & Bot

Dies ist das Repository für die **Organizr-API** und den zugehörigen **Telegram-Bot**, ein Programmierprojekt im Rahmen der schulischen Ausbildung.

Das Projektziel ist die Entwicklung einer zentralen API zum Verwalten von persönlichen Notizen, Tasks und Kalendereinträgen. Als Client dient ein Telegram-Bot, der mittels Natural Language Processing und Function Calling mit der API interagiert, um eine natürliche Bedienung zu ermöglichen.

### Technologie-Stack

* **Backend:** Python mit dem FastAPI-Framework
* **Datenbank:** MySQL
* **Bot:** Python mit `py-telegram-bot-api`
* **AI:** OpenAI-kompatibles API für Function Calling
* **Deployment:** Containerisierung mit Docker und Orchestrierung via Docker-Compose
* **Code-Qualität:** Kontinuierliche Analyse durch SonarCloud, integriert via GitHub Actions

### Setup und Inbetriebnahme

Um das Projekt lokal auszuführen, müssen folgende Schritte befolgt werden:

**1. Repository klonen:**
```bash
git clone https://github.com/cwhde/organizr-api.git
cd organizr-api
````

**2. Environment-Datei vorbereiten:**
Im Verzeichnis `docker/` liegt eine Datei mit dem Namen `stack.env`. Diese Datei wird vom Docker-Compose-Setup für die Konfiguration aller Dienste verwendet.
Die Inhalte müssen vor der Inbetriebnahme angepasst werden, insbesondere die MySQL-Passwörter sowie die API-Keys für Telegram und den LLM-Provider. Der `ORGANIZR_API_KEY` wird vorerst leergelassen.

```env
# docker/stack.env

# --- MySQL Database Configuration ---
MYSQL_HOST=db
MYSQL_PORT=3306
MYSQL_DATABASE=organizr
MYSQL_USER=organizr-user
MYSQL_PASSWORD=changeBeforeUse
MYSQL_ROOT_PASSWORD=changeBeforeUse

# --- Telegram Bot Configuration ---
TELEGRAM_API_KEY=dein_telegram_api_key
# HIER NOCH LEER LASSEN!
ORGANIZR_API_KEY=
ORGANIZR_BASE_URL=http://organizr-api:8000

# --- LLM (OpenAI Compatible) Configuration ---
OPENAI_API_KEY=dein_openai_compatible_api_key
OPENAI_BASE_URL=[https://api.openai.com/v1](https://api.openai.com/v1)
OPENAI_MODEL=gpt-4o
```

**3. Admin-Key generieren:**
Der Bot benötigt einen Admin-API-Key, um Benutzer für Telegram-User anlegen zu können. Dieser Key wird beim ersten Start der API generiert.

a. Es werden nur die API und die Datenbank gestartet:

```bash
cd docker
docker-compose up -d organizr-api db
```

b. Der Admin-Key wird aus den Logs des API-Containers ausgelesen:

```bash
docker-compose logs organizr-api
```

Es sollte eine Ausgabe erscheinen, die wie folgt aussieht:

```
============================================================
ORGANIZR-API ADMIN USER CREATED
Admin User ID: XXXXXXXX
Admin API Key: YYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYY
SAVE THESE CREDENTIALS - THEY WILL NOT BE SHOWN AGAIN!
============================================================
```

c. Der `Admin API Key` muss kopiert werden.

**4. Konfiguration abschliessen und alles starten:**

a. Die laufenden Container werden gestoppt:

```bash
docker-compose down
```

b. Nun wird die `docker/stack.env` Datei geöffnet und der kopierte Admin-Key bei der Variable `ORGANIZR_API_KEY` eingefügt.

c. Zum Schluss wird der gesamte Stack gestartet, inklusive des Bots:

```bash
docker-compose up -d
```

Jetzt laufen die API, die Datenbank und der Telegram-Bot.

### API-Dokumentation

Nach dem Start ist die API unter `http://organizr-api-ip:8080` erreichbar.

Eine interaktive Dokumentation der API-Endpunkte wird per Swagger UI automatisch unter `http://organizr-api-ip:8080/docs` generiert. Dort können alle Endpunkte eingesehen und direkt getestet werden.