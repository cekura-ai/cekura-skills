"""Offline drill stand-in for the Modal sandbox API, backed by local Docker containers.

Selected only by CEKURA_SANDBOX_BACKEND=local-docker, which preflight rejects for scored
runs. It implements just the calls the generator path makes, so the real generator
script, Claude Agent SDK and Pi CLIs run against fake providers with no network.
"""
import io
import json
import os
import socket
import tarfile
import threading

import docker
import modal

_client = docker.from_env()
_api = docker.APIClient()


class Image:
    def __init__(self, identifier):
        self.object_id = identifier

    @classmethod
    def from_id(cls, identifier):
        return cls(identifier)


class Secret:
    """Secrets are a local JSON file of placeholder-only environment values."""
    def __init__(self, env):
        self.env = env

    @classmethod
    def from_name(cls, name):
        values = json.loads(open(os.environ["CEKURA_LOCAL_SECRETS"]).read())
        return cls(values[name])


class App:
    @staticmethod
    def lookup(name, create_if_missing=False):
        return name


class _Stdin:
    def __init__(self, sock):
        self.sock = sock

    def write(self, data):
        self.sock.sendall(data.encode() if isinstance(data, str) else data)

    def drain(self):
        pass


class _Process:
    def __init__(self, container, args, env, workdir, text):
        self.exec_id = _api.exec_create(container, list(args), stdin=True, environment=env or {}, workdir=workdir)["Id"]
        self.sock = _api.exec_start(self.exec_id, socket=True)._sock
        out_r, self._out = os.pipe()
        err_r, self._err = os.pipe()
        mode = "r" if text else "rb"
        self.stdout, self.stderr = os.fdopen(out_r, mode), os.fdopen(err_r, mode)
        self.stdin = _Stdin(self.sock)
        self.thread = threading.Thread(target=self._demux, daemon=True)
        self.thread.start()
        self.returncode = None

    def _demux(self):
        buffer = b""
        try:
            while True:
                chunk = self.sock.recv(65536)
                if not chunk:
                    break
                buffer += chunk
                while len(buffer) >= 8:
                    size = int.from_bytes(buffer[4:8], "big")
                    if len(buffer) < 8 + size:
                        break
                    os.write(self._err if buffer[0] == 2 else self._out, buffer[8:8 + size])
                    buffer = buffer[8 + size:]
        except OSError:
            pass
        finally:
            os.close(self._out)
            os.close(self._err)

    def wait(self):
        self.thread.join()
        while True:
            state = _api.exec_inspect(self.exec_id)
            if not state["Running"]:
                self.returncode = state["ExitCode"]
                return self.returncode
            threading.Event().wait(.1)


class _Filesystem:
    def __init__(self, container):
        self.container = container

    def write_bytes(self, data, path):
        stream = io.BytesIO()
        with tarfile.open(fileobj=stream, mode="w") as archive:
            info = tarfile.TarInfo(os.path.basename(path))
            info.size, info.mode = len(data), 0o644
            archive.addfile(info, io.BytesIO(data))
        self.container.exec_run(["mkdir", "-p", os.path.dirname(path)])
        self.container.put_archive(os.path.dirname(path), stream.getvalue())

    def write_text(self, text, path):
        self.write_bytes(text.encode(), path)


class Sandbox:
    def __init__(self, container):
        self.container, self.object_id = container, container.id
        self.filesystem = _Filesystem(container)

    @classmethod
    def create(cls, app=None, name=None, image=None, secrets=(), workdir=None, idle_timeout=None, timeout=300,
               block_network=False, cpu=None, memory=None, **unused):
        env = {}
        for secret in secrets:
            env.update(secret.env)
        container = _client.containers.run(
            image.object_id, ["sleep", str(int(timeout))], detach=True, auto_remove=False, working_dir=workdir,
            network_mode="none" if block_network else "bridge", environment=env, labels={
                "cekura_sandbox_name": name or "", "cekura_scope": os.environ.get("CEKURA_SCOPE", "")})
        return cls(container)

    @classmethod
    def from_name(cls, app, name):
        found = _client.containers.list(filters={"label": "cekura_sandbox_name=" + name})
        if not found:
            raise modal.exception.NotFoundError(name)
        return cls(found[0])

    def set_tags(self, tags):
        self.tags = dict(tags)

    def exec(self, *args, env=None, workdir=None, text=True, bufsize=-1, **unused):
        return _Process(self.object_id, args, env, workdir, text)

    def terminate(self):
        try:
            self.container.remove(force=True)
        except docker.errors.NotFound:
            pass

    def detach(self):
        pass
