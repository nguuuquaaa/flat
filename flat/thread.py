from . import base, content, error, participant, user

#==================================================================================================================================================

class _BaseThread(base.Object, base.Messageable, base.Partial):
    pass

class OneToOne(_BaseThread, base.OneToOneMixin):
    @property
    def recipient(self):
        return self._recipient

class Group(_BaseThread, base.GroupMixin):
    @property
    def participants(self):
        return list(self._participants.value())

    def get_participant(self, id):
        if self._partial:
            state = self._state
            return participant.Participant(id, state=state, partial=True, user=state.get_user(id, cls=user.User))
        else:
            return self._participants.get(id)
