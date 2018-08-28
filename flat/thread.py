from .base import *
from .content import Content
from .error import *
from .participant import Participant
from .user import *

#==================================================================================================================================================

class _BaseThread(Object):
    @property
    def me(self):
        return self._me


class OneToOne(_BaseThread, OneToOneMixin):
    @property
    def recipient(self):
        return self._recipient

    def store_recipient(self, user, *, nickname=None):
        if isinstance(user, Page):
            self._recipient = user
        else:
            self._recipient = Participant(user.id, state=self._state, user=user, thread=self, admin=None, nickname=nickname)

    def store_me(self, *, nickname=None):
        cu = self._state.client_user
        if isinstance(cu, ClientPage):
            self._me = cu
        else:
            self._me = Participant(cu.id, state=self._state, user=cu, thread=self, admin=None, nickname=nickname)

    def get_participant(self, pid):
        return self._me if pid==self._me.id else self._recipient if pid==self._recipient.id else None

class Group(_BaseThread, GroupMixin):
    @property
    def participants(self):
        return list(self._participants.value())

    def store_participant(self, user, *, admin=False, nickname=None):
        self._participants[user.id] = Participant(user.id, state=self._state, user=user, thread=self, admin=admin, nickname=nickname)

    def store_me(self, *, admin=False, nickname=None):
        cu = self._state.client_user
        cuid = cu.id
        if cuid in self._participants:
            self._me = self._participants[cuid]
        else:
            me = Participant(cuid, state=self._state, user=cu, thread=self, admin=admin, nickname=nickname)
            self._participants[cuid] = me
            self._me = me

    def get_participant(self, pid):
        return self._participants.get(pid)
