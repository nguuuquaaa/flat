import aiohttp
import asyncio
from bs4 import BeautifulSoup as BS
from . import error, utils, content
import random
import re
import json

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
except:
    PARSER = "html.parser"
else:
    PARSER = "lxml"

#==================================================================================================================================================

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

    @classmethod
    def get_query_data(cls, *, query={}, params={}, doc_id=None):
        if query:
            return {
                "priority": 0,
                "q": query,
                "query_params": params
            }
        elif doc_id:
            return {
                "doc_id": doc_id,
                "query_params": params
            }
        else:
            raise ValueError

#==================================================================================================================================================

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
    STICKY = "https://0-edge-chat.facebook.com/pull"
    PING = "https://0-edge-chat.facebook.com/active_ping"
    UPLOAD = "https://upload.facebook.com/ajax/mercury/upload.php"
    INFO = "https://www.facebook.com/chat/user_info/"
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
    MESSAGE_REACTION = "https://www.facebook.com/webgraphql/mutation"
    TYPING = "https://www.facebook.com/ajax/messaging/typ.php"
    GRAPHQL = "https://www.facebook.com/api/graphqlbatch/"
    ATTACHMENT_PHOTO = "https://www.facebook.com/mercury/attachments/photo/"
    EVENT_REMINDER = "https://www.facebook.com/ajax/eventreminder/create"
    MODERN_SETTINGS_MENU = "https://www.facebook.com/bluebar/modern_settings_menu/"
    REMOVE_FRIEND = "https://m.facebook.com/a/removefriend.php"

    def __init__(self, username, password, *, loop=None, user_agent=None):
        if username and password:
            self.username = username
            self.password = password
        else:
            raise error.LoginError("Username and password must be non-empty.")
        self.loop = loop or asyncio.get_event_loop()
        self.pull_channel = 0
        self.client = "mercury"
        self.headers = {
            "Content-Type" : 'application/x-www-form-urlencoded',
            "Referer": self.BASE,
            "Origin": self.BASE,
            "User-Agent": user_agent or random.choice(USER_AGENTS),
            "Connection": "keep-alive",
        }
        self.clear()

    def clear(self):
        self.session = aiohttp.ClientSession(loop=self.loop)
        self.params = {}
        self.request_counter = 1
        self.seq = "0"

    async def cleanup(self):
        await self.session.close()

    def update_params(self, extra={}):
        params = self.params.copy()
        params["__req"] = utils.str_base(self.request_counter)
        params["seq"] = self.seq
        params.update(extra)
        return params

    async def get(self, url, *, headers=None, params=None, timeout=30, as_json=False, json_decoder=utils.load_broken_json, **kwargs):
        headers = headers or self.headers
        params = self.update_params(params or {})
        self.request_counter += 1
        async with self.session.get(url, headers=headers, params=params, timeout=timeout, **kwargs) as response:
            bytes_ = await response.read()
            if as_json:
                return json_decoder(bytes_)
            else:
                return bytes_

    async def post(self, url, *, headers=None, data=None, timeout=30, as_json=False, json_decoder=utils.load_broken_json, **kwargs):
        headers = headers or self.headers
        data = self.update_params(data or {})
        self.request_counter += 1
        async with self.session.post(url, headers=headers, data=data, timeout=timeout, **kwargs) as response:
            bytes_ = await response.read()
            if as_json:
                return json_decoder(bytes_)
            else:
                return bytes_

    async def login(self):
        bytes_ = await self.get(self.MOBILE)
        soup = BS(bytes_.decode("utf-8"), PARSER)
        data = {tag["name"]: tag["value"] for tag in soup.find_all("input") if "name" in tag.attrs and "value" in tag.attrs}
        data["email"] = self.username
        data["pass"] = self.password
        data["login"] = "Log In"

        self.request_counter += 1

        resp = await self.session.post(self.LOGIN, headers=self.headers, data=data)

        if "checkpoint" in resp.url.human_repr():
            bytes_ = await resp.read()
            resp = await self.handle_2FA(bytes_)

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
        self.start_time = utils.now()
        for cookie in self.session.cookie_jar:
            if cookie.key == "c_user":
                self.user_id = int(cookie.value)
                break
        else:
            raise error.LoginError("Cannot find c_user cookie.")
        self.user_channel = "p_" + str(self.user_id)
        self.ttstamp = ""

        bytes_ = await self.get(self.BASE)
        html = bytes_.decode("utf-8")
        with open("test.html", "w", encoding="utf-8") as f:
            f.write(html)
        soup = BS(html, PARSER)

        fb_dtsg = soup.find("input", attrs={"name": "fb_dtsg"})
        if fb_dtsg:
            self.fb_dtsg = fb_dtsg["value"]
        else:
            m = re.search(r"name=\"fb_dtsg\"\svalue=\"(.?*)\"", r.text)
            self.fb_dtsg = m.group(1)

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

        self.prev = utils.now()
        self.tmp_prev = utils.now()
        self.last_sync = utils.now()

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
        otid = utils.generate_offline_threading_id()
        data = {
            "client": self.client,
            "author": "fbid:" + str(self.user_id),
            "timestamp": utils.now(),
            "source": "source:chat:web",
            "offline_threading_id": otid,
            "message_id": otid,
            "ephemeral_ttl_mode": "0"
        }

        data.update(dest.to_dict())
        data.update(ctn.to_dict())

        d = await self.post(self.SEND, data=data, as_json=True)
        try:
            return [m for m in d["payload"]["actions"] if m]
        except KeyError:
            #raise error.SendFailure("Facebook didn't return any message.")
            print(json.dumps(d, indent=4))

    async def graphql_request(self, data):
        return await self.post(self.GRAPHQL, data=data, as_json=True, json_decoder=utils.load_concat_json)

    async def fetch_sticky(self):
        params = {
            "msgs_recv": 0,
            "channel": self.user_channel,
            "clientid": self.client_id
        }

        d = await self.get(self.STICKY, params=params, as_json=True)

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
        await self.get(self.PING, params=params)

    async def pull(self):
        params = {
            "msgs_recv": 0,
            "sticky_token": self.sticky,
            "sticky_pool": self.pool,
            "clientid": self.client_id,
        }

        d = await self.get(self.STICKY, params=params, timeout=15, as_json=True)
        self.seq = d.get("seq", "0")

        return d
