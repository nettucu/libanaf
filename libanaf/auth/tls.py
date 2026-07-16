import datetime
import ipaddress
from pathlib import Path

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID

DEFAULT_CERT_FILE = Path("secrets/localhost.crt")
DEFAULT_KEY_FILE = Path("secrets/localhost.key")


def ensure_tls_cert(cert_file: Path | None, key_file: Path | None) -> tuple[Path, Path]:
    """Return a usable PEM cert/key pair for the local OAuth callback server, generating one if needed.

    Falls back to ``secrets/localhost.crt`` / ``secrets/localhost.key`` when no
    path is configured. If the resolved files already exist on disk they are
    reused as-is; otherwise a self-signed certificate (CN=localhost, SAN
    localhost/127.0.0.1) is generated and written to those paths so it
    persists across runs and does not need to be recreated or copied between
    machines each time.

    Args:
        cert_file: Configured certificate path, or ``None`` to use the default.
        key_file: Configured private key path, or ``None`` to use the default.

    Returns:
        The (cert_file, key_file) paths, guaranteed to exist on disk in PEM format.
    """
    cert_path = cert_file or DEFAULT_CERT_FILE
    key_path = key_file or DEFAULT_KEY_FILE

    if cert_path.exists() and key_path.exists():
        return cert_path, key_path

    cert_path.parent.mkdir(parents=True, exist_ok=True)
    key_path.parent.mkdir(parents=True, exist_ok=True)

    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    subject = issuer = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "localhost")])
    now = datetime.datetime.now(datetime.timezone.utc)
    cert = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - datetime.timedelta(days=1))
        .not_valid_after(now + datetime.timedelta(days=825))
        .add_extension(
            x509.SubjectAlternativeName(
                [x509.DNSName("localhost"), x509.IPAddress(ipaddress.IPv4Address("127.0.0.1"))]
            ),
            critical=False,
        )
        .sign(key, hashes.SHA256())
    )

    key_path.write_bytes(
        key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        )
    )
    cert_path.write_bytes(cert.public_bytes(serialization.Encoding.PEM))

    return cert_path, key_path
