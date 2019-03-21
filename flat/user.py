from .base import *
from .enums import *

#==================================================================================================================================================

class _BaseUser(Object, OneToOneMixin):
    pass

class UnavailableUser(_BaseUser):
    pass

UNAVAILABLE_USER = UnavailableUser("0")

class User(_BaseUser):
    @classmethod
    def from_data(cls, state, data):
        if data["id"] == 0:
            return UNAVAILABLE_USER
        else:
            return cls(
                data["id"],
                _state=state,
                full_name=data["name"],
                first_name=data["firstName"],
                gender=Gender(data["gender"]),
                alias=data["alternateName"] or None,
                thumbnail=data["thumbSrc"],
                url=data["uri"],
                is_friend=data["is_friend"]
            )

class Page(_BaseUser):
    @classmethod
    def from_data(cls, state, data):
        if data["id"] == 0:
            return UNAVAILABLE_USER
        else:
            return cls(
                data["id"],
                _state=state,
                name=data["name"],
                category=data["gender"],
                thumbnail=data["thumbSrc"],
                url=data["uri"]
            )

class _ClientPrivilege:
    pass

class ClientUser(User, _ClientPrivilege):
    pass

class ClientPage(Page, _ClientPrivilege):
    pass
