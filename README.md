# immo-vendee-alertes

Outil local Python pour analyser des alertes email immobilières (Vendée), stocker les annonces dans SQLite, calculer un score d'opportunité, et générer un rapport HTML lisible pour aider un achat personnel de résidence secondaire.

## 1. Objectif du projet

`immo-vendee-alertes` lit des emails d'alertes immobilières reçus volontairement dans une boîte dédiée, extrait les annonces candidates, les déduplique, calcule des indicateurs (prix/m², travaux, score, décision), puis génère un rapport local `output/rapport.html`.

## 2. Limites juridiques / éthiques

- Usage strictement personnel.
- Pas de scraping massif.
- Pas de contournement captcha/anti-bot.
- Pas de republication des annonces.
- Les données viennent uniquement des emails d'alerte reçus volontairement.

## 3. Prérequis

- Python 3.12+
- Docker + Docker Compose (recommandé pour Portainer)
- Boîte mail IMAP dédiée

## Exécution avec Portainer (recommandé)

Le déploiement Portainer se fait depuis Git, sans fichier `.env` dans le dépôt.

1. Dans Portainer, créer/mettre à jour une stack avec le `docker-compose.yml` du repo.
2. Dans les variables d'environnement de la stack, renseigner:
- `IMAP_HOST`
- `IMAP_PORT`
- `IMAP_USER`
- `IMAP_PASSWORD`
- `IMAP_FOLDER`
- `MARK_EMAILS_AS_SEEN`

3. Volumes persistants utilisés:
- `/docker/data/immo-vendee/data:/app/data`
- `/docker/data/immo-vendee/output:/app/output`

4. Services de la stack:
- `immo-vendee`: exécution du script Python
- `immo-vendee-web`: publication du dossier `output` via Nginx sur le port `8088`

5. Rapport HTML consultable via:
- `http://<IP_SERVEUR>:8088/rapport.html`

## Exécution avec Docker Compose (hors Portainer)

```bash
docker compose up --build
```

Variables d'environnement attendues dans votre shell/outil d'orchestration:

- `IMAP_HOST`
- `IMAP_PORT`
- `IMAP_USER`
- `IMAP_PASSWORD`
- `IMAP_FOLDER`
- `MARK_EMAILS_AS_SEEN`

Le compose injecte aussi:
- `CONFIG_PATH=/app/config.yml`
- `DB_PATH=/app/data/annonces.sqlite`
- `OUTPUT_PATH=/app/output/rapport.html`

## Configuration `config.yml`

Le fichier contient:
- villes ciblées,
- critères prix/surface/prix-m²,
- fenêtre de lecture email,
- coûts travaux,
- pondération du scoring.

## Notes robustesse

- Si `config.yml` est absent: erreur claire + code de sortie non nul.
- Si `.env` est absent: warning explicite, puis usage des variables d'environnement existantes.
- Si aucun email n'est trouvé: exécution OK, rapport généré.
- Si IMAP échoue (hors `--no-mail`): erreur claire + code de sortie non nul.
- En mode `--no-mail`: pas de dépendance aux variables IMAP.

## Notes sécurité

- `.env` ne doit pas être committé.
- `data/*.sqlite` et `output/*.html` ne doivent pas être committés.
- Le mot de passe IMAP n'est jamais affiché dans les logs.

## Préparation des dossiers hôte (Linux)

```bash
sudo mkdir -p /docker/data/immo-vendee/data
sudo mkdir -p /docker/data/immo-vendee/output
sudo nano /docker/data/immo-vendee/config.yml
sudo chmod -R 775 /docker/data/immo-vendee
```
