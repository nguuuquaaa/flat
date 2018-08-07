from . import base
import asyncio


class _BaseAttachment(base.Object):
    pass
    
class FileAttachment(_BaseAttachment):
    pass
    
class ImageAttachment(FileAttachment):
    @property
    def preview_url(self):
        return self._preview_url

class Sticker(_BaseAttachment):
    pass

#==================================================================================================================================================

try:
    from PIL import Image
except:
    pass
else:
    from io import BytesIO

    async def to_gif(self, fp, *, executor=None, loop=None):
        bytes_ = await self._state.http.session.get(self._url)
        frames = []
        frame_width = self._width
        frame_height = self._height

        def do_stuff():
            image = Image.open(BytesIO(bytes_))
            width, height = image.size
            for y in range(0, height, frame_height):
                for x in range(0, width, frame_width):
                    f = Image.new("RGB", (frame_height, frame_width), (255, 255, 255))
                    cur = image.crop((x, y, x+frame_width, y+frame_height))
                    f.paste(cur, (0, 0), cur)
                    frames.append(f)

            frames[0].save(fp, "gif", save_all=True, append_images=frames[1:], loop=0, duration=self._frame_rate, optimize=True)

        loop = loop or asyncio.get_event_loop()
        await loop.run_in_executor(executor, do_stuff)

    Sticker.to_gif = to_gif
