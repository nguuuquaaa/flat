import flat

class Bot(flat.Client):
    async def on_message(self, message):
        #do not response to self message
        if message.author.id == self.user.id:
            return

        text = message.text
        thread = message.thread
        if text == "ping":
            await thread.send("pong")

        if text == "hi":
            #response with "hi @author"
            ctn = flat.Content()
            ctn.write("hi ")
            ctn.mention(message.author)
            await thread.send(ctn)

        elif text == "url":
            #response with an url embed for google homepage
            ctn = flat.Content()
            ctn.write("this is the url of google: ")
            ctn.embed_link("https://www.google.com", append=True)
            await thread.send(ctn)

#cookies saving/loading only works with elevated permissions
bot = Bot(save_cookies="cookies.pkl")
email = "this_is@my.email"
password = "this is my password"
bot.run(email, password, load_cookies="cookies.pkl")
