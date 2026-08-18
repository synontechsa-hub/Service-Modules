class LicensingError(Exception):
    """Base exception for licensing errors."""
    pass

class LicenseNotFoundError(LicensingError):
    """Raised when a license key cannot be found."""
    pass

class PoolEmptyError(LicensingError):
    """Raised when the pre-generated license pool is empty."""
    pass

class IssuanceFailedError(LicensingError):
    """Raised when license issuance fails after multiple attempts."""
    pass

class TrialAlreadyStartedError(LicensingError):
    """Raised when trying to start a trial for a license that already has one."""
    pass
