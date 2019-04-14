from . import base, user, participant, content, error

#==================================================================================================================================================

def _get_emoji_and_color(data):
    customization = data["customization_info"]
    if customization:
        emoji = customization["emoji"]
        try:
            color = int(customization["outgoing_bubble_color"][2:], 16)
        except ValueError:
            color = None
    else:
        emoji = None
        color = None
    return emoji, color

#==================================================================================================================================================

class _BaseThread(base.Object):
    @property
    def me(self):
        return self._me

    async def seen(self):
        await self._state.http.mark_as_read(self._id)

#==================================================================================================================================================

class OneToOne(_BaseThread, base.OneToOneMixin):
    @classmethod
    def from_data(cls, state, data):
        thread_id = data["thread_key"]["other_user_id"]
        emoji, color = _get_emoji_and_color(data)
        return cls(
            thread_id,
            _state=state,
            emoji=emoji,
            color=color
        )

    @property
    def recipient(self):
        return self._recipient

    def store_recipient(self, user, *, nickname=None):
        p = participant.Participant(_state=self._state, user=user, thread=self, admin=None, nickname=nickname)
        self._recipient = p
        return p

    def store_me(self, *, nickname=None):
        cu = self._state.client_user
        p = participant.Participant(_state=self._state, user=cu, thread=self, admin=None, nickname=nickname)
        self._me = p
        return p

    def get_participant(self, pid):
        return self._me if pid==self._me.id else self._recipient if pid==self._recipient.id else None

class Group(_BaseThread, base.GroupMixin):
    @classmethod
    def from_data(cls, state, data):
        thread_id = data["thread_key"]["thread_fbid"]
        emoji, color = _get_emoji_and_color(data)
        raw_image = data["image"]
        if raw_image:
            image_url = raw_image["uri"]
        else:
            image_url = None
        return cls(
            thread_id,
            _state=state,
            image_url=image_url,
            emoji=emoji,
            color=color,
            approval_mode=data["approval_mode"],
            _participants={}
        )

    @property
    def participants(self):
        return list(self._participants.value())

    def store_participant(self, user, *, admin=False, nickname=None):
        p = participant.Participant(_state=self._state, user=user, thread=self, admin=admin, nickname=nickname)
        self._participants[user.id] = p
        return p

    def store_me(self, *, admin=False, nickname=None):
        cu = self._state.client_user
        cuid = cu.id
        if cuid in self._participants:
            self._me = self._participants[cuid]
            return self._me
        else:
            me = participant.Participant(_state=self._state, user=cu, thread=self, admin=admin, nickname=nickname)
            self._participants[cuid] = me
            self._me = me
            return me

    def get_participant(self, pid):
        return self._participants.get(pid)
