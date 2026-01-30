import logging
import sys
from pathlib import Path

import paramiko
import yaml


class MikrotikConnectionError(Exception):
    pass


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
        try:
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
            self.connected = True
            return self

        except paramiko.AuthenticationException as e:
            raise MikrotikConnectionError(
                f"Authentication failed for {self.username}@{self.hostname}"
            ) from e
        except paramiko.SSHException as e:
            raise MikrotikConnectionError(
                f"SSH error connecting to {self.hostname}:{self.port} - {str(e)}"
            ) from e
        except FileNotFoundError as e:
            raise MikrotikConnectionError(
                f"SSH key file not found: {self.key_file}"
            ) from e
        except (TimeoutError, OSError) as e:
            raise MikrotikConnectionError(
                f"Connection timeout/network error to {self.hostname}:{self.port}"
            ) from e
        except Exception as e:
            raise MikrotikConnectionError(
                f"Unexpected error connecting to {self.hostname}: {str(e)}"
            ) from e

    def _disconnect(self):
        if self.client:
            try:
                self.client.close()
            except Exception as e:
                logging.warning(f"Error during disconnect: {e}")
            finally:
                self.client = None
                self.connected = False

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self._disconnect()

    def _exec(self, command: str) -> str:
        if not self.client or not self.connected:
            raise RuntimeError("SSH client is not connected")
        try:
            stdin, stdout, stderr = self.client.exec_command(command)
            error_output = stderr.read().decode()

            if error_output:
                logging.warning(f"Command stderr: {error_output}")

            return stdout.read().decode()
        except paramiko.SSHException as e:
            raise RuntimeError(f"SSH error executing command: {str(e)}") from e
        except Exception as e:
            raise RuntimeError(f"Error executing command: {str(e)}") from e

    def _parse_mikrotik_data(self, data: str):
        lines = [line.strip() for line in data.splitlines() if ": " in line]
        d = dict(line.split(": ", 1) for line in lines)
        return d

    def get_routerboard_info(self):
        raw = self._exec("/system/routerboard/logging.info")
        data = self._parse_mikrotik_data(raw)
        return data

    def get_resource_info(self):
        raw = self._exec("/system/resource/logging.info")
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
            Path.home() / ".config" / "mikrotik-upgrade" / "config.yaml",
        ]:
            if path.exists():
                hostlist = path
        if not hostlist:
            logging.error("No valid config file found")
            sys.exit(1)
        with open(hostlist) as f:
            self.hosts = yaml.safe_load(f)

    def update(self):
        for host in self.hosts:
            logging.info("=" * 80)
            logging.info("==" + f"{host['name']: ^76}" + "==")
            logging.info("=" * 80)
            try:
                with Mikrotik(
                    host.get("hostname"),
                    username=host.get("username", "admin"),
                    port=host.get("port", 22),
                    key_file=host.get("keyfile"),
                ) as mt:
                    info = mt.get_routerboard_info()
                    info.update(mt.get_resource_info())
                    status = mt.check_for_updates()
                    logging.info(status["status"])
                    if status["status"] != "System is already up to date":
                        logging.info("Download updates")
                        mt.download_updates()
                        logging.info("Upgrade routerboard")
                        mt.upgrade_routerboard()
                        logging.info("Reboot System")
                        mt.reboot()
            except MikrotikConnectionError as e:
                print(f"Failed to connect: {e}")
            except RuntimeError as e:
                print(f"Command execution failed: {e}")


def main():
    u = Updater()
    u.update()


if __name__ == "__main__":
    main()
