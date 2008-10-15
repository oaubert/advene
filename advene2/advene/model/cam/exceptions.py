"""
I define exceptions used in the Cinelab Application Model.
"""

class UnsafeUseWarning(Warning):
    """
    Issued whenever a method inherited from the core model is used in an
    unsafe way w.r.t. the Cinelab Application Model. This means that the CAM
    prescribes a specific way to use the method, and provides secialized
    method complying with those prescriptions.
    """
    pass

class SemanticError(Exception):
    """
    Raised whenever a CAM specific metadata is used in an inconsistent way.
    """
    pass
