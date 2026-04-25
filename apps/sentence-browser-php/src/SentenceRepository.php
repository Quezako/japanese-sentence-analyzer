<?php

declare(strict_types=1);

class SentenceRepository
{
    private PDO $pdo;

    /** JLPT level sort order: N5 (easiest) first, N1 last, then other values, NULL/-  at the end */
    private const JLPT_ORDER = ['N5', 'N4', 'N3', 'N2', 'N1'];

    private array $allowedSorts = [
        'id',
        'char_len',
        'jlpt_no_katakana',
        'vocab_jlpt_pedagogical',
        'vocab_jlpt_strict',
        'grammar_jlpt',
        'kanji_jlpt',
        'JLPT_origin',
        'english',
        'tags',
    ];

    public function __construct(PDO $pdo)
    {
        $this->pdo = $pdo;
    }

    public function getFacets(): array
    {
        return [
            'jlpt_no_katakana'       => $this->facetJlpt('jlpt_no_katakana'),
            'vocab_jlpt_pedagogical' => $this->facetJlpt('vocab_jlpt_pedagogical'),
            'vocab_jlpt_strict'      => $this->facetJlpt('vocab_jlpt_strict'),
            'grammar_jlpt'           => $this->facetJlpt('grammar_jlpt'),
            'kanji_jlpt'             => $this->facetJlpt('kanji_jlpt'),
            'JLPT_origin'            => $this->facetJlpt('JLPT_origin'),
            'tags'                   => $this->facetTags(),
        ];
    }

    /**
     * Facet for JLPT-level columns: sorted N5→N1, then other values alpha, then NULL/- last.
     */
    private function facetJlpt(string $column): array
    {
        $sql = "SELECT COALESCE($column, '-') AS value, COUNT(*) AS count
                FROM sentences
                GROUP BY COALESCE($column, '-')";
        $stmt = $this->pdo->query($sql);
        $rows = $stmt->fetchAll();

        $order = self::JLPT_ORDER;
        usort($rows, function (array $a, array $b) use ($order) {
            $ia = array_search($a['value'], $order, true);
            $ib = array_search($b['value'], $order, true);
            $aIsNull = ($a['value'] === '-' || $a['value'] === '');
            $bIsNull = ($b['value'] === '-' || $b['value'] === '');
            // nulls last
            if ($aIsNull && !$bIsNull) return 1;
            if (!$aIsNull && $bIsNull) return -1;
            // both known JLPT levels
            if ($ia !== false && $ib !== false) return $ia - $ib;
            // known before unknown
            if ($ia !== false) return -1;
            if ($ib !== false) return 1;
            // both unknown: alpha
            return strcmp($a['value'], $b['value']);
        });

        return $rows;
    }

    /**
     * Facet for tags column (pipe-separated values e.g. "bunpro|JLPT5").
     * Explodes, counts individual tags, sorts by count desc.
     */
    private function facetTags(): array
    {
        // Only fetch distinct non-null tags values
        $stmt = $this->pdo->query("SELECT tags, COUNT(*) AS cnt FROM sentences WHERE tags IS NOT NULL AND tags <> '' GROUP BY tags");
        $tagCounts = [];
        while ($row = $stmt->fetch()) {
            $parts = preg_split('/[\s|,]+/', (string)$row['tags']);
            foreach ($parts as $tag) {
                $tag = trim($tag);
                if ($tag === '') continue;
                $tagCounts[$tag] = ($tagCounts[$tag] ?? 0) + (int)$row['cnt'];
            }
        }
        arsort($tagCounts);
        $result = [];
        foreach ($tagCounts as $tag => $count) {
            $result[] = ['value' => $tag, 'count' => $count];
        }
        return $result;
    }

    public function search(array $params): array
    {
        $where = [];
        $bindings = [];

        $this->addInFilter($where, $bindings, 'jlpt_no_katakana', $params['jlpt_no_katakana'] ?? []);
        $this->addInFilter($where, $bindings, 'vocab_jlpt_pedagogical', $params['vocab_jlpt_pedagogical'] ?? []);
        $this->addInFilter($where, $bindings, 'vocab_jlpt_strict', $params['vocab_jlpt_strict'] ?? []);
        $this->addInFilter($where, $bindings, 'grammar_jlpt', $params['grammar_jlpt'] ?? []);
        $this->addInFilter($where, $bindings, 'kanji_jlpt', $params['kanji_jlpt'] ?? []);
        $this->addInFilter($where, $bindings, 'JLPT_origin', $params['JLPT_origin'] ?? []);

        // Tags: each selected tag must appear in the pipe-separated tags column
        foreach (($params['tags'] ?? []) as $idx => $tag) {
            $tag = trim((string)$tag);
            if ($tag === '') continue;
            $key = ':tag_' . $idx;
            $where[] = "tags LIKE $key";
            $bindings[$key] = '%' . $tag . '%';
        }

        if (($params['char_len_min'] ?? '') !== '') {
            $where[] = 'char_len >= :char_len_min';
            $bindings[':char_len_min'] = max(0, (int)$params['char_len_min']);
        }
        if (($params['char_len_max'] ?? '') !== '') {
            $where[] = 'char_len <= :char_len_max';
            $bindings[':char_len_max'] = max(0, (int)$params['char_len_max']);
        }
        $this->addTextSearchWithRomaji(
            $where,
            $bindings,
            'sentence',
            (string)($params['q'] ?? ''),
            'q'
        );
        if (!empty($params['english_q'])) {
            $where[] = 'english LIKE :english_q';
            $bindings[':english_q'] = '%' . $params['english_q'] . '%';
        }
        $this->addTextSearchWithRomaji(
            $where,
            $bindings,
            'grammar_details',
            (string)($params['grammar_details_q'] ?? ''),
            'grammar_details_q'
        );

        $whereSql = $where ? ('WHERE ' . implode(' AND ', $where)) : '';
        $sortBy = (string)($params['sort_by'] ?? 'id');
        if (!in_array($sortBy, $this->allowedSorts, true)) {
            $sortBy = 'id';
        }
        // Quote column name to handle uppercase (JLPT_origin)
        $sortByQuoted = "`$sortBy`";
        $sortDir = strtolower((string)($params['sort_dir'] ?? 'asc')) === 'desc' ? 'DESC' : 'ASC';

        $page = max(1, (int)($params['page'] ?? 1));
        $pageSize = max(1, min(200, (int)($params['page_size'] ?? 50)));
        $offset = ($page - 1) * $pageSize;

        $countStmt = $this->pdo->prepare("SELECT COUNT(*) FROM sentences $whereSql");
        foreach ($bindings as $key => $value) {
            $countStmt->bindValue($key, $value);
        }
        $countStmt->execute();
        $total = (int)$countStmt->fetchColumn();

        $sql = "SELECT id, sentence, char_len, english, sounds, sounds_online, JLPT_origin, tags,
                       jlpt_no_katakana, vocab_jlpt_strict, grammar_jlpt, kanji_jlpt,
                       vocab_jlpt_pedagogical, vocab_details, vocab_pedagogical_details,
                       kanji_details, grammar_details
                FROM sentences
                $whereSql
                ORDER BY $sortByQuoted $sortDir, id ASC
                LIMIT :limit OFFSET :offset";
        $stmt = $this->pdo->prepare($sql);
        foreach ($bindings as $key => $value) {
            $stmt->bindValue($key, $value);
        }
        $stmt->bindValue(':limit', $pageSize, PDO::PARAM_INT);
        $stmt->bindValue(':offset', $offset, PDO::PARAM_INT);
        $stmt->execute();

        return [
            'items' => $stmt->fetchAll(),
            'total' => $total,
            'page' => $page,
            'page_size' => $pageSize,
        ];
    }

    private function addInFilter(array &$where, array &$bindings, string $column, array $values): void
    {
        if (!$values) {
            return;
        }
        $cleanValues = array_values(array_filter(array_map('strval', $values), fn($v) => $v !== ''));
        if (!$cleanValues) {
            return;
        }
        $placeholders = [];
        $safePrefix = preg_replace('/[^a-zA-Z0-9_]/', '_', $column);
        foreach ($cleanValues as $index => $value) {
            $key = ':' . $safePrefix . '_' . $index;
            $placeholders[] = $key;
            $bindings[$key] = ($value === '-') ? null : $value;
        }
        // Handle possible NULL values (stored as '-' in UI)
        $hasNull = in_array('-', $cleanValues, true);
        $nonNullPlaceholders = array_filter($placeholders, fn($k) => $bindings[$k] !== null);
        if ($hasNull && $nonNullPlaceholders) {
            $where[] = sprintf('(`%s` IN (%s) OR `%s` IS NULL)', $column, implode(',', array_values($nonNullPlaceholders)), $column);
        } elseif ($hasNull) {
            $where[] = sprintf('`%s` IS NULL', $column);
        } else {
            $where[] = sprintf('`%s` IN (%s)', $column, implode(',', $placeholders));
        }
        // Remove null bindings (not used as PDO params)
        foreach ($bindings as $k => $v) {
            if ($v === null) unset($bindings[$k]);
        }
    }

    private function addTextSearchWithRomaji(
        array &$where,
        array &$bindings,
        string $column,
        string $rawQuery,
        string $paramBase
    ): void {
        $query = trim($rawQuery);
        if ($query === '') {
            return;
        }

        $likeParts = [];
        $seen = [];

        $baseKey = ':' . $paramBase . '_raw';
        $bindings[$baseKey] = '%' . $query . '%';
        $likeParts[] = sprintf('%s LIKE %s', $column, $baseKey);
        $seen[$query] = true;

        foreach ($this->romajiToJapaneseVariants($query) as $index => $variant) {
            if ($variant === '' || isset($seen[$variant])) {
                continue;
            }
            $seen[$variant] = true;
            $key = ':' . $paramBase . '_r' . $index;
            $bindings[$key] = '%' . $variant . '%';
            $likeParts[] = sprintf('%s LIKE %s', $column, $key);
        }

        $where[] = '(' . implode(' OR ', $likeParts) . ')';
    }

    private function romajiToJapaneseVariants(string $query): array
    {
        if (!$this->looksLikeRomaji($query)) {
            return [];
        }

        $tokenized = preg_split('/\s+/', mb_strtolower(trim($query), 'UTF-8'));
        if (!$tokenized) {
            return [];
        }

        $kanaTokens = [];
        foreach ($tokenized as $token) {
            $token = preg_replace('/[^a-z\-]/', '', $token ?? '');
            if ($token === '') {
                continue;
            }
            $kana = $this->romajiTokenToHiragana($token);
            if ($kana === '') {
                continue;
            }
            $kanaTokens[] = $kana;
        }

        if (!$kanaTokens) {
            return [];
        }

        $joined = implode('', $kanaTokens);
        $spaced = implode(' ', $kanaTokens);

        if ($spaced === $joined) {
            return [$joined];
        }

        return [$joined, $spaced];
    }

    private function looksLikeRomaji(string $query): bool
    {
        return (bool)preg_match("/^[a-zA-Z\\s\\-`']+$/", trim($query));
    }

    private function romajiTokenToHiragana(string $token): string
    {
        $map3 = [
            'kya' => 'きゃ', 'kyu' => 'きゅ', 'kyo' => 'きょ',
            'gya' => 'ぎゃ', 'gyu' => 'ぎゅ', 'gyo' => 'ぎょ',
            'sha' => 'しゃ', 'shu' => 'しゅ', 'sho' => 'しょ',
            'sya' => 'しゃ', 'syu' => 'しゅ', 'syo' => 'しょ',
            'ja' => 'じゃ', 'ju' => 'じゅ', 'jo' => 'じょ',
            'jya' => 'じゃ', 'jyu' => 'じゅ', 'jyo' => 'じょ',
            'cha' => 'ちゃ', 'chu' => 'ちゅ', 'cho' => 'ちょ',
            'tya' => 'ちゃ', 'tyu' => 'ちゅ', 'tyo' => 'ちょ',
            'nya' => 'にゃ', 'nyu' => 'にゅ', 'nyo' => 'にょ',
            'hya' => 'ひゃ', 'hyu' => 'ひゅ', 'hyo' => 'ひょ',
            'bya' => 'びゃ', 'byu' => 'びゅ', 'byo' => 'びょ',
            'pya' => 'ぴゃ', 'pyu' => 'ぴゅ', 'pyo' => 'ぴょ',
            'mya' => 'みゃ', 'myu' => 'みゅ', 'myo' => 'みょ',
            'rya' => 'りゃ', 'ryu' => 'りゅ', 'ryo' => 'りょ',
            'shi' => 'し', 'chi' => 'ち', 'tsu' => 'つ',
        ];

        $map2 = [
            'ka' => 'か', 'ki' => 'き', 'ku' => 'く', 'ke' => 'け', 'ko' => 'こ',
            'ga' => 'が', 'gi' => 'ぎ', 'gu' => 'ぐ', 'ge' => 'げ', 'go' => 'ご',
            'sa' => 'さ', 'si' => 'し', 'su' => 'す', 'se' => 'せ', 'so' => 'そ',
            'za' => 'ざ', 'zi' => 'じ', 'zu' => 'ず', 'ze' => 'ぜ', 'zo' => 'ぞ',
            'ta' => 'た', 'ti' => 'ち', 'tu' => 'つ', 'te' => 'て', 'to' => 'と',
            'da' => 'だ', 'di' => 'ぢ', 'du' => 'づ', 'de' => 'で', 'do' => 'ど',
            'na' => 'な', 'ni' => 'に', 'nu' => 'ぬ', 'ne' => 'ね', 'no' => 'の',
            'ha' => 'は', 'hi' => 'ひ', 'hu' => 'ふ', 'fu' => 'ふ', 'he' => 'へ', 'ho' => 'ほ',
            'ba' => 'ば', 'bi' => 'び', 'bu' => 'ぶ', 'be' => 'べ', 'bo' => 'ぼ',
            'pa' => 'ぱ', 'pi' => 'ぴ', 'pu' => 'ぷ', 'pe' => 'ぺ', 'po' => 'ぽ',
            'ma' => 'ま', 'mi' => 'み', 'mu' => 'む', 'me' => 'め', 'mo' => 'も',
            'ya' => 'や', 'yu' => 'ゆ', 'yo' => 'よ',
            'ra' => 'ら', 'ri' => 'り', 'ru' => 'る', 're' => 'れ', 'ro' => 'ろ',
            'wa' => 'わ', 'wo' => 'を',
        ];

        $map1 = [
            'a' => 'あ', 'i' => 'い', 'u' => 'う', 'e' => 'え', 'o' => 'お',
            'n' => 'ん',
        ];

        $result = '';
        $i = 0;
        $len = strlen($token);

        while ($i < $len) {
            $rest = substr($token, $i);

            if (
                $i + 1 < $len
                && $token[$i] === $token[$i + 1]
                && preg_match('/[bcdfghjklmpqrstvwxyz]/', $token[$i])
                && $token[$i] !== 'n'
            ) {
                $result .= 'っ';
                $i++;
                continue;
            }

            if ($token[$i] === 'n') {
                $next = $i + 1 < $len ? $token[$i + 1] : '';
                if ($next === '' || preg_match('/[^aeiouy]/', $next)) {
                    $result .= 'ん';
                    $i++;
                    continue;
                }
            }

            $chunk3 = substr($rest, 0, 3);
            if (isset($map3[$chunk3])) {
                $result .= $map3[$chunk3];
                $i += 3;
                continue;
            }

            $chunk2 = substr($rest, 0, 2);
            if (isset($map2[$chunk2])) {
                $result .= $map2[$chunk2];
                $i += 2;
                continue;
            }

            $chunk1 = substr($rest, 0, 1);
            if (isset($map1[$chunk1])) {
                $result .= $map1[$chunk1];
                $i += 1;
                continue;
            }

            $i++;
        }

        return $result;
    }
}
