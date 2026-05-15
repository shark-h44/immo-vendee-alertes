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
- (optionnel) Docker + Docker Compose
- Boîte mail IMAP dédiée

## 4. Installation locale Python

```bash
cd immo-vendee-alertes
python -m venv .venv
# Windows
.venv\Scripts\activate
# Linux/macOS
source .venv/bin/activate
pip install -r requirements.txt
```

## 5. Installation Docker

```bash
cd immo-vendee-alertes
docker compose up --build
```

## 6. Configuration `.env`

1. Copier `.env.example` vers `.env`
2. Renseigner vos identifiants IMAP

Exemple:

```env
IMAP_HOST=imap.example.com
IMAP_PORT=993
IMAP_USER=immo.alertes@example.com
IMAP_PASSWORD=change_me
IMAP_FOLDER=INBOX
MARK_EMAILS_AS_SEEN=false
```

## 7. Configuration `config.yml`

Le fichier contient:
- villes ciblées,
- critères prix/surface/prix-m²,
- fenêtre de lecture email,
- coûts travaux,
- pondération du scoring.

Vous pouvez l'ajuster librement selon votre stratégie.

## 8. Lancement

### Mode normal

```bash
python app/main.py
```

### Régénération rapport sans IMAP

```bash
python app/main.py --no-mail
```

## 9. Exemples de commandes

```bash
python app/main.py --debug
python app/main.py --days-back 14 --limit 50
python app/main.py --no-mail
python app/main.py --eml-file samples/alerte_sample_1.eml --debug
```

## 10. Création d'alertes email sur les portails

Créer des alertes avec:
- zones: Saint-Jean-de-Monts, Saint-Hilaire-de-Riez, Saint-Gilles-Croix-de-Vie, Le Fenouiller, Notre-Dame-de-Riez, Brétignolles-sur-Mer, Soullans, Challans,
- type: maison / appartement,
- plafond: 95 000 €,
- surface mini: 30 m².

Configurer l'envoi vers la boîte IMAP dédiée.

## 11. Explication du scoring

Score sur 100 basé sur:
- prix total,
- prix/m²,
- surface,
- niveau de travaux,
- DPE,
- potentiel de négociation.

Décision:
- `>= 75`: À visiter en priorité
- `>= 60`: À surveiller / visiter si emplacement intéressant
- `>= 45`: Possible mais prudence
- `< 45`: À écarter sauf élément exceptionnel

## 12. Roadmap

- V3: intégration DVF
- V4: agent navigateur ponctuel
- V5: analyse photos
- V6: export Excel

## Exécution avec Docker

1. Prérequis Docker
- Installer Docker Desktop (Windows/macOS) ou Docker Engine + Docker Compose plugin (Linux).

2. Copier `.env.example` vers `.env`

```bash
cp .env.example .env
```

3. Modifier les paramètres IMAP dans `.env`

4. Vérifier `config.yml`
- Le fichier est monté en lecture seule dans le conteneur: `./config.yml:/app/config.yml:ro`.

5. Créer les dossiers si nécessaire

```bash
mkdir -p data output
```

6. Build et lancement

```bash
docker compose up --build
```

7. Lancement ponctuel

```bash
docker compose run --rm immo-vendee
```

8. Lancement sans lecture mail

```bash
docker compose run --rm immo-vendee --no-mail
```

9. Debug

```bash
docker compose run --rm immo-vendee --debug
```

10. Emplacement de la base SQLite
- `data/annonces.sqlite`

11. Emplacement du rapport
- `output/rapport.html`

12. Voir les logs

```bash
docker compose logs
```

13. Reconstruire proprement

```bash
docker compose build --no-cache
```

14. Supprimer les conteneurs arrêtés

```bash
docker compose down
```

## Variables d'environnement de chemins

Le runtime supporte ces surcharges:

- `CONFIG_PATH` (défaut: `config.yml`, Docker: `/app/config.yml`)
- `DB_PATH` (défaut: `data/annonces.sqlite`, Docker: `/app/data/annonces.sqlite`)
- `OUTPUT_PATH` (défaut: `output/rapport.html`, Docker: `/app/output/rapport.html`)

## Notes robustesse

- Si `config.yml` est absent: erreur claire + code de sortie non nul.
- Si `.env` est absent: warning explicite, puis usage des variables d'environnement existantes.
- Si aucun email n'est trouvé: exécution OK, rapport quand même généré.
- Si IMAP échoue (hors `--no-mail`): erreur claire + code de sortie non nul.
- En mode `--no-mail`: pas de dépendance aux variables IMAP.

## Structure

```text
immo-vendee-alertes/
├── README.md
├── .env.example
├── .dockerignore
├── .gitignore
├── requirements.txt
├── Dockerfile
├── docker-compose.yml
├── config.yml
├── data/
│   ├── .gitkeep
│   └── annonces.sqlite
├── output/
│   ├── .gitkeep
│   └── rapport.html
├── samples/
│   ├── alerte_sample_1.eml
│   └── alerte_sample_2.eml
└── app/
    ├── main.py
    ├── config.py
    ├── db.py
    ├── models.py
    ├── mail_reader.py
    ├── email_parser.py
    ├── analyzers.py
    ├── report.py
    └── utils.py
```

## Notes sécurité

- `.env` n'est jamais copié dans l'image Docker.
- `data/*.sqlite` et `output/*.html` ne sont pas copiés dans l'image.
- Le mot de passe IMAP n'est jamais affiché dans les logs.
