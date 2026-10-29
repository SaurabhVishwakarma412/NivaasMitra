from django.contrib.sessions.backends.base import CreateError, SessionBase, UpdateError
from django.utils import timezone
from pymongo.errors import DuplicateKeyError

from .database import get_database


class SessionStore(SessionBase):
    @classmethod
    def clear_expired(cls):
        get_database()["django_session"].delete_many(
            {"expire_date": {"$lte": timezone.now()}}
        )

    def exists(self, session_key):
        return get_database()["django_session"].count_documents(
            {"_id": session_key},
            limit=1,
        ) > 0

    def create(self):
        self._session_cache = self._session
        while True:
            self._session_key = self._get_new_session_key()
            try:
                self.save(must_create=True)
            except CreateError:
                continue
            return

    def save(self, must_create=False):
        if self.session_key is None:
            if must_create:
                raise CreateError("The session has no session key.")
            return self.create()
        collection = get_database()["django_session"]
        document = {
            "session_data": self.encode(self._session),
            "expire_date": self.get_expiry_date(),
        }
        if must_create:
            try:
                collection.insert_one({"_id": self.session_key, **document})
            except DuplicateKeyError as error:
                raise CreateError from error
            return

        result = collection.update_one(
            {"_id": self.session_key},
            {"$set": document},
        )
        if result.matched_count != 1:
            raise UpdateError("The session was deleted before it could be saved.")

    def delete(self, session_key=None):
        key = session_key or self.session_key
        if key:
            get_database()["django_session"].delete_one({"_id": key})

    def load(self):
        if self.session_key is None:
            return {}
        document = get_database()["django_session"].find_one(
            {
                "_id": self.session_key,
                "expire_date": {"$gt": timezone.now()},
            },
            {"session_data": 1},
        )
        if document is None:
            self._session_key = None
            return {}
        return self.decode(document.get("session_data", ""))
