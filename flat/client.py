from . import http, state, user
import asyncio
import traceback
import inspect
import sys

#==================================================================================================================================================

class Client:
    def __init__(self, *, loop=None, max_messages=1000):
        self.loop = loop or asyncio.get_event_loop()

        self._wait_events = {}
        self._form_events = {}
        self._running = asyncio.Event()
        self._ready = asyncio.Event()
        self._max_messages = max_messages

        for name, member in inspect.getmembers(self):
            if name.startswith("on_"):
                ev_name = name[3:]
                if ev_name in self._form_events:
                    self._form_events[ev_name].append(member)
                else:
                    self._form_events[ev_name]= [member]

    def dispatch(self, name, *args):
        wait_events = self._wait_events.get(name)
        if wait_events:
            removed = []
            for i, ev in enumerate(wait_events):
                fut = ev[0]
                check = ev[1]
                try:
                    r = check(*args)
                except Exception as e:
                    fut.set_exception(e)
                    removed.append(i)
                else:
                    if r:
                        if len(args) == 0:
                            fut.set_result(None)
                        elif len(args) == 1:
                            fut.set_result(args[0])
                        else:
                            fut.set_result(args)
                        removed.append(i)

            if len(removed) == len(wait_events):
                self._wait_events.pop(name)
            else:
                for i in reversed(removed):
                    wait_events.pop(i)

        events = self._form_events.get(name)
        if events:
            for ev in events:
                self.loop.create_task(self._wrap_error(name, ev, *args))

    async def _wrap_error(self, name, event, *args):
        try:
            await event(*args)
        except asyncio.CancelledError:
            pass
        except:
            try:
                await self.on_error(name, *args)
            except asyncio.CancelledError:
                pass

    async def on_error(self, event, *args):
        print("Ignoring exception in {}\n{}".format(event, traceback.format_exc()), file=sys.stderr)

    def is_running(self):
        return self._running.is_set()

    def initialize(self, username, password):
        self._http = http.HTTPRequest(username, password, loop=self.loop)
        self._state = state.State(loop=self.loop, http=self._http, dispatch=self.dispatch, max_messages=self._max_messages)

    async def start(self, username, password):
        self._running.set()
        self.initialize(username, password)
        self.dispatch("start")
        await self._http.login()
        await self._http.fetch_sticky()
        self._user = self._state.get_user(self._http.user_id, cls=user.User)
        self.dispatch("ready")

        while self.is_running():
            try:
                await self._http.ping()
                raw = await self._http.pull()
            except (asyncio.TimeoutError, ConnectionError):
                continue
            except:
                traceback.print_exc()
                await asyncio.sleep(10)
            else:
                try:
                    self._state.process_raw_data(raw)
                except:
                    traceback.print_exc()

    def run(self, username, password):
        try:
            self.loop.run_until_complete(self.start(username, password))
        except KeyboardInterrupt:
            pass
        finally:
            self.loop.run_until_complete(self._http.logout())
            self.loop.run_until_complete(self._cleanup())
            self.loop.close()

    async def _cleanup(self):
        await self._http.cleanup()

    async def on_ready(self):
        print("listening...")

    @property
    def user(self):
        return self._user

