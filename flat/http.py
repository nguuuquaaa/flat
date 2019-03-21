import aiohttp
import asyncio
from bs4 import BeautifulSoup as BS
from . import error, content, utils
import random
import re
import json
import mimetypes
import time
import json
import re
import functools

#==================================================================================================================================================

USER_AGENTS = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/67.0.3396.99 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_10_2) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/42.0.2311.90 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_10_3) AppleWebKit/601.1.10 (KHTML, like Gecko) Version/8.0.5 Safari/601.1.10",
    "Mozilla/5.0 (Windows NT 6.3; WOW64; ; NCT50_AAP285C84A1328) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/42.0.2311.90 Safari/537.36",
    "Mozilla/5.0 (Windows NT 6.1; WOW64) AppleWebKit/537.1 (KHTML, like Gecko) Chrome/22.0.1207.1 Safari/537.1",
    "Mozilla/5.0 (X11; CrOS i686 2268.111.0) AppleWebKit/536.11 (KHTML, like Gecko) Chrome/20.0.1132.57 Safari/536.11",
    "Mozilla/5.0 (Windows NT 6.1; WOW64) AppleWebKit/536.6 (KHTML, like Gecko) Chrome/20.0.1092.0 Safari/536.6"
)

try:
    import lxml
except ImportError:
    PARSER = "html.parser"
else:
    PARSER = "lxml"

#==================================================================================================================================================

_DIGITS = "0123456789abcdefghijklmnopqrstuvwxyz"
def str_base(number, base=36):
    if isinstance(number, int):
        if number == 0:
            return "0"
        elif number < 0:
            value = -number
            sign = "-"
        else:
            value = number
            sign = ""

        ret = ""
        while value > 0:
            value, remainder = divmod(value, base)
            ret = _DIGITS[remainder] + ret
        return sign + ret
    else:
        raise TypeError("Input number must be int.")

def now():
    return int(time.time()*1000)

def generate_offline_threading_id():
    t = now()
    v = random.randrange(0xffffffff)
    return (t << 22) + (v & 0x7ffff)

def strip_to_json(s):
    start = "[{"
    for i, c in enumerate(s):
        if c in start:
            return s[i:]
    else:
        return None

def load_broken_json(b):
    return json.loads(strip_to_json(b.decode("utf-8")))

def get_jsmods_require(d, index, default=None):
    try:
        return d["jsmods"]["require"][0][index][0]
    except (KeyError, IndexError):
        return default

def get_between(text, start, end):
    parts = text.partition(start)
    if parts[2]:
        ret = parts[2].partition(end)
        if ret[2]:
            return ret[0]
        else:
            raise IndexError("Cannot find end token.")
    else:
        raise IndexError("Cannot find start token.")

def flatten(data, prefix):
    if isinstance(data, dict):
        iterator = data.items()
    elif isinstance(data, (list, tuple)):
        iterator = enumerate(data)
    else:
        data = data or ""
        return {prefix: data}

    ret = {}
    for key, value in iterator:
        proc = flatten(value, "{}[{}]".format(prefix, key))
        ret.update(proc)
    return ret

#==================================================================================================================================================

_WHITESPACE = re.compile(r"\s*")

class ConcatJSONDecoder(json.JSONDecoder):
    def decode(self, s, _w=_WHITESPACE.match):
        s = s.strip()
        s_len = len(s)

        objs = []
        end = 0
        while end != s_len:
            obj, end = self.raw_decode(s, idx=_w(s, end).end())
            objs.append(obj)
        return objs

load_concat_json = functools.partial(json.loads, cls=ConcatJSONDecoder)

#==================================================================================================================================================

#straight up stolen from fbchat
class GraphQL:
    FRAGMENT_USER = """
    QueryFragment User: User {
        id,
        name,
        first_name,
        last_name,
        profile_picture.width(<pic_size>).height(<pic_size>) {
            uri
        },
        is_viewer_friend,
        url,
        gender,
        viewer_affinity
    }
    """

    FRAGMENT_GROUP = """
    QueryFragment Group: MessageThread {
        name,
        thread_key {
            thread_fbid
        },
        image {
            uri
        },
        is_group_thread,
        all_participants {
            nodes {
                messaging_actor {
                    id
                }
            }
        },
        customization_info {
            participant_customizations {
                participant_id,
                nickname
            },
            outgoing_bubble_color,
            emoji
        }
    }
    """

    FRAGMENT_PAGE = """
    QueryFragment Page: Page {
        id,
        name,
        profile_picture.width(32).height(32) {
            uri
        },
        url,
        category_type,
        city {
            name
        }
    }
    """

    SEARCH_USER = """
    Query SearchUser(<search> = '', <limit> = 1) {
        entities_named(<search>) {
            search_results.of_type(user).first(<limit>) as users {
                nodes {
                    @User
                }
            }
        }
    }
    """ + FRAGMENT_USER

    SEARCH_GROUP = """
    Query SearchGroup(<search> = '', <limit> = 1, <pic_size> = 32) {
        viewer() {
            message_threads.with_thread_name(<search>).last(<limit>) as groups {
                nodes {
                    @Group
                }
            }
        }
    }
    """ + FRAGMENT_GROUP

    SEARCH_PAGE = """
    Query SearchPage(<search> = '', <limit> = 1) {
        entities_named(<search>) {
            search_results.of_type(page).first(<limit>) as pages {
                nodes {
                    @Page
                }
            }
        }
    }
    """ + FRAGMENT_PAGE

    SEARCH_THREAD = """
    Query SearchThread(<search> = '', <limit> = 1) {
        entities_named(<search>) {
            search_results.first(<limit>) as threads {
                nodes {
                    __typename,
                    @User,
                    @Group,
                    @Page
                }
            }
        }
    }
    """ + FRAGMENT_USER + FRAGMENT_GROUP + FRAGMENT_PAGE

    def __init__(self, *, query={}, params={}, doc_id=None):
        if query:
            self.value = {
                "priority": 0,
                "q": query,
                "query_params": params
            }
        elif doc_id:
            self.value = {
                "doc_id": doc_id,
                "query_params": params
            }
        else:
            raise ValueError("Need either query or doc_id.")

    @classmethod
    def fetch_thread_info(cls, thread_id):
        return cls(
            doc_id="1386147188135407",
            params={
                "id": thread_id,
                "message_limit": 0,
                "load_messages": False,
                "load_read_receipts": False,
                "before": None
            }
        )

#==================================================================================================================================================

#partially stolen from fbchat, and converted to aiohttp
class HTTPRequest:
    SEARCH = "https://www.facebook.com/ajax/typeahead/search.php"
    LOGIN = "https://m.facebook.com/login.php?login_attempt=1"
    SEND = "https://www.facebook.com/messaging/send/"
    UNREAD_THREADS = "https://www.facebook.com/ajax/mercury/unread_threads.php"
    UNSEEN_THREADS = "https://www.facebook.com/mercury/unseen_thread_ids/"
    THREADS = "https://www.facebook.com/ajax/mercury/threadlist_info.php"
    MESSAGES = "https://www.facebook.com/ajax/mercury/thread_info.php"
    READ_STATUS = "https://www.facebook.com/ajax/mercury/change_read_status.php"
    DELIVERED = "https://www.facebook.com/ajax/mercury/delivery_receipts.php"
    MARK_SEEN = "https://www.facebook.com/ajax/mercury/mark_seen.php"
    BASE = "https://www.facebook.com"
    MOBILE = "https://m.facebook.com/"
    STICKY = "https://{}-edge-chat.facebook.com/pull"
    PING = "https://{}-edge-chat.facebook.com/active_ping"
    UPLOAD = "https://upload.facebook.com/ajax/mercury/upload.php"
    USER_INFO = "https://www.facebook.com/chat/user_info/"
    CONNECT = "https://www.facebook.com/ajax/add_friend/action.php?dpr=1"
    REMOVE_USER = "https://www.facebook.com/chat/remove_participants/"
    LOGOUT = "https://www.facebook.com/logout.php"
    ALL_USERS = "https://www.facebook.com/chat/user_info_all"
    SAVE_DEVICE = "https://m.facebook.com/login/save-device/cancel/"
    CHECKPOINT = "https://m.facebook.com/login/checkpoint/"
    THREAD_COLOR = "https://www.facebook.com/messaging/save_thread_color/?source=thread_settings&dpr=1"
    THREAD_NICKNAME = "https://www.facebook.com/messaging/save_thread_nickname/?source=thread_settings&dpr=1"
    THREAD_EMOJI = "https://www.facebook.com/messaging/save_thread_emoji/?source=thread_settings&dpr=1"
    THREAD_IMAGE = "https://www.facebook.com/messaging/set_thread_image/?dpr=1"
    THREAD_NAME = "https://www.facebook.com/messaging/set_thread_name/?dpr=1"
    WEBGRAPHQL = "https://www.facebook.com/webgraphql/query/"
    MESSAGE_REACTION = "https://www.facebook.com/webgraphql/mutation"
    TYPING = "https://www.facebook.com/ajax/messaging/typ.php"
    GRAPHQL = "https://www.facebook.com/api/graphqlbatch/"
    ATTACHMENT_PHOTO = "https://www.facebook.com/mercury/attachments/photo/"
    EVENT_REMINDER = "https://www.facebook.com/ajax/eventreminder/create"
    MODERN_SETTINGS_MENU = "https://www.facebook.com/bluebar/modern_settings_menu/"
    REMOVE_FRIEND = "https://m.facebook.com/a/removefriend.php"
    EMBED_LINK = "https://www.facebook.com/message_share_attachment/fromURI/"
    MARK_FOLDER_AS_READ = "https://www.facebook.com/ajax/mercury/mark_folder_as_read.php?dpr=1"

    def __init__(self, *, loop=None, user_agent=None, cookie_jar=None):
        self.loop = loop or asyncio.get_event_loop()
        self.pull_channel = 0
        self.client = "mercury"
        self.headers = {
            "Content-Type" : "application/x-www-form-urlencoded",
            "Referer": self.BASE,
            "Origin": self.BASE,
            "User-Agent": user_agent or USER_AGENTS[0],
            "Connection": "keep-alive",
        }
        self.cookie_jar = cookie_jar
        self.clear()

    def change_pull_channel(self):
        self.pull_channel = (self.pull_channel + 1) % 6

    def clear(self):
        self.session = aiohttp.ClientSession(loop=self.loop, cookie_jar=self.cookie_jar)
        self.params = {}
        self.request_counter = 1
        self.seq = "0"

    async def close(self):
        await self.session.close()

    def update_params(self, extra={}):
        params = self.params.copy()
        params["__req"] = str_base(self.request_counter)
        params["seq"] = self.seq
        params.update(extra)
        self.request_counter += 1
        return params

    def retries_wrap(times, *, verbose=True):
        def wrapped(func):
            @functools.wraps(func)
            async def new_func(self, *args, **kwargs):
                for i in range(times):
                    try:
                        return await func(self, *args, **kwargs)
                    except (asyncio.TimeoutError, KeyboardInterrupt, RuntimeError):
                        raise
                    except error.HTTPRequestFailure as e:
                        status = e.response.status
                        if status in (502, 503):
                            self.change_pull_channel()
                        elif status == 1357004:
                            await self.save_login_state()
                        continue
                    except Exception as e:
                        if verbose:
                            print("Ignored {}, retrying... ({}/{})".format(type(e), i+1, times))
                else:
                    raise error.HTTPException("Cannot send HTTP request.")
            return new_func
        return wrapped

    @retries_wrap(3)
    async def get(self, url, *, headers=None, params=None, timeout=30, as_json=False, json_decoder=load_broken_json, **kwargs):
        headers = headers or self.headers
        params = self.update_params(params or {})
        async with self.session.get(url, headers=headers, params=params, timeout=timeout, **kwargs) as response:
            if response.status != 200:
                raise error.HTTPRequestFailure(response)
            bytes_ = await response.read()
            if as_json:
                return json_decoder(bytes_)
            else:
                return bytes_

    @retries_wrap(3)
    async def post(self, url, *, headers=None, data=None, timeout=30, as_json=False, json_decoder=load_broken_json, **kwargs):
        headers = headers or self.headers
        data = self.update_params(data or {})
        async with self.session.post(url, headers=headers, data=data, timeout=timeout, **kwargs) as response:
            if response.status != 200:
                raise error.HTTPRequestFailure(response)
            bytes_ = await response.read()
            if as_json:
                return json_decoder(bytes_)
            else:
                return bytes_

    async def login(self, username, password):
        if username and password:
            #self.username = username
            #self.password = password
            pass
        else:
            raise error.LoginError("Username and password must be non-empty.")
        bytes_ = await self.get(self.MOBILE)
        soup = BS(bytes_.decode("utf-8"), PARSER)
        data = {tag["name"]: tag["value"] for tag in soup.find_all("input") if "name" in tag.attrs and "value" in tag.attrs}
        data["email"] = username
        data["pass"] = password
        data["login"] = "Log In"

        self.request_counter += 1

        resp = await self.session.post(self.LOGIN, headers=self.headers, data=data)

        if "checkpoint" in resp.url.human_repr():
            bytes_ = await resp.read()
            #resp = await self.handle_2FA(bytes_)
            #I don't think this does anything anymore

        if "save-device" in resp.url.human_repr():
            resp = await self.session.get(self.SAVE_DEVICE, headers=self.headers)

        if "home" in resp.url.human_repr():
            return await self.save_login_state()
        else:
            raise error.LoginError("Login failed, reason unknown.")

    async def handle_2FA(self, bytes_):
        soup = BS(bytes_.decode("utf-8"), PARSER)

        code = input("Input 2FA code here: ")
        data = {
            "approvals_code": code,
            "fb_dtsg": soup.find("input", attrs={"name": "fb_dtsg"})["value"],
            "nh": soup.find("input", attrs={"name": "nh"})["value"],
            "submit[Submit Code]": "Submit Code",
            "codes_submitted": 0
        }

        resp = await self.session.post(self.CHECKPOINT, headers=self.headers, data=data)
        if "home" in resp.url.human_repr():
            return resp

        data.pop("approvals_code")
        data.pop("submit[Submit Code]")
        data.pop("codes_submitted")
        data["name_action_selected"] = "save_device"
        data["submit[Continue]"] = "Continue"

        resp = await self.session.post(self.CHECKPOINT, headers=self.headers, data=data)
        if "home" in resp.url.human_repr():
            return resp

        data.pop("name_action_selected")

        resp = await self.session.post(self.CHECKPOINT, headers=self.headers, data=data)
        if "home" in resp.url.human_repr():
            return resp

        data.pop("submit[Continue]")
        data["submit[This was me]"] = "This Was Me"

        resp = await self.session.post(self.CHECKPOINT, headers=self.headers, data=data)
        if "home" in resp.url.human_repr():
            return resp

        data.pop("submit[This was me]")
        data["submit[Continue]"] = "Continue"
        data["name_action_selected"] = "save_device"

        return await self.session.post(self.CHECKPOINT, headers=self.headers, data=data)

    async def save_login_state(self):
        self.params.clear()
        self.client_id = "{:x}".format(random.randrange(0x80000000))
        self.start_time = now()
        for cookie in self.session.cookie_jar:
            if cookie.key == "c_user":
                self.user_id = str(cookie.value)
                break
        else:
            raise error.LoginError("Cannot find c_user cookie.")
        self.user_channel = "p_" + self.user_id
        self.ttstamp = ""

        bytes_ = await self.get(self.BASE)
        html = bytes_.decode("utf-8")
        soup = BS(html, PARSER)

        fb_dtsg = soup.find("input", attrs={"name": "fb_dtsg"})
        if fb_dtsg:
            self.fb_dtsg = fb_dtsg["value"]
        else:
            m = re.search(r"name=\"fb_dtsg\"\svalue=\"(.?*)\"", html)
            self.fb_dtsg = m.group(1)

        jazoest = soup.find("input", attrs={"name": "jazoest"})
        if jazoest:
            self.jazoest = jazoest["value"]
        else:
            m = re.search(r"name=\"jazoest\"\svalue=\"(.?*)\"", html)
            self.jazoest = m.group(1)

        h = soup.find("input", attrs={"name": "h"})
        if h:
            self.h = h["value"]

        t = "".join((str(ord(c)) for c in self.fb_dtsg))
        self.ttstamp = t + "2"

        self.params["__rev"] = int(html.partition("\"client_revision\":")[2].partition(",")[0])
        self.params["__user"] = int(self.user_id)
        self.params["__a"] = "1"
        self.params["ttstamp"] = self.ttstamp
        self.params["fb_dtsg"] = self.fb_dtsg
        self.params["jazoest"] = self.jazoest

        self.form = {
            "channel": self.user_channel,
            "partition": "-2",
            "clientid": self.client_id,
            "viewer_uid": self.user_id,
            "uid": self.user_id,
            "state": "active",
            "format": "json",
            "idle": 0,
            "cap": "8"
        }

        self.prev = now()
        self.tmp_prev = now()
        self.last_sync = now()

        return self.user_id

    async def logout(self):
        if not hasattr(self, "h"):
            bytes_ =  await self.post(self.MODERN_SETTINGS_MENU, data={"pmid": "4"})
            m = re.search(r"name=\"h\"\svalue=\"(.*?)\"", bytes_.decode("utf-8"))
            self.h = m.group(1)

        await self.get(self.LOGOUT, params={"ref": "mb", "h": self.h})

    async def send_message(self, dest, ctn):
        if not isinstance(ctn, content.Content):
            ctn = content.Content(ctn)
        otid = generate_offline_threading_id()
        data = {
            "client": self.client,
            "author": "fbid:" + str(self.user_id),
            "timestamp": now(),
            "source": "source:chat:web",
            "offline_threading_id": otid,
            "message_id": otid,
            "ephemeral_ttl_mode": "0"
        }

        data.update(dest.to_dict())
        send_data = await ctn.to_dict(self)

        ms = []
        for sd in send_data:
            sd.update(data)
            d = await self.post(self.SEND, data=sd, as_json=True)
            fb_dtsg = get_jsmods_require(d, 2)
            if fb_dtsg is not None:
                self.params["fb_dtsg"] = fb_dtsg
            try:
                send = [m for m in d["payload"]["actions"] if m]
            except:
                continue
            else:
                ms.extend(send)
        return ms

    async def fetch_embed_data(self, url):
        ret = await self.post(
            self.EMBED_LINK,
            data={"uri": url, "image_height": 960, "image_width": 960},
            as_json=True
        )
        share_data = ret["payload"]["share_data"]
        return flatten(share_data, "shareable_attachment")

    async def upload_file(self, f):
        b, filename = f.read()
        if not filename:
            filename = "file_" + str(i)
            content_type = None
        else:
            content_type = mimetypes.guess_type(filename)[0]

        params = self.update_params()
        headers = self.headers.copy()
        headers.pop("Content-Type")

        file_payload = aiohttp.FormData()
        file_payload.add_field("upload_1024", b, filename=filename, content_type=content_type)
        resp = await self.session.post(
            self.UPLOAD,
            headers=headers,
            params=params,
            data=file_payload
        )

        ret = load_broken_json(await resp.read())
        return ret["payload"]["metadata"][0]

    async def fetch_sticky(self):
        params = {
            "msgs_recv": 0,
            "channel": self.user_channel,
            "clientid": self.client_id
        }

        d = await self.get(self.STICKY.format(self.pull_channel), params=params, as_json=True)

        lb = d.get("lb_info")
        if lb:
            self.sticky = lb["sticky"]
            self.pool = lb["pool"]
        else:
            raise error.HTTPException("Fetch sticky failed.")

    async def ping(self):
        params = {
            "channel": self.user_channel,
            "clientid": self.client_id,
            "partition": -2,
            "cap": 0,
            "uid": self.user_id,
            "sticky_token": self.sticky,
            "sticky_pool": self.pool,
            "viewer_uid": self.user_id,
            "state": "active"
        }
        return await self.get(self.PING.format(self.pull_channel), params=params)

    async def pull(self):
        params = {
            "msgs_recv": 0,
            "sticky_token": self.sticky,
            "sticky_pool": self.pool,
            "clientid": self.client_id,
            "state": "active"
        }

        d = await self.get(self.STICKY.format(self.pull_channel), params=params, timeout=15, as_json=True)
        self.seq = d.get("seq", "0")

        return d

    async def fetch_image_url(self, image_id):
        data = await self.get(self.ATTACHMENT_PHOTO, params={"photo_id": image_id}, as_json=True)
        url = get_jsmods_require(data, 3)
        if url:
            return url
        else:
            raise error.UnexpectedResponse("Cannot find image url.")

    async def graphql_request(self, *queries):
        data = {}
        for i, query in enumerate(queries):
            data["q{}".format(i)] = query.value
        d = {
            "method": "GET",
            "response_format": "json",
            "queries": json.dumps(data)
        }
        batch = await self.post(self.GRAPHQL, data=d, as_json=True, json_decoder=load_concat_json)
        return batch

    async def fetch_threads(self, *thread_ids):
        queries = []
        for tid in thread_ids:
            queries.append(GraphQL.fetch_thread_info(tid))

        ret = await self.graphql_request(*queries)
        return list(ret[0].values())

    async def fetch_users(self, *user_ids):
        queries = {"ids[{}]".format(i): uid for i, uid in enumerate(user_ids)}

        data = await self.post(self.USER_INFO, data=queries, as_json=True)
        return data["payload"]["profiles"]

    async def mark_seen(self):
        #this actually mark as seeing message notification
        await self.post(self.MARK_SEEN, data={"seen_timestamp": 0})

    async def change_read_status(self, status, thread_id):
        data = {
            "ids[{}]".format(thread_id): "true" if status else "false",
            "watermarkTimestamp": now(),
            "shouldSendReadReceipt": "true"
        }
        await self.post(self.READ_STATUS, data=data)

    async def mark_as_read(self, thread_id):
        #this is the true infamous "seen"
        await self.change_read_status(True, thread_id)

    async def mark_folder_as_read(self, folder):
        if folder in ("inbox", "archieved", "pending"):
            await self.post(self.MARK_FOLDER_AS_READ, data={"folder": folder})


