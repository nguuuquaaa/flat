from .base import *
from .thread import *
from .user import *
from datetime import datetime

__all__ = ["Message", "Reaction"]

#==================================================================================================================================================

class Reaction:
    def __init__(self, emoji, *, author, message):
        self._emoji = emoji
        self._author = author
        self._message = message

    @property
    def emoji(self):
        return self._emoji

    @property
    def author():
        return self._author

    @property
    def message():
        return self._message

#==================================================================================================================================================

class Message(Object):
    @property
    def author(self):
        return self._author

    @property
    def thread(self):
        return self._thread

    @property
    def timestamp(self):
        return self._timestamp

    @property
    def text(self):
        return self._text

    @property
    def bigmoji(self):
        return self._bigmoji

    @property
    def files(self):
        return tuple(self._files)

    @property
    def sticker(self):
        return self._sticker

    @property
    def embed_link(self):
        return self._embed_link

    @property
    def mentions(self):
        return self._mentions
