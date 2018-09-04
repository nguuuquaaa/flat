from .user import *
from .participant import *
from .thread import *
from .content import *
from .message import *
from .attachment import *
from .error import *
from .enums import *
from . import utils
import collections
import json
import traceback
import asyncio
from datetime import datetime
from yarl import URL
import copy

#==================================================================================================================================================

def get_thread_id(node):
    key = node["threadKey"]
    try:
        return key["threadFbId"]
    except KeyError:
        return key["otherUserFbId"]

#==================================================================================================================================================

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

        self.process = {
            ("delta", "ParticipantsAddedToGroupThread", None):          self.process_participants_add,
            ("delta", "ParticipantLeftGroupThread", None):              self.process_participants_leave,
            ("delta", "AdminTextMessage", "change_thread_nickname"):    self.process_nickname_change,
            ("delta", "AdminTextMessage", "change_thread_theme"):       self.process_thread_color_change,
            ("delta", "AdminTextMessage", "change_thread_icon"):        self.process_thread_emoji_change,
            ("delta", "AdminTextMessage", "change_thread_admins"):      self.process_admin_add,
            ("delta", "AdminRemovedFromGroupThread", None):             self.process_admin_remove,
            ("delta", "ThreadName", None):                              self.process_thread_name_change,
            ("delta", "ForcedFetch", None):                             self.process_force_thread_update,
            ("delta", "DeliveryReceipt", None):                         self.process_message_delivered,
            ("delta", "ReadReceipt", None):                             self.process_message_seen,
            ("delta", "NewMessage", None):                              self.process_message,
            ("delta", "ClientPayload", None):                           self.process_reaction_add,
            "inbox":                                                    self.process_inbox,
            "typ":                                                      self.process_typing,
            "ttyp":                                                     self.process_typing,
            "jewel_requests_add":                                       self.process_friend_request,
            "qprimer":                                                  self.process_qprimer,
            "chatproxy-presence":                                       self.process_presence_update
        }

    def clear(self):
        self.threads = {}
        self.users = {}
        self.messages = collections.deque(maxlen=self.max_messages)

    def _parse_user(self, user_id, data):
        utype = data["type"]
        if utype in ("user", "friend"):
            g = data["gender"]
            if g == 2:  
                gender = Gender.MALE
            elif g == 1:
                gender = Gender.FEMALE
            else:
                gender = Gender.UNDEFINED
                
            u = User(
                user_id,
                state=self,
                full_name=data["name"],
                first_name=data["firstName"],
                gender=gender,
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
                url=data["uri"]
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
            full_name=data["name"],
            first_name=data["firstName"],
            gender=data["gender"],
            alias=data["alternateName"] or None,
            thumbnail=data["thumbSrc"],
            url=data["uri"]
        )
        self.client_user = u
        self.users[client_user_id] = u
        return u

    async def bulk_get_users(self, user_ids):
        async with self.user_lock:
            need_to_fetch = [uid for uid in user_ids if uid not in self.users]
            if need_to_fetch:
                batch_data = await self.http.fetch_users(*need_to_fetch)
                if isinstance(batch_data, list):
                    print(batch_data)
                users = self.users
                for user_id, data in batch_data.items():
                    u = self._parse_user(user_id, data)
                    users[user_id] = u
            return {uid: users[uid] for uid in user_ids}

    async def _fetch_thread_info(self, thread_id):
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
            return t

        elif ttype == "GROUP":
            thread_id = data["thread_key"]["thread_fbid"]
            nodes = data["all_participants"]["nodes"]
            all_participant_ids = [n["messaging_actor"]["id"] for n in nodes]
            all_participants = await self.bulk_get_users(all_participant_ids)
            raw_image = data["image"]
            if raw_image:
                image_url = raw_image["uri"]
            else:
                image_url = None

            t = Group(
                thread_id,
                state=self,
                image_url=image_url,
                emoji=emoji,
                color=color,
                approval_mode=data["approval_mode"],
                participants={}
            )

            admins = [a["id"] for a in data["thread_admins"]]
            for uid, u in all_participants.items():
                t.store_participant(u, admin=uid in admins, nickname=nicks.get(uid))
            t.store_me()
            return t

        else:
            raise UnexpectedResponse("Unknown thread type: {}".format(ttype))

    async def get_thread(self, thread_id):
        async with self.thread_lock:
            try:
                return self.threads[thread_id]
            except KeyError:
                pass
            thread = await self._fetch_thread_info(thread_id)
            self.threads[thread_id] = thread
            return thread

    async def process_raw_data(self, raw_data):
        self.dispatch("raw_pull_data", raw_data)
        if "ms" not in raw_data:
            return
        for m in raw_data["ms"]:
            self.dispatch("raw_event", m)
            message_type = m.get("type")
            if message_type == "delta":
                delta = m["delta"]
                key = (message_type, delta.get("class"), delta.get("type"))
            else:
                key = message_type

            proc = self.process.get(key, self.process_unknown_message)
            try:
                await proc(m)
            except:
                traceback.print_exc()

    async def get_message_info(self, metadata):
        message_id = metadata["messageId"]
        author_id = metadata["actorFbId"]
        timestamp = datetime.fromtimestamp(int(metadata["timestamp"])/1000)
        thread_id = get_thread_id(metadata)

        thread = await self.get_thread(thread_id)
        author = thread.get_participant(author_id)

        return message_id, author, thread, timestamp

    async def process_participants_add(self, raw_message):
        delta = raw_message["delta"]
        metadata = delta["messageMetadata"]
        message_id, author, thread, timestamp = await self.get_message_info(metadata)

        added_ids = (x["userFbId"] for x in delta["addedParticipants"])
        users = await self.bulk_get_users(added_ids)
        added_participants = [thread.store_participant(u) for u in users]

        self.dispatch("participants_added", author, thread, added_participants)

    async def process_participants_leave(self, raw_message):
        delta = raw_message["delta"]
        metadata = delta["messageMetadata"]
        message_id, author, thread, timestamp = await self.get_message_info(metadata)

        left_id = delta["leftParticipantFbId"]
        user = thread.get_participant(left_id)

        if user == self.client_user:
            self.threads.pop(thread_id)
        left_participant = thread._participants.pop(left_id)

        self.dispatch("participants_leave", author, thread, left_participant)

    async def process_thread_color_change(self, raw_message):
        delta = raw_message["delta"]
        metadata = delta["messageMetadata"]
        message_id, author, thread, timestamp = await self.get_message_info(metadata)

        new_color = int(delta["untypedData"]["theme_color"][2:], 16)
        old_color, thread._color = thread._color, new_color

        self.dispatch("thread_color_change", author, thread, old_color, new_color)

    async def process_thread_emoji_change(self, raw_message):
        delta = raw_message["delta"]
        metadata = delta["messageMetadata"]
        message_id, author, thread, timestamp = await self.get_message_info(metadata)

        new_emoji = delta["untypedData"]["thread_icon"]
        old_emoji, thread._emoji = thread._emoji, new_emoji

        self.dispatch("thread_emoji_change", author, thread, old_emoji, new_emoji)

    async def process_nickname_change(self, raw_message):
        delta = raw_message["delta"]
        metadata = delta["messageMetadata"]
        message_id, author, thread, timestamp = await self.get_message_info(metadata)

        data = delta["untypedData"]
        new_nickname = data["nickname"] or None
        target_id = data["participant_id"]
        target = thread.get_participant(target_id)
        old_nickname, target._nickname = target._nickname, new_nickname

        self.dispatch("nickname_change", author, target, old_nickname, new_nickname)

    async def process_thread_name_change(self, raw_message):
        delta = raw_message["delta"]
        metadata = delta["messageMetadata"]
        message_id, author, thread, timestamp = await self.get_message_info(metadata)

        new_name = delta["name"]
        old_name, thread._name = thread._name, new_name

        self.dispatch("thread_name_change", author, thread, old_name, new_name)

    async def process_admin_add(self, raw_message):
        delta = raw_message["delta"]
        metadata = delta["messageMetadata"]
        message_id, author, thread, timestamp = await self.get_message_info(metadata)

        added_id = data["untypedData"]["TARGET_ID"]
        added_admin = thread.get_participant(added_id)
        added_admin._admin = True

        self.dispatch("admin_add", author, added_admin)

    async def process_admin_remove(self, raw_message):
        delta = raw_message["delta"]
        metadata = delta["messageMetadata"]
        message_id, author, thread, timestamp = await self.get_message_info(metadata)

        removed_id = data["removedAdminFbIds"][0]
        removed_admin = thread.get_participant(removed_id)
        if removed_admin:
            removed_admin._admin = False

        self.dispatch("admin_remove", author, removed_admin)

    async def update_thread(self, thread):
        '''
        Update pic and admins
        '''
        raw = await self.http.fetch_thread_info(thread.id)
        data = raw[0]["data"]["message_thread"]
        if isinstance(thread, Group):
            before = copy.copy(thread)
            admins = [adm["id"] for adm in data["thread_admins"]]
            for p in thread._participants:
                p._admin = p.id in admins
            raw_image = data["image"]
            if raw_image:
                thread._image_url = raw_image["uri"]
            else:
                thread._image_url = None

            return before, thread

    async def process_force_thread_update(self, raw_message):
        delta = raw_message["delta"]
        thread_id = get_thread_id(delta)
        thread = self.threads.get(thread_id)
        if thread:
            before, after = await self.update_thread(thread)
            self.dispatch("force_thread_update", before, after)

    async def process_message_delivered(self, raw_message):
        pass

    async def process_message_seen(self, raw_message):
        pass

    async def process_reaction_add(self, raw_message):
        delta = raw_message["delta"]
        payload = json.loads(bytes(delta["payload"]))
        deltas = payload["deltas"]
        self.dispatch("raw_reaction_add", deltas)
        for d in deltas:
            node = d["deltaMessageReaction"]
            sender_id = node["senderId"]
            m = utils.get_elem(self.messages, lambda m: m.id==sender_id)
            if m:
                author = m.thread.get_participant(node["userId"])
                self.dispatch("reaction_add", Reaction(node["reaction"], author=author, message=message))

    async def process_message(self, raw_message):
        self.dispatch("raw_message", raw_message)
        delta = raw_message["delta"]
        metadata = delta["messageMetadata"]
        mid, author, thread, ts = await self.get_message_info(metadata)

        text = delta.get("body", "")
        bigmoji = None
        for tag in metadata["tags"]:
            if tag.startswith("hot_emoji_size:"):
                bigmoji = Bigmoji(emoji=text, size=tag[15:])
                text = ""

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
            files=files, mentions=mentions, reactions=[]
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
        url = node["sprite_image_2x"]["uri"]

        return Sticker(
            sid, state=self, label=label, url=url, width=width, height=height, column_count=column_count,
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

        return EmbedLink(eid, state=self, url=url, title=title, description=desc, media_url=media_url)

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
        if not isinstance(content, Content):
            content = Content(content)
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
                files=files, mentions=[], reactions=[]
            )

        elif bigmoji:
            return Message(
                mid, state=self, author=author, thread=thread, timestamp=ts,
                text="", bigmoji=bigmoji, sticker=None, embed_link=None,
                files=[], mentions=[], reactions=[]
            )

        else:
            text = content._text
            mentions = []
            for m in content._mentions:
                mentions.append(Mention(user=thread.get_participant(m.user.id), offset=m.offset, length=m.length))
            return Message(
                mid, state=self, author=author, thread=thread, timestamp=ts,
                text=text, bigmoji=None, sticker=None, embed_link=embed_link,
                files=[], mentions=[], reactions=[]
            )


