from . import base, content, attachment
from datetime import datetime

__all__ = ("Message", "Reaction")

#==================================================================================================================================================

class Reaction:
    def __init__(self, emoji, *, author, message):
        self.emoji = emoji
        self.author = author
        self.message = message

#==================================================================================================================================================

class Message(base.Object):
    @classmethod
    def from_content(cls, state, data, ctn):
        if not isinstance(ctn, content.Content):
            ctn = content.Content(ctn)
        messages = []
        mid = data["message_id"]
        thread_id = data["thread_fbid"] or data["other_user_fbid"]
        thread = state.threads[thread_id]
        author = thread.get_participant(state.client_user.id)
        ts = datetime.fromtimestamp(data["timestamp"]/1000)

        bigmoji = ctn.bigmoji

        files = []
        sticker = None
        embed_link = None
        if data["graphql_payload"]:
            for item in data["graphql_payload"]:
                node = item["node"]
                attachment_type = node["__typename"]
                if attachment_type == "ExtensibleMessageAttachment":
                    embed_link = attachment.EmbedLink.from_data(state, node)
                    break
                elif attachment_type == "Sticker":
                    sticker = attachment.Sticker.from_data(state, node)
                    break
                else:
                    files.append(state._parse_file(node))

        if files or sticker:
            return cls(
                mid, _state=state, author=author, thread=thread, timestamp=ts,
                text="", bigmoji=None, sticker=sticker, embed_link=None,
                files=files, mentions=[], reactions=[]
            )

        elif bigmoji:
            return cls(
                mid, _state=state, author=author, thread=thread, timestamp=ts,
                text="", bigmoji=bigmoji, sticker=None, embed_link=None,
                files=[], mentions=[], reactions=[]
            )

        else:
            text = ctn._text
            mentions = []
            for m in ctn._mentions:
                mentions.append(ctn.Mention(user=thread.get_participant(m.user.id), offset=m.offset, length=m.length))
            return cls(
                mid, _state=state, author=author, thread=thread, timestamp=ts,
                text=text, bigmoji=None, sticker=None, embed_link=embed_link,
                files=[], mentions=[], reactions=[]
            )
