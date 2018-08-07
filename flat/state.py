from . import http, user, participant, thread, content, message, attachment
import collections
import json
import traceback


class State:
    def __init__(self, *, loop, http, dispatch, max_messages):
        self.dispatch = dispatch
        self.http = http
        self._max_messages = max_messages
        self.clear()

    def clear(self):
        self._threads = {}
        self._users = {}
        self._participants = {}
        self._messages = collections.deque(maxlen=self._max_messages)

    def process_post_messages(self, raw_messages):
        return raw_messages

    def process_raw_data(self, raw_data):
        self.dispatch("raw_pull_data", raw_data)
        if "ms" not in raw_data:
            return
        for m in raw_data["ms"]:
            self.dispatch("raw_event", m)
            message_type = m.get("type")
            if message_type == "delta":
                delta = m["delta"]
                delta_type = delta.get("type")
                delta_class = delta.get("class")

                if "addedParticipants" in delta:
                    self.process_participants_add(m)

                elif "leftParticipantFbId" in delta:
                    self.process_participants_leave(m)

                elif delta_type == "change_thread_theme":
                    self.process_thread_theme_change(m)

                elif delta_type == "change_thread_icon":
                    self.process_thread_icon_change(m)

                elif delta_type == "change_thread_nickname":
                    self.process_participant_nickname_change(m)

                elif delta_class == "ThreadName":
                    self.process_thread_name_change(m)

                elif delta_class == "DeliveryReceipt":
                    self.process_message_delivered(m)

                elif delta_class == "ReadReceipt":
                    self.process_message_seen(m)

                elif delta_class == "MarkRead":
                    self.process_message_mark_as_seen(m)

                elif delta_class == "NewMessage":
                    try:
                        self.process_message(m)
                    except:
                        traceback.print_exc()
                        print(json.dumps(m, indent=4))


            elif message_type == "inbox":
                self.process_inbox(m)

            elif message_type in ("typ", "ttyp"):
                self.process_typing(m)

            elif message_type in "jewel_requests_add":
                self.process_friend_request(m)

            elif message_type == "qprimer":
                self.process_qprimer(m)

            elif message_type == "chatproxy-presence":
                self.process_presence_update(m)

            else:
                self.process_unknown_message(m)

    def get_message_info(self, metadata):
        return metadata["messageId"], metadata["actorFbId"], int(metadata["timestamp"])

    def get_thread(self, id, *, cls, **kwargs):
        try:
            th = self._threads[id]
        except KeyError:
            th = cls(id, state=self, partial=True, **kwargs)
            self._threads[id] = th
        finally:
            return th

    def get_user(self, id, *, cls, **kwargs):
        try:
            u = self._users[id]
        except KeyError:
            u = cls(id, state=self, partial=True, **kwargs)
            self._users[id] = u
        finally:
            return u

    def process_participants_add(self, raw_message):
        delta = raw_message["delta"]
        metadata = delta["messageMetadata"]
        message_id, author_id, timestamp = self.get_message_info(metadata)

        added = (x for x in delta["addedParticipants"])
        thread_id = metadata["threadKey"]["ThreadFbId"]
        author_id = metadata["actorFbId"]
        self.dispatch("participants_added", added, author_id)

    def process_participants_leave(self, m):
        pass

    def process_thread_theme_change(self, m):
        pass

    def process_thread_icon_change(self, m):
        pass

    def process_participant_nickname_change(self, m):
        pass

    def process_thread_name_change(self, m):
        pass

    def process_message_delivered(self, m):
        pass

    def process_message_seen(self, m):
        pass

    def process_message_mark_as_seen(self, m):
        pass

    def process_message(self, raw_message):
        self.dispatch("raw_message", raw_message)
        delta = raw_message["delta"]
        metadata = delta["messageMetadata"]
        mid = metadata["messageId"]
        text = delta.get("body")
        ts = int(metadata["timestamp"])

        author_id = int(metadata["actorFbId"])
        author_type = user.User
        emoji_size = None
        for tag in metadata["tags"]:
            if tag == "source:page_unified_inbox":
                author_type = user.Page
            elif tag.startswith("hot_emoji_size:"):
                emoji_size = tag[15:]


        thread_key = metadata["threadKey"]
        try:
            thread_id = thread_key["threadFbId"]
        except KeyError:
            thread_id = thread_key["otherUserFbId"]
            thread_type = thread.OneToOne
        else:
            thread_type = thread.Group
        finally:
            th = self.get_thread(thread_id, cls=thread_type)

        if delta["attachments"]:
            attachments = tuple(self._parse_attachment(a) for a in delta["attachments"])
        else:
            attachments = ()

        try:
            raw_mentions = json.loads(delta["data"]["prng"])
        except KeyError:
            mentions = ()
        else:
            mentions = tuple(content.Mention(user=self.get_user(i["i"], cls=author_type), offset=i["o"], length=i["l"]) for i in raw_mentions)

        m = message.Message(mid, state=self, author_id=author_id, thread=th, timestamp=ts, text=text, emoji_size=emoji_size, attachments=attachments, mentions=mentions)
        self.dispatch("message", m)

    def _parse_attachment(self, a):
        mercury = a["mercury"]
        if "sticker_attachment" in mercury:
            st = mercury["sticker_attachment"]
            sid = int(st["id"])
            label = st["label"]
            width = st["width"]
            height = st["height"]
            frame_rate = st["frame_rate"]
            preview_url = st["url"]
            url = st.get("sprite_image_2x", preview_url)

            return attachment.Sticker(sid, label=label, url=url, preview_url=preview_url, width=width, height=height, frame_rate=frame_rate)

        elif "blob_attachment" in mercury:
            bl = mercury["blob_attachment"]
            aid = int(a["id"])
            filename = a["filename"]
            mimetype = a["mimetype"]
            attachment_type = bl["__typename"]

            if attachment_type == "MessageImage":
                cls = attachment.ImageAttachment
                mt = a["imageMetadata"]
                kwargs = {
                    "preview_url": mercury["large_preview"]["uri"],
                    "height": mt["height"],
                    "width": mt["width"]
                }

            else:
                cls = attachment.FileAttachment
                kwargs = {
                    "size": int(a["fileSize"]),
                    "url": mercury.get("url", mercury.get("playable_url"))
                }

            return cls(aid, filename=filename, mimetype=mimetype, **kwargs)

    def process_inbox(self, m):
        pass

    def process_typing(self, m):
        pass

    def process_friend_request(self, m):
        pass

    def process_qprimer(self, m):
        pass

    def process_presence_update(self, m):
        pass

    def process_unknown_message(self, m):
        pass

