from .base import *

#==================================================================================================================================================

class _BaseUser(Object, OneToOneMixin):
    pass

class User(_BaseUser):
    @property
    def full_name(self):
        return self._full_name

    @property
    def name(self):
        return self._full_name

    @property
    def first_name(self):
        return self._first_name

    @property
    def gender(self):
        return self._gender

    @property
    def alias(self):
        return self._alias

class Page(_BaseUser):
    @property
    def name(self):
        return self._name

class _ClientPrivilege:
    pass

class ClientUser(User, _ClientPrivilege):
    pass

class ClientPage(Page, _ClientPrivilege):
    pass
