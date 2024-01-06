<?php

if ($_SERVER["REQUEST_METHOD"] == "GET") {
    header("Content-Type: text/plain");
    print(file_get_contents("./mam.py"));
    exit();
}

$data = json_decode(file_get_contents("php://input"), true);

function arg($name) {
    global $data;

    if (!array_key_exists($name, $data)) error("Missing argument: $name");
    return $data[$name];
}

function error($msg) {
    header("Content-Type: application/json");
    print(json_encode(["good" => false, "error" => $msg]));
    file_put_contents("php://stderr", $msg . "\n");
    exit();
}

function respond($data = null) {
    $data = ["good" => true, "data" => $data];

    header("Content-Type: application/json");
    print(json_encode($data));
    exit();
}

$PASSWORD = getenv("MAM_PASSWORD");
if (!$PASSWORD) error("MAM_PASSWORD not set");
if (is_null($data)) error("Invalid request");
if (arg("password") !== $PASSWORD) error("Invalid password");

$db = new SQLite3("mam.db");
$db->exec("CREATE TABLE IF NOT EXISTS `files` (
    `id` TEXT PRIMARY KEY,
    `version` INTEGER DEFAULT 0,
    `content` TEXT DEFAULT '',
    `owner` INTEGER DEFAULT 0,
    `group` INTEGER DEFAULT 0,
    `mode` INTEGER DEFAULT 0
)");
$db->exec("CREATE TABLE IF NOT EXISTS `directories` (
    `id` TEXT PRIMARY KEY,
    `version` INTEGER DEFAULT 0,
    `content` TEXT DEFAULT '{\"dirs\": {}, \"files\": {}}',
    `owner` INTEGER DEFAULT 0,
    `group` INTEGER DEFAULT 0,
    `mode` INTEGER DEFAULT 0
)");

switch (arg("action")) {
    case "check":
        respond(true);

    case "file-create":
        $stmt = $db->prepare("INSERT INTO `files` (`id`) VALUES (:id)");
        $stmt->bindValue(":id", arg("id"));
        $stmt->execute();
        respond();

    case "file-delete":
        $stmt = $db->prepare("DELETE FROM `files` WHERE `id` = :id");
        $stmt->bindValue(":id", arg("id"));
        $stmt->execute();
        respond();

    case "file-exists":
        $stmt = $db->prepare("SELECT COUNT(*) FROM `files` WHERE `id` = :id");
        $stmt->bindValue(":id", arg("id"));
        $result = $stmt->execute();
        respond($result->fetchArray()[0] > 0);

    case "file-list":
        $stmt = $db->prepare("SELECT `id`, `version` FROM `files`");
        $result = $stmt->execute();
        $files = [];
        while ($row = $result->fetchArray(SQLITE3_ASSOC)) $files[$row["id"]] = $row["version"];
        respond($files);

    case "file-set-content":
        $stmt = $db->prepare("UPDATE `files` SET `content` = :content, `version` = :version WHERE `id` = :id");
        $stmt->bindValue(":id", arg("id"));
        $stmt->bindValue(":content", arg("content"));
        $stmt->bindValue(":version", arg("version"));
        $stmt->execute();
        respond();

    case "file-set-meta":
        $stmt = $db->prepare("UPDATE `files` SET `owner` = :owner, `group` = :group, `mode` = :mode WHERE `id` = :id");
        $stmt->bindValue(":id", arg("id"));
        $stmt->bindValue(":owner", arg("owner"));
        $stmt->bindValue(":group", arg("group"));
        $stmt->bindValue(":mode", arg("mode"));
        $stmt->execute();
        respond();

    case "file-get-content":
        $stmt = $db->prepare("SELECT `content` FROM `files` WHERE `id` = :id");
        $stmt->bindValue(":id", arg("id"));
        $result = $stmt->execute();
        $row = $result->fetchArray(SQLITE3_ASSOC);
        respond($row["content"]);

    case "file-get-meta":
        $stmt = $db->prepare("SELECT `version`, `owner`, `group`, `mode` FROM `files` WHERE `id` = :id");
        $stmt->bindValue(":id", arg("id"));
        $result = $stmt->execute();
        $row = $result->fetchArray(SQLITE3_ASSOC);
        respond($row);

    case "directory-create":
        $stmt = $db->prepare("INSERT INTO `directories` (`id`) VALUES (:id)");
        $stmt->bindValue(":id", arg("id"));
        $stmt->execute();
        respond();

    case "directory-delete":
        $stmt = $db->prepare("DELETE FROM `directories` WHERE `id` = :id");
        $stmt->bindValue(":id", arg("id"));
        $stmt->execute();
        respond();

    case "directory-exists":
        $stmt = $db->prepare("SELECT COUNT(*) FROM `directories` WHERE `id` = :id");
        $stmt->bindValue(":id", arg("id"));
        $result = $stmt->execute();
        respond($result->fetchArray()[0] > 0);

    case "directory-list":
        $stmt = $db->prepare("SELECT `id`, `version` FROM `directories`");
        $result = $stmt->execute();
        $directories = [];
        while ($row = $result->fetchArray(SQLITE3_ASSOC)) $directories[$row["id"]] = $row["version"];
        respond($directories);

    case "directory-set-content":
        $stmt = $db->prepare("UPDATE `directories` SET `content` = :content, `version` = :version WHERE `id` = :id");
        $stmt->bindValue(":id", arg("id"));
        $stmt->bindValue(":content", json_encode(arg("content")));
        $stmt->bindValue(":version", arg("version"));
        $stmt->execute();
        respond();

    case "directory-set-meta":
        $stmt = $db->prepare("UPDATE `directories` SET `owner` = :owner, `group` = :group, `mode` = :mode WHERE `id` = :id");
        $stmt->bindValue(":id", arg("id"));
        $stmt->bindValue(":owner", arg("owner"));
        $stmt->bindValue(":group", arg("group"));
        $stmt->bindValue(":mode", arg("mode"));
        $stmt->execute();
        respond();

    case "directory-get-content":
        $stmt = $db->prepare("SELECT `content` FROM `directories` WHERE `id` = :id");
        $stmt->bindValue(":id", arg("id"));
        $result = $stmt->execute();
        $row = $result->fetchArray(SQLITE3_ASSOC);
        respond(json_decode($row["content"], true));

    case "directory-get-meta":
        $stmt = $db->prepare("SELECT `version`, `owner`, `group`, `mode` FROM `directories` WHERE `id` = :id");
        $stmt->bindValue(":id", arg("id"));
        $result = $stmt->execute();
        $row = $result->fetchArray(SQLITE3_ASSOC);
        respond($row);

    default:
        error("Invalid action: " . arg("action"));
}
