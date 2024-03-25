#!/usr/bin/env python3

import base64
import json
import os
import re
import shutil
import sys
import urllib.request
from datetime import datetime
from getpass import getpass
from typing import Any, TypeVar

T = TypeVar("T")

DIR = "/var/lib/mam"
CONFIG = {"address": "http://localhost", "password": ""}


def b32e(s: str) -> str:
    return base64.b32encode(s.encode()).decode()


def b32d(s: str) -> str:
    return base64.b32decode(s.encode()).decode()


def b64e(b: bytes) -> str:
    return base64.b64encode(b).decode()


def b64d(s: str) -> bytes:
    return base64.b64decode(s.encode())


def date(timestamp: int = int(datetime.now().timestamp())) -> str:
    return datetime.fromtimestamp(timestamp).strftime("%Y-%m-%d %H:%M:%S")


def json_read(path: str, default: T) -> T:
    if not os.path.isfile(path):
        return default

    with open(path, "r") as f:
        return json.load(f)


def json_write(path: str, data: object):
    with open(path, "w") as f:
        json.dump(data, f)


def lines_read(path: str) -> list[str]:
    if not os.path.isfile(path):
        return []

    with open(path, "r") as f:
        return f.read().splitlines()


def lines_write(path: str, lines: list[str]):
    with open(path, "w") as f:
        f.write("\n".join(lines) + "\n")


def makedirs(path: str) -> list[str]:
    dirs = []
    while not os.path.isdir(path):
        dirs.insert(0, path)
        path = os.path.dirname(path)

    for dir in dirs:
        os.mkdir(dir)

    return dirs


def handleCreatedDirs(dirs: list[str], owner: int, group: int):
    created_dirs = json_read(f"{DIR}/objects/created_dirs", [])
    for dir in dirs:
        os.chown(dir, owner, group)
        if not dir in created_dirs:
            created_dirs.append(dir)

    json_write(f"{DIR}/objects/created_dirs", created_dirs)


def arg(n: int) -> str | None:
    return sys.argv[n] if len(sys.argv) > n else None


def requireAuth():
    if not os.path.isfile(f"{DIR}/config"):
        print("Not configured.")
    elif not api("check"):
        print("Authentication failed.")
    else:
        return

    sys.exit(1)


def requireArgs(n: int | list[int], message: str):
    if not isinstance(n, list):
        n = [n]

    if not len(sys.argv) in n:
        print(message)
        sys.exit(1)


def api(action: str, data: dict = {}) -> Any:
    data["action"] = action
    data["password"] = CONFIG["password"]

    try:
        headers = {"Content-Type": "application/json", "User-Agent": "MultiArchManager"}
        req = urllib.request.Request(CONFIG["address"], data=json.dumps(data).encode(), headers=headers)
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
    data = json_read(f"{DIR}/objects/files/{obj}", {"local": 0, "remote": 0})
    return data["local"], data["remote"]


def file_backup(obj: str):
    file = b32d(obj)
    if not os.path.isfile(file):
        return

    stat = os.stat(file)
    shutil.copy(file, f"{DIR}/backups/files/{obj}")
    os.chown(f"{DIR}/backups/files/{obj}", stat.st_uid, stat.st_gid)
    os.chmod(f"{DIR}/backups/files/{obj}", stat.st_mode)


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
    handleCreatedDirs(dirs, meta["owner"], meta["group"])


def file_upload(obj: str):
    file = b32d(obj)
    version = file_version(obj)
    stat = os.stat(file)

    with open(file, "rb") as f:
        api("file-set-content", {"id": obj, "content": b64e(f.read()), "version": version})

    api("file-set-meta", {"id": obj, "owner": stat.st_uid, "group": stat.st_gid, "mode": stat.st_mode})
    json_write(f"{DIR}/objects/files/{obj}", {"local": version, "remote": version})


def directory_version(obj: str) -> int:
    dir = b32d(obj)
    if not os.path.isdir(dir):
        return 0

    stat = os.stat(dir)
    version = int(max(stat.st_mtime, stat.st_ctime))
    for root, dirs, files in os.walk(dir):
        for file in files:
            stat = os.stat(os.path.join(root, file))
            version = int(max(version, stat.st_mtime, stat.st_ctime))

        for dir in dirs:
            stat = os.stat(os.path.join(root, dir))
            version = int(max(version, stat.st_mtime, stat.st_ctime))

    return version


def directory_syncVersion(obj: str) -> tuple[int, int]:
    data = json_read(f"{DIR}/objects/directories/{obj}", {"local": 0, "remote": 0})
    return data["local"], data["remote"]


def directory_backup(obj: str):
    directory = b32d(obj)
    if not os.path.isdir(directory):
        return

    stat = os.stat(directory)
    shutil.copytree(directory, f"{DIR}/backups/directories/{obj}")
    os.chown(f"{DIR}/backups/directories/{obj}", stat.st_uid, stat.st_gid)
    os.chmod(f"{DIR}/backups/directories/{obj}", stat.st_mode)

    for root, dirs, files in os.walk(f"{DIR}/backups/directories/{obj}"):
        for file in files:
            stat = os.stat(os.path.join(root.replace(f"{DIR}/backups/directories/{obj}", directory), file))
            os.chown(os.path.join(root, file), stat.st_uid, stat.st_gid)
            os.chmod(os.path.join(root, file), stat.st_mode)

        for dir in dirs:
            stat = os.stat(os.path.join(root.replace(f"{DIR}/backups/directories/{obj}", directory), dir))
            os.chown(os.path.join(root, dir), stat.st_uid, stat.st_gid)
            os.chmod(os.path.join(root, dir), stat.st_mode)


def directory_restore(obj: str):
    directory = b32d(obj)
    if os.path.isdir(directory):
        shutil.rmtree(directory)

    if os.path.isdir(f"{DIR}/backups/directories/{obj}"):
        shutil.move(f"{DIR}/backups/directories/{obj}", directory)

    if os.path.isfile(f"{DIR}/objects/directories/{obj}"):
        os.remove(f"{DIR}/objects/directories/{obj}")


def directory_download(obj: str, version: int):
    directory = b32d(obj)
    dirs = makedirs(os.path.dirname(directory))
    meta = api("directory-get-meta", {"id": obj})

    if os.path.isdir(directory):
        shutil.rmtree(directory)

    os.mkdir(directory)
    os.chown(directory, meta["owner"], meta["group"])
    os.chmod(directory, meta["mode"])

    content = api("directory-get-content", {"id": obj})
    for dir in sorted(content["dirs"], key=lambda dir: dir.count("/")):
        path = os.path.join(directory, b32d(dir))
        meta = content["dirs"][dir]
        os.mkdir(path)
        os.chown(path, meta["owner"], meta["group"])
        os.chmod(path, meta["mode"])

    for file in content["files"]:
        path = os.path.join(directory, b32d(file))
        meta = content["files"][file]

        with open(path, "wb") as f:
            f.write(b64d(meta["content"]))

        os.chown(path, meta["owner"], meta["group"])
        os.chmod(path, meta["mode"])

    json_write(f"{DIR}/objects/directories/{obj}", {"local": directory_version(obj), "remote": version})
    handleCreatedDirs(dirs, meta["owner"], meta["group"])


def directory_upload(obj: str):
    directory = b32d(obj)
    version = directory_version(obj)

    content = {"dirs": {}, "files": {}}
    for root, dirs, files in os.walk(directory):
        for dir in dirs:
            path = os.path.join(root, dir)
            stat = os.stat(path)
            content["dirs"][b32e(os.path.relpath(path, directory))] = {"owner": stat.st_uid, "group": stat.st_gid, "mode": stat.st_mode}

        for file in files:
            path = os.path.join(root, file)
            stat = os.stat(path)
            with open(path, "rb") as f:
                content["files"][b32e(os.path.relpath(path, directory))] = {
                    "owner": stat.st_uid,
                    "group": stat.st_gid,
                    "mode": stat.st_mode,
                    "content": b64e(f.read()),
                }

    stat = os.stat(directory)
    api("directory-set-content", {"id": obj, "content": content, "version": version})
    api("directory-set-meta", {"id": obj, "owner": stat.st_uid, "group": stat.st_gid, "mode": stat.st_mode})
    json_write(f"{DIR}/objects/directories/{obj}", {"local": version, "remote": version})


def package_backup(obj: str):
    if os.system(f"paru -Q {b32d(obj)}") == 0:
        open(f"{DIR}/backups/packages/{obj}", "w").close()


def package_restore(obj: str):
    if os.path.isfile(f"{DIR}/backups/packages/{obj}"):
        os.remove(f"{DIR}/backups/packages/{obj}")
    else:
        os.system(f"paru --noconfirm -Rs {b32d(obj)}")

    if os.path.isfile(f"{DIR}/objects/packages/{obj}"):
        os.remove(f"{DIR}/objects/packages/{obj}")


def package_install(obj: str):
    if os.system(f"paru -Q {b32d(obj)}") != 0:
        if os.system(f"paru -Syia {b32d(obj)}") != 0:
            os.system(f"paru --noconfirm -Sy {b32d(obj)}")
        else:
            os.system("mkdir -p /tmp/mam && chown mam:mam /tmp/mam")
            os.system(f"sudo -u mam HOME=/tmp/mam paru --noconfirm -Sy {b32d(obj)}")

    open(f"{DIR}/objects/packages/{obj}", "w").close()


def partial_version(obj: str) -> int:
    partial = b32d(obj)
    if not os.path.isfile(partial):
        return 0

    stat = os.stat(partial)
    return int(max(stat.st_mtime, stat.st_ctime))


def partial_syncVersion(obj: str) -> tuple[int, int]:
    data = json_read(f"{DIR}/objects/partials/{obj}", {"local": 0, "remote": 0})
    return data["local"], data["remote"]


def partial_backup(obj: str):
    partial = b32d(obj)
    if not os.path.isfile(partial):
        return

    stat = os.stat(partial)
    shutil.copy(partial, f"{DIR}/backups/partials/{obj}")
    os.chown(f"{DIR}/backups/partials/{obj}", stat.st_uid, stat.st_gid)
    os.chmod(f"{DIR}/backups/partials/{obj}", stat.st_mode)


def partial_restore(obj: str):
    partial = b32d(obj)
    if os.path.isfile(partial):
        os.remove(partial)

    if os.path.isfile(f"{DIR}/backups/partials/{obj}"):
        shutil.move(f"{DIR}/backups/partials/{obj}", partial)

    if os.path.isfile(f"{DIR}/objects/partials/{obj}"):
        os.remove(f"{DIR}/objects/partials/{obj}")


def partial_download(obj: str, version: int):
    partial = b32d(obj)
    dirs = makedirs(os.path.dirname(partial))
    meta = api("partial-get-meta", {"id": obj})

    lines = lines_read(partial)
    content = api("partial-get-content", {"id": obj})
    for cnt in content:
        cnt["active"] = cnt["section"] == None

    for i in range(len(lines)):
        for cnt in content:
            if cnt["active"] and re.match(cnt["pattern"], lines[i]):
                lines[i] = cnt["value"]
                cnt["active"] = cnt["section"] == None
            elif not cnt["active"] and re.match(cnt["section"], lines[i]):
                cnt["active"] = True

    lines_write(partial, lines)
    os.chown(partial, meta["owner"], meta["group"])
    os.chmod(partial, meta["mode"])
    json_write(f"{DIR}/objects/partials/{obj}", {"local": partial_version(obj), "remote": version})
    handleCreatedDirs(dirs, meta["owner"], meta["group"])


def partial_upload(obj: str):
    partial = b32d(obj)
    version = partial_version(obj)
    stat = os.stat(partial)

    lines = lines_read(partial)
    content = api("partial-get-content", {"id": obj})
    for cnt in content:
        cnt["active"] = cnt["section"] == None

    for line in lines:
        for cnt in content:
            if cnt["active"] and re.match(cnt["pattern"], line):
                cnt["value"] = line
                cnt["active"] = cnt["section"] == None
            elif not cnt["active"] and re.match(cnt["section"], line):
                cnt["active"] = True

    for cnt in content:
        del cnt["active"]

    api("partial-set-content", {"id": obj, "content": content, "version": version})
    api("partial-set-meta", {"id": obj, "owner": stat.st_uid, "group": stat.st_gid, "mode": stat.st_mode})
    json_write(f"{DIR}/objects/partials/{obj}", {"local": version, "remote": version})


def partial_printDetails(obj: str):
    content = api("partial-get-content", {"id": obj})
    for cnt in content:
        if cnt["section"] == None:
            print(f"    /{cnt['pattern']}/: {cnt['value']}")
        else:
            print(f"    /{cnt['pattern']}/ after /{cnt['section']}/: {cnt['value']}")


def additional_version(obj: str) -> int:
    additional = b32d(obj)
    if not os.path.isfile(additional):
        return 0

    stat = os.stat(additional)
    return int(max(stat.st_mtime, stat.st_ctime))


def additional_syncVersion(obj: str) -> tuple[int, int]:
    data = json_read(f"{DIR}/objects/additionals/{obj}", {"local": 0, "remote": 0})
    return data["local"], data["remote"]


def additional_backup(obj: str):
    additional = b32d(obj)
    if not os.path.isfile(additional):
        return

    stat = os.stat(additional)
    shutil.copy(additional, f"{DIR}/backups/additionals/{obj}")
    os.chown(f"{DIR}/backups/additionals/{obj}", stat.st_uid, stat.st_gid)
    os.chmod(f"{DIR}/backups/additionals/{obj}", stat.st_mode)


def additional_restore(obj: str):
    additional = b32d(obj)
    if os.path.isfile(additional):
        os.remove(additional)

    if os.path.isfile(f"{DIR}/backups/additionals/{obj}"):
        shutil.move(f"{DIR}/backups/additionals/{obj}", additional)

    if os.path.isfile(f"{DIR}/objects/additionals/{obj}"):
        os.remove(f"{DIR}/objects/additionals/{obj}")


def additional_download(obj: str, version: int):
    additional = b32d(obj)
    dirs = makedirs(os.path.dirname(additional))
    meta = api("additional-get-meta", {"id": obj})

    lines = lines_read(additional)
    prefix = api("additional-get-prefix", {"id": obj})
    content = api("additional-get-content", {"id": obj})
    if f"{prefix} BEGIN MAM ADDITIONAL" in lines:
        idx = lines.index(f"{prefix} BEGIN MAM ADDITIONAL") + 1
        while lines[idx] != f"{prefix} END MAM ADDITIONAL":
            lines.pop(idx)

        for line in content:
            lines.insert(idx, line)
            idx += 1
    else:
        lines.append(f"{prefix} BEGIN MAM ADDITIONAL")
        lines += content
        lines.append(f"{prefix} END MAM ADDITIONAL")

    lines_write(additional, lines)
    os.chown(additional, meta["owner"], meta["group"])
    os.chmod(additional, meta["mode"])
    json_write(f"{DIR}/objects/additionals/{obj}", {"local": additional_version(obj), "remote": version})
    handleCreatedDirs(dirs, meta["owner"], meta["group"])


def additional_upload(obj: str):
    additional = b32d(obj)
    version = additional_version(obj)
    stat = os.stat(additional)

    lines = lines_read(additional)
    prefix = api("additional-get-prefix", {"id": obj})
    content = []
    if f"{prefix} BEGIN MAM ADDITIONAL" in lines:
        idx = lines.index(f"{prefix} BEGIN MAM ADDITIONAL") + 1
        while lines[idx] != f"{prefix} END MAM ADDITIONAL":
            content.append(lines[idx])
            idx += 1

    api("additional-set-content", {"id": obj, "content": content, "version": version})
    api("additional-set-meta", {"id": obj, "owner": stat.st_uid, "group": stat.st_gid, "mode": stat.st_mode})
    json_write(f"{DIR}/objects/additionals/{obj}", {"local": version, "remote": version})


def action_install():
    print("Adding mam user...")
    if os.system("id mam") != 0:
        os.system("useradd --system mam")

    with open("/etc/sudoers.d/mam", "w") as f:
        f.write("mam ALL=(root) NOPASSWD: /usr/bin/pacman\n")

    print("Installing dependencies...")
    if os.system("pacman -Q base-devel") != 0:
        os.system("pacman --noconfirm -Sy base-devel")

    if os.system("pacman -Q git") != 0:
        os.system("pacman --noconfirm -Sy git")

    if os.system("paru --version") != 0:
        if os.path.isdir("/tmp/paru"):
            shutil.rmtree("/tmp/paru")

        os.system("git clone https://aur.archlinux.org/paru.git /tmp/paru && chown -R mam:mam /tmp/paru")
        os.system("mkdir -p /tmp/mam && chown mam:mam /tmp/mam")
        os.system("cd /tmp/paru && sudo -u mam HOME=/tmp/mam makepkg --noconfirm -sir")

    print("Creating directories...")
    for type in ["files", "directories", "packages", "partials", "additionals"]:
        os.makedirs(f"{DIR}/objects/{type}", exist_ok=True)
        os.makedirs(f"{DIR}/backups/{type}", exist_ok=True)

    print("Installing mam...")
    shutil.copy(__file__, "/usr/local/bin/mam")
    os.chmod("/usr/local/bin/mam", 0o755)

    print("Installing daemon...")
    with open("/etc/systemd/system/mam.service", "w") as f:
        f.write("[Unit]\n")
        f.write("Description=MAM Daemon\n")
        f.write("After=network-online.target\n")
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
    os.system("systemctl enable mam.service")

    print("Done!")

    if not api("check"):
        print("Please run `mam auth` to authenticate with a MAM server.")


def action_auth():
    while True:
        CONFIG["address"] = input("Server address: ")
        CONFIG["password"] = getpass("Server password: ")

        if api("check"):
            print("Authentication successful!")
            json_write(f"{DIR}/config", CONFIG)
            os.chmod(f"{DIR}/config", 0o600)
            break

        print("Authentication failed!")
        print("Please try again.")
        print()


def action_uninstall():
    print("Stopping daemon...")
    os.system("systemctl stop mam.service")
    os.remove("/etc/systemd/system/mam.service")

    print("Restoring local files...")
    for obj in os.listdir(f"{DIR}/objects/files"):
        file_restore(obj)

    print("Restoring local directories...")
    for obj in os.listdir(f"{DIR}/objects/directories"):
        directory_restore(obj)

    print("Restoring local packages...")
    for obj in os.listdir(f"{DIR}/objects/packages"):
        package_restore(obj)

    print("Restoring local partials...")
    for obj in os.listdir(f"{DIR}/objects/partials"):
        partial_restore(obj)

    print("Restoring local additionals...")
    for obj in os.listdir(f"{DIR}/objects/additionals"):
        additional_restore(obj)

    print("Removing created directories...")
    dirs = json_read(f"{DIR}/objects/created_dirs", [])
    dirs = sorted(dirs, key=lambda dir: dir.count("/"), reverse=True)
    for dir in dirs:
        try:
            os.rmdir(dir)
        except:
            pass

    print("Uninstalling mam binary...")
    os.remove("/usr/local/bin/mam")
    shutil.rmtree(DIR)

    print("Removing mam user...")
    os.system("userdel mam")
    os.remove("/etc/sudoers.d/mam")

    print("Done!")


def action_update():
    requireAuth()

    req = urllib.request.Request(CONFIG["address"])
    try:
        res = urllib.request.urlopen(req).read().decode()
        with open("/tmp/mam.py", "w") as f:
            f.write(res)
    except:
        print("Could not download mam binary.")
        sys.exit(1)

    os.system("python3 /tmp/mam.py install")
    print("Updated!")


def action_status():
    requireAuth()

    if not os.path.isfile(f"{DIR}/state"):
        print("Not synced.")
        return

    with open(f"{DIR}/state", "r") as f:
        print(f.read())


def action_list():
    requireAuth()

    print("Synchronized files:")
    local_objects = sorted(os.listdir(f"{DIR}/objects/files"), key=lambda obj: b32d(obj))
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
        elif local_version == 0:
            print(f"  {file} ({date(remote_version)}, local deleted)")
        else:
            print(f"  {file} ({date(remote_version)})")

    for obj in remote_objects:
        if not obj in local_objects:
            print(f"  {b32d(obj)} ({date(remote_objects[obj])}, remote only)")

    for obj in local_objects:
        if not obj in remote_objects:
            print(f"  {b32d(obj)} ({date(file_version(obj))}, local only)")

    print("\nSynchronized directories:")
    local_objects = sorted(os.listdir(f"{DIR}/objects/directories"), key=lambda obj: b32d(obj))
    remote_objects = api("directory-list")

    for obj in local_objects:
        if not obj in remote_objects:
            continue

        directory = b32d(obj)
        local_version = directory_version(obj)
        remote_version = remote_objects[obj]
        local_sync_version, remote_sync_version = directory_syncVersion(obj)

        if remote_version > remote_sync_version:
            print(f"  {directory} ({date(remote_version)}, remote changed)")
        elif local_version > local_sync_version:
            print(f"  {directory} ({date(local_version)}, local changed)")
        elif local_version == 0:
            print(f"  {directory} ({date(remote_version)}, local deleted)")
        else:
            print(f"  {directory} ({date(remote_version)})")

    for obj in remote_objects:
        if not obj in local_objects:
            print(f"  {b32d(obj)} ({date(remote_objects[obj])}, remote only)")

    for obj in local_objects:
        if not obj in remote_objects:
            print(f"  {b32d(obj)} ({date(directory_version(obj))}, local only)")

    print("\nSynchronized packages:")
    local_objects = sorted(os.listdir(f"{DIR}/objects/packages"), key=lambda obj: b32d(obj))
    remote_objects = api("package-list")

    for obj in local_objects:
        if obj in remote_objects:
            print(f"  {b32d(obj)}")

    for obj in remote_objects:
        if not obj in local_objects:
            print(f"  {b32d(obj)} (remote only)")

    for obj in local_objects:
        if not obj in remote_objects:
            print(f"  {b32d(obj)} (local only)")

    print("\nSynchronized partials:")
    local_objects = sorted(os.listdir(f"{DIR}/objects/partials"), key=lambda obj: b32d(obj))
    remote_objects = api("partial-list")

    for obj in local_objects:
        if not obj in remote_objects:
            continue

        partial = b32d(obj)
        local_version = partial_version(obj)
        remote_version = remote_objects[obj]
        local_sync_version, remote_sync_version = partial_syncVersion(obj)

        if remote_version > remote_sync_version:
            print(f"  {partial} ({date(remote_version)}, remote changed)")
        elif local_version > local_sync_version:
            print(f"  {partial} ({date(local_version)}, local changed)")
        elif local_version == 0:
            print(f"  {partial} ({date(remote_version)}, local deleted)")
        else:
            print(f"  {partial} ({date(remote_version)})")

        partial_printDetails(obj)

    for obj in remote_objects:
        if not obj in local_objects:
            print(f"  {b32d(obj)} ({date(remote_objects[obj])}, remote only)")
            partial_printDetails(obj)

    for obj in local_objects:
        if not obj in remote_objects:
            print(f"  {b32d(obj)} ({date(partial_version(obj))}, local only)")
            partial_printDetails(obj)

    print("\nSynchronized additionals:")
    local_objects = sorted(os.listdir(f"{DIR}/objects/additionals"), key=lambda obj: b32d(obj))
    remote_objects = api("additional-list")

    for obj in local_objects:
        if not obj in remote_objects:
            continue

        additional = b32d(obj)
        local_version = additional_version(obj)
        remote_version = remote_objects[obj]
        local_sync_version, remote_sync_version = additional_syncVersion(obj)

        if remote_version > remote_sync_version:
            print(f"  {additional} ({date(remote_version)}, remote changed)")
        elif local_version > local_sync_version:
            print(f"  {additional} ({date(local_version)}, local changed)")
        elif local_version == 0:
            print(f"  {additional} ({date(remote_version)}, local deleted)")
        else:
            print(f"  {additional} ({date(remote_version)})")

    for obj in remote_objects:
        if not obj in local_objects:
            print(f"  {b32d(obj)} ({date(remote_objects[obj])}, remote only)")

    for obj in local_objects:
        if not obj in remote_objects:
            print(f"  {b32d(obj)} ({date(additional_version(obj))}, local only)")


def action_sync():
    requireAuth()

    with open(f"{DIR}/state", "w") as f:
        f.write("Syncing...")

    local_files = os.listdir(f"{DIR}/objects/files")
    remote_files = api("file-list")
    for file in local_files:
        if not file in remote_files:
            file_restore(file)

    local_directories = os.listdir(f"{DIR}/objects/directories")
    remote_directories = api("directory-list")
    for directory in local_directories:
        if not directory in remote_directories:
            directory_restore(directory)

    local_packages = os.listdir(f"{DIR}/objects/packages")
    remote_packages = api("package-list")
    for package in local_packages:
        if not package in remote_packages:
            package_restore(package)

    local_partials = os.listdir(f"{DIR}/objects/partials")
    remote_partials = api("partial-list")
    for partial in local_partials:
        if not partial in remote_partials:
            partial_restore(partial)

    local_additionals = os.listdir(f"{DIR}/objects/additionals")
    remote_additionals = api("additional-list")
    for additional in local_additionals:
        if not additional in remote_additionals:
            additional_restore(additional)

    for file in remote_files:
        if not file in local_files:
            file_backup(file)
            file_download(file, remote_files[file])
        else:
            local_version = file_version(file)
            remote_version = remote_files[file]
            local_sync_version, remote_sync_version = file_syncVersion(file)

            if remote_version > remote_sync_version or local_version == 0:
                file_download(file, remote_version)
            elif local_version > local_sync_version:
                file_upload(file)

    for directory in remote_directories:
        if not directory in local_directories:
            directory_backup(directory)
            directory_download(directory, remote_directories[directory])
        else:
            local_version = directory_version(directory)
            remote_version = remote_directories[directory]
            local_sync_version, remote_sync_version = directory_syncVersion(directory)

            if remote_version > remote_sync_version or local_version == 0:
                directory_download(directory, remote_version)
            elif local_version > local_sync_version:
                directory_upload(directory)

    for package in remote_packages:
        if not package in local_packages:
            package_backup(package)

        package_install(package)

    for partial in remote_partials:
        if not partial in local_partials:
            partial_backup(partial)
            partial_download(partial, remote_partials[partial])
        else:
            local_version = partial_version(partial)
            remote_version = remote_partials[partial]
            local_sync_version, remote_sync_version = partial_syncVersion(partial)

            if remote_version > remote_sync_version or local_version == 0:
                partial_download(partial, remote_version)
            elif local_version > local_sync_version:
                partial_upload(partial)

    for additional in remote_additionals:
        if not additional in local_additionals:
            additional_backup(additional)
            additional_download(additional, remote_additionals[additional])
        else:
            local_version = additional_version(additional)
            remote_version = remote_additionals[additional]
            local_sync_version, remote_sync_version = additional_syncVersion(additional)

            if remote_version > remote_sync_version or local_version == 0:
                additional_download(additional, remote_version)
            elif local_version > local_sync_version:
                additional_upload(additional)

    with open(f"{DIR}/state", "w") as f:
        f.write(f"Last sync: {date()}")


def action_addFile(path: str):
    file = os.path.abspath(path)
    if not os.path.isfile(file):
        print("File does not exist.")
        sys.exit(1)

    obj = b32e(file)
    if api("file-exists", {"id": obj}):
        print("File is already synced.")
        sys.exit(1)

    if api("partial-exists", {"id": obj}):
        print("File is already synced as a partial.")
        sys.exit(1)

    if api("additional-exists", {"id": obj}):
        print("File is already synced as an additional.")
        sys.exit(1)

    dirs = api("directory-list")
    for dir in dirs:
        if file.startswith(b32d(dir)):
            print(f"File is part of synced directory {b32d(dir)}.")
            sys.exit(1)

    file_backup(obj)
    api("file-create", {"id": obj})
    file_upload(obj)
    print("File added!")


def action_removeFile(path: str):
    file = os.path.abspath(path)
    obj = b32e(file)
    if not api("file-exists", {"id": obj}):
        print("File is not synced.")
        sys.exit(1)

    api("file-delete", {"id": obj})
    file_restore(obj)
    print("File removed!")


def action_addDirectory(path: str):
    directory = os.path.abspath(path)
    if not os.path.isdir(directory):
        print("Directory does not exist.")
        sys.exit(1)

    obj = b32e(directory)
    if api("directory-exists", {"id": obj}):
        print("Directory is already synced.")
        sys.exit(1)

    dirs = api("directory-list")
    for dir in dirs:
        if directory.startswith(b32d(dir)):
            print(f"Directory is part of synced directory {b32d(dir)}.")
            sys.exit(1)

    files = api("file-list")
    for file in files:
        if b32d(file).startswith(directory):
            print(f"Directory contains synced file {b32d(file)}.")
            sys.exit(1)

    dirs = api("directory-list")
    for dir in dirs:
        if b32d(dir).startswith(directory):
            print(f"Directory contains synced directory {b32d(dir)}.")
            sys.exit(1)

    partials = api("partial-list")
    for partial in partials:
        if b32d(partial).startswith(directory):
            print(f"Directory contains synced partial {b32d(partial)}.")
            sys.exit(1)

    additionals = api("additional-list")
    for additional in additionals:
        if b32d(additional).startswith(directory):
            print(f"Directory contains synced additional {b32d(additional)}.")
            sys.exit(1)

    directory_backup(obj)
    api("directory-create", {"id": obj})
    directory_upload(obj)
    print("Directory added!")


def action_removeDirectory(path: str):
    directory = os.path.abspath(path)
    obj = b32e(directory)
    if not api("directory-exists", {"id": obj}):
        print("Directory is not synced.")
        sys.exit(1)

    api("directory-delete", {"id": obj})
    directory_restore(obj)
    print("Directory removed!")


def action_addPackage(name: str):
    if os.system(f"paru -Syi {name}") != 0:
        print("Package does not exist.")
        sys.exit(1)

    obj = b32e(name)
    if api("package-exists", {"id": obj}):
        print("Package is already synced.")
        sys.exit(1)

    package_backup(obj)
    api("package-add", {"id": obj})
    package_install(obj)
    print("Package added!")


def action_removePackage(name: str):
    obj = b32e(name)
    if not api("package-exists", {"id": obj}):
        print("Package is not synced.")
        sys.exit(1)

    api("package-remove", {"id": obj})
    package_restore(obj)
    print("Package removed!")


def action_addPartial(path: str, pattern: str, section: str | None):
    partial = os.path.abspath(path)
    if not os.path.isfile(partial):
        print("Partial does not exist.")
        sys.exit(1)

    obj = b32e(partial)
    if api("file-exists", {"id": obj}):
        print("Partial is already synced as a file.")
        sys.exit(1)

    if api("additional-exists", {"id": obj}):
        print("Partial is already synced as an additional.")
        sys.exit(1)

    dirs = api("directory-list")
    for dir in dirs:
        if partial.startswith(b32d(dir)):
            print(f"Partial is part of synced directory {b32d(dir)}.")
            sys.exit(1)

    if not api("partial-exists", {"id": obj}):
        partial_backup(obj)
        api("partial-create", {"id": obj})

    content = api("partial-get-content", {"id": obj})
    content.append({"pattern": pattern, "value": "", "section": section})
    api("partial-set-content", {"id": obj, "content": content, "version": int(datetime.now().timestamp())})
    partial_upload(obj)
    print("Partial added!")


def action_removePartial(path: str, pattern: str, section: str | None):
    partial = os.path.abspath(path)
    obj = b32e(partial)
    if not api("partial-exists", {"id": obj}):
        print("Partial is not synced.")
        sys.exit(1)

    content = api("partial-get-content", {"id": obj})
    content = [cnt for cnt in content if cnt["pattern"] != pattern or cnt["section"] != section]
    version = int(datetime.now().timestamp())
    api("partial-set-content", {"id": obj, "content": content, "version": version})
    partial_download(obj, version)
    print("Partial removed!")


def action_purgePartial(path: str):
    partial = os.path.abspath(path)
    obj = b32e(partial)
    if not api("partial-exists", {"id": obj}):
        print("Partial is not synced.")
        sys.exit(1)

    api("partial-delete", {"id": obj})
    partial_restore(obj)
    print("Partial removed!")


def action_addAdditional(path: str, prefix: str):
    additional = os.path.abspath(path)
    if not os.path.isfile(additional):
        print("Additional does not exist.")
        sys.exit(1)

    obj = b32e(additional)
    if api("additional-exists", {"id": obj}):
        print("Additional is already synced.")
        sys.exit(1)

    if api("file-exists", {"id": obj}):
        print("Additional is already synced as a file.")
        sys.exit(1)

    if api("partial-exists", {"id": obj}):
        print("Additional is already synced as a partial.")
        sys.exit(1)

    dirs = api("directory-list")
    for dir in dirs:
        if additional.startswith(b32d(dir)):
            print(f"Additional is part of synced directory {b32d(dir)}.")
            sys.exit(1)

    additional_backup(obj)

    lines = lines_read(additional)
    if not f"{prefix} BEGIN MAM ADDITIONAL" in lines:
        lines.append(f"{prefix} BEGIN MAM ADDITIONAL")
        lines.append(f"{prefix} END MAM ADDITIONAL")
        lines_write(additional, lines)

    api("additional-create", {"id": obj, "prefix": prefix})
    additional_upload(obj)
    print("Additional added!")


def action_removeAdditional(path: str):
    additional = os.path.abspath(path)
    obj = b32e(additional)
    if not api("additional-exists", {"id": obj}):
        print("Additional is not synced.")
        sys.exit(1)

    api("additional-delete", {"id": obj})
    additional_restore(obj)
    print("Additional removed!")


if __name__ == "__main__":
    if os.geteuid() != 0:
        print("This script must be run as root.")
        sys.exit(1)

    os.makedirs(DIR, exist_ok=True)
    CONFIG = json_read(f"{DIR}/config", CONFIG)

    match arg(1):
        case "install":
            requireArgs(2, "Usage: mam install")
            action_install()

        case "auth":
            requireArgs(2, "Usage: mam auth")
            action_auth()

        case "uninstall":
            requireArgs(2, "Usage: mam uninstall")
            action_uninstall()

        case "update":
            requireArgs(2, "Usage: mam update")
            action_update()

        case "status":
            requireArgs(2, "Usage: mam status")
            action_status()

        case "list":
            requireArgs(2, "Usage: mam list")
            action_list()

        case "sync":
            requireArgs(2, "Usage: mam sync")
            action_sync()

        case "add":
            match arg(2):
                case "file":
                    requireArgs(4, "Usage: mam add file <path>")
                    action_addFile(str(arg(3)))

                case "directory":
                    requireArgs(4, "Usage: mam add directory <path>")
                    action_addDirectory(str(arg(3)))

                case "package":
                    requireArgs(4, "Usage: mam add package <name>")
                    action_addPackage(str(arg(3)))

                case "partial":
                    requireArgs([5, 6], "Usage: mam add partial <path> <pattern> [<section>]")
                    action_addPartial(str(arg(3)), str(arg(4)), arg(5))

                case "additional":
                    requireArgs(5, "Usage: mam add additional <path> <prefix>")
                    action_addAdditional(str(arg(3)), str(arg(4)))

                case _:
                    print("Usage: mam add <object>")
                    print("Add an object to sync")
                    print()
                    print("mam add file <path>                           Add a file to sync")
                    print("mam add directory <path>                      Add a directory to sync")
                    print("mam add package <name>                        Add a package to sync")
                    print("mam add partial <path> <pattern> [<section>]  Add a partial to sync")
                    print("mam add additional <path> <prefix>            Add an additional to sync")
                    sys.exit(1)

        case "remove":
            match arg(2):
                case "file":
                    requireArgs(4, "Usage: mam remove file <path>")
                    action_removeFile(str(arg(3)))

                case "directory":
                    requireArgs(4, "Usage: mam remove directory <path>")
                    action_removeDirectory(str(arg(3)))

                case "package":
                    requireArgs(4, "Usage: mam remove package <name>")
                    action_removePackage(str(arg(3)))

                case "partial":
                    requireArgs([4, 5, 6], "Usage: mam remove partial <path> [<pattern> [<section>]]")
                    if arg(4) == None:
                        action_purgePartial(str(arg(3)))
                    else:
                        action_removePartial(str(arg(3)), str(arg(4)), arg(5))

                case "additional":
                    requireArgs(4, "Usage: mam remove additional <path>")
                    action_removeAdditional(str(arg(3)))

                case _:
                    print("Usage: mam remove <object>")
                    print("Remove an object from sync")
                    print()
                    print("mam remove file <path>                             Remove a file from sync")
                    print("mam remove directory <path>                        Remove a directory from sync")
                    print("mam remove package <name>                          Remove a package from sync")
                    print("mam remove partial <path> [<pattern> [<section>]]  Remove a partial from sync")
                    print("mam remove additional <path> <prefix>              Remove an additional from sync")
                    sys.exit(1)

        case _:
            print("Usage: mam <command>")
            print("Mange multiple Arch Linux machines")
            print()
            print("mam install    Install mam on this machine")
            print("mam auth       Authenticate this machine with a mam server")
            print("mam uninstall  Uninstall mam from this machine")
            print("mam update     Update mam binary to latest version")
            print("mam status     Show last sync status")
            print("mam list       List all synced objects")
            print("mam sync       Sync all objects")
            print("mam add        Add an object to sync")
            print("mam remove     Remove an object from sync")
            sys.exit(1)
