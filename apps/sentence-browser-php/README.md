# Sentence Browser (Apache + PHP + MySQL)

Interface web pour explorer les 60k phrases analysées avec tri, filtres, pagination et recherche texte.

## Structure

- `public/`: app web et endpoints API
- `src/`: bootstrap, accès DB, repository SQL
- `config/`: config par environnement (`local`, `prod`)
- `scripts/`: génération SQL depuis CSV
- `sql/`: fichier SQL à importer en base

## SQL prêt à injecter

Fichier généré:
- `sql/sentence_browser_60000.sql`

Contenu:
- création table `sentences`
- création index
- insertion des 60 000 lignes
- enrichissement via `input/sentences.csv` (jointure par `id`) avec les colonnes:
  - `fr` -> `english`
  - `sounds`
  - `JLPT` -> `JLPT_origin`
  - `tags`
- référence audio informative: `D:\PortableApps\AnkiPortable\Data\AnkiAppData\sentences\collection.media`

## Régénérer le SQL depuis le CSV

Depuis la racine `apps/sentence-browser-php`:

```bash
/d/01-Drive/50-Dev/sentences/venv/Scripts/python.exe scripts/build_sql_dump.py
```

Source CSV utilisée:
- `../../output/full-60000-rerun.csv`

## Configuration local / prod

Fichiers:
- `config/config.local.php`
- `config/config.prod.php`
- `config/config.example.php`

Le bootstrap charge la config selon `APP_ENV`:
- `APP_ENV=local` -> `config.local.php`
- `APP_ENV=prod` -> `config.prod.php`
- fallback: `config.local.php`, puis `config.example.php`

### Exemple local

`config/config.local.php`:
- host: `127.0.0.1`
- db: `sentence_browser_local`
- user: `root`

### Exemple prod (OVH)

`config/config.prod.php`:
- host: serveur MySQL OVH
- db/user/pass: credentials OVH
- `base_path`: chemin public réel

## Définir l’environnement sur Apache

Option 1 (recommandée): variable d’environnement Apache:

```apache
SetEnv APP_ENV prod
```

Option 2: si non disponible sur mutualisé, copier les valeurs prod dans `config.local.php`.

## Déploiement OVH mutualisé

1. Créer la base MySQL OVH.
2. Importer `sql/sentence_browser_60000.sql` via phpMyAdmin.
3. Uploader `apps/sentence-browser-php` sur l’hébergement.
4. Mettre à jour `config/config.prod.php`.
5. Pointer le dossier web vers `public/` (ou adapter selon arbo OVH).

## Endpoints

- `GET /api/health.php`
- `GET /api/facets.php`
- `GET /api/sentences.php`

## Paramètres `sentences.php`

- `q`
- `jlpt_no_katakana[]`
- `vocab_jlpt_strict[]`
- `grammar_jlpt[]`
- `kanji_jlpt[]`
- `char_len_min`, `char_len_max`
- `sort_by`, `sort_dir`
- `page`, `page_size`

## Notes sécurité

- requêtes préparées PDO
- whitelist sur tri
- `page_size` plafonné à 200
- ne pas committer de secrets réels dans `config.prod.php`
