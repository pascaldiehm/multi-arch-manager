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

switch (arg("action")) {
    case "check":
        respond(true);

    default:
        error("Invalid action: " . arg("action"));
}
