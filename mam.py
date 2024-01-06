#!/usr/bin/env python3

import base64
import json
import os
import shutil
import subprocess
import sys
import urllib.request
from datetime import datetime
from getpass import getpass

DIR = "/usr/local/share/mam"
CONFIG = {"address": "localhost", "password": "", "sudoer": "nobody"}


def b32e(s: str) -> str:
    return base64.b32encode(s.encode()).decode()


def b32d(s: str) -> str:
    return base64.b32decode(s.encode()).decode()


def b64e(b: bytes) -> str:
    return base64.b64encode(b).decode()


def b64d(s: str) -> bytes:
    return base64.b64decode(s.encode())


def makedirs(path: str) -> list[str]:
    dirs = []
    while not os.path.isdir(path):
        dirs.insert(0, path)
        path = os.path.dirname(path)

    for dir in dirs:
        os.mkdir(dir)

    return dirs


def date(timestamp: int = datetime.now().timestamp()) -> str:
    return datetime.fromtimestamp(timestamp).strftime("%Y-%m-%d %H:%M:%S")


def json_read(path: str, default: any = None):
    if not os.path.isfile(path):
        return default

    with open(path) as f:
        return json.load(f)


def json_write(path: str, data: dict):
    with open(path, "w") as f:
        json.dump(data, f)


def arg(n: int) -> str:
    return sys.argv[n] if len(sys.argv) > n else None


def api(action: str, data: dict = {}):
    data["action"] = action
    data["password"] = CONFIG["password"]
    data = json.dumps(data).encode()

    req = urllib.request.Request(CONFIG["address"], data=data, headers={"Content-Type": "application/json"})
    try:
        res = json.loads(urllib.request.urlopen(req).read().decode())
        if res["good"]:
            return res["data"]
    except:
        pass

    return None


def file_version(obj: str) -> int:
    file = b32d(obj)
    if not os.path.isfile(file):
        return 0

    stat = os.stat(file)
    return int(max(stat.st_mtime, stat.st_ctime))


def file_syncVersion(obj: str) -> tuple[int, int]:
    if not os.path.isfile(f"{DIR}/objects/files/{obj}"):
        return 0, 0

    data = json_read(f"{DIR}/objects/files/{obj}", {"local": 0, "remote": 0})
    return data["local"], data["remote"]


def file_backup(obj: str):
    file = b32d(obj)
    if not os.path.isfile(file):
        return

    shutil.copy(file, f"{DIR}/backups/files/{obj}")
    os.chown(f"{DIR}/backups/files/{obj}", os.stat(file).st_uid, os.stat(file).st_gid)
    os.chmod(f"{DIR}/backups/files/{obj}", os.stat(file).st_mode)


def file_restore(obj: str):
    file = b32d(obj)
    if os.path.isfile(file):
        os.remove(file)

    if os.path.isfile(f"{DIR}/backups/files/{obj}"):
        shutil.move(f"{DIR}/backups/files/{obj}", file)

    if os.path.isfile(f"{DIR}/objects/files/{obj}"):
        os.remove(f"{DIR}/objects/files/{obj}")


def file_download(obj: str, version: int):
    file = b32d(obj)
    dirs = makedirs(os.path.dirname(file))
    meta = api("file-get-meta", {"id": obj})

    with open(file, "wb") as f:
        f.write(b64d(api("file-get-content", {"id": obj})))

    os.chown(file, meta["owner"], meta["group"])
    os.chmod(file, meta["mode"])

    json_write(f"{DIR}/objects/files/{obj}", {"local": file_version(obj), "remote": version})

    created_dirs = json_read(f"{DIR}/objects/created_dirs", [])
    for dir in dirs:
        os.chown(dir, meta["owner"], meta["group"])
        if not dir in created_dirs:
            created_dirs.append(dir)

    json_write(f"{DIR}/objects/created_dirs", created_dirs)


def file_upload(obj: str):
    file = b32d(obj)
    version = file_version(obj)
    stat = os.stat(file)

    with open(file, "rb") as f:
        api("file-set-content", {"id": obj, "content": b64e(f.read()), "version": version})

    api("file-set-meta", {"id": obj, "owner": stat.st_uid, "group": stat.st_gid, "mode": stat.st_mode})
    json_write(f"{DIR}/objects/files/{obj}", {"local": version, "remote": version})


def action_install():
    print("Creating directories...")
    for type in ["files"]:
        os.makedirs(f"{DIR}/objects/{type}", exist_ok=True)
        os.makedirs(f"{DIR}/backups/{type}", exist_ok=True)

    print("Installing mam...")
    shutil.copy(__file__, "/usr/local/bin/mam")
    os.chmod("/usr/local/bin/mam", 0o755)

    print("Installing daemon...")
    with open("/etc/systemd/system/mam.service", "w") as f:
        f.write("[Unit]\n")
        f.write("Description=MAM Daemon\n")
        f.write("After=network.target\n")
        f.write("\n")
        f.write("[Service]\n")
        f.write("Type=simple\n")
        f.write("ExecStart=/usr/local/bin/mam sync\n")
        f.write("Restart=always\n")
        f.write("RestartSec=600\n")
        f.write("\n")
        f.write("[Install]\n")
        f.write("WantedBy=default.target\n")

    os.system("systemctl daemon-reload")
    os.system("systemctl enable --now mam.service")

    print("Done!")
    print("Please run `mam auth` to authenticate this machine.")


def action_auth():
    while True:
        CONFIG["address"] = input("Server address: ")
        CONFIG["password"] = getpass("Server password: ")
        CONFIG["sudoer"] = input("Preferred sudo user: ")

        if not api("check"):
            print("Authentication failed!")
            print("Please try again.")
            print()
            continue

        if "not allowed" in subprocess.check_output(["sudo", "-l", "-U", CONFIG["sudoer"]]).decode():
            print("Invalid sudo user!")
            print("Please try again.")
            print()
            continue

        break

    print("Authentication successful!")
    json_write(f"{DIR}/config", CONFIG)
    os.chmod(f"{DIR}/config", 0o600)


def action_uninstall():
    print("Restoring local files...")
    for obj in os.listdir(f"{DIR}/objects/files"):
        file_restore(obj)

    print("Removing created directories...")
    dirs = json_read(f"{DIR}/objects/created_dirs", [])
    dirs = sorted(dirs, key=lambda dir: dir.count("/"), reverse=True)
    for dir in dirs:
        try:
            os.rmdir(dir)
        except:
            pass

    print("Stopping daemon...")
    os.system("systemctl disable --now mam.service")
    os.remove("/etc/systemd/system/mam.service")

    print("Uninstalling mam...")
    os.remove("/usr/local/bin/mam")
    shutil.rmtree(DIR)

    print("Done!")


def action_status():
    if not os.path.isfile(f"{DIR}/config"):
        print("Not configured.")
        sys.exit(1)
    elif not api("check"):
        print("Authentication failed.")
        sys.exit(1)
    elif not os.path.isfile(f"{DIR}/state"):
        print("Not synced.")
    else:
        with open(f"{DIR}/state") as f:
            print(f.read())


def action_list():
    if not api("check"):
        print("Authentication failed.")
        sys.exit(1)

    print("Synchronized files:")
    local_objects = os.listdir(f"{DIR}/objects/files")
    remote_objects = api("file-list")

    for obj in local_objects:
        if not obj in remote_objects:
            continue

        file = b32d(obj)
        local_version = file_version(obj)
        remote_version = remote_objects[obj]
        local_sync_version, remote_sync_version = file_syncVersion(obj)

        if remote_version > remote_sync_version:
            print(f"  {file} ({date(remote_version)}, remote changed)")
        elif local_version > local_sync_version:
            print(f"  {file} ({date(local_version)}, local changed)")
        elif local_version < local_sync_version:
            print(f"  {file} ({date(local_version)}, local deleted)")
        else:
            print(f"  {file} ({date(remote_version)})")

    for obj in remote_objects:
        if not obj in local_objects:
            file = b32d(obj)
            print(f"  {file} ({date(remote_objects[obj])}, remote only)")

    for obj in local_objects:
        if not obj in remote_objects:
            file = b32d(obj)
            print(f"  {file} ({date(file_version(obj))}, local only)")


def action_sync():
    if not api("check"):
        with open(f"{DIR}/state") as f:
            f.write("Authentication failed.")

        sys.exit(1)

    with open(f"{DIR}/state", "w") as f:
        f.write("Syncing...")

    local_files = os.listdir(f"{DIR}/objects/files")
    remote_files = api("file-list")
    for file in local_files:
        if not file in remote_files:
            file_restore(file)

    for file in remote_files:
        if not file in local_files:
            file_backup(file)
            file_download(file, remote_files[file])
        else:
            local_version = file_version(file)
            remote_version = remote_files[file]
            local_sync_version, remote_sync_version = file_syncVersion(file)

            if remote_version > remote_sync_version or local_version < local_sync_version:
                file_download(file)
            elif local_version > local_sync_version:
                file_upload(file)

    with open(f"{DIR}/state", "w") as f:
        f.write(f"Last sync: {date()}")


def action_addFile(path: str):
    file = os.path.abspath(path)
    if not os.path.isfile(file):
        print("File does not exist")
        sys.exit(1)

    obj = b32e(file)
    if api("file-exists", {"id": obj}):
        print("File is already synced")
        sys.exit(1)

    file_backup(obj)
    api("file-create", {"id": obj})
    file_upload(obj)

    print("File added")


def action_removeFile(path: str):
    file = os.path.abspath(path)
    obj = b32e(file)
    if not api("file-exists", {"id": obj}):
        print("File is not synced")
        sys.exit(1)

    api("file-delete", {"id": obj})
    file_restore(obj)

    print("File removed")


if __name__ == "__main__":
    if os.geteuid() != 0:
        print("This script must be run as root")
        sys.exit(1)

    os.makedirs(DIR, exist_ok=True)
    CONFIG = json_read(f"{DIR}/config", CONFIG)

    match arg(1):
        case "install":
            if len(sys.argv) != 2:
                print("Usage: mam install")
                sys.exit(1)

            action_install()

        case "auth":
            if len(sys.argv) != 2:
                print("Usage: mam auth")
                sys.exit(1)

            action_auth()

        case "uninstall":
            if len(sys.argv) != 2:
                print("Usage: mam uninstall")
                sys.exit(1)

            action_uninstall()

        case "status":
            if len(sys.argv) != 2:
                print("Usage: mam status")
                sys.exit(1)

            action_status()

        case "list":
            if len(sys.argv) != 2:
                print("Usage: mam list")
                sys.exit(1)

            action_list()

        case "sync":
            if len(sys.argv) != 2:
                print("Usage: mam sync")
                sys.exit(1)

            action_sync()

        case "add":
            match arg(2):
                case "file":
                    if len(sys.argv) != 4:
                        print("Usage: mam add file <path>")
                        sys.exit(1)

                    action_addFile(arg(3))

                case _:
                    print("Usage: mam add <object>")
                    print("Add an object to sync")
                    print()
                    print("mam add file <path>       Add a file to sync")
                    sys.exit(1)

        case "remove":
            match arg(2):
                case "file":
                    if len(sys.argv) != 4:
                        print("Usage: mam remove file <path>")
                        sys.exit(1)

                    action_removeFile(arg(3))

                case _:
                    print("Usage: mam remove <object>")
                    print("Remove an object from sync")
                    print()
                    print("mam remove file <path>       Remove a file from sync")
                    sys.exit(1)

        case _:
            print("Usage: mam <command>")
            print("Mange multiple Arch Linux machines")
            print()
            print("mam install    Install mam on this machine")
            print("mam auth       Authenticate this machine with a mam server")
            print("mam uninstall  Uninstall mam from this machine")
            print("mam status     Show last sync status")
            print("mam list       List all synced objects")
            print("mam sync       Sync all objects")
            print("mam add        Add an object to sync")
            print("mam remove     Remove an object from sync")
            sys.exit(1)
