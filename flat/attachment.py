from . import base, utils
import asyncio
from yarl import URL

#==================================================================================================================================================

def _may_has_extension(filename):
    if filename.partition(".")[1]:
        return filename
    else:
        ext, hyph, name = filename.partition("-")
        return name + "." + ext

#==================================================================================================================================================

class _BaseAttachment(base.Object):
    pass

class FileAttachment(_BaseAttachment):
    @classmethod
    def _extract_data(cls, node):
        return {"url": node.get("url")}

    @classmethod
    def from_data(cls, state, node):
        aid = node["legacy_attachment_id"]
        filename = _may_has_extension(node["filename"])
        return cls(aid, _state=state, filename=filename, **cls._extract_data(node))

class ImageAttachment(FileAttachment):
    @classmethod
    def _extract_data(cls, node):
        xy = node["original_dimensions"]
        try:
            url = node["animated_image"]["uri"]
            animated = True
        except KeyError:
            url = None
            animated = False
        return {
            "url": url,
            "animated": animated,
            "height": xy["y"],
            "width": xy["x"]
        }

    async def get_url(self):
        if self.url is None:
            self.url = await self._state.http.fetch_image_url(self._id)
        return self.url

    async def save(self):
        url = await self.get_url()
        return await self._state.http.get(url)

class AudioAttachment(FileAttachment):
    @classmethod
    def _extract_data(cls, node):
        return {
            "url": node["playable_url"],
            "duration": node["playable_duration_in_ms"]
        }

class VideoAttachment(FileAttachment):
    @classmethod
    def _extract_data(cls, node):
        xy = node["original_dimensions"]
        return {
            "url": node["playable_url"],
            "duration": node["playable_duration_in_ms"],
            "height": xy["y"],
            "width": xy["x"]
        }

class Sticker(_BaseAttachment):
    @classmethod
    def from_data(cls, state, node):
        sid = node["id"]
        label = node["label"]
        width = node["width"]
        height = node["height"]
        column_count = node["frames_per_row"]
        row_count = node["frames_per_column"]
        frame_count = node["frame_count"]
        frame_rate = node["frame_rate"]
        preview_url = node["url"]
        raw_ = utils.get_either(node, "sprite_image_2x", "padded_sprite_image_2x", "sprite_image", "padded_sprite_image")
        try:
            url = raw_["uri"]
        except TypeError:
            url = None

        return cls(
            sid, _state=state, label=label, url=url, width=width, height=height, column_count=column_count,
            row_count=row_count, frame_count=frame_count, frame_rate=frame_rate
        )

class EmbedLink(_BaseAttachment):
    @classmethod
    def from_data(cls, state, node):
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

        return cls(eid, _state=state, url=url, title=title, description=desc, media_url=media_url)

#==================================================================================================================================================

try:
    from PIL import Image
except ImportError:
    pass
else:
    from io import BytesIO

    async def _to_gif(self, fp, *, executor=None, loop=None):
        bytes_ = await self._state.http.get(self.url)
        im = BytesIO(bytes_)
        frames = []
        row_count = self.row_count
        column_count = self.column_count
        frame_count = self.frame_count
        duration = self.frame_rate

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

    Sticker.to_gif = _to_gif
