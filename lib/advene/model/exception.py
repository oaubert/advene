class AdveneException (Exception):
    """
    Advene-specific exception.
    
    Appart from being a specific class,
    this class is absolutely homogeneous to Exception.
    """
    pass

class AdveneValueError (AdveneException, ValueError):
    """
    Advene-specific value error.
    """
    pass
