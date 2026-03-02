"""VAPID 키 생성 스크립트 — 한 번만 실행하고 .env에 저장"""
import base64
from cryptography.hazmat.primitives.asymmetric.ec import generate_private_key, SECP256R1
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat

private_key = generate_private_key(SECP256R1(), default_backend())
public_key = private_key.public_key()

pub_bytes = public_key.public_bytes(Encoding.X962, PublicFormat.UncompressedPoint)
pub_b64 = base64.urlsafe_b64encode(pub_bytes).rstrip(b'=').decode()

priv_value = private_key.private_numbers().private_value
priv_bytes = priv_value.to_bytes(32, 'big')
priv_b64 = base64.urlsafe_b64encode(priv_bytes).rstrip(b'=').decode()

print("=== .env 파일에 아래 값을 추가하세요 ===")
print(f"VAPID_PUBLIC_KEY={pub_b64}")
print(f"VAPID_PRIVATE_KEY={priv_b64}")
print(f"VAPID_CLAIMS_SUB=mailto:contact@momoai.com")
