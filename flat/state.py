from .user import *
from .participant import *
from .thread import *
from .content import *
from .message import *
from .attachment import *
from .error import *
import collections
import json
import traceback
import asyncio
from datetime import datetime
from yarl import URL

class State:
    def __init__(self, *, loop, http, dispatch, max_messages):
        self.dispatch = dispatch
        self.http = http
        self.max_messages = max_messages
        self.client_user = None
        self.clear()
        self.user_lock = asyncio.Lock()
        self.thread_lock = asyncio.Lock()
        self._job_queue = asyncio.Queue()

    def clear(self):
        self.threads = {}
        self.users = {}
        self.messages = collections.deque(maxlen=self.max_messages)

    def _parse_user(self, user_id, data):
        utype = data["type"]
        if utype in ("user", "friend"):
            u = User(
                user_id,
                state=self,
                name=data["name"],
                first_name=data["firstName"],
                gender=data["gender"],
                alias=data["alternateName"] or None,
                thumbnail=data["thumbSrc"],
                url=data["uri"],
                is_friend=data["is_friend"]
            )
            return u
        elif utype == "page":
            p = Page(
                user_id,
                state=self,
                name=data["name"],
                category=data["gender"],
                thumbnail=data["thumbSrc"],
                url=data["url"]
            )
            return p
        else:
            raise UnexpectedResponse("Unknown user type: {}".format(ttype))

    async def get_user(self, user_id):
        async with self.user_lock:
            try:
                return self.users[user_id]
            except KeyError:
                pass
            raw = await self.http.fetch_users(user_id)
            data = raw[user_id]
            u = self._parse_user(user_id, data)
            self.users[user_id] = u
            return u

    async def fetch_client_user(self):
        client_user_id = self.http.user_id
        raw = await self.http.fetch_users(client_user_id)
        data = raw[client_user_id]
        u = ClientUser(
            client_user_id,
            state=self,
            name=data["name"],
            first_name=data["firstName"],
            gender=data["gender"],
            alias=data["alternateName"] or None,
            thumbnail=data["thumbSrc"],
            url=data["uri"]
        )
        self.client_user = u
        self.users[client_user_id] = u
        return u

    async def get_users(self, user_ids):
        async with self.user_lock:
            need_to_fetch = [uid for uid in user_ids if uid not in self.users]
            batch_data = await self.http.fetch_users(need_to_fetch)
            users = self.users
            for user_id, data in batch_data.items():
                u = self._parse_user(user_id, data)
                users[user_id] = u
            return {uid: users[uid] for uid in user_ids}

    async def get_thread(self, thread_id):
        async with self.thread_lock:
            try:
                return self.threads[thread_id]
            except KeyError:
                pass
            raw = await self.http.fetch_threads(thread_id)
            data = raw[0]["data"]["message_thread"]
            ttype = data["thread_type"]
            client_user = self.client_user

            customization = data["customization_info"]
            nicks = {}
            if customization:
                emoji = customization["emoji"]
                try:
                    color = int(customization["outgoing_bubble_color"][2:], 16)
                except:
                    color = None

                for pc in customization["participant_customizations"]:
                    nicks[pc["participant_id"]] = pc["nickname"]
            else:
                emoji = None
                color = None

            if ttype == "ONE_TO_ONE":
                user_thread_id = data["thread_key"]["other_user_id"]
                other_user = await self.get_user(user_thread_id)

                t = OneToOne(
                    user_thread_id,
                    state=self,
                    emoji=emoji,
                    color=color
                )
                t.store_recipient(other_user, nickname=nicks.get(user_thread_id))
                t.store_me(nickname=nicks.get(client_user.id))
                self.threads[user_thread_id] = t
                return t

            elif ttype == "GROUP":
                thread_id = data["thread_key"]["thread_fbid"]
                nodes = data["all_participants"]["nodes"]
                all_participant_ids = [n["messaging_actor"]["id"] for n in nodes]
                all_participants = self.get_users(all_participant_ids)

                t = Group(
                    thread_id,
                    state=self,
                    emoji=emoji,
                    color=color,
                    approval_mode=data["approval_mode"]
                )

                admins = [a["id"] for a in data["thread_admins"]]
                for uid, u in all_participants:
                    t.store_participant(u, admin=uid in admins, nickname=nicks.get(uid))
                t.store_me()
                self.threads[thread_id] = t
                return t

            else:
                raise UnexpectedResponse("Unknown thread type: {}".format(ttype))

            return cls.from_data(self, data)

    async def process_raw_data(self, raw_data):
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
                    await self.process_participants_add(m)

                elif "leftParticipantFbId" in delta:
                    await self.process_participants_leave(m)

                elif delta_type == "change_thread_theme":
                    await self.process_thread_theme_change(m)

                elif delta_type == "change_thread_icon":
                    await self.process_thread_icon_change(m)

                elif delta_type == "change_thread_nickname":
                    await self.process_participant_nickname_change(m)

                elif delta_class == "ThreadName":
                    await self.process_thread_name_change(m)

                elif delta_class == "DeliveryReceipt":
                    await self.process_message_delivered(m)

                elif delta_class == "ReadReceipt":
                    await self.process_message_seen(m)

                elif delta_class == "MarkRead":
                    await self.process_message_mark_as_seen(m)

                elif delta_class == "NewMessage":
                    try:
                        await self.process_message(m)
                    except:
                        traceback.print_exc()


            elif message_type == "inbox":
                await self.process_inbox(m)

            elif message_type in ("typ", "ttyp"):
                await self.process_typing(m)

            elif message_type in "jewel_requests_add":
                await self.process_friend_request(m)

            elif message_type == "qprimer":
                await self.process_qprimer(m)

            elif message_type == "chatproxy-presence":
                await self.process_presence_update(m)

            else:
                await self.process_unknown_message(m)

    def get_message_info(self, metadata):
        return metadata["messageId"], metadata["actorFbId"], int(metadata["timestamp"])

    async def process_participants_add(self, raw_message):
        delta = raw_message["delta"]
        metadata = delta["messageMetadata"]
        message_id, author_id, timestamp = self.get_message_info(metadata)

        added = (x for x in delta["addedParticipants"])
        thread_id = metadata["threadKey"]["ThreadFbId"]
        author_id = metadata["actorFbId"]
        self.dispatch("participants_added", added, author_id)

    async def process_participants_leave(self, m):
        pass

    async def process_thread_theme_change(self, m):
        pass

    async def process_thread_icon_change(self, m):
        pass

    async def process_participant_nickname_change(self, m):
        pass

    async def process_thread_name_change(self, m):
        pass

    async def process_message_delivered(self, m):
        pass

    async def process_message_seen(self, m):
        pass

    async def process_message_mark_as_seen(self, m):
        pass

    async def process_message(self, raw_message):
        self.dispatch("raw_message", raw_message)
        delta = raw_message["delta"]
        metadata = delta["messageMetadata"]
        mid = metadata["messageId"]
        text = delta.get("body", "")
        ts = datetime.fromtimestamp(int(metadata["timestamp"])/1000)

        author_id = metadata["actorFbId"]
        bigmoji = None
        for tag in metadata["tags"]:
            if tag.startswith("hot_emoji_size:"):
                bigmoji = Bigmoji(emoji=text, size=tag[15:])
                text = ""

        thread_key = metadata["threadKey"]
        try:
            thread_id = thread_key["threadFbId"]
        except KeyError:
            thread_id = thread_key["otherUserFbId"]
        finally:
            thread = await self.get_thread(thread_id)
            author = thread.get_participant(author_id)

        files = []
        sticker = None
        embed_link = None
        if delta["attachments"]:
            for a in delta["attachments"]:
                a = self._parse_attachment(a)
                if isinstance(a, Sticker):
                    sticker = a
                    break
                elif isinstance(a, EmbedLink):
                    embed_link = a
                    break
                else:
                    files.append(a)

        mentions = []
        try:
            raw_mentions = json.loads(delta["data"]["prng"])
        except KeyError:
            pass
        else:
            for i in raw_mentions:
                mentions.append(Mention(user=thread.get_participant(i["i"]), offset=i["o"], length=i["l"]))

        m = Message(
            mid, state=self, author=author, thread=thread, timestamp=ts,
            text=text, bigmoji=bigmoji, sticker=sticker, embed_link=embed_link,
            files=files, mentions=mentions
        )
        self.messages.append(m)
        self.dispatch("message", m)

    def _parse_attachment(self, a):
        mercury = a["mercury"]
        if "sticker_attachment" in mercury:
            return self._parse_sticker(mercury["sticker_attachment"])

        elif "blob_attachment" in mercury:
            return self._parse_file(mercury["blob_attachment"])

        elif "extensible_attachment" in mercury:
            return self._parse_embed_link(mercury["extensible_attachment"])

    def _parse_sticker(self, node):
        sid = node["id"]
        label = node["label"]
        width = node["width"]
        height = node["height"]
        column_count = node["frames_per_row"]
        row_count = node["frames_per_column"]
        frame_count = node["frame_count"]
        frame_rate = node["frame_rate"]
        preview_url = node["url"]
        url = node.get("sprite_image_2x")

        return Sticker(
            sid, label=label, url=url, width=width, height=height, column_count=column_count,
            row_count=row_count, frame_count=frame_count, frame_rate=frame_rate
        )

    def _parse_file(self, node):
        aid = node["legacy_attachment_id"]
        attachment_type = node["__typename"]
        filename = utils.may_has_extension(node["filename"])

        if attachment_type == "MessageImage":
            cls = ImageAttachment
            xy = node["original_dimensions"]
            url = None
            kwargs = {
                "animated": False,
                "height": xy["y"],
                "width": xy["x"]
            }

        elif attachment_type == "MessageAnimatedImage":
            cls = ImageAttachment
            xy = node["original_dimensions"]
            url = node["animated_image"]["uri"]
            kwargs = {
                "animated": True,
                "height": xy["y"],
                "width": xy["x"]
            }

        elif attachment_type == "MessageAudio":
            cls = AudioAttachment
            url = node["playable_url"]
            kwargs = {
                "duration": node["playable_duration_in_ms"]
            }

        elif attachment_type == "MessageVideo":
            cls = VideoAttachment
            xy = node["original_dimensions"]
            url = node["playable_url"]
            kwargs = {
                "duration": node["playable_duration_in_ms"],
                "height": xy["y"],
                "width": xy["x"]
            }

        else:
            cls = FileAttachment
            url = node.get("url")
            kwargs = {}

        return cls(aid, state=self, filename=filename, url=url, **kwargs)

    def _parse_embed_link(self, node):
        eid = node["legacy_attachment_id"]
        story = node["story_attachment"]
        desc = story["description"]["text"]
        title = story["title_with_entities"]["text"]
        url = URL(story["url"]).query.get("u")
        media = story["media"]
        if media:
            media_url = media["animated_image"]
            if media_url:
                media_url = media_url["uri"]
            else:
                media_url = media["playable_url"]
                if not media_url:
                    media_url = media["image"]
                    if media_url:
                        media_url = media_url["uri"]
        else:
            media_url = None

        return EmbedLink(eid, url=url, title=title, description=desc, media_url=media_url)

    async def process_inbox(self, m):
        pass

    async def process_typing(self, m):
        pass

    async def process_friend_request(self, m):
        pass

    async def process_qprimer(self, m):
        pass

    async def process_presence_update(self, m):
        pass

    async def process_unknown_message(self, m):
        pass

    def get_send_message(self, data, content):
        messages = []
        mid = data["message_id"]
        thread_id = data["thread_fbid"] or data["other_user_fbid"]
        thread = self.threads[thread_id]
        author = thread.get_participant(self.client_user.id)
        ts = datetime.fromtimestamp(data["timestamp"]/1000)

        bigmoji = content._bigmoji

        files = []
        sticker = None
        embed_link = None
        if data["graphql_payload"]:
            for item in data["graphql_payload"]:
                node = item["node"]
                attachment_type = node["__typename"]
                if attachment_type == "ExtensibleMessageAttachment":
                    embed_link = self._parse_embed_link(node)
                    break
                elif attachment_type == "Sticker":
                    sticker = self._parse_sticker(node)
                    break
                else:
                    files.append(self._parse_file(node))

        if files or sticker:
            return Message(
                mid, state=self, author=author, thread=thread, timestamp=ts,
                text="", bigmoji=None, sticker=sticker, embed_link=None,
                files=files, mentions=[]
            )

        elif bigmoji:
            return Message(
                mid, state=self, author=author, thread=thread, timestamp=ts,
                text="", bigmoji=bigmoji, sticker=None, embed_link=None,
                files=[], mentions=[]
            )

        else:
            text = content._text
            mentions = []
            for m in content._mentions:
                mentions.append(Mention(user=thread.get_participant(m.user.id), offset=m.offset, length=m.length))
            return Message(
                mid, state=self, author=author, thread=thread, timestamp=ts,
                text=text, bigmoji=None, sticker=None, embed_link=embed_link,
                files=[], mentions=[]
            )


