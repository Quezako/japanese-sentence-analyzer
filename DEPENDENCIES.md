# Dépendances et sources de données

## Dépendances Python (requirements.txt)

### janome (0.4.2)
- **Rôle** : Analyseur morphologique japonais
- **Fonctionnalité** : 
  - Tokenization des phrases en mots
  - Lemmatisation (reconnaissance des verbes conjugués, etc.)
  - Extraction des niveaux JLPT du vocabulaire et kanji
- **Source** : PyPI - https://pypi.org/project/janome/
- **Dictionnaire intégré** : Utilise le dictionnaire MeCab standard enrichi avec les données JLPT

### pandas (2.0.3)
- **Rôle** : Manipulation de données tabulaires
- **Fonctionnalité** : Lecture/écriture CSV, manipulation de colonnes
- **Source** : PyPI - https://pypi.org/project/pandas/

## Données JLPT

### Vocabulaire et Kanji
- **Source** : Dictionnaire intégré de janome
- **Données** : Niveaux JLPT (N1-N5) associés à chaque mot et kanji
- **Format** : Métadonnées dans le dictionnaire MeCab

### Grammaire
- **Source** : `data/grammar_patterns.csv` (fichier local)
- **Données** : Patterns regex + niveaux JLPT pour les structures grammaticales courantes
- **Format** : CSV avec colonnes `pattern | jlpt_level | description | pattern_type`
- **Maintien** : À enrichir manuellement ou via des sources comme :
  - https://jlptsensei.com/ (ressources JLPT)
  - https://www.marugotojapan.com/ (patterns de grammaire)
  - Manuels JLPT officiels

## Configuration du script

Le script `process_sentences.py` :
- Lit `sentences-only.csv` (ou tout CSV avec colonne `sentence`)
- Utilise `data/grammar_patterns.csv` pour la détection de grammaire
- Génère `sentences-with-levels.csv` avec 4 colonnes :
  1. ID
  2. Phrase
  3. Niveau JLPT Vocabulaire
  4. Niveau JLPT Kanji
  5. Niveau JLPT Grammaire

## Mise à jour des données

Pour mettre à jour les patterns de grammaire :
1. Éditer `data/grammar_patterns.csv`
2. Ajouter de nouveaux patterns avec leurs niveaux JLPT respectifs
3. Relancer le script
