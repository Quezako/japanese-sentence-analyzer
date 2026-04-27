<?php

declare(strict_types=1);

require_once dirname(__DIR__, 2) . '/src/bootstrap.php';

function tr_read_payload(): array
{
    $raw = file_get_contents('php://input');
    if (!is_string($raw) || trim($raw) === '') {
        return [];
    }
    $decoded = json_decode($raw, true);
    return is_array($decoded) ? $decoded : [];
}

function tr_normalize_lang(string $lang): string
{
    $lang = strtoupper(trim($lang));
    if ($lang === '') {
        return 'FR';
    }
    if (preg_match('/^[A-Z]{2}$/', $lang)) {
        return $lang;
    }
    if (preg_match('/^([A-Z]{2})-[A-Z]{2}$/', $lang, $m)) {
        return $m[1];
    }
    return 'FR';
}

function tr_translate_deepl(string $text, string $targetLang, string $apiKey): ?string
{
    if ($apiKey === '') {
        return null;
    }

    $url = 'https://api-free.deepl.com/v2/translate';
    $postFields = http_build_query([
        'auth_key' => $apiKey,
        'text' => $text,
        'target_lang' => $targetLang,
    ]);

    if (function_exists('curl_init')) {
        $ch = curl_init($url);
        curl_setopt_array($ch, [
            CURLOPT_RETURNTRANSFER => true,
            CURLOPT_POST => true,
            CURLOPT_POSTFIELDS => $postFields,
            CURLOPT_TIMEOUT => 12,
            CURLOPT_CONNECTTIMEOUT => 6,
            CURLOPT_HTTPHEADER => ['Content-Type: application/x-www-form-urlencoded'],
        ]);
        $response = curl_exec($ch);
        $httpCode = (int)curl_getinfo($ch, CURLINFO_HTTP_CODE);
        curl_close($ch);

        if (!is_string($response) || $httpCode < 200 || $httpCode >= 300) {
            return null;
        }

        $json = json_decode($response, true);
        $translated = $json['translations'][0]['text'] ?? null;
        return is_string($translated) && $translated !== '' ? $translated : null;
    }

    $context = stream_context_create([
        'http' => [
            'method' => 'POST',
            'header' => "Content-Type: application/x-www-form-urlencoded\r\n",
            'content' => $postFields,
            'timeout' => 12,
        ],
    ]);

    $response = @file_get_contents($url, false, $context);
    if (!is_string($response) || $response === '') {
        return null;
    }

    $json = json_decode($response, true);
    $translated = $json['translations'][0]['text'] ?? null;
    return is_string($translated) && $translated !== '' ? $translated : null;
}

function tr_translate_google(string $text, string $targetLang): ?string
{
    $url = 'https://translate.googleapis.com/translate_a/single?client=gtx&sl=auto&dt=t&tl=' . rawurlencode($targetLang) . '&q=' . rawurlencode($text);

    $response = null;

    if (function_exists('curl_init')) {
        $ch = curl_init($url);
        curl_setopt_array($ch, [
            CURLOPT_RETURNTRANSFER => true,
            CURLOPT_TIMEOUT => 12,
            CURLOPT_CONNECTTIMEOUT => 6,
        ]);
        $response = curl_exec($ch);
        $httpCode = (int)curl_getinfo($ch, CURLINFO_HTTP_CODE);
        curl_close($ch);
        if (!is_string($response) || $httpCode < 200 || $httpCode >= 300) {
            $response = null;
        }
    }

    if (!is_string($response) || $response === '') {
        $context = stream_context_create([
            'http' => [
                'method' => 'GET',
                'timeout' => 12,
            ],
        ]);
        $response = @file_get_contents($url, false, $context);
        if (!is_string($response) || $response === '') {
            return null;
        }
    }

    $json = json_decode($response, true);
    if (!is_array($json) || !isset($json[0]) || !is_array($json[0])) {
        return null;
    }

    $parts = [];
    foreach ($json[0] as $segment) {
        if (is_array($segment) && isset($segment[0]) && is_string($segment[0])) {
            $parts[] = $segment[0];
        }
    }

    $translated = trim(implode('', $parts));
    return $translated !== '' ? $translated : null;
}

try {
    $config = sb_load_config();
    $payload = tr_read_payload();

    $text = trim((string)($payload['text'] ?? $_POST['text'] ?? $_GET['text'] ?? ''));
    if ($text === '') {
        sb_error('Missing text', 400);
    }

    $targetLangRaw = (string)($payload['target_lang'] ?? $_POST['target_lang'] ?? $_GET['target_lang'] ?? 'FR');
    $targetLang = tr_normalize_lang($targetLangRaw);

    $deepLKey = (string)($config['services']['deepl_api_key'] ?? getenv('DEEPL_API_KEY') ?: '');

    $translated = tr_translate_deepl($text, $targetLang, $deepLKey);
    $provider = null;

    if (is_string($translated) && $translated !== '') {
        $provider = 'deepl';
    } else {
        $translated = tr_translate_google($text, $targetLang);
        $provider = (is_string($translated) && $translated !== '') ? 'google' : null;
    }

    if (!is_string($translated) || $translated === '') {
        sb_error('Translation failed', 502);
    }

    sb_json([
        'ok' => true,
        'translated_text' => $translated,
        'target_lang' => $targetLang,
        'provider' => $provider,
    ]);
} catch (Throwable $e) {
    sb_error('Translation error: ' . $e->getMessage(), 500);
}
