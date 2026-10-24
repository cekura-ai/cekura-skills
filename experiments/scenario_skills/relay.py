"""Root-only Modal exec stdio transport; no external socket is opened here."""
import base64
import json
import socket
import sys
import threading
from contextlib import suppress

MAX_TRANSFER = 64 * 1024 * 1024


def close_connection(sockets, identifier):
    """Both peers may report EOF; closing an already closed peer is harmless."""
    connection = sockets.pop(identifier, None)
    if connection is not None:
        with suppress(OSError):
            connection.shutdown(socket.SHUT_RDWR)
        connection.close()


def main():
    sockets, lock, total = {}, threading.Lock(), [0]

    def emit(value):
        line = json.dumps(value) + "\n"
        with lock:
            total[0] += len(line.encode())
            if total[0] > MAX_TRANSFER:
                raise RuntimeError("Relay transfer allowance exhausted")
            sys.stdout.write(line)
            sys.stdout.flush()

    # One loopback listener per service; "model" is the provider gateway and "mcp", when
    # requested, the real-backend bridge. Connections carry their service to the host.
    services = sys.argv[sys.argv.index("--services") + 1].split(",") if "--services" in sys.argv else ["model"]
    listeners = {}
    for service in services:
        listeners[service] = socket.socket()
        listeners[service].bind(("127.0.0.1", 0))
        listeners[service].listen(8)
    ports = {k: v.getsockname()[1] for k, v in listeners.items()}
    emit({"type": "ready", "port": ports["model"], "ports": ports})

    def pump(identifier, connection):
        try:
            while True:
                data = connection.recv(32768)
                if not data:
                    break
                emit({"type": "data", "id": identifier, "data": base64.b64encode(data).decode()})
        finally:
            close_connection(sockets, identifier)
            emit({"type": "close", "id": identifier})

    counter, counter_lock = [0], threading.Lock()

    def accept(service, listener):
        while True:
            connection, _ = listener.accept()
            with counter_lock:
                counter[0] += 1
                identifier = counter[0]
            sockets[identifier] = connection
            emit({"type": "open", "id": identifier, "service": service})
            threading.Thread(target=pump, args=(identifier, connection), daemon=True).start()

    for service, listener in listeners.items():
        threading.Thread(target=accept, args=(service, listener), daemon=True).start()
    try:
        for line in sys.stdin:
            total[0] += len(line.encode())
            if total[0] > MAX_TRANSFER or len(line) > 65536:
                raise RuntimeError("Relay transfer allowance exhausted")
            event = json.loads(line)
            connection = sockets.get(event["id"])
            if connection:
                if event["type"] == "data":
                    connection.sendall(base64.b64decode(event["data"], validate=True))
                elif event["type"] == "close":
                    close_connection(sockets, event["id"])
    finally:
        for listener in listeners.values():
            listener.close()
        for identifier in list(sockets):
            close_connection(sockets, identifier)


if __name__ == "__main__":
    main()
