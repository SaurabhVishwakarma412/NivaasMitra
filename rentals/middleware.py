from .models import AnonymousUser
from .repository import get_user


class MongoUserAuthenticationMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        user_id = request.session.get("user_id")
        user = get_user(user_id) if user_id else None
        if user_id and user is None:
            request.session.pop("user_id", None)
        request.user = user or AnonymousUser()
        return self.get_response(request)
