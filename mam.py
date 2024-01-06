#!/usr/bin/env python3

import json
import os
import shutil
import subprocess
import sys
import urllib.request
from getpass import getpass

DIR = "/usr/local/share/mam"
CONFIG = {"address": "localhost", "password": "", "sudoer": "nobody"}


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


def action_install():
    print("Installing mam...")
    shutil.copy(__file__, "/usr/local/bin/mam")
    os.chmod("/usr/local/bin/mam", 0o755)

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
    print("Uninstalling mam...")
    os.remove("/usr/local/bin/mam")
    shutil.rmtree(DIR)

    print("Done!")


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


        case _:
            print("Usage: mam <command>")
            print("Mange multiple Arch Linux machines")
            print()
            print("mam install    Install mam on this machine")
            print("mam auth       Authenticate this machine with a mam server")
            print("mam uninstall  Uninstall mam from this machine")
            sys.exit(1)
