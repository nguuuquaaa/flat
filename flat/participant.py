from .base import *

#==================================================================================================================================================

class Participant(Object):
    def __init__(self, **kwargs):
        for key, value in kwargs.items():
            setattr(self, key, value)

    @property
    def id(self):
        return self.user.id

    @property
    def name(self):
        return self.nickname or self.user.full_name
