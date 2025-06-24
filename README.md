[![Quality Gate Status](https://sonarcloud.io/api/project_badges/measure?project=cwhde_organizr-api&metric=alert_status&token=84681f1b724cc905c5711ff62744b85c201afe3d)](https://sonarcloud.io/summary/new_code?id=cwhde_organizr-api) [![Coverage](https://sonarcloud.io/api/project_badges/measure?project=cwhde_organizr-api&metric=coverage&token=84681f1b724cc905c5711ff62744b85c201afe3d)](https://sonarcloud.io/summary/new_code?id=cwhde_organizr-api) [![Bugs](https://sonarcloud.io/api/project_badges/measure?project=cwhde_organizr-api&metric=bugs&token=84681f1b724cc905c5711ff62744b85c201afe3d)](https://sonarcloud.io/summary/new_code?id=cwhde_organizr-api) [![Code Smells](https://sonarcloud.io/api/project_badges/measure?project=cwhde_organizr-api&metric=code_smells&token=84681f1b724cc905c5711ff62744b85c201afe3d)](https://sonarcloud.io/summary/new_code?id=cwhde_organizr-api) [![Duplicated Lines (%)](https://sonarcloud.io/api/project_badges/measure?project=cwhde_organizr-api&metric=duplicated_lines_density&token=84681f1b724cc905c5711ff62744b85c201afe3d)](https://sonarcloud.io/summary/new_code?id=cwhde_organizr-api) [![Lines of Code](https://sonarcloud.io/api/project_badges/measure?project=cwhde_organizr-api&metric=ncloc&token=84681f1b724cc905c5711ff62744b85c201afe3d)](https://sonarcloud.io/summary/new_code?id=cwhde_organizr-api)

# Organizr-API

Dies ist das Repository für die **Organizr-API**, ein Programmierprojekt im Rahmen der schulischen Ausbildung. 

Das Projektziel ist die Entwicklung einer zentralen API zum Verwalten von persönlichen Notizen, Tasks und Kalendereinträgen.  Als Demonstrations-Client soll zudem ein Telegram-Bot entwickelt werden, der mittels Natural Language Processing und Function Calling mit der API interagiert. 

### Geplante Features

* **Benutzerverwaltung:** Multi-User-System mit Rollen (Admin, User) und Authentifizierung via API-Key. 
* **Kalenderverwaltung:** Vollständige CRUD-Operationen für Kalendereinträge, inklusive Unterstützung für Wiederholungsregeln nach dem iCalendar RRULE-Standard. 
* **Taskverwaltung:** CRUD-Funktionalität für Aufgaben mit Status, Fälligkeitsdaten und optionalen Wiederholungen. 
* **Notizverwaltung:** CRUD-Funktionalität für textbasierte Notizen. 

### Technologie-Stack

* **Backend:** Python mit dem FastAPI-Framework 
* **Datenbank:** MySQL 
* **Deployment:** Containerisierung mit Docker und Orchestrierung via Docker-Compose 
* **Code-Qualität:** Kontinuierliche Analyse durch SonarCloud, integriert via GitHub Actions

### Setup und Inbetriebnahme

Um das Projekt lokal auszuführen, müssen folgende Schritte befolgt werden:

1.  **Repository klonen:**
    ```bash
    git clone https://github.com/cwhde/organizr-api.git
    cd organizr-api
    ```
2.  **Environment-Datei bearbeiten:**
    Im Verzeichnis `docker/` liegt eine Datei mit dem Namen `stack.env`. Diese Datei wird vom Docker-Compose-Setup für die Datenbankkonfiguration verwendet. Ihre Inhalte müssen vor Inbetriebnahme noch angepasst werden, um die Zugangsdaten für die MySQL-Datenbank festzulegen.
    ```env
    # docker/stack.env
    MYSQL_USER=user
    MYSQL_PASSWORD=your_secure_password
    MYSQL_DATABASE=organizr
    MYSQL_ROOT_PASSWORD=your_very_secure_root_password
    ```

3.  **Docker-Container starten:**
    Innerhalb des docker-Verzeichnisses befindet sich eine `docker-compose.yml`-Datei, die die Konfiguration für die Docker-Container enthält. Um die API und die MySQL-Datenbank zu starten, muss folgender Befehl ausgeführt werden:
    ```bash
    docker-compose up -d
    ```
4.  **Admin-Zugangsdaten abrufen:**
    Beim ersten Start führt das API-Setup-Skript eine automatische Datenbankmigration durch und erstellt einen initialen Admin-Benutzer. Die generierten Zugangsdaten (`user_id` und `api_key`) werden in die Logs des API-Containers geschrieben.

    Um die Zugangsdaten zu erhalten, müssen die Logs des `organizr-api`-Containers eingesehen werden:
    ```bash
    docker-compose logs organizr-api
    ```
    **Wichtig:** Diese Zugangsdaten werden nur einmalig angezeigt. Sie müssen daher sicher aufbewahrt werden.

### API-Dokumentation

Nach dem Start ist die API unter `http://localhost:8080` erreichbar.

Eine interaktive Dokumentation der API-Endpunkte wird per Swagger UI automatisch unter  `http://localhost:8080/docs` generiert. Dort können alle Endpunkte eingesehen und direkt getestet werden.

Die Authentifizierung für alle API-Anfragen erfolgt über den `X-API-Key` im HTTP-Header. Dieser ist entweder ein Admin oder ein User Key.
