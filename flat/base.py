#==================================================================================================================================================

class Object:
    def __init__(self, id, **kwargs):
        self._id = id
        for key, value in kwargs.items():
            setattr(self, key, value)

    @property
    def id(self):
        return self._id

    def __eq__(self, other):
        return isinstance(other, self.__class__) and other.id == self.id

    def __ne__(self, other):
        return not (isinstance(other, self.__class__) and other.id == self.id)

    def __hash__(self):
        return hash(self._id)

#==================================================================================================================================================

class Messageable:
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    async def send(self, content):
        raw_messages = await self._state.http.send_message(self, content)
        return [await self._state.parse_send_message(rm, content) for rm in raw_messages]

class OneToOneMixin(Messageable):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def to_dict(self):
        return {"other_user_fbid": self._id}

class GroupMixin(Messageable):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def to_dict(self):
        return {"thread_fbid": self._id}
