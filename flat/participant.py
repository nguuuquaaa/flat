from . import base


#==================================================================================================================================================

class Participant(base.Object, base.Partial):
    @property
    def thread(self):
        return self._thread
        
        
    