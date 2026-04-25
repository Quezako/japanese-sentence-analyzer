# Conception — Interface web 60k phrases (Apache + PHP + MySQL)

Date: 2026-04-25  
Projet: `japanese-sentence-analyzer`

## 1) Contrainte et objectif

Contrainte de prod: hébergement **OVH mutualisé** avec stack classique **Apache + PHP + MySQL**.  
Objectif: livrer une interface web légère pour explorer les 60k phrases avec:
- recherche texte,
- filtres par niveaux,
- filtre longueur min/max,
- tri par colonnes,
- pagination côté serveur.

## 2) Décision d’architecture

## Décision

Créer un mini-projet dédié compatible mutualisé, par exemple:
- `apps/sentence-browser-php/`

Séparer:
- pipeline d’analyse Python (génère CSV),
- application web PHP/MySQL (consomme les données pour la navigation).

## Pourquoi

- compatible 100% OVH mutualisé,
- pas de process backend permanent à maintenir,
- déploiement simple via FTP/Git deploy,
- maintenance plus robuste pour ce type d’hébergement.

---

## 3) Stack recommandée (cible prod)

- **Serveur web**: Apache (OVH)
- **Backend**: PHP 8.1+ (PDO)
- **DB**: MySQL 8+ (ou MariaDB compatible)
- **Frontend**: HTML/CSS/JS vanilla (ou micro-lib type Alpine.js), sans Node requis en prod

Option: garder un frontend buildé (Vite) possible, mais pas nécessaire pour V1.

---

## 4) Modèle de données MySQL

Table principale: `sentences`

Colonnes minimales:
- `id` BIGINT PRIMARY KEY
- `sentence` TEXT NOT NULL
- `char_len` INT NOT NULL
- `jlpt_no_katakana` VARCHAR(10)
- `vocab_jlpt_pedagogical` VARCHAR(10)
- `vocab_jlpt_strict` VARCHAR(10)
- `kanji_jlpt` VARCHAR(10)
- `grammar_jlpt` VARCHAR(10)
- `vocab_details` TEXT
- `vocab_pedagogical_details` TEXT
- `kanji_details` TEXT
- `grammar_details` TEXT

Index recommandés:
- `idx_jlpt_no_katakana`
- `idx_vocab_jlpt_strict`
- `idx_grammar_jlpt`
- `idx_kanji_jlpt`
- `idx_char_len`

Recherche texte:
- V1: `sentence LIKE :q`
- V2 (si dispo): `FULLTEXT(sentence)` + `MATCH ... AGAINST`

---

## 5) API PHP (JSON) — contrat V1

## `GET /api/sentences.php`

Paramètres:
- `q`
- `jlpt_no_katakana[]`
- `vocab_jlpt_strict[]`
- `grammar_jlpt[]`
- `kanji_jlpt[]`
- `char_len_min`, `char_len_max`
- `sort_by`, `sort_dir`
- `page`, `page_size`

Réponse:
- `items`
- `total`
- `page`
- `page_size`

## `GET /api/facets.php`

Renvoie les comptes par niveau pour alimenter les filtres UI.

## `POST /api/admin/reload.php` (optionnel V1)

Recharge depuis CSV (protégé par token simple).

---

## 6) Interface web (V1)

Composants:
- champ recherche,
- checkboxes niveaux,
- inputs longueur min/max,
- tableau triable,
- pagination,
- bouton reset filtres.

UX:
- requêtes API server-side (pas de chargement des 60k lignes côté navigateur),
- état des filtres dans l’URL,
- debounce 300ms sur recherche.

---

## 7) Sécurité minimale (obligatoire)

- requêtes SQL préparées (`PDO::prepare`),
- whitelist stricte `sort_by` / `sort_dir`,
- `page_size` max (ex: 200),
- token admin pour endpoints sensibles,
- pas d’erreurs SQL affichées en public.

---

## 8) Plan de réalisation étape par étape

## Étape 0 — Initialiser le projet PHP (0.5 jour)

Créer:
- `apps/sentence-browser-php/public/index.php`
- `apps/sentence-browser-php/public/api/sentences.php`
- `apps/sentence-browser-php/public/api/facets.php`
- `apps/sentence-browser-php/src/Db.php`
- `apps/sentence-browser-php/src/QueryBuilder.php`
- `apps/sentence-browser-php/scripts/import_csv.php`
- `apps/sentence-browser-php/config/config.example.php`

Livrable: structure projet + config DB example.

## Étape 1 — Import CSV vers MySQL (0.5–1 jour)

Script `scripts/import_csv.php`:
- lit `output/full-60000-rerun.csv`,
- calcule `char_len`,
- insère en batch dans `sentences`,
- crée index.

Livrable: table remplie (60k lignes).

## Étape 2 — API `sentences.php` (1 jour)

Implémenter:
- filtres multi-colonnes,
- recherche `q`,
- tri validé par whitelist,
- pagination + total.

Livrable: endpoint JSON stable.

## Étape 3 — API `facets.php` (0.5 jour)

Retourner les comptes par niveau (global/vocab/grammar/kanji).

Livrable: endpoint JSON pour l’UI filtres.

## Étape 4 — Frontend léger (1 jour)

Créer une page unique:
- formulaire filtres,
- tableau résultats,
- tri/pagination côté API.

Livrable: interface opérationnelle.

## Étape 5 — Déploiement OVH mutualisé (0.5 jour)

- créer DB MySQL OVH,
- importer données,
- upload code dans `www/`,
- config `config.php`,
- tester endpoints + UI.

Livrable: application publique en prod.

---

## 9) Critères de succès

- temps de réponse raisonnable (< 500 ms sur requêtes filtrées simples),
- UX fluide sur 60k lignes (pagination serveur),
- aucun chargement massif côté navigateur,
- déploiement/maintenance possibles sans VPS.

---

## 10) Décisions à figer avant implémentation

1. Le projet PHP est-il dans ce repo (`apps/sentence-browser-php`) ou dans un repo dédié ?
2. La recherche texte reste en `LIKE` (V1) ou passe en `FULLTEXT` si disponible ?
3. Refresh data manuel (upload CSV + import) ou cron ?
4. Accès public en lecture ou protection simple (mot de passe) ?

---

## 11) Évolutions futures

- export CSV des résultats filtrés,
- sauvegarde de vues/filtres favoris,
- stats agrégées (distribution JLPT, longueur moyenne),
- cache HTTP simple sur endpoints les plus fréquents.

Ce plan vise une livraison rapide, compatible mutualisé, avec un niveau de complexité maîtrisé.