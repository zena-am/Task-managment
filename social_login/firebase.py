from firebase_admin import auth as firebase_auth
import firebase_admin
from firebase_admin import credentials
from pathlib import Path
from django.conf import settings

if not firebase_admin._apps:
    cred = credentials.Certificate(
        str(Path(__file__).resolve().parent / "serviceAccountKey.json")
    )
    firebase_admin.initialize_app(cred)