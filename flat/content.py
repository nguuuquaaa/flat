from . import attachment
import enum
import os
import collections

#==================================================================================================================================================

Mention = collections.namedtuple("Mention", "user offset length")

#==================================================================================================================================================

class File:
    def __init__(self, f, filename=None):
        self.f = f
        self.filename = filename

    def read(self):
        f = self.f
        if isinstance(f, str):
            other, self.filename = os.path.split(f)
            with open(f, "rb") as fp:
                return fp.read()
        else:
            try:
                b = f.read()
            except AttributeError:
                return f
            else:
                self.filename = getattr(f, "name", self.filename)
                return b

#==================================================================================================================================================

class Content:
    def __init__(self, text=""):
        self._clear()
        self._text = str(text)

    def _clear(self):
        self._text = ""
        self._mentions = []
        self._emoji_size = None
        self._attachments = []
        self._sticker_id = None

    def _clear_non_text(self):
        self._emoji_size = None
        self._attachments = []
        self._sticker_id = None

    def _clear_non_file(self):
        self._text = ""
        self._mentions = []
        self._emoji_size = None
        self._sticker_id = None

    def write(self, text):
        self._clear_non_text()
        self._text += str(text)
        return self

    def mention(self, user):
        self._clear_non_text()
        t = user.full_name
        self._mentions.append(Mention(user, len(self._text), len(t)))
        self._text += t
        return self

    def emoji(self, e, size="small"):
        self._clear()
        self._text = e
        if size in ("big", "medium", "small"):
            self._emoji_size = size
        else:
            raise ValueError("Emoji size must be either big, medium or small (lowercase).")
        return self

    def attach(self, *fp):
        self._clear_non_file()
        self._attachments.extend(f for f in fp if isinstance(f, File))
        return self

    def sticker(self, sticker_id):
        self._clear()
        self._sticker_id = sticker_id
        return self

    def to_dict(self):
        data = {
            "action_type": "ma-type:user-generated-message",
            "body": self._text
        }

        for i, m in enumerate(self._mentions):
            data["profile_xmd[{}][id]".format(i)] = m.user.id
            data["profile_xmd[{}][offset]".format(i)] = m.offset
            data["profile_xmd[{}][length]".format(i)] = m.length
            data["profile_xmd[{}][type]".format(i)] = "p"

        if self._emoji_size is not None:
            data["tags[0]"] = "hot_emoji_size:" + self._emoji_size

        if self._sticker_id:
            data["sticker_id"] = self._sticker_id

        return data

    @classmethod
    def from_message(cls, message):
        ctn = cls(message.text)
        ctn._mentions = message.mentions
        ctn._emoji_size = message.emoji_size
        for a in message.attachments:
            if isinstance(a, attachment.Sticker):
                ctn.sticker(a._id)
                break
        return ctn
