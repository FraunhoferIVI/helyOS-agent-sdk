
    

class HelyOSAnonymousConnectionError(Exception):
    """ Raised on anonymous connection during checkin procedure. """
    pass

class HelyOSClientAutheticationError(Exception):
    """ Raised if is not yet authenticated. """
    pass

class HelyOSCheckinError(Exception):
    """ Raised on check in errors. """
    pass
