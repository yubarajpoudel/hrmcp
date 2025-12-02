from pwdlib import PasswordHash
from pwdlib.hashers.argon2 import Argon2Hasher
from pwdlib.hashers.bcrypt import BcryptHasher

password_hash = PasswordHash([Argon2Hasher(), BcryptHasher()])


def generate_hashed_password(plain_password: str) -> str:
    if not plain_password or not isinstance(plain_password, str):
        raise ValueError("Password must be a non-empty string.")

    return password_hash.hash(plain_password)

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return password_hash.verify(plain_password, hashed_password)

if __name__ == "__main__":
    pwd = "secret!"
    hashed = generate_hashed_password(pwd)
    print("Generated Hash:", hashed)
    print("Verification:", verify_password("secret!", hashed))