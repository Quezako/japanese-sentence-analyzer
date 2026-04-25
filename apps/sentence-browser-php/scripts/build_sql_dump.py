import csv
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
APP_ROOT = Path(__file__).resolve().parents[1]
INPUT_CSV = ROOT / "output" / "full-60000-rerun.csv"
INPUT_SENTENCES_CSV = ROOT / "input" / "sentences.csv"
LEGACY_INPUT_SENTENCES_CSV = Path(r"D:\Dev\sentences\input\sentences.csv")
INPUT_MP3_MAP_CSV = ROOT / "output" / "sentences-only-mp3-map.csv"
OUTPUT_SQL = APP_ROOT / "sql" / "sentence_browser_60000.sql"

ANKI_MEDIA_BASE_PATH = r"D:\PortableApps\AnkiPortable\Data\AnkiAppData\sentences\collection.media"

ANKI_SOUND_RE = re.compile(r"\[sound:([^\]]+)\]", re.IGNORECASE)


SCHEMA_SQL = """
-- Auto-generated dump for Sentence Browser (MySQL)
SET NAMES utf8mb4;
SET FOREIGN_KEY_CHECKS=0;

DROP TABLE IF EXISTS `sentences`;
CREATE TABLE `sentences` (
  `id` BIGINT NOT NULL,
  `sentence` TEXT NOT NULL,
  `char_len` INT NOT NULL,
  `english` TEXT,
  `sounds` TEXT,
    `sounds_online` TEXT,
  `JLPT_origin` VARCHAR(20) DEFAULT NULL,
  `tags` TEXT,
  `jlpt_no_katakana` VARCHAR(10) DEFAULT NULL,
  `vocab_jlpt_pedagogical` VARCHAR(10) DEFAULT NULL,
  `vocab_pedagogical_details` TEXT,
  `vocab_jlpt_strict` VARCHAR(10) DEFAULT NULL,
  `vocab_details` TEXT,
  `kanji_jlpt` VARCHAR(10) DEFAULT NULL,
  `kanji_details` TEXT,
  `grammar_jlpt` VARCHAR(10) DEFAULT NULL,
  `grammar_details` TEXT,
  PRIMARY KEY (`id`),
  KEY `idx_jlpt_no_katakana` (`jlpt_no_katakana`),
  KEY `idx_vocab_jlpt_strict` (`vocab_jlpt_strict`),
  KEY `idx_grammar_jlpt` (`grammar_jlpt`),
  KEY `idx_kanji_jlpt` (`kanji_jlpt`),
  KEY `idx_char_len` (`char_len`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Référence du dossier audio local (informatif)
-- Base path: D:\\PortableApps\\AnkiPortable\\Data\\AnkiAppData\\sentences\\collection.media

""".lstrip()


def sql_value(value: str | None) -> str:
    if value is None:
        return "NULL"
    text = str(value)
    if text == "":
        return "NULL"
    escaped = text.replace("\\", "\\\\").replace("'", "\\'")
    return f"'{escaped}'"


def normalize_local_sounds(value: str | None) -> str:
    text = str(value or "").strip()
    if not text:
        return ""

    matches = [m.strip() for m in ANKI_SOUND_RE.findall(text) if m.strip()]
    if matches:
        deduped = list(dict.fromkeys(matches))
        return ",".join(deduped)

    fallback = (
        text.replace("<br />", "\n")
        .replace("<br/>", "\n")
        .replace("<br>", "\n")
    )

    parts = []
    for part in re.split(r"[,;\n]+", fallback):
        cleaned = part.strip().strip("[]")
        if cleaned.lower().startswith("sound:"):
            cleaned = cleaned[6:].strip()
        if cleaned:
            parts.append(cleaned)

    deduped = list(dict.fromkeys(parts))
    return ",".join(deduped)


def load_sentences_metadata() -> tuple[dict[str, dict[str, str]], Path | None]:
    metadata: dict[str, dict[str, str]] = {}
    source_path: Path | None = None

    for candidate in (INPUT_SENTENCES_CSV, LEGACY_INPUT_SENTENCES_CSV):
        if candidate.exists():
            source_path = candidate
            break

    if source_path is None:
        print(f"Warning: metadata CSV not found: {INPUT_SENTENCES_CSV} or {LEGACY_INPUT_SENTENCES_CSV}")
        return metadata, None

    with source_path.open("r", encoding="utf-8-sig", newline="") as source:
        reader = csv.DictReader(source, delimiter=";")
        for row in reader:
            row_id = str(row.get("0") or row.get("id") or row.get("\ufeff0") or "").strip()
            if not row_id:
                continue
            metadata[row_id] = {
                "english": str(row.get("fr", "") or ""),
                "sounds": normalize_local_sounds(str(row.get("sounds", "") or "")),
                "jlpt_origin": str(row.get("JLPT", "") or ""),
                "tags": str(row.get("tags", "") or ""),
            }
    return metadata, source_path


def load_online_sounds_by_id() -> tuple[dict[str, str], Path | None]:
    mapping: dict[str, str] = {}

    if not INPUT_MP3_MAP_CSV.exists():
        print(f"Warning: online mp3 map CSV not found: {INPUT_MP3_MAP_CSV}")
        return mapping, None

    with INPUT_MP3_MAP_CSV.open("r", encoding="utf-8-sig", newline="") as source:
        reader = csv.DictReader(source, delimiter=";")
        for row in reader:
            row_id = str(row.get("id", "") or "").strip()
            if not row_id:
                continue
            mapping[row_id] = str(row.get("mp3_urls", "") or "").strip()

    return mapping, INPUT_MP3_MAP_CSV


def build_dump() -> None:
    if not INPUT_CSV.exists():
        raise FileNotFoundError(f"Input CSV not found: {INPUT_CSV}")

    OUTPUT_SQL.parent.mkdir(parents=True, exist_ok=True)
    metadata_by_id, metadata_source = load_sentences_metadata()
    online_sounds_by_id, online_sounds_source = load_online_sounds_by_id()

    with INPUT_CSV.open("r", encoding="utf-8", newline="") as source, OUTPUT_SQL.open("w", encoding="utf-8", newline="\n") as out:
        out.write(SCHEMA_SQL)

        reader = csv.DictReader(source, delimiter=";")
        batch: list[str] = []
        batch_size = 1000
        inserted = 0

        for row in reader:
            sentence = str(row.get("sentence", "") or "")
            row_id = str(row.get("id", "") or "")
            meta = metadata_by_id.get(row_id, {})
            values = [
                sql_value(row_id),
                sql_value(sentence),
                str(len(sentence)),
                sql_value(meta.get("english")),
                sql_value(meta.get("sounds")),
                sql_value(online_sounds_by_id.get(row_id, "")),
                sql_value(meta.get("jlpt_origin")),
                sql_value(meta.get("tags")),
                sql_value(row.get("jlpt_no_katakana")),
                sql_value(row.get("vocab_jlpt_pedagogical")),
                sql_value(row.get("vocab_pedagogical_details")),
                sql_value(row.get("vocab_jlpt_strict")),
                sql_value(row.get("vocab_details")),
                sql_value(row.get("kanji_jlpt")),
                sql_value(row.get("kanji_details")),
                sql_value(row.get("grammar_jlpt")),
                sql_value(row.get("grammar_details")),
            ]
            batch.append("(" + ",".join(values) + ")")
            inserted += 1

            if len(batch) >= batch_size:
                out.write(
                    "INSERT INTO `sentences` (`id`,`sentence`,`char_len`,`english`,`sounds`,`sounds_online`,`JLPT_origin`,`tags`,`jlpt_no_katakana`,`vocab_jlpt_pedagogical`,`vocab_pedagogical_details`,`vocab_jlpt_strict`,`vocab_details`,`kanji_jlpt`,`kanji_details`,`grammar_jlpt`,`grammar_details`) VALUES\n"
                )
                out.write(",\n".join(batch))
                out.write(";\n")
                batch = []

        if batch:
            out.write(
                "INSERT INTO `sentences` (`id`,`sentence`,`char_len`,`english`,`sounds`,`sounds_online`,`JLPT_origin`,`tags`,`jlpt_no_katakana`,`vocab_jlpt_pedagogical`,`vocab_pedagogical_details`,`vocab_jlpt_strict`,`vocab_details`,`kanji_jlpt`,`kanji_details`,`grammar_jlpt`,`grammar_details`) VALUES\n"
            )
            out.write(",\n".join(batch))
            out.write(";\n")

        out.write("\nSET FOREIGN_KEY_CHECKS=1;\n")

    print(f"SQL dump generated: {OUTPUT_SQL}")
    print(f"Rows exported: {inserted}")
    print(f"Metadata source: {metadata_source if metadata_source else 'not found'}")
    print(f"Online MP3 map source: {online_sounds_source if online_sounds_source else 'not found'}")
    print(f"Audio base path (informative): {ANKI_MEDIA_BASE_PATH}")


if __name__ == "__main__":
    build_dump()
