# Regression workflow (manuel + semi-automatique)

## Fichiers

- `validated_cases.csv` : lignes **validées manuellement** (gold). Toute différence est traitée comme régression.
- `waiting_review_cases.csv` : lignes **globalement OK** (niveau général cohérent) mais pas encore validées en détail.
  Comparées sur colonnes réduites (coarse), non bloquant par défaut.
- `review_overestimated_cases.csv` : lignes **surévaluées** à surveiller (non bloquant).
- `review_underestimated_cases.csv` : lignes **sous-évaluées** à surveiller (non bloquant).
- `check_regression.py` : script de comparaison.

## Format attendu

Tous les CSV utilisent le même format (copie directe d'une ligne de sortie):

`id;sentence;jlpt_no_katakana;vocab_jlpt_pedagogical;vocab_pedagogical_details;vocab_jlpt_strict;vocab_details;kanji_jlpt;kanji_details;grammar_jlpt;grammar_details;note`

- `note` est optionnelle et sert à documenter ton jugement.

## Comment peupler

1. Ouvre `output/first1000-rerun.csv`.
2. Copie les lignes jugées correctes dans `validated_cases.csv`.
3. Copie les lignes globalement cohérentes (mais pas validées au détail) dans `waiting_review_cases.csv`.
4. Copie les lignes surévaluées dans `review_overestimated_cases.csv`.
5. Copie les lignes sous-évaluées dans `review_underestimated_cases.csv`.

Important: un même `id` ne doit pas exister dans plusieurs fichiers.
Le script signale les doublons d'ID comme erreur.

## Lancer le check

```bash
cd /d/01-Drive/50-Dev/sentences
venv/Scripts/python.exe tests/regression/check_regression.py --current output/first1000-rerun.csv
```

## Interprétation

- `[OK] No regression detected on validated cases.` : pas de régression sur ton gold.
- `[ERROR] Regressions detected...` : au moins une ligne validée a changé.
- `[WAITING_REVIEW] ...` : changements détectés sur le fichier intermédiaire (coarse) à revue.
- `[REVIEW_OVER] ...` et `[REVIEW_UNDER] ...` : suivi informatif par type de problème.

Par défaut, seuls les cas `validated` sont bloquants.
Si tu veux rendre aussi `waiting_review` bloquant:

```bash
venv/Scripts/python.exe tests/regression/check_regression.py \
  --current output/first1000-rerun.csv \
  --fail-on-waiting-review
```

Tu peux ajuster les colonnes comparées avec `--columns`.
Exemple: comparer seulement les niveaux résumés:

```bash
venv/Scripts/python.exe tests/regression/check_regression.py \
  --current output/first1000-rerun.csv \
  --columns jlpt_no_katakana,vocab_jlpt_pedagogical,vocab_jlpt_strict,grammar_jlpt
```

Colonnes coarse par défaut pour `waiting_review`:

`sentence,jlpt_no_katakana,vocab_jlpt_pedagogical,vocab_jlpt_strict,kanji_jlpt,grammar_jlpt`
