

#==================================================================================================================================================

class FBException(Exception):
    def __init__(self, message):
        self.message = message
        
    def __str__(self):
        return "<{}: {}>".format(self.__class__.__name__, self.message)

#==================================================================================================================================================

class HTTPException(FBException):
    pass

class LoginError(HTTPException):
    pass
    
class SendFailure(HTTPException):
    pass