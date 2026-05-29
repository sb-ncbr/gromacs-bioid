class CriticalStepError(Exception):
    def __init__(self, message, code=None, details=None):
        super().__init__(message)
        self.code = code or "critical_step_error"
        self.details = details or {}


class PreconditionFailedError(Exception):
    pass


class PostconditionFailedError(Exception):
    pass
