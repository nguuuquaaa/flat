import time
import json
import random
import re
import functools

#==================================================================================================================================================

_WHITESPACE = re.compile(r"[ \t\n\r]*", re.VERBOSE|re.MULTILINE|re.DOTALL)

class ConcatJSONDecoder(json.JSONDecoder):
    def decode(self, s, _w=_WHITESPACE.match):
        s_len = len(s)

        objs = []
        end = 0
        while end != s_len:
            obj, end = self.raw_decode(s, idx=_w(s, end).end())
            end = _w(s, end).end()
            objs.append(obj)
        return objs

load_concat_json = functools.partial(json.loads, cls=ConcatJSONDecoder)

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

def get_jsmods_require(j, index):
    jsmods = j.get("jsmods")
    if jsmods:
        rq = jsmods.get("require")
        if rq:
            try:
                return rq[0][index][0]
            except (KeyError, IndexError):
                pass
    return None