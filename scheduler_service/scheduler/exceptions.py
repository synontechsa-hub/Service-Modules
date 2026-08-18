class SchedulerError(Exception):
    """Base exception for scheduler errors."""
    pass

class JobNotFoundError(SchedulerError):
    """Raised when a job cannot be found."""
    pass

class ClaimFailedError(SchedulerError):
    """Raised when claiming a job fails."""
    pass
