<?php
// votes.php - простой обработчик голосований

header('Content-Type: application/json');
header('Access-Control-Allow-Origin: *');
header('Access-Control-Allow-Methods: POST, GET, OPTIONS');
header('Access-Control-Allow-Headers: Content-Type');

if ($_SERVER['REQUEST_METHOD'] === 'OPTIONS') {
    exit(0);
}

// Получаем данные
$input = json_decode(file_get_contents('php://input'), true);

if (!$input) {
    echo json_encode(['success' => false, 'error' => 'No data']);
    exit;
}

$userId = $input['userId'] ?? 'unknown';
$trackId = $input['trackId'] ?? 0;
$voteValue = $input['value'] ?? 0; // 1 = like, -1 = dislike

// Логируем голос
$logEntry = date('Y-m-d H:i:s') . " | User: $userId | Track: $trackId | Vote: $voteValue\n";
file_put_contents('votes.log', $logEntry, FILE_APPEND);

// Обновляем треки если нужно
$tracksFile = 'tracks.json';
if (file_exists($tracksFile)) {
    $tracks = json_decode(file_get_contents($tracksFile), true);
    
    foreach ($tracks as &$track) {
        if ($track['id'] == $trackId) {
            if (!isset($track['votes'])) {
                $track['votes'] = ['likes' => 0, 'dislikes' => 0];
            }
            
            if ($voteValue === 1) {
                $track['votes']['likes']++;
            } elseif ($voteValue === -1) {
                $track['votes']['dislikes']++;
            }
            
            break;
        }
    }
    
    file_put_contents($tracksFile, json_encode($tracks, JSON_PRETTY_PRINT | JSON_UNESCAPED_UNICODE));
}

echo json_encode(['success' => true]);
?>
