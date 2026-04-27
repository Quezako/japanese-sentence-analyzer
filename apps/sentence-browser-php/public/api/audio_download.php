<?php

declare(strict_types=1);

require_once dirname(__DIR__, 2) . '/src/bootstrap.php';

function ad_fail(string $message, int $status = 400): void
{
    http_response_code($status);
    header('Content-Type: text/plain; charset=UTF-8');
    echo $message;
    exit;
}

function ad_sanitize_filename(string $filename): string
{
    $filename = trim($filename);
    if ($filename === '') {
        return 'audio.mp3';
    }

    $filename = preg_replace('/[\\\\\/\:\*\?\"\<\>\|]+/', '_', $filename) ?? 'audio.mp3';
    $filename = preg_replace('/\s+/', ' ', $filename) ?? 'audio.mp3';
    $filename = trim($filename, " \t\n\r\0\x0B.");

    if ($filename === '') {
        return 'audio.mp3';
    }

    return $filename;
}

function ad_filename_from_url(string $url): string
{
    $path = (string)parse_url($url, PHP_URL_PATH);
    $base = basename($path);
    if ($base === '' || $base === '/' || $base === '.') {
        return 'audio.mp3';
    }

    $decoded = rawurldecode($base);
    return ad_sanitize_filename($decoded);
}

function ad_fetch_with_curl(string $url): array
{
    $ch = curl_init($url);
    curl_setopt_array($ch, [
        CURLOPT_RETURNTRANSFER => true,
        CURLOPT_FOLLOWLOCATION => true,
        CURLOPT_MAXREDIRS => 5,
        CURLOPT_CONNECTTIMEOUT => 8,
        CURLOPT_TIMEOUT => 30,
        CURLOPT_HTTPGET => true,
        CURLOPT_USERAGENT => 'SentenceBrowserAudioDownload/1.0',
    ]);

    $body = curl_exec($ch);
    $httpCode = (int)curl_getinfo($ch, CURLINFO_HTTP_CODE);
    $contentType = (string)curl_getinfo($ch, CURLINFO_CONTENT_TYPE);
    $error = curl_error($ch);
    curl_close($ch);

    if (!is_string($body)) {
        throw new RuntimeException($error !== '' ? $error : 'Download failed');
    }
    if ($httpCode < 200 || $httpCode >= 300) {
        throw new RuntimeException('Remote HTTP ' . $httpCode);
    }

    return [
        'body' => $body,
        'content_type' => $contentType,
    ];
}

function ad_fetch_with_stream(string $url): array
{
    $context = stream_context_create([
        'http' => [
            'method' => 'GET',
            'follow_location' => 1,
            'max_redirects' => 5,
            'timeout' => 30,
            'header' => "User-Agent: SentenceBrowserAudioDownload/1.0\r\n",
        ],
    ]);

    $body = @file_get_contents($url, false, $context);
    if (!is_string($body) || $body === '') {
        throw new RuntimeException('Download failed');
    }

    $headers = $http_response_header ?? [];
    $httpCode = 0;
    $contentType = '';
    foreach ($headers as $header) {
        if (preg_match('/^HTTP\/(?:1\.[01]|2)\s+(\d{3})/i', (string)$header, $m)) {
            $httpCode = (int)$m[1];
        }
        if (stripos((string)$header, 'Content-Type:') === 0) {
            $contentType = trim(substr((string)$header, strlen('Content-Type:')));
        }
    }

    if ($httpCode < 200 || $httpCode >= 300) {
        throw new RuntimeException('Remote HTTP ' . $httpCode);
    }

    return [
        'body' => $body,
        'content_type' => $contentType,
    ];
}

try {
    $url = trim((string)($_GET['url'] ?? ''));
    $filenameHint = trim((string)($_GET['filename'] ?? ''));

    if ($url === '') {
        ad_fail('Missing url parameter', 400);
    }

    if (strlen($url) > 2000) {
        ad_fail('URL too long', 400);
    }

    $parts = parse_url($url);
    if (!is_array($parts)) {
        ad_fail('Invalid URL', 400);
    }

    $scheme = strtolower((string)($parts['scheme'] ?? ''));
    if ($scheme !== 'http' && $scheme !== 'https') {
        ad_fail('Only http/https URLs are allowed', 400);
    }

    if (function_exists('curl_init')) {
        $download = ad_fetch_with_curl($url);
    } elseif (ini_get('allow_url_fopen')) {
        $download = ad_fetch_with_stream($url);
    } else {
        ad_fail('No download transport available on server', 500);
    }

    $body = (string)($download['body'] ?? '');
    $contentType = trim((string)($download['content_type'] ?? ''));
    if ($contentType === '') {
        $contentType = 'application/octet-stream';
    }

    $filename = $filenameHint !== '' ? ad_sanitize_filename($filenameHint) : ad_filename_from_url($url);
    if (!preg_match('/\.[A-Za-z0-9]{2,5}$/', $filename)) {
        $filename .= '.mp3';
    }

    header('Content-Type: ' . $contentType);
    header('Content-Length: ' . (string)strlen($body));
    header('Content-Disposition: attachment; filename="' . str_replace('"', '', $filename) . '"; filename*=UTF-8\'\'' . rawurlencode($filename));
    header('Cache-Control: private, no-store, max-age=0');
    header('Pragma: no-cache');
    echo $body;
    exit;
} catch (Throwable $e) {
    ad_fail('Download error: ' . $e->getMessage(), 502);
}
