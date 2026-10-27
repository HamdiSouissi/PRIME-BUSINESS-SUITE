"""Chiffrement symétrique des secrets applicatifs (clés API IA…).

La clé dérive de FIELD_ENCRYPTION_KEY ou, à défaut en développement, de
SECRET_KEY. En production, FIELD_ENCRYPTION_KEY doit être défini
explicitement (voir .env.example).
"""

import base64
import hashlib

from cryptography.fernet import Fernet, InvalidToken
from django.conf import settings


def _fernet() -> Fernet:
    source = settings.FIELD_ENCRYPTION_KEY or settings.SECRET_KEY
    key = base64.urlsafe_b64encode(hashlib.sha256(source.encode()).digest())
    return Fernet(key)


def chiffrer(valeur: str) -> str:
    if not valeur:
        return ""
    return _fernet().encrypt(valeur.encode()).decode()


def dechiffrer(valeur_chiffree: str) -> str:
    if not valeur_chiffree:
        return ""
    try:
        return _fernet().decrypt(valeur_chiffree.encode()).decode()
    except InvalidToken:
        # La clé a changé : le secret n'est plus récupérable.
        return ""
