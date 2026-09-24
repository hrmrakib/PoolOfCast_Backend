import time
import jwt
from django.conf import settings


def generate_zego_token(user_id = None):
    payload = {
        "app_id": settings.ZEGO_APP_ID,
        "user_id": str(user_id),
        "nonce": int(time.time()),
        "ctime": int(time.time()),
        "expire": int(time.time()) + 3600
    }

    token = jwt.encode(
        payload,
        settings.ZEGO_SERVER_SECRET,
        algorithm="HS256"
    )

    return token