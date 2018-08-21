from . import http, state, user
import asyncio
import traceback
import inspect
import sys
import logging

log = logging.getLogger(__name__)

#==================================================================================================================================================

class Client:
    '''
    This is heavily influenced by discord.py, or more like most are blatantly copy-pasted.
    '''
    def __init__(self, *, loop=None, max_messages=1000):
        self.loop = loop or asyncio.get_event_loop()

        self._wait_events = {}
        self._form_events = {}
        self._closed = asyncio.Event()
        self._ready = asyncio.Event()
        self._max_messages = max_messages

        for name, member in inspect.getmembers(self):
            if name.startswith("on_"):
                ev_name = name[3:]
                if ev_name in self._form_events:
                    self._form_events[ev_name].append(member)
                else:
                    self._form_events[ev_name] = [member]

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
        return not self._closed.is_set()

    def _do_cleanup(self):
        log.info("Cleaning up event loop.")
        loop = self.loop
        if loop.is_closed():
            return # we're already cleaning up

        task = loop.create_task(self.close())

        def _silence_gathered(fut):
            try:
                fut.result()
            except:
                pass
            finally:
                loop.stop()

        def when_future_is_done(fut):
            pending = asyncio.Task.all_tasks(loop=loop)
            if pending:
                log.info("Cleaning up after %s tasks", len(pending))
                gathered = asyncio.gather(*pending, loop=loop)
                gathered.cancel()
                gathered.add_done_callback(_silence_gathered)
            else:
                loop.stop()

        task.add_done_callback(when_future_is_done)
        if not loop.is_running():
            loop.run_forever()
        else:
            # on Linux, we're still running because we got triggered via
            # the signal handler rather than the natural KeyboardInterrupt
            # Since that's the case, we're going to return control after
            # registering the task for the event loop to handle later
            return None

        try:
            return task.result() # suppress unused task warning
        except:
            return None

    async def start(self, email, password):
        self._closed.clear()
        self._http = http.HTTPRequest(loop=self.loop)
        self._state = state.State(loop=self.loop, http=self._http, dispatch=self.dispatch, max_messages=self._max_messages)
        self.dispatch("start")
        await self._http.login(email, password)
        await self._http.fetch_sticky()
        self._user = self._state.get_user(self._http.user_id, cls=user.User)
        self._ready.set()
        self.dispatch("ready")

        def retry():
            t = 0
            while True:
                if t < 60:
                    yield t
                    t += 10
                else:
                    yield 60

        retry_after = retry()

        while self.is_running():
            try:
                await self._http.ping()
                raw = await self._http.pull()
            except (asyncio.TimeoutError, ConnectionError):
                continue
            except asyncio.CancelledError:
                return
            except:
                traceback.print_exc()
                await asyncio.sleep(next(retry_after))
            else:
                self.loop.create_task(self._state.process_raw_data(raw))

    def run(self, *args, **kwargs):
        is_windows = sys.platform == 'win32'
        loop = self.loop
        if not is_windows:
            loop.add_signal_handler(signal.SIGINT, self._do_cleanup)
            loop.add_signal_handler(signal.SIGTERM, self._do_cleanup)

        task = self.loop.create_task(self.start(*args, **kwargs))

        def stop_loop_on_finish(fut):
            loop.stop()

        task.add_done_callback(stop_loop_on_finish)

        try:
            loop.run_forever()
        except KeyboardInterrupt:
            log.info("Received signal to terminate bot and event loop.")
        finally:
            task.remove_done_callback(stop_loop_on_finish)
            if is_windows:
                self._do_cleanup()

            loop.close()
            if task.cancelled() or not task.done():
                return None
            return task.result()

    async def close(self):
        await self._http.logout()
        await self._http.close()
        self._closed.set()
        self._ready.clear()

    async def on_ready(self):
        print("listening...")

    @property
    def user(self):
        return self._user

