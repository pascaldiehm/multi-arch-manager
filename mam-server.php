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
$db->exec("CREATE TABLE IF NOT EXISTS `packages` (
    `id` TEXT PRIMARY KEY
)");
$db->exec("CREATE TABLE IF NOT EXISTS `partials` (
    `id` TEXT PRIMARY KEY,
    `version` INTEGER DEFAULT 0,
    `content` TEXT DEFAULT '[]',
    `fallback` TEXT DEFAULT '',
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

    case "package-add":
        $stmt = $db->prepare("INSERT INTO `packages` (`id`) VALUES (:id)");
        $stmt->bindValue(":id", arg("id"));
        $stmt->execute();
        respond();

    case "package-remove":
        $stmt = $db->prepare("DELETE FROM `packages` WHERE `id` = :id");
        $stmt->bindValue(":id", arg("id"));
        $stmt->execute();
        respond();

    case "package-exists":
        $stmt = $db->prepare("SELECT COUNT(*) FROM `packages` WHERE `id` = :id");
        $stmt->bindValue(":id", arg("id"));
        $result = $stmt->execute();
        respond($result->fetchArray()[0] > 0);

    case "package-list":
        $stmt = $db->prepare("SELECT `id` FROM `packages`");
        $result = $stmt->execute();
        $packages = [];
        while ($row = $result->fetchArray(SQLITE3_ASSOC)) $packages[] = $row["id"];
        respond($packages);

    case "partial-create":
        $stmt = $db->prepare("INSERT INTO `partials` (`id`) VALUES (:id)");
        $stmt->bindValue(":id", arg("id"));
        $stmt->execute();
        respond();

    case "partial-delete":
        $stmt = $db->prepare("DELETE FROM `partials` WHERE `id` = :id");
        $stmt->bindValue(":id", arg("id"));
        $stmt->execute();
        respond();

    case "partial-exists":
        $stmt = $db->prepare("SELECT COUNT(*) FROM `partials` WHERE `id` = :id");
        $stmt->bindValue(":id", arg("id"));
        $result = $stmt->execute();
        respond($result->fetchArray()[0] > 0);

    case "partial-list":
        $stmt = $db->prepare("SELECT `id`, `version` FROM `partials`");
        $result = $stmt->execute();
        $partials = [];
        while ($row = $result->fetchArray(SQLITE3_ASSOC)) $partials[$row["id"]] = $row["version"];
        respond($partials);

    case "partial-set-content":
        $stmt = $db->prepare("UPDATE `partials` SET `content` = :content, `version` = :version WHERE `id` = :id");
        $stmt->bindValue(":id", arg("id"));
        $stmt->bindValue(":content", json_encode(arg("content")));
        $stmt->bindValue(":version", arg("version"));
        $stmt->execute();
        respond();

    case "partial-set-meta":
        $stmt = $db->prepare("UPDATE `partials` SET `owner` = :owner, `group` = :group, `mode` = :mode WHERE `id` = :id");
        $stmt->bindValue(":id", arg("id"));
        $stmt->bindValue(":owner", arg("owner"));
        $stmt->bindValue(":group", arg("group"));
        $stmt->bindValue(":mode", arg("mode"));
        $stmt->execute();
        respond();

    case "partial-set-fallback":
        $stmt = $db->prepare("UPDATE `partials` SET `fallback` = :fallback WHERE `id` = :id");
        $stmt->bindValue(":id", arg("id"));
        $stmt->bindValue(":fallback", arg("fallback"));
        $stmt->execute();
        respond();

    case "partial-get-content":
        $stmt = $db->prepare("SELECT `content` FROM `partials` WHERE `id` = :id");
        $stmt->bindValue(":id", arg("id"));
        $result = $stmt->execute();
        $row = $result->fetchArray(SQLITE3_ASSOC);
        respond(json_decode($row["content"], true));

    case "partial-get-meta":
        $stmt = $db->prepare("SELECT `version`, `owner`, `group`, `mode` FROM `partials` WHERE `id` = :id");
        $stmt->bindValue(":id", arg("id"));
        $result = $stmt->execute();
        $row = $result->fetchArray(SQLITE3_ASSOC);
        respond($row);

    case "partial-get-fallback":
        $stmt = $db->prepare("SELECT `fallback` FROM `partials` WHERE `id` = :id");
        $stmt->bindValue(":id", arg("id"));
        $result = $stmt->execute();
        $row = $result->fetchArray(SQLITE3_ASSOC);
        respond($row["fallback"]);

    default:
        error("Invalid action: " . arg("action"));
}
