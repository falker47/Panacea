"""Check urllib's process trust against one loopback TLS origin on a hosted runner."""

import argparse
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, HTTPServer
import ipaddress
import os
import select
import socket
import ssl
import subprocess
import sys
from threading import Thread

from scripts.update_compat.hosted import hosted_guard, report


class Origin(BaseHTTPRequestHandler):
    def do_GET(self):
        self.server.requests.append(self.path)
        if self.path != "/ping":
            self.send_error(404)
            return
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"loopback-ok")


class Tunnel(BaseHTTPRequestHandler):
    def do_CONNECT(self):
        origin = self.server.origin
        self.server.requests.append(self.path)
        if self.path != f"{origin[0]}:{origin[1]}":
            self.send_error(404)
            return
        # Both sockets belong to this test. TLS terminates at Origin.
        with socket.create_connection(origin, timeout=5) as upstream:
            self.send_response(200)
            self.end_headers()
            sockets = (self.connection, upstream)
            while readable := select.select(sockets, [], [], 10)[0]:
                for source in readable:
                    chunk = source.recv(16384)
                    if not chunk:
                        return
                    destination = upstream if source is self.connection else self.connection
                    destination.sendall(chunk)


@contextmanager
def serving(server):
    worker = Thread(target=server.serve_forever, daemon=True)
    worker.start()
    try:
        yield
    finally:
        server.shutdown()
        worker.join()


def loopback_context(folder):
    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import ec
    from cryptography.x509.oid import ExtendedKeyUsageOID, NameOID

    key = ec.generate_private_key(ec.SECP256R1())
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "Panacea loopback canary")])
    now = datetime.now(timezone.utc)
    cert = (x509.CertificateBuilder().subject_name(name).issuer_name(name)
            .public_key(key.public_key()).serial_number(x509.random_serial_number())
            .not_valid_before(now - timedelta(minutes=2)).not_valid_after(now + timedelta(minutes=30))
            .add_extension(x509.SubjectAlternativeName([x509.IPAddress(ipaddress.ip_address("127.0.0.1"))]), False)
            .add_extension(x509.BasicConstraints(ca=False, path_length=None), True)
            .add_extension(x509.ExtendedKeyUsage([ExtendedKeyUsageOID.SERVER_AUTH]), False)
            .sign(key, hashes.SHA256()))
    pem = folder / "loopback.pem"
    pem.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
    key_path = folder / "loopback-key.pem"
    key_path.write_bytes(key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                                           serialization.NoEncryption()))
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.load_cert_chain(pem, key_path)
    key_path.unlink()
    return context, pem


# Use the default opener in two fresh Python interpreters, with no shared SSL context.
CLIENT = """
import ssl
import sys
import urllib.error
import urllib.request

try:
    with urllib.request.urlopen(sys.argv[1], timeout=8) as response:
        if response.status != 200 or response.read(64) != b'loopback-ok':
            raise RuntimeError('Unexpected canary response')
except urllib.error.URLError as error:
    if not isinstance(error.reason, ssl.SSLCertVerificationError):
        raise
    print('certificate rejected')
else:
    print('trusted response')
"""


def cleanup(folder):
    if folder.is_symlink() or folder.is_junction():
        raise RuntimeError("Unexpected link at canary workspace")
    if folder.exists():
        for name in ("loopback-key.pem", "loopback.pem"):
            (folder / name).unlink(missing_ok=True)
        folder.rmdir()


def check(folder, result):
    if sys.version_info[:2] != (3, 12):
        raise RuntimeError("Transport control requires CPython 3.12")
    tls, pem = loopback_context(folder)
    with HTTPServer(("127.0.0.1", 0), Origin) as origin, HTTPServer(("127.0.0.1", 0), Tunnel) as proxy:
        origin.socket = tls.wrap_socket(origin.socket, server_side=True)
        origin.requests = result["origin_requests"] = []
        proxy.requests = result["tunnel_requests"] = []
        proxy.origin = origin.server_address
        endpoint = f"https://127.0.0.1:{origin.server_port}/ping"
        address = f"http://127.0.0.1:{proxy.server_port}"
        env = {k: v for k, v in os.environ.items() if not k.lower().endswith("_proxy")
               and k.upper() not in {"SSL_CERT_FILE", "SSL_CERT_DIR", "REQUEST_METHOD"}}
        env.update(HTTPS_PROXY=address, HTTP_PROXY=address, NO_PROXY="unused.invalid")
        with serving(origin), serving(proxy):
            for field, expected in [("default_trust", "certificate rejected"), ("explicit_pem", "trusted response")]:
                if field == "explicit_pem":
                    env["SSL_CERT_FILE"] = str(pem)
                child = subprocess.run([sys.executable, "-I", "-c", CLIENT, endpoint], env=env,
                                       capture_output=True, text=True, check=True, timeout=12)
                result[field] = child.stdout.strip()
                if result[field] != expected:
                    raise RuntimeError(f"Unexpected urllib result for {field}: {result[field]}")
        if proxy.requests != [f"127.0.0.1:{origin.server_port}"] * 2 or origin.requests != ["/ping"]:
            raise RuntimeError("Unexpected tunnel or TLS origin request log")


def main():
    temp, _ = hosted_guard()
    parser = argparse.ArgumentParser()
    parser.add_argument("--cleanup", action="store_true")
    folder = temp / "panacea-urllib-loopback"
    if parser.parse_args().cleanup:
        cleanup(folder)
        if folder.exists():
            raise RuntimeError("Canary files remain")
        return
    with report("loopback-tls") as result:
        folder.mkdir()
        try:
            check(folder, result)
        finally:
            cleanup(folder)
            result["temporary_files_removed"] = not folder.exists()


if __name__ == "__main__":
    main()
