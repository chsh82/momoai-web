"""
VAPID 키 생성 스크립트
웹 푸시 알림을 위한 VAPID 키를 생성합니다.
"""

from py_vapid import Vapid01 as Vapid
import os

print("Generating VAPID keys...")
print("="*50)

# VAPID 키 생성
vapid = Vapid()
vapid.generate_keys()

private_key = vapid.private_key_export().decode('utf-8')
public_key = vapid.public_key_export().decode('utf-8')

print("\n[SUCCESS] VAPID keys generated!")
print("\nAdd these to your .env file:")
print("="*50)
print(f"\nVAPID_PRIVATE_KEY={private_key.strip()}")
print(f"\nVAPID_PUBLIC_KEY={public_key.strip()}")
print("\n" + "="*50)
print("\nIMPORTANT:")
print("1. Copy the above keys to your .env file")
print("2. Never commit these keys to Git")
print("3. Keep them secret and secure")
