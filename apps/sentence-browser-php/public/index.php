<?php

declare(strict_types=1);

require_once dirname(__DIR__) . '/src/bootstrap.php';
$config = sb_load_config();
$appName = $config['app']['name'] ?? 'Sentence Browser';
$displayAppName = stripos($appName, 'japanese') === false ? ('Japanese ' . $appName) : $appName;
$localAudioBaseUrl = (string)($config['audio']['local_base_url'] ?? 'audio/');
?>
<!doctype html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title><?= htmlspecialchars($displayAppName, ENT_QUOTES, 'UTF-8') ?></title>
    <style>
        *, *::before, *::after { box-sizing: border-box; }
        body { font-family: Arial, sans-serif; margin: 0; background: #f4f6fa; font-size: 14px; }
        .container { width: 95%; margin: 0 auto; padding: 16px; }
        h1 { margin: 0 0 12px; font-size: 20px; }
        .card { background: white; border: 1px solid #dce3ef; border-radius: 8px; padding: 12px; margin-bottom: 12px; }
        .filters-grid { display: flex; gap: 12px; flex-wrap: wrap; align-items: flex-start; }
        .filter-group { display: flex; flex-direction: column; gap: 4px; min-width: 120px; }
        .filter-group label { font-size: 12px; font-weight: 600; color: #555; text-transform: uppercase; letter-spacing: .4px; }
        .filter-label-row { display: flex; align-items: center; justify-content: space-between; gap: 6px; }
        .filter-clear-btn {
            border: 1px solid #cfd7e6;
            background: #fff;
            color: #6b7280;
            border-radius: 999px;
            width: 16px;
            height: 16px;
            min-width: 16px;
            padding: 0;
            line-height: 14px;
            text-align: center;
            font-size: 12px;
            cursor: pointer;
        }
        .filter-clear-btn:hover { background: #f3f4f6; color: #111827; }
        input[type=text], input[type=number] { padding: 6px 8px; border: 1px solid #c9d2e3; border-radius: 6px; width: 100%; }
        select { padding: 4px 6px; border: 1px solid #c9d2e3; border-radius: 6px; width: 100%; }
        button { padding: 6px 14px; border: 1px solid #c9d2e3; border-radius: 6px; cursor: pointer; background: #f0f3f8; }
        button:hover { background: #e2e8f4; }
        .toolbar { display: flex; justify-content: space-between; align-items: center; margin: 8px 0; flex-wrap: wrap; gap: 8px; }
        .toolbar-left { display: flex; align-items: center; gap: 12px; }
        .loading-indicator { display: inline-flex; align-items: center; gap: 6px; color: #4b5563; font-size: 12px; }
        .loading-indicator.hidden { display: none; }
        .spinner {
            width: 14px;
            height: 14px;
            border: 2px solid #d1d5db;
            border-top-color: #3b82f6;
            border-radius: 50%;
            animation: spin .8s linear infinite;
        }
        @keyframes spin {
            to { transform: rotate(360deg); }
        }
        .pagination { display: flex; gap: 8px; align-items: center; }
        table { width: 100%; border-collapse: collapse; font-size: 13px; }
        th { cursor: pointer; background: #f0f3f8; white-space: nowrap; user-select: none; }
        th:hover { background: #e2e8f4; }
        th.sort-asc::after { content: ' ▲'; font-size: 10px; }
        th.sort-desc::after { content: ' ▼'; font-size: 10px; }
        th, td { border-bottom: 1px solid #edf1f7; padding: 6px 8px; vertical-align: top; text-align: left; }
        td.sentence { max-width: 340px; word-break: break-all; }
        td.english { max-width: 300px; color: #444; }
        td.tags { font-size: 11px; color: #666; }
        .tag-badge { display: inline-block; background: #e8f0fe; color: #1a56db; border-radius: 4px; padding: 1px 5px; margin: 1px; font-size: 11px; }
        .audio-btn { cursor: pointer; background: none; border: none; padding: 0 4px; font-size: 16px; line-height: 1; }
        .audio-btn:hover { color: #1a56db; }
        .audio-cell { min-width: 115px; }
        .audio-item { display: inline-flex; flex-direction: column; align-items: center; margin: 0 4px 4px 0; }
        .audio-btn-local, .audio-btn-online {
            border: 1px solid #c9d2e3;
            border-radius: 6px;
            padding: 2px 6px;
            background: #f8fbff;
            min-width: 28px;
            text-align: center;
        }
        .audio-btn-online {
            background: #eaf2ff;
            border-color: #8bb8ff;
            color: #1f5fbf;
        }
        .audio-download-btn {
            margin-top: 2px;
            font-size: 10px;
            border: 1px solid #c9d2e3;
            border-radius: 6px;
            padding: 1px 4px;
            background: #fff;
            color: #4a5568;
            text-decoration: none;
            line-height: 1.3;
        }
        .audio-download-btn-online {
            border-color: #8bb8ff;
            color: #1f5fbf;
        }
        .level-badge { display: inline-block; padding: 1px 6px; border-radius: 4px; font-weight: 700; font-size: 11px; }
        .lvl-N5 { background:#d1fae5; color:#065f46; }
        .lvl-N4 { background:#dbeafe; color:#1e40af; }
        .lvl-N3 { background:#fef9c3; color:#854d0e; }
        .lvl-N2 { background:#fed7aa; color:#9a3412; }
        .lvl-N1 { background:#fce7f3; color:#9d174d; }
        .row-detail { display: none; background: #f9fafb; }
        .row-detail td { font-size: 12px; color: #555; padding: 0 8px; }
        .detail-panel {
            max-height: 0;
            opacity: 0;
            overflow: hidden;
            transform: translateY(-4px);
            transition: max-height .24s ease, opacity .2s ease, transform .2s ease, padding .2s ease;
            padding: 0;
        }
        .row-detail.open .detail-panel {
            max-height: 360px;
            opacity: 1;
            transform: translateY(0);
            padding: 8px 0 10px;
        }
        .annotated-sentence {
            line-height: 1.9;
            font-size: 15px;
            color: #111827;
            margin-bottom: 8px;
            word-break: break-word;
        }
        .annotated-sentence .token-vocab {
            border-radius: 4px;
            padding: 0 2px;
            margin: 0 1px;
        }
        .token-vocab-N5 { background: #dcfce7; }
        .token-vocab-N4 { background: #dbeafe; }
        .token-vocab-N3 { background: #fef9c3; }
        .token-vocab-N2 { background: #ffedd5; }
        .token-vocab-N1 { background: #fce7f3; }
        .kanji-underline {
            text-decoration-line: underline;
            text-decoration-thickness: 2px;
            text-underline-offset: 2px;
        }
        .kanji-underline-N5 { text-decoration-color: #16a34a; }
        .kanji-underline-N4 { text-decoration-color: #2563eb; }
        .kanji-underline-N3 { text-decoration-color: #ca8a04; }
        .kanji-underline-N2 { text-decoration-color: #ea580c; }
        .kanji-underline-N1 { text-decoration-color: #be185d; }
        .detail-grid { display: flex; gap: 20px; flex-wrap: wrap; }
        .detail-item { display: flex; flex-direction: column; gap: 2px; }
        .detail-item strong { color: #333; }
        tr.expandable:hover { background: #fafbff; cursor: pointer; }
        #page-size-select { padding: 4px 6px; border: 1px solid #c9d2e3; border-radius: 6px; }
        .no-results { text-align: center; padding: 40px; color: #888; }
    </style>
</head>
<body>
<main class="container">
    <h1><?= htmlspecialchars($displayAppName, ENT_QUOTES, 'UTF-8') ?></h1>

    <div class="card">
        <div class="filters-grid">
            <div class="filter-group" style="min-width:200px;">
                <label for="q" class="filter-label-row"><span>Japanese search</span><button class="filter-clear-btn" type="button" data-clear-target="q" title="Clear Japanese search">×</button></label>
                <input id="q" type="text" placeholder="Search sentence…">
                <button id="resetBtn" type="button" style="margin-top:6px; align-self:flex-start; padding:4px 10px; font-size:12px;">✕ Reset filters</button>
            </div>
            <div class="filter-group" style="min-width:200px;">
                <label for="english_q" class="filter-label-row"><span>English search</span><button class="filter-clear-btn" type="button" data-clear-target="english_q" title="Clear English search">×</button></label>
                <input id="english_q" type="text" placeholder="Search translation…">
            </div>
            <div class="filter-group" style="min-width:220px;">
                <label for="grammar_details_q" class="filter-label-row"><span>Grammar details search</span><button class="filter-clear-btn" type="button" data-clear-target="grammar_details_q" title="Clear grammar details search">×</button></label>
                <input id="grammar_details_q" type="text" placeholder="Search grammar rules/details…">
            </div>
            <div class="filter-group" style="min-width:66px; max-width:66px;">
                <label for="char_len_min" class="filter-label-row"><span>Length min</span><button class="filter-clear-btn" type="button" data-clear-target="char_len_min" title="Clear min length">×</button></label>
                <input id="char_len_min" type="number" min="0" placeholder="0">
            </div>
            <div class="filter-group" style="min-width:66px; max-width:66px;">
                <label for="char_len_max" class="filter-label-row"><span>Length max</span><button class="filter-clear-btn" type="button" data-clear-target="char_len_max" title="Clear max length">×</button></label>
                <input id="char_len_max" type="number" min="0" placeholder="∞">
            </div>
            <div class="filter-group">
                <label for="jlpt_no_katakana" class="filter-label-row"><span>Overall level</span><button class="filter-clear-btn" type="button" data-clear-target="jlpt_no_katakana" title="Clear overall level">×</button></label>
                <select id="jlpt_no_katakana" multiple size="6"></select>
            </div>
            <div class="filter-group">
                <label for="vocab_jlpt_pedagogical" class="filter-label-row"><span>Vocab (flexible)</span><button class="filter-clear-btn" type="button" data-clear-target="vocab_jlpt_pedagogical" title="Clear vocab flexible">×</button></label>
                <select id="vocab_jlpt_pedagogical" multiple size="6"></select>
            </div>
            <div class="filter-group">
                <label for="vocab_jlpt_strict" class="filter-label-row"><span>Vocab (strict)</span><button class="filter-clear-btn" type="button" data-clear-target="vocab_jlpt_strict" title="Clear vocab strict">×</button></label>
                <select id="vocab_jlpt_strict" multiple size="6"></select>
            </div>
            <div class="filter-group" style="min-width:95px;">
                <label for="grammar_jlpt" class="filter-label-row"><span>Grammar</span><button class="filter-clear-btn" type="button" data-clear-target="grammar_jlpt" title="Clear grammar">×</button></label>
                <select id="grammar_jlpt" multiple size="6"></select>
            </div>
            <div class="filter-group" style="min-width:95px;">
                <label for="kanji_jlpt" class="filter-label-row"><span>Kanji</span><button class="filter-clear-btn" type="button" data-clear-target="kanji_jlpt" title="Clear kanji">×</button></label>
                <select id="kanji_jlpt" multiple size="6"></select>
            </div>
            <div class="filter-group" style="min-width:95px;">
                <label for="JLPT_origin" class="filter-label-row"><span>Origin level</span><button class="filter-clear-btn" type="button" data-clear-target="JLPT_origin" title="Clear origin level">×</button></label>
                <select id="JLPT_origin" multiple size="6"></select>
            </div>
            <div class="filter-group">
                <label for="tags" class="filter-label-row"><span>Tags</span><button class="filter-clear-btn" type="button" data-clear-target="tags" title="Clear tags">×</button></label>
                <select id="tags" multiple size="6"></select>
            </div>
        </div>
    </div>

    <div class="toolbar">
        <div class="toolbar-left">
            <span id="meta">Total: 0</span>
            <span id="loadingIndicator" class="loading-indicator hidden"><span class="spinner"></span>Loading…</span>
            <label style="display:flex;align-items:center;gap:6px;">
                Rows per page
                <select id="page-size-select">
                    <option value="25">25</option>
                    <option value="50" selected>50</option>
                    <option value="100">100</option>
                    <option value="200">200</option>
                </select>
            </label>
        </div>
        <div class="pagination">
            <button id="prevBtn" type="button">&#x2039; Prev</button>
            <span id="pageInfo">Page 1 / 1</span>
            <button id="nextBtn" type="button">Next &#x203a;</button>
        </div>
    </div>

    <div class="card" style="overflow:auto; padding:0;">
        <table>
            <thead>
            <tr>
                <th data-sort="id">ID</th>
                <th data-sort="sentence">Sentence</th>
                <th>Audio</th>
                <th data-sort="english">English</th>
                <th data-sort="char_len">Len</th>
                <th data-sort="jlpt_no_katakana">Overall</th>
                <th data-sort="vocab_jlpt_pedagogical">Vocab flexible</th>
                <th data-sort="vocab_jlpt_strict">Vocab strict</th>
                <th data-sort="grammar_jlpt">Grammar</th>
                <th data-sort="kanji_jlpt">Kanji</th>
                <th data-sort="JLPT_origin">Origin</th>
                <th data-sort="tags">Tags</th>
            </tr>
            </thead>
            <tbody id="rows"></tbody>
        </table>
        <div id="no-results" class="no-results" style="display:none;">No results found.</div>
    </div>

    <div class="pagination" style="justify-content:center; margin: 8px 0 16px;">
        <button id="prevBtn2" type="button">&#x2039; Prev</button>
        <span id="pageInfo2">Page 1 / 1</span>
        <button id="nextBtn2" type="button">Next &#x203a;</button>
    </div>
</main>

<script>
// ─── JLPT sort order ──────────────────────────────────────────────────────────
const JLPT_ORDER = ['N5','N4','N3','N2','N1'];

// ─── State ────────────────────────────────────────────────────────────────────
const state = {
    q: '',
    english_q: '',
    grammar_details_q: '',
    jlpt_no_katakana: [],
    vocab_jlpt_pedagogical: [],
    vocab_jlpt_strict: [],
    grammar_jlpt: [],
    kanji_jlpt: [],
    JLPT_origin: [],
    tags: [],
    char_len_min: '',
    char_len_max: '',
    sort_by: 'id',
    sort_dir: 'asc',
    page: 1,
    page_size: 50,
    total: 0,
};

const multiKeys = ['jlpt_no_katakana','vocab_jlpt_pedagogical','vocab_jlpt_strict','grammar_jlpt','kanji_jlpt','JLPT_origin','tags'];

// ─── URL deep-link ────────────────────────────────────────────────────────────
function readStateFromURL() {
    const p = new URLSearchParams(location.search);
    state.q            = p.get('q')            ?? '';
    state.english_q    = p.get('english_q')    ?? '';
    state.grammar_details_q = p.get('grammar_details_q') ?? '';
    state.char_len_min = p.get('char_len_min') ?? '';
    state.char_len_max = p.get('char_len_max') ?? '';
    state.sort_by      = p.get('sort_by')      ?? 'id';
    state.sort_dir     = p.get('sort_dir')     ?? 'asc';
    state.page         = parseInt(p.get('page') ?? '1', 10) || 1;
    state.page_size    = parseInt(p.get('page_size') ?? '50', 10) || 50;
    multiKeys.forEach(key => { state[key] = p.getAll(key + '[]'); });
}

function pushStateToURL() {
    const p = new URLSearchParams();
    if (state.q)            p.set('q', state.q);
    if (state.english_q)    p.set('english_q', state.english_q);
    if (state.grammar_details_q) p.set('grammar_details_q', state.grammar_details_q);
    if (state.char_len_min !== '') p.set('char_len_min', state.char_len_min);
    if (state.char_len_max !== '') p.set('char_len_max', state.char_len_max);
    if (state.sort_by !== 'id')   p.set('sort_by', state.sort_by);
    if (state.sort_dir !== 'asc') p.set('sort_dir', state.sort_dir);
    if (state.page > 1)    p.set('page', String(state.page));
    if (state.page_size !== 50) p.set('page_size', String(state.page_size));
    multiKeys.forEach(key => state[key].forEach(v => p.append(key + '[]', v)));
    const qs = p.toString();
    history.pushState(null, '', qs ? ('?' + qs) : location.pathname);
}

function buildApiParams() {
    const p = new URLSearchParams();
    if (state.q)            p.set('q', state.q);
    if (state.english_q)    p.set('english_q', state.english_q);
    if (state.grammar_details_q) p.set('grammar_details_q', state.grammar_details_q);
    if (state.char_len_min !== '') p.set('char_len_min', state.char_len_min);
    if (state.char_len_max !== '') p.set('char_len_max', state.char_len_max);
    p.set('sort_by', state.sort_by);
    p.set('sort_dir', state.sort_dir);
    p.set('page', String(state.page));
    p.set('page_size', String(state.page_size));
    multiKeys.forEach(key => state[key].forEach(v => p.append(key + '[]', v)));
    return p;
}

// ─── DOM helpers ──────────────────────────────────────────────────────────────
function selectedValues(selectEl) {
    return Array.from(selectEl.selectedOptions).map(o => o.value);
}

function syncFormFromState() {
    document.getElementById('q').value            = state.q;
    document.getElementById('english_q').value    = state.english_q;
    document.getElementById('grammar_details_q').value = state.grammar_details_q;
    document.getElementById('char_len_min').value = state.char_len_min;
    document.getElementById('char_len_max').value = state.char_len_max;
    document.getElementById('page-size-select').value = String(state.page_size);
    multiKeys.forEach(key => {
        const sel = document.getElementById(key);
        if (!sel) return;
        Array.from(sel.options).forEach(o => { o.selected = state[key].includes(o.value); });
    });
}

// ─── Facets ───────────────────────────────────────────────────────────────────
async function loadFacets() {
    const response = await fetch('api/facets.php');
    const data = await response.json();
    const noDashEmptyKeys = new Set(['grammar_jlpt', 'kanji_jlpt', 'JLPT_origin']);

    ['jlpt_no_katakana','vocab_jlpt_pedagogical','vocab_jlpt_strict','grammar_jlpt','kanji_jlpt','JLPT_origin'].forEach(key => {
        const select = document.getElementById(key);
        if (!select) return;
        select.innerHTML = '';
        (data[key] || []).forEach(item => {
            const opt = document.createElement('option');
            opt.value = item.value;
            if (item.value === '-') {
                opt.textContent = noDashEmptyKeys.has(key) ? `empty (${item.count})` : `\u2014 empty (${item.count})`;
            } else {
                opt.textContent = `${item.value} (${item.count})`;
            }
            select.appendChild(opt);
        });
    });

    const tagsSelect = document.getElementById('tags');
    if (tagsSelect && data.tags) {
        tagsSelect.innerHTML = '';
        const sortedTags = [...(data.tags || [])].sort((a, b) => a.value.localeCompare(b.value));
        sortedTags.forEach(item => {
            const opt = document.createElement('option');
            opt.value = item.value;
            opt.textContent = `${item.value} (${item.count})`;
            tagsSelect.appendChild(opt);
        });
    }
}

// ─── Render helpers ───────────────────────────────────────────────────────────
function escHtml(s) {
    return String(s ?? '').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}

function levelBadge(val) {
    if (!val || val === '-') return '<span style="color:#bbb">—</span>';
    const cls = JLPT_ORDER.includes(val) ? ` class="level-badge lvl-${val}"` : ' class="level-badge"';
    return `<span${cls}>${escHtml(val)}</span>`;
}

function renderTags(tagStr) {
    if (!tagStr) return '';
    return tagStr.split(/[\s|,]+/).filter(Boolean)
        .map(t => `<span class="tag-badge">${escHtml(t)}</span>`).join('');
}

function stripHtml(value) {
    return String(value ?? '').replace(/<[^>]*>/g, '');
}

function parseLevelDetails(detailsText) {
    const map = new Map();
    if (!detailsText) return map;

    String(detailsText)
        .split(',')
        .map(part => part.trim())
        .filter(Boolean)
        .forEach(part => {
            const match = part.match(/^(.*?):\s*(N[1-5]|-)\s*$/i);
            if (!match) return;
            const term = (match[1] || '').trim();
            const level = (match[2] || '').toUpperCase();
            if (!term || !level || level === '-') return;
            map.set(term, level);
        });

    return map;
}

function splitChars(text) {
    return Array.from(String(text ?? ''));
}

function isKanjiChar(char) {
    return /[\u3400-\u4DBF\u4E00-\u9FFF\uF900-\uFAFF々〆〤]/.test(char);
}

function applyKanjiUnderline(char, kanjiMap, tooltip) {
    const kanjiLevel = isKanjiChar(char) ? kanjiMap.get(char) : null;
    if (!kanjiLevel) {
        return `<span title="${escHtml(tooltip)}">${escHtml(char)}</span>`;
    }
    return `<span class="kanji-underline kanji-underline-${escHtml(kanjiLevel)}" title="${escHtml(tooltip)}">${escHtml(char)}</span>`;
}

function renderAnnotatedSentence(row) {
    const sentencePlain = stripHtml(row.sentence);
    if (!sentencePlain) return '';

    const vocabMap = parseLevelDetails(row.vocab_details || row.vocab_pedagogical_details || '');
    const kanjiMap = parseLevelDetails(row.kanji_details || '');
    const vocabWords = Array.from(vocabMap.keys()).sort((a, b) => b.length - a.length);

    const out = [];
    let cursor = 0;

    const buildTooltip = (word, wordLevel, kanjiPairs) => {
        const lines = [`Vocabulary: ${word} (${wordLevel})`];
        if (kanjiPairs.length) {
            lines.push(`Kanji: ${kanjiPairs.join(', ')}`);
        }
        return lines.join(' | ');
    };

    while (cursor < sentencePlain.length) {
        let matchedWord = null;
        let matchedLevel = null;

        for (const word of vocabWords) {
            if (!word) continue;
            if (sentencePlain.startsWith(word, cursor)) {
                matchedWord = word;
                matchedLevel = vocabMap.get(word) || null;
                break;
            }
        }

        if (matchedWord && matchedLevel) {
            const kanjiBits = [];
            const chars = splitChars(matchedWord);
            chars.forEach(ch => {
                const kl = kanjiMap.get(ch);
                if (kl) {
                    kanjiBits.push(`${ch} (${kl})`);
                }
            });
            const tooltip = buildTooltip(matchedWord, matchedLevel, kanjiBits);
            const renderedChars = chars.map(ch => {
                return applyKanjiUnderline(ch, kanjiMap, tooltip);
            }).join('');

            out.push(`<span class="token-vocab token-vocab-${escHtml(matchedLevel)}" title="${escHtml(tooltip)}">${renderedChars}</span>`);
            cursor += matchedWord.length;
            continue;
        }

        const ch = sentencePlain[cursor];
        const kl = kanjiMap.get(ch);
        if (kl) {
            out.push(`<span class="kanji-underline kanji-underline-${escHtml(kl)}" title="${escHtml(`Kanji: ${ch} (${kl})`)}">${escHtml(ch)}</span>`);
        } else {
            out.push(escHtml(ch));
        }
        cursor += 1;
    }

    return out.join('');
}

// ─── Audio ────────────────────────────────────────────────────────────────────
const ONLINE_AUDIO_BASE = 'https://receptomanijalogi.web.app/audio/';
const LOCAL_AUDIO_BASE = <?= json_encode($localAudioBaseUrl, JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES) ?>;

function parseSound(sounds) {
    if (!sounds) return [];

    const text = String(sounds).trim();
    if (!text) return [];

    const ankiMatches = [...text.matchAll(/\[sound:([^\]]+)\]/g)].map(m => m[1].trim()).filter(Boolean);
    if (ankiMatches.length) {
        return [...new Set(ankiMatches)];
    }

    return [...new Set(
        text
            .split(',')
            .map(part => part.trim())
            .filter(Boolean)
    )];
}

function parseOnlineSounds(value) {
    if (!value) return [];
    return String(value)
        .split(',')
        .map(part => part.trim())
        .filter(Boolean);
}

function toOnlineAudioUrl(path) {
    if (!path) return '';
    if (/^https?:\/\//i.test(path)) return path;
    return ONLINE_AUDIO_BASE + path.replace(/^\/+/, '');
}

function toLocalAudioUrl(filename) {
    if (!filename) return '';
    const safeBase = String(LOCAL_AUDIO_BASE || 'audio/');
    const baseWithSlash = safeBase.endsWith('/') ? safeBase : (safeBase + '/');
    return baseWithSlash + encodeURIComponent(filename);
}

function setLoading(isLoading) {
    const indicator = document.getElementById('loadingIndicator');
    if (!indicator) return;
    indicator.classList.toggle('hidden', !isLoading);
}

let currentAudio = null;
let currentAudioUrl = null;
let currentAudioButton = null;

function setAudioButtonState(button, isPlaying) {
    if (!button) return;
    button.textContent = isPlaying ? '\u23F8' : '\u25B6';
}

function resetCurrentAudioState() {
    if (currentAudioButton) {
        setAudioButtonState(currentAudioButton, false);
    }
    currentAudio = null;
    currentAudioUrl = null;
    currentAudioButton = null;
}

function playAudioUrl(url, button) {
    if (!url) return;

    if (currentAudio && currentAudioUrl === url) {
        if (currentAudio.paused) {
            currentAudio.play().then(() => {
                setAudioButtonState(button, true);
            }).catch(() => {});
        } else {
            currentAudio.pause();
            setAudioButtonState(button, false);
        }
        return;
    }

    if (currentAudio) {
        currentAudio.pause();
        resetCurrentAudioState();
    }

    const audio = new Audio(url);
    audio.addEventListener('ended', () => {
        resetCurrentAudioState();
    });
    audio.play().then(() => {
        setAudioButtonState(button, true);
    }).catch(() => {});
    currentAudio = audio;
    currentAudioUrl = url;
    currentAudioButton = button;
}

// ─── Rows ─────────────────────────────────────────────────────────────────────
function renderRows(rows) {
    const tbody = document.getElementById('rows');
    tbody.innerHTML = '';
    document.getElementById('no-results').style.display = rows.length ? 'none' : '';
    if (!rows.length) return;

    rows.forEach(row => {
        const localSounds = parseSound(row.sounds);
        const onlineSounds = parseOnlineSounds(row.sounds_online);

        const tr = document.createElement('tr');
        tr.className = 'expandable';
        tr.innerHTML = `
            <td>${escHtml(row.id)}</td>
            <td class="sentence">${row.sentence ?? ''}</td>
            <td class="audio-cell"></td>
            <td class="english">${row.english ?? ''}</td>
            <td style="text-align:center;">${escHtml(row.char_len)}</td>
            <td>${levelBadge(row.jlpt_no_katakana)}</td>
            <td>${levelBadge(row.vocab_jlpt_pedagogical)}</td>
            <td>${levelBadge(row.vocab_jlpt_strict)}</td>
            <td>${levelBadge(row.grammar_jlpt)}</td>
            <td>${levelBadge(row.kanji_jlpt)}</td>
            <td>${levelBadge(row.JLPT_origin)}</td>
            <td class="tags">${renderTags(row.tags)}</td>`;

        // Audio buttons built via DOM to allow stopPropagation
        const audioTd = tr.querySelector('.audio-cell');
        const addAudioControls = ({ playUrl, downloadUrl, title, isOnline }) => {
            const wrap = document.createElement('div');
            wrap.className = 'audio-item';

            const btn = document.createElement('button');
            btn.className = 'audio-btn ' + (isOnline ? 'audio-btn-online' : 'audio-btn-local');
            btn.title = title;
            btn.textContent = '\u25B6';
            btn.addEventListener('click', e => {
                e.stopPropagation();
                playAudioUrl(playUrl, btn);
            });

            const download = document.createElement('a');
            download.className = 'audio-download-btn' + (isOnline ? ' audio-download-btn-online' : '');
            download.href = downloadUrl;
            download.target = '_blank';
            download.rel = 'noopener';
            download.textContent = 'DL';
            download.addEventListener('click', e => {
                e.stopPropagation();
            });

            wrap.appendChild(btn);
            wrap.appendChild(download);
            audioTd.appendChild(wrap);
        };

        localSounds.forEach(filename => {
            const localUrl = toLocalAudioUrl(filename);
            addAudioControls({
                playUrl: localUrl,
                downloadUrl: localUrl,
                title: `Local: ${filename}`,
                isOnline: false,
            });
        });

        onlineSounds.forEach(path => {
            const onlineUrl = toOnlineAudioUrl(path);
            addAudioControls({
                playUrl: onlineUrl,
                downloadUrl: onlineUrl,
                title: `Online: ${path}`,
                isOnline: true,
            });
        });

        const trDetail = document.createElement('tr');
        trDetail.className = 'row-detail';
        trDetail.innerHTML = `<td colspan="12"><div class="detail-panel">
            <div class="annotated-sentence">${renderAnnotatedSentence(row)}</div>
            <div class="detail-grid">
                <div class="detail-item"><strong>Vocab flexible</strong><span>${escHtml(row.vocab_pedagogical_details)}</span></div>
                <div class="detail-item"><strong>Vocab strict</strong><span>${escHtml(row.vocab_details)}</span></div>
                <div class="detail-item"><strong>Kanji details</strong><span>${escHtml(row.kanji_details)}</span></div>
                <div class="detail-item"><strong>Grammar details</strong><span>${escHtml(row.grammar_details)}</span></div>
            </div>
        </div></td>`

        tr.addEventListener('click', () => {
            const isOpen = trDetail.classList.contains('open');
            if (isOpen) {
                trDetail.classList.remove('open');
                window.setTimeout(() => {
                    if (!trDetail.classList.contains('open')) {
                        trDetail.style.display = 'none';
                    }
                }, 240);
            } else {
                trDetail.style.display = 'table-row';
                requestAnimationFrame(() => trDetail.classList.add('open'));
            }
        });
        tbody.appendChild(tr);
        tbody.appendChild(trDetail);
    });
}

// ─── Pagination ───────────────────────────────────────────────────────────────
function updatePagination() {
    const totalPages = Math.max(1, Math.ceil(state.total / state.page_size));
    const txt = `Page ${state.page} / ${totalPages}`;
    document.getElementById('pageInfo').textContent  = txt;
    document.getElementById('pageInfo2').textContent = txt;
    document.getElementById('meta').textContent = `Total: ${state.total.toLocaleString()}`;
    ['prevBtn','prevBtn2'].forEach(id => document.getElementById(id).disabled = state.page <= 1);
    ['nextBtn','nextBtn2'].forEach(id => document.getElementById(id).disabled = state.page >= totalPages);
}

function syncSortHeaders() {
    document.querySelectorAll('th[data-sort]').forEach(th => {
        th.classList.remove('sort-asc','sort-desc');
        if (th.dataset.sort === state.sort_by)
            th.classList.add(state.sort_dir === 'asc' ? 'sort-asc' : 'sort-desc');
    });
}

// ─── Main load ────────────────────────────────────────────────────────────────
async function loadRows() {
    setLoading(true);
    pushStateToURL();
    try {
        const response = await fetch('api/sentences.php?' + buildApiParams().toString());
        const data = await response.json();
        state.total = data.total || 0;
        renderRows(data.items || []);
        updatePagination();
        syncSortHeaders();
    } finally {
        setLoading(false);
    }
}

// ─── Events ───────────────────────────────────────────────────────────────────
function bindEvents() {
    let timer = null;
    const trigger = () => { clearTimeout(timer); timer = setTimeout(() => { state.page = 1; loadRows(); }, 300); };

    const clearFilterTarget = (key) => {
        if (!key) return;

        if (multiKeys.includes(key)) {
            state[key] = [];
            const selectEl = document.getElementById(key);
            if (selectEl) {
                Array.from(selectEl.options).forEach(opt => { opt.selected = false; });
            }
        } else if (key === 'q' || key === 'english_q' || key === 'grammar_details_q' || key === 'char_len_min' || key === 'char_len_max') {
            state[key] = '';
            const inputEl = document.getElementById(key);
            if (inputEl) {
                inputEl.value = '';
            }
        } else {
            return;
        }

        state.page = 1;
        loadRows();
    };

    document.querySelectorAll('.filter-clear-btn').forEach(btn => {
        btn.addEventListener('click', (event) => {
            event.preventDefault();
            event.stopPropagation();
            const key = btn.getAttribute('data-clear-target') || '';
            clearFilterTarget(key);
        });
    });

    document.getElementById('q').addEventListener('input', e => { state.q = e.target.value.trim(); trigger(); });
    document.getElementById('english_q').addEventListener('input', e => { state.english_q = e.target.value.trim(); trigger(); });
    document.getElementById('grammar_details_q').addEventListener('input', e => { state.grammar_details_q = e.target.value.trim(); trigger(); });
    document.getElementById('char_len_min').addEventListener('input', e => { state.char_len_min = e.target.value; trigger(); });
    document.getElementById('char_len_max').addEventListener('input', e => { state.char_len_max = e.target.value; trigger(); });

    multiKeys.forEach(key => {
        const el = document.getElementById(key);
        if (!el) return;
        el.addEventListener('change', () => { state[key] = selectedValues(el); state.page = 1; loadRows(); });
    });

    document.querySelectorAll('th[data-sort]').forEach(th => {
        th.addEventListener('click', () => {
            const sort = th.dataset.sort;
            state.sort_dir = (state.sort_by === sort && state.sort_dir === 'asc') ? 'desc' : 'asc';
            state.sort_by = sort;
            state.page = 1;
            loadRows();
        });
    });

    const pagePrev = () => { if (state.page > 1) { state.page--; loadRows(); } };
    const pageNext = () => {
        if (state.page < Math.ceil(state.total / state.page_size)) { state.page++; loadRows(); }
    };
    ['prevBtn','prevBtn2'].forEach(id => document.getElementById(id).addEventListener('click', pagePrev));
    ['nextBtn','nextBtn2'].forEach(id => document.getElementById(id).addEventListener('click', pageNext));

    document.getElementById('page-size-select').addEventListener('change', e => {
        state.page_size = parseInt(e.target.value, 10);
        state.page = 1;
        loadRows();
    });

    document.getElementById('resetBtn').addEventListener('click', () => {
        state.q = ''; state.english_q = ''; state.grammar_details_q = '';
        state.char_len_min = ''; state.char_len_max = '';
        state.sort_by = 'id'; state.sort_dir = 'asc'; state.page = 1;
        multiKeys.forEach(key => state[key] = []);
        syncFormFromState();
        loadRows();
    });

    window.addEventListener('popstate', () => {
        readStateFromURL();
        syncFormFromState();
        loadRows();
    });
}

// ─── Init ─────────────────────────────────────────────────────────────────────
(async function init() {
    readStateFromURL();
    await loadFacets();
    syncFormFromState();
    bindEvents();
    await loadRows();
})();
</script>
</body>
</html>
