from .base import *

#==================================================================================================================================================

class _BaseUser(Object, OneToOneMixin):
    @property
    def full_name(self):
        return self._full_name
        
    @property
    def name(self):
        return self._full_name

    @property
    def first_name(self):
        return self._first_name

class User(_BaseUser):
    pass

class Page(_BaseUser):
    pass

class _ClientPrivilege:
    pass

class ClientUser(User, _ClientPrivilege):
    pass

class ClientPage(Page, _ClientPrivilege):
    pass
