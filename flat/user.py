from .base import *

#==================================================================================================================================================

class _BaseUser(Object, OneToOneMixin):
    @property
    def name(self):
        return self._name

    full_name = name

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
