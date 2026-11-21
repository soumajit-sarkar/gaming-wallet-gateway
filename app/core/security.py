import hashlib
import hmac


def hash_client_api_key(api_key: str) -> str:
    return hashlib.sha256(api_key.encode("utf-8")).hexdigest()


def verify_client_api_key(api_key: str, stored_hash: str) -> bool:
    candidate = hash_client_api_key(api_key)
    return hmac.compare_digest(candidate, stored_hash)
