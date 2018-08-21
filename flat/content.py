from . import attachment
import enum
import os
import collections
from io import BytesIO

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
            other, filename = os.path.split(f)
            with open(f, "rb") as fp:
                return fp.read(), filename
        else:
            try:
                b = f.read()
            except AttributeError:
                return f, self.filename
            else:
                filename = getattr(f, "name", self.filename)
                return b, filename

#==================================================================================================================================================

class Content:
    def __init__(self, text=""):
        self._clear()
        self._text = str(text)

    def _clear(self):
        self._text = ""
        self._mentions = []
        self._url = None
        self._emoji_size = None
        self._attachments = []
        self._sticker_id = None

    def _clear_non_text(self):
        self._emoji_size = None
        self._attachments = []
        self._sticker_id = None

    def _clear_non_file(self):
        self._text = ""
        self._url = None
        self._mentions = []
        self._emoji_size = None
        self._sticker_id = None

    def write(self, text):
        self._clear_non_text()
        self._text += str(text)
        return self

    def mention(self, user, att="full_name"):
        self._clear_non_text()
        if att in ("full_name", "first_name", "last_name", "alias", "nick"):
            t = getattr(user, att)
        else:
            raise ValueError("Att is not accepted.")
        self._mentions.append(Mention(user, len(self._text), len(t)))
        self._text += t
        return self

    def emoji(self, e, size="small"):
        self._clear()
        self._text = e
        if size in ("large", "medium", "small"):
            self._emoji_size = size
        else:
            raise ValueError("Emoji size must be either large, medium or small (lowercase).")
        return self

    def attach(self, *fp):
        self._clear_non_file()
        self._attachments.extend(f for f in fp if isinstance(f, File))
        return self

    def sticker(self, sticker_id):
        self._clear()
        self._sticker_id = sticker_id
        return self

    def link(self, url):
        if url.startswith(("https://", "http://")):
            self._clear_non_text()
            self._text += url
            self._url = url
            return self
        else:
            raise ValueError("This accepts url with http(s) scheme only.")

    def to_dict(self):
        data = {
            "action_type": "ma-type:user-generated-message",
            "body": self._text,
            "has_attachment": "false"
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
            data["has_attachment"] = "true"

        if self._attachments:
            data["has_attachment"] = "true"

        return data

    @classmethod
    async def from_message(cls, message):
        ctn = cls(message.text)
        ctn._mentions = message.mentions
        ctn._emoji_size = message.emoji_size
        for a in message.attachments:
            if isinstance(a, attachment.Sticker):
                ctn.sticker(a.id)
                break
            elif isinstance(a, attachment.FileAttachment):
                b = BytesIO()
                await a.save(b)
                ctn.attach(File(b.getvalue(), a._filename))
        return ctn
