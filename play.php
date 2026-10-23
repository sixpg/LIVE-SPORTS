<?php
$mpd = $_GET['mpd'] ?? '';

$keyIds = isset($_GET['keyid']) ? explode(',', $_GET['keyid']) : [];
$keys = isset($_GET['key']) ? explode(',', $_GET['key']) : [];

// Alternative format: ?keys=KID1:KEY1,KID2:KEY2
if (isset($_GET['keys'])) {
    $keyIds = [];
    $keys = [];

    foreach (explode(',', $_GET['keys']) as $pair) {
        $parts = explode(':', $pair, 2);

        if (count($parts) === 2) {
            $keyIds[] = trim($parts[0]);
            $keys[] = trim($parts[1]);
        }
    }
}

if (empty($mpd) ||
    !filter_var($mpd, FILTER_VALIDATE_URL) ||
    !in_array(parse_url($mpd, PHP_URL_SCHEME), ['http', 'https'], true)) {
    http_response_code(400);
    exit('Please provide a valid MPD URL using ?mpd=...');
}

$clearKeys = [];

if (count($keyIds) !== count($keys)) {
    http_response_code(400);
    exit('The number of key IDs and keys must match.');
}

foreach ($keyIds as $i => $kid) {
    $kid = strtolower(trim($kid));
    $key = strtolower(trim($keys[$i]));

    if (!preg_match('/^[a-f0-9]{32}$/', $kid) ||
        !preg_match('/^[a-f0-9]{32}$/', $key)) {
        http_response_code(400);
        exit('Invalid ClearKey format.');
    }

    $clearKeys[$kid] = $key;
}

$playerData = [
    'mpd' => $mpd,
    'keys' => $clearKeys
];
?>
