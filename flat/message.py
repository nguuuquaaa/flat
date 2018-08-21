from . import base, thread, user
from datetime import datetime

#==================================================================================================================================================

class Message(base.Object):
    @property
    def author(self):
        if isinstance(self._thread, thread.OneToOne):
            return self._state.get_user(self._author_id, cls=user.User)
        else:
            return self._thread.get_participant(self._author_id)

    @property
    def thread(self):
        return self._thread

    @property
    def timestamp(self):
        return datetime.fromtimestamp(self._timestamp/1000)

    @property
    def text(self):
        return self._text

    @property
    def attachments(self):
        return tuple(self._attachments)

    @property
    def mentions(self):
        return self._mentions

    @property
    def emoji_size(self):
        return self._emoji_size
