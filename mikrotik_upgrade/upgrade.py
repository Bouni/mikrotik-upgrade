import sys
from pathlib import Path

import paramiko
import yaml


class Mikrotik:
    def __init__(
        self, hostname: str, username="admin", port=22, key_file="~/.ssh/id_rsa"
    ):
        self.hostname = hostname
        self.username = username
        self.port = port
        self.key_file = key_file
        self.client = None
        self._connect()

    def _connect(self):
        self.client = paramiko.SSHClient()
        self.client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

        key = paramiko.RSAKey.from_private_key_file(self.key_file)

        self.client.connect(
            hostname=self.hostname,
            username=self.username,
            pkey=key,
            port=self.port,
            timeout=10,
        )
        return self

    def _disconnect(self):
        if self.client:
            self.client.close()
            self.client = None

    def __exit__(self, exc_type, exc_value, traceback):
        self._disconnect()

    def _exec(self, command: str) -> str:
        if not self.client:
            raise RuntimeError("SSH client is not connected")
        stdin, stdout, stderr = self.client.exec_command(command)
        return stdout.read().decode()

    def _parse_mikrotik_data(self, data: str):
        lines = [line.strip() for line in data.splitlines() if ": " in line]
        d = dict(line.split(": ", 1) for line in lines)
        return d

    def get_routerboard_info(self):
        raw = self._exec("/system/routerboard/print")
        data = self._parse_mikrotik_data(raw)
        return data

    def get_resource_info(self):
        raw = self._exec("/system/resource/print")
        data = self._parse_mikrotik_data(raw)
        return data

    def check_for_updates(self):
        raw = self._exec(
            "/system/package/update/check-for-updates proplist=latest-version,installed-version,status,channel"
        )
        data = self._parse_mikrotik_data(raw)
        return data

    def download_updates(self):
        raw = self._exec("/system/package/update/download proplist=status")
        data = self._parse_mikrotik_data(raw)
        return data

    def upgrade_routerboard(self):
        self._exec("/system/routerboard/upgrade")

    def reboot(self):
        self._exec("/system/reboot")
        self._disconnect()


class Updater:
    def __init__(self):
        hostlist = None
        for path in [
            Path("/etc/mikrotik-upgrade") / "config.yaml",
            Path.home() / ".config" / "mikrotik-upgrade" / "config.yaml"
                ]:
            if path.exists():
                hostlist = path
        if not hostlist:
            print("No valid config file found")
            sys.exit(1)
        with open(hostlist) as f:
            self.hosts = yaml.safe_load(f)

    def update(self):
        for host in self.hosts:
            print("=" * 80)
            print("==" + f"{host['name']: ^76}" + "==")
            print("=" * 80)
            mt = Mikrotik(
                host.get("hostname"),
                username=host.get("username", "admin"),
                port=host.get("port", 22),
                key_file=host.get("keyfile"),
            )
            info = mt.get_routerboard_info()
            info.update(mt.get_resource_info())
            status = mt.check_for_updates()
            print(status["status"])
            if status["status"] != "System is already up to date":
                print("Download updates")
                mt.download_updates()
                print("Upgrade routerboard")
                mt.upgrade_routerboard()
                print("Reboot System")
                mt.reboot()


def main():
    u = Updater()
    u.update()


if __name__ == "__main__":
    main()
