import ipaddress
import os
import socket
from datetime import datetime, timedelta
from pathlib import Path

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID


def discover_hostnames_and_ips() -> tuple[list[str], list[str]]:
    dns_names: list[str] = []
    ip_addrs: list[str] = []

    # Always include localhost
    dns_names.extend(["localhost"])  # DNS
    ip_addrs.extend(["127.0.0.1"])  # IPv4 loopback

    # OS hostname and its primary IP
    try:
        hostname = socket.gethostname()
        if hostname and hostname not in dns_names:
            dns_names.append(hostname)
        primary_ip = socket.gethostbyname(hostname)
        if primary_ip and primary_ip not in ip_addrs:
            ip_addrs.append(primary_ip)
    except Exception:
        pass

    # Optional: add IP provided via env var
    env_ip = os.environ.get("LAN_IP")
    if env_ip:
        try:
            ipaddress.ip_address(env_ip)
            if env_ip not in ip_addrs:
                ip_addrs.append(env_ip)
        except Exception:
            pass

    return dns_names, ip_addrs


def generate_self_signed_cert(cert_dir: Path) -> tuple[Path, Path]:
    cert_dir.mkdir(parents=True, exist_ok=True)
    key_path = cert_dir / "key.pem"
    cert_path = cert_dir / "cert.pem"

    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)

    dns_names, ip_addrs = discover_hostnames_and_ips()

    subject = issuer = x509.Name(
        [
            x509.NameAttribute(NameOID.COUNTRY_NAME, "US"),
            x509.NameAttribute(NameOID.ORGANIZATION_NAME, "Local Dev"),
            x509.NameAttribute(NameOID.COMMON_NAME, dns_names[0]),
        ]
    )

    san_list: list[x509.GeneralName] = []
    for name in dns_names:
        san_list.append(x509.DNSName(name))
    for ip_str in ip_addrs:
        try:
            san_list.append(x509.IPAddress(ipaddress.ip_address(ip_str)))
        except Exception:
            pass

    cert = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(datetime.utcnow() - timedelta(minutes=1))
        .not_valid_after(datetime.utcnow() + timedelta(days=3650))
        .add_extension(x509.SubjectAlternativeName(san_list), critical=False)
        .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
        .sign(private_key=key, algorithm=hashes.SHA256())
    )

    with key_path.open("wb") as f:
        f.write(
            key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.TraditionalOpenSSL,
                encryption_algorithm=serialization.NoEncryption(),
            )
        )

    with cert_path.open("wb") as f:
        f.write(cert.public_bytes(serialization.Encoding.PEM))

    print("Generated:")
    print(f"  Cert: {cert_path}")
    print(f"  Key:  {key_path}")
    print("SANs:")
    for name in dns_names:
        print(f"  DNS: {name}")
    for ip_str in ip_addrs:
        print(f"  IP:  {ip_str}")

    return cert_path, key_path


if __name__ == "__main__":
    generate_self_signed_cert(Path("certs"))


