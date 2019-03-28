from . import base, enums

#==================================================================================================================================================

class _BaseUser(base.Object):
    pass

class UnavailableUser(_BaseUser):
    pass

FACEBOOK_USER = UnavailableUser("0")

class User(_BaseUser, base.OneToOneMixin):
    @classmethod
    def from_data(cls, state, data):
        if data["id"] == 0:
            return FACEBOOK_USER
        else:
            return cls(
                data["id"],
                _state=state,
                full_name=data["name"],
                first_name=data["firstName"],
                gender=enums.Gender(data["gender"]),
                alias=data["alternateName"] or None,
                thumbnail=data["thumbSrc"],
                url=data["uri"],
                is_friend=data["is_friend"]
            )

class Page(_BaseUser, base.OneToOneMixin):
    @classmethod
    def from_data(cls, state, data):
        if data["id"] == 0:
            return FACEBOOK_USER
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
