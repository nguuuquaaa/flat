#==================================================================================================================================================

class Object:
    def __init__(self, id, **kwargs):
        self._id = id
        for key, value in kwargs.items():
            setattr(self, "_"+key, value)

    @property
    def id(self):
        return self._id

    def __eq__(self, other):
        return isinstance(other, self.__class__) and other.id == self.id

    def __ne__(self, other):
        return not (isinstance(other, self.__class__) and other.id == self.id)

#==================================================================================================================================================

class Messageable:
    async def send(self, ctn):
        return await self._state.http.send_message(self, ctn)

class Partial:
    @property
    def partial(self):
        return self._partial

class OneToOneMixin:
    def to_dict(self):
        return {"other_user_fbid": self._id}

class GroupMixin:
    def to_dict(self):
        return {"thread_fbid": self._id}
