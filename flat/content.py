import enum
import os
import collections
from io import BytesIO
import mimetypes

__all__ = ("File", "Content", "Mention", "Bigmoji")

#==================================================================================================================================================

Mention = collections.namedtuple("Mention", "user offset length")

Bigmoji = collections.namedtuple("Bigmoji", "emoji size")

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
        self._embed_url = None
        self._bigmoji = None
        self._files = []
        self._sticker_id = None

    def write(self, text):
        self._text += str(text)
        return self

    def mention(self, user, att="name"):
        if att in ("name", "full_name", "first_name", "alias", "nickname"):
            t = getattr(user, att)
        else:
            raise ValueError("Att is not accepted.")
        self._mentions.append(Mention(user, len(self._text), len(t)))
        self._text += t
        return self

    def bigmoji(self, emoji, size="small"):
        if size in ("large", "medium", "small"):
            self._bigmoji = Bigmoji(emoji=e, size=size)
            return self
        else:
            raise ValueError("Emoji size must be either large, medium or small (lowercase).")

    def attach_file(self, *fp):
        self._files.extend(f for f in fp if isinstance(f, File))
        return self

    def add_sticker(self, sticker_id):
        self._sticker_id = sticker_id
        return self

    def embed_link(self, url, *, append=True):
        if url.startswith(("https://", "http://")):
            if append:
                self._text += url
            self._embed_url = url
            return self
        else:
            raise ValueError("This accepts url with http(s) scheme only.")

    async def to_dict(self, http):
        base = {
            "action_type": "ma-type:user-generated-message",
            "body": ""
        }

        data = []

        if self._text or self._mentions or self._embed_url:
            cur = base.copy()
            cur["body"] = self._text

            for i, m in enumerate(self._mentions):
                cur["profile_xmd[{}][id]".format(i)] = m.user.id
                cur["profile_xmd[{}][offset]".format(i)] = m.offset
                cur["profile_xmd[{}][length]".format(i)] = m.length
                cur["profile_xmd[{}][type]".format(i)] = "p"

            if self._embed_url:
                d = await http.fetch_embed_data(self._embed_url)
                cur.update(d)

            data.append(cur)

        if self._bigmoji:
            cur = base.copy()
            cur["body"] = self._bigmoji.emoji
            cur["tags[0]"] = "hot_emoji_size:" + self._bigmoji.size
            data.append(cur)

        if self._sticker_id:
            cur = base.copy()
            cur["sticker_id"] = self._sticker_id
            cur["has_attachment"] = "true"
            data.append(cur)

        if self._files:
            cur = []
            cur["has_attachment"] = "true"

            count = {
                "image": 0,
                "gif": 0,
                "audio": 0,
                "video": 0,
                "file": 0
            }

            for i, f in enumerate(self._files):
                d = await http.upload_file(f)

                for t in count.items():
                    file_id = d.get(t+"_id")
                    if file_id:
                        data_for_this = cur.get(t, base.copy())
                        if t in ("image", "gif"):
                            c = count["image"] + count["gif"]
                        else:
                            c = count[t]
                        data_for_this["{}_ids[{}]".format(t, c)] = file_id
                        cur[t] = data_for_this
                        count[t] = v + 1

            data.extend(cur)

        return data

    @classmethod
    async def from_message(cls, message):
        ctn = cls(message.text)
        ctn._mentions = message.mentions
        if message.bigmoji:
            ctn.bigmoji(message.bigmoji.id, size=message.bigmoji.size)
        if message.sticker:
            ctn.add_sticker(message.sticker.id)
        if message.embed_link:
            ctn.embed_link(message.embed_link.url, append=False)
        for f in message.files:
            b = BytesIO()
            await f.save(b)
            ctn.attach(File(b.getvalue(), f.filename))
        return ctn
