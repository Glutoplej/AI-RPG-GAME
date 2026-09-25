# AI RPG Game Master – Automated Cloud Deployment & CI/CD

Projekt demonstracyjny przedstawiający skonteneryzowaną aplikację w Pythonie (Flask + Groq LLM) wraz z automatycznym pipeline'em **CI/CD** i wdrożeniem w chmurze **AWS**.

---

## Arcitektura i Technologie

* **Aplikacja:** Python 3.11, Flask, Gunicorn
* **Konteneryzacja:** Docker, Docker Hub
* **Chmura (AWS):** EC2 (Ubuntu Server), Security Groups
* **CI/CD & Automatyzacja:** GitHub Actions, GitHub Secrets
* **Dostępność:** Produkcyjny deployment na porcie 8080

---

## Pipeline CI/CD (GitHub Actions)

Każdy `git push` na gałąź `main` wyzwala automatyczny workflow (`.github/workflows/deploy.yml`):

1. **Build & Push:** Zbudowanie obrazu Dockerowego i wysłanie go do rejestru **Docker Hub**.
2. **Automated Deployment:** Połączenie przez SSH z instancją **AWS EC2**, pobranie najnowszej wersji obrazu oraz restart kontenera z przekazaniem sekretów produkcyjnych.
