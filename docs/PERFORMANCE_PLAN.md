# Plan d’amélioration performance & qualité (pragmatique)

Date: 2026-04-25
Contexte: traitement de `60k` phrases via `process_sentences.py` (pipeline JLPT vocab/kanji/grammaire).

## 1) Objectif (sans industrialiser)

- Réduire le temps total du run `60k` de manière visible (cible initiale: **-25% à -40%**).
- Garder un code lisible et limiter le risque de régression fonctionnelle.
- Éviter un gros chantier infra tant que ce n’est pas justifié par les mesures.

---

## 2) Constats rapides sur le code actuel

Observations sur `process_sentences.py`:

- La tokenisation Janome est appelée plusieurs fois par phrase:
  - `analyze_vocabulary(...)`
  - `analyze_vocab_pedagogical(..., ignore_katakana=False)`
  - `analyze_vocab_pedagogical(..., ignore_katakana=True)`
- Certaines transformations de candidats lexicaux sont répétées:
  - `candidate_forms_for_lookup(...)`
  - `expand_candidates_with_variants(...)`
  - `enrich_candidates_with_hira_map(...)`
- De nombreux CSV sont chargés puis fusionnés à chaque run.

Ces points sont des candidats naturels pour un gain de perf sans changer la logique métier.

---

## 3) Axes d’amélioration

## Axe A — Quick wins Python (priorité haute)

### A1. Tokeniser une seule fois par phrase

**Idée**
- Calculer `tokens = list(tokenizer.tokenize(sentence))` une seule fois dans la boucle principale.
- Passer `tokens` aux fonctions d’analyse au lieu de retokenizer dans chaque fonction.

**Impact attendu**
- Fort (souvent le plus gros levier CPU).

**Risque**
- Modéré (signature de fonctions à ajuster proprement).

---

### A2. Cache léger pour transformations répétitives

**Idée**
- Mémoriser certains résultats déterministes avec `functools.lru_cache` ou dict local run:
  - `candidate_forms_for_lookup(base, surface, reading)`
  - expansions `variants/hira` pour un tuple de candidats.

**Impact attendu**
- Moyen à fort sur 60k lignes (forte redondance lexicale).

**Risque**
- Faible si cache borné et clé simple.

---

### A3. Éviter du travail inutile dans la double passe pédagogique

**Idée**
- `analyze_vocab_pedagogical` est appelée 2 fois (avec/sans katakana).
- Factoriser la partie commune, ou calculer une seule structure intermédiaire puis filtrer katakana au besoin.

**Impact attendu**
- Moyen.

**Risque**
- Modéré (attention à ne pas changer la sémantique de `jlpt_no_katakana`).

---

## Axe B — Données consolidées CSV (priorité moyenne)

### B1. Générer 2 fichiers consolidés versionnés

**Proposition**
- `data/cache/vocab_consolidated.csv`
- `data/cache/grammar_consolidated.csv`

**Contenu recommandé (vocab)**
- `word|jlpt_level|source_primary|sources_all|flags`
- niveau déjà arbitré (règle “plus facile” ou règle métier explicite)

**Contenu recommandé (grammaire)**
- `pattern|jlpt_level|description|type|source`

**Bénéfice**
- Moins de chargements/fusions au runtime.
- Traçabilité claire des priorités de sources.

**Risque**
- Faible à modéré (nécessite script de build des consolidés).

---

### B2. Mode exécution: `--use-consolidated`

**Idée**
- Garder le mode actuel pour debug/édition des sources.
- Ajouter un mode rapide qui lit directement les consolidés.

**Bénéfice**
- Sécurité (fallback facile) + adoption progressive.

---

## Axe C — SQLite (optionnel, à décider après mesures)

### Verdict pragmatique

- Pour des lookups en mémoire par clé exacte, des `dict` Python restent souvent plus rapides qu’un accès SQLite requête par requête.
- SQLite est intéressant surtout pour:
  - gouvernance des données,
  - requêtes de debug/audit,
  - pipeline de préparation (pré-calcul),
  - indexation riche sur gros volumes hétérogènes.

### Recommandation

- **Court terme**: rester sur dict in-memory + CSV consolidés.
- **Moyen terme**: SQLite comme backend de préparation/offline, puis export en consolidé pour le runtime.

---

## Axe D — Qualité de code & dette technique (priorité moyenne)

### D1. Identifier code mort / branches inutilisées

- Outils: `vulture`, `ruff` (imports, complexité), éventuellement `radon`.
- Cible: helpers non utilisés, chemins legacy, duplication entre analyses strict/pedagogical.

### D2. Réduire la duplication d’algorithmes

- Extraire un cœur commun d’analyse token-level.
- Encapsuler les variations (strict vs pedagogical, ignore katakana) par stratégie/flags.

### D3. Garde-fous qualité

- Ajouter un mini benchmark reproductible (échantillon fixe ex: 5k lignes).
- Ajouter un test de non-régression temps (seuil indicatif, pas bloquant dur au début).

---

## 4) Feuille de route proposée (simple)

## Phase 0 — Mesure de base (0.5 jour)

- Mesurer un baseline sur 5k et 60k:
  - temps total,
  - temps moyen / phrase,
  - top fonctions CPU (`cProfile`).
- Sauvegarder les résultats dans `output/perf-baseline-*.txt`.

## Phase 1 — Quick wins code (1 à 2 jours)

- Tokenisation unique par phrase.
- Cache léger sur candidats.
- Petite factorisation de la double passe pédagogique.
- Re-mesure vs baseline.

## Phase 2 — Consolidation données (1 jour)

- Script `scripts/build_consolidated_data.py`.
- Ajout d’un mode `--use-consolidated`.
- Re-mesure chargement + runtime.

## Phase 3 — Nettoyage qualité (1 jour)

- Passage outils (`vulture`, `ruff`) + suppression code mort sûr.
- Refacto minimale de duplication critique.

SQLite: à lancer seulement si les phases 1-2 ne suffisent pas.

---

## 5) KPI de succès

- Temps run 60k: baisse mesurée >= 25%.
- Résultats fonctionnels inchangés sur un set de régression.
- Pas d’augmentation notable de complexité (fichiers/flags limités).

---

## 6) Décision recommandée maintenant

1. Faire **Phase 0 + Phase 1** en priorité.
2. Ajouter les **CSV consolidés** ensuite si besoin.
3. Reporter **SQLite runtime** (pas prioritaire à ce stade).

Ce plan reste volontairement léger et orienté gains rapides, sans transformer le projet en chantier industriel.
