#!/usr/bin/env python3

import base64
import json
import os
import shutil
import sys
import urllib.request
from datetime import datetime
from getpass import getpass

DIR = "/var/lib/mam"
CONFIG = {"address": "localhost", "password": ""}


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


def arg(n: int) -> str | None:
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
    dirs = makedirs(directory)
    meta = api("directory-get-meta", {"id": obj})

    shutil.rmtree(directory)
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

    created_dirs = json_read(f"{DIR}/objects/created_dirs", [])
    for dir in dirs:
        os.chown(dir, meta["owner"], meta["group"])
        if not dir in created_dirs:
            created_dirs.append(dir)

    json_write(f"{DIR}/objects/created_dirs", created_dirs)


def directory_upload(obj: str):
    directory = b32d(obj)
    version = directory_version(obj)

    content = {"dirs": {}, "files": {}}
    for root, dirs, files in os.walk(directory):
        for dir in dirs:
            path = os.path.join(root, dir)
            stat = os.stat(path)
            content["dirs"][b32e(os.path.relpath(path, directory))] = {
                "owner": stat.st_uid,
                "group": stat.st_gid,
                "mode": stat.st_mode,
            }

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


def action_install():
    print("Adding mam user...")
    if os.system("id mam") != 0:
        os.system("useradd --system mam")

    with open("/etc/sudoers.d/mam", "w") as f:
        f.write("mam ALL=(root) NOPASSWD: /usr/bin/pacman\n")

    print("Installing dependencies...")
    os.system("pacman --noconfirm -Syu git fakeroot binutils")
    if os.system("paru --version") != 0:
        if os.path.isdir("/tmp/paru"):
            shutil.rmtree("/tmp/paru")

        os.system("git clone https://aur.archlinux.org/paru-bin.git /tmp/paru && chown -R mam:mam /tmp/paru")
        os.system("mkdir -p /tmp/mam && chown mam:mam /tmp/mam")
        os.system("cd /tmp/paru && sudo -u mam HOME=/tmp/mam makepkg")
        os.system("pacman --noconfirm -U /tmp/paru/paru-*.pkg.tar.zst")

    print("Creating directories...")
    for type in ["directories", "files", "packages"]:
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

        if not api("check"):
            print("Authentication failed!")
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

    print("Restoring local directories...")
    for obj in os.listdir(f"{DIR}/objects/directories"):
        directory_restore(obj)

    print("Restoring local packages...")
    for obj in os.listdir(f"{DIR}/objects/packages"):
        package_restore(obj)

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

    print("Removing mam user...")
    os.system("userdel mam")
    os.remove("/etc/sudoers.d/mam")

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

    print("\nSynchronized directories:")
    local_objects = os.listdir(f"{DIR}/objects/directories")
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
        elif local_version < local_sync_version:
            print(f"  {directory} ({date(local_version)}, local deleted)")
        else:
            print(f"  {directory} ({date(remote_version)})")

    for obj in remote_objects:
        if not obj in local_objects:
            directory = b32d(obj)
            print(f"  {directory} ({date(remote_objects[obj])}, remote only)")

    for obj in local_objects:
        if not obj in remote_objects:
            directory = b32d(obj)
            print(f"  {directory} ({date(directory_version(obj))}, local only)")

    print("\nSynchronized packages:")
    local_objects = os.listdir(f"{DIR}/objects/packages")
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

    for file in remote_files:
        if not file in local_files:
            file_backup(file)
            file_download(file, remote_files[file])
        else:
            local_version = file_version(file)
            remote_version = remote_files[file]
            local_sync_version, remote_sync_version = file_syncVersion(file)

            if remote_version > remote_sync_version or local_version < local_sync_version:
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

            if remote_version > remote_sync_version or local_version < local_sync_version:
                directory_download(directory, remote_version)
            elif local_version > local_sync_version:
                directory_upload(directory)

    for package in remote_packages:
        if not package in local_packages:
            package_backup(package)

        package_install(package)

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

    directories = api("directory-list")
    parents = [b32d(dir) for dir in directories if file.startswith(b32d(dir))]
    if len(parents) > 0:
        print(f"File is part of synced directory {parents[0]}")
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


def action_addDirectory(path: str):
    directory = os.path.abspath(path)
    if not os.path.isdir(directory):
        print("Directory does not exist")
        sys.exit(1)

    obj = b32e(directory)
    if api("directory-exists", {"id": obj}):
        print("Directory is already synced")
        sys.exit(1)

    directories = api("directory-list")
    parents = [b32d(dir) for dir in directories if directory.startswith(b32d(dir))]
    if len(parents) > 0:
        print(f"Directory is part of synced directory {parents[0]}")
        sys.exit(1)

    files = api("file-list")
    children = [b32d(file) for file in files if b32d(file).startswith(directory)]
    if len(children) > 0:
        print(f"Directory contains synced file {children[0]}")
        sys.exit(1)

    directory_backup(obj)
    api("directory-create", {"id": obj})
    directory_upload(obj)

    print("Directory added")


def action_removeDirectory(path: str):
    directory = os.path.abspath(path)
    obj = b32e(directory)
    if not api("directory-exists", {"id": obj}):
        print("Directory is not synced")
        sys.exit(1)

    api("directory-delete", {"id": obj})
    directory_restore(obj)

    print("Directory removed")


def action_addPackage(name: str):
    obj = b32e(name)
    if api("package-exists", {"id": obj}):
        print("Package is already synced")
        sys.exit(1)

    package_backup(obj)
    api("package-add", {"id": obj})
    package_install(obj)

    print("Package added")


def action_removePackage(name: str):
    obj = b32e(name)
    if not api("package-exists", {"id": obj}):
        print("Package is not synced")
        sys.exit(1)

    api("package-remove", {"id": obj})
    package_restore(obj)

    print("Package removed")


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

                case "directory":
                    if len(sys.argv) != 4:
                        print("Usage: mam add directory <path>")
                        sys.exit(1)

                    action_addDirectory(arg(3))

                case "package":
                    if len(sys.argv) != 4:
                        print("Usage: mam add package <name>")
                        sys.exit(1)

                    action_addPackage(arg(3))

                case _:
                    print("Usage: mam add <object>")
                    print("Add an object to sync")
                    print()
                    print("mam add file <path>       Add a file to sync")
                    print("mam add directory <path>  Add a directory to sync")
                    print("mam add package <name>    Add a package to sync")
                    sys.exit(1)

        case "remove":
            match arg(2):
                case "file":
                    if len(sys.argv) != 4:
                        print("Usage: mam remove file <path>")
                        sys.exit(1)

                    action_removeFile(arg(3))

                case "directory":
                    if len(sys.argv) != 4:
                        print("Usage: mam remove directory <path>")
                        sys.exit(1)

                    action_removeDirectory(arg(3))

                case "package":
                    if len(sys.argv) != 4:
                        print("Usage: mam remove package <name>")
                        sys.exit(1)

                    action_removePackage(arg(3))

                case _:
                    print("Usage: mam remove <object>")
                    print("Remove an object from sync")
                    print()
                    print("mam remove file <path>       Remove a file from sync")
                    print("mam remove directory <path>  Remove a directory from sync")
                    print("mam remove package <name>    Remove a package from sync")
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
