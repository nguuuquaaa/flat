import flat
import asyncio
import json
import discord
import aiohttp
import sys
import datetime

class Bot(flat.Client):
    def __init__(self, *args, **kwargs):
        super().__init__()

    def log(self, data):
        s = json.dumps(data, indent=4, ensure_ascii=False)
        now = datetime.datetime.now()
        with open(now.strftime("log/log_%Y-%m-%d_%H-%M-%S.%f.json"), "w", encoding="utf-8") as f:
            f.write(s)

    async def on_raw_message(self, raw_message):
        #self.log(raw_message)
        pass

    async def on_message(self, message):
        if message.author.id == self.user.id:
            return

        #echo text, mentions, bigmoji, sticker and file
        ctn = flat.Content.from_message(message)
        await message.thread.send(ctn)


bot = Bot()
with open("cres.txt") as f:
    c = f.read().splitlines()
bot.run(c[0], c[1])
