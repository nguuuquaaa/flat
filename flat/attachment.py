from .base import *
import asyncio

#==================================================================================================================================================

class _BaseAttachment(Object):
    pass

class FileAttachment(_BaseAttachment):
    @property
    def filename(self):
        return self._filename

class ImageAttachment(FileAttachment):
    @property
    def animated(self):
        return self._animated

    async def get_url(self):
        if self._url is None:
            self._url = await self._state.http.fetch_image_url(self._id)
        return self._url

    async def save(self):
        url = await self.get_url()
        return await self._state.http.get(url)

class AudioAttachment(FileAttachment):
    pass

class VideoAttachment(FileAttachment):
    pass

class Sticker(_BaseAttachment):
    pass

class EmbedLink(_BaseAttachment):
    @property
    def url(self):
        return self._url

#==================================================================================================================================================

try:
    from PIL import Image
except:
    pass
else:
    from io import BytesIO

    async def to_gif(self, fp, *, executor=None, loop=None):
        resp = await self._state.http.session.get(self._url)
        im = BytesIO(await resp.read())
        frames = []
        row_count = self._row_count
        column_count = self._column_count
        frame_count = self._frame_count
        duration = self._frame_rate

        def do_stuff():
            image = Image.open(im)
            img_width, img_height = image.size
            width = img_width/column_count
            height = img_height/row_count
            frames = []
            count = 0

            for y_count in range(row_count):
                y = y_count * height
                for x_count in range(column_count):
                    x = x_count * width
                    raw = image.crop((x, y, x+width, y+height))
                    frames.append(raw)
                    count += 1
                    if count == frame_count:
                        break
                else:
                    continue
                break

            frames[0].save(fp, "gif", save_all=True, append_images=frames[1:], loop=0, duration=duration, transparency=255, disposal=2, optimize=False)

        loop = loop or asyncio.get_event_loop()
        await loop.run_in_executor(executor, do_stuff)

    Sticker.to_gif = to_gif
