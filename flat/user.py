from . import base


#==================================================================================================================================================

class _BaseUser(base.Object, base.OneToOneMixin, base.Partial):
    pass

class User(_BaseUser):
    pass

class Page(_BaseUser):
    pass
