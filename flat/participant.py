from .base import *

#==================================================================================================================================================

class Participant(Object):
    def __init__(self, **kwargs):
        for key, value in kwargs.items():
            setattr(self, "_"+key, value)

    @property
    def id(self):
        return self._user.id

    @property
    def user(self):
        return self._user

    @property
    def thread(self):
        return self._thread

    @property
    def name(self):
        return self._nickname or self._user.full_name


