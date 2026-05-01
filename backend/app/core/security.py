from secrets import token_urlsafe


def generate_secure_token(byte_length: int = 32) -> str:
    return token_urlsafe(byte_length)

