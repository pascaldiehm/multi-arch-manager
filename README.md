# Multi Arch Manager

Keep files synchronized between multiple Arch Linux machines.

## Usage

1. Host [mam-server.php](mam-server.php) on a server accessible to all synced clients. The easiest way to do this is using the prebuilt docker image: `docker run -d -p 1234:80 -e MAM_PASSWORD=INSERT_PASSWORD_HERE -v PATH_TO_DATA_FOLDER:/data ghcr.io/pascaldiehm/multi-arch-manager` (replace `INSERT_PASSWORD_HERE` with your password, `1234` with your preferred port and `PATH_TO_DATA_FOLDER` with a persistent data folder or volume name).
2. Run `curl SERVER_URL > /tmp/mam.py && sudo python3 /tmp/mam.py install` (replace `SERVER_URL` with the URL of your mam server) to install mam on a machine.
3. Run `sudo mam auth` and enter your server URL (including method) and password.
4. See `sudo mam help` for a list of commands.

## Supported Objects

- Files: Synchronizes an entire file including ownership and permissions between systems.
- Directories: Synchronizes an entire directory including all subdirectories, files and their owner and permission data between systems.
- Packages: Makes sure a package is installed on all synchronized systems.
- Partials: Synchronizes lines matching a pattern between systems. Always make sure to match exactly one line per pattern, otherwise the last matching line will override all matching lines. Try to capture the entire line in your pattern.
- Additionals: Synchronizes a defined block in a file that will also be appended to new files. Requires the prefix to start a line comment in the given file.

## Technical details

### Versioning

An objects version is the larger of the modification and change times reported by `stat`. Object versions are used to detect and synchronize changes.

### Strategy

When a version difference with a remote object is detected or the local object has been deleted, the remote object is pulled. Otherwise, when a version difference with a local object is detected, the local object is pushed.

Remote changes always take precedence.

### Background synchronization

Installing mam also creates a systemd service `/etc/systemd/system/mam.service` that is automatically enabled and started. This service triggers a sync action every 10 minutes. You can use `sudo mam status` to get the result of the last synchronization.

### Partial line matching

If no section is defined, a partial will apply to all lines matching the pattern. If a section is defined, the partial will apply to the first line matching the pattern _after_ any line matching the section.
