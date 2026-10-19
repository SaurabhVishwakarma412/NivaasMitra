from django.core import signing
from django.conf import settings

from .models import User
from .repository import get_user


AUTH_COOKIE_NAME = "renthouse_auth"
AUTH_COOKIE_SALT = "rentals.authentication"
AUTH_COOKIE_MAX_AGE = 60 * 60 * 24 * 14


class AnonymousUser:
    id = None
    pk = None
    username = ""
    email = ""
    first_name = ""
    last_name = ""
    role = ""
    is_staff = False
    is_authenticated = False

    def get_full_name(self):
        return ""

    def get_role_display(self):
        return ""


class MongoAuthenticationMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        raw_token = request.COOKIES.get(AUTH_COOKIE_NAME)
        request.invalid_auth_cookie = False
        user = None
        if raw_token:
            try:
                user_id = signing.loads(
                    raw_token,
                    salt=AUTH_COOKIE_SALT,
                    max_age=AUTH_COOKIE_MAX_AGE,
                )
            except signing.BadSignature:
                request.invalid_auth_cookie = True
            else:
                user = get_user(user_id)
                if user is None:
                    request.invalid_auth_cookie = True
        request.user = user or AnonymousUser()
        response = self.get_response(request)
        if request.invalid_auth_cookie:
            response.delete_cookie(AUTH_COOKIE_NAME, samesite="Lax")
        return response


def set_auth_cookie(response, user: User):
    response.set_cookie(
        AUTH_COOKIE_NAME,
        signing.dumps(user.id, salt=AUTH_COOKIE_SALT),
        max_age=AUTH_COOKIE_MAX_AGE,
        httponly=True,
        secure=not settings.DEBUG,
        samesite="Lax",
    )
    return response
