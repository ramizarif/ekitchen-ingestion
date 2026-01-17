"""Custom exceptions for Spoonacular API client"""


class SpoonacularError(Exception):
    """Base exception for all Spoonacular API errors"""
    
    def __init__(self, message: str, status_code: int = None, response_data: dict = None):
        super().__init__(message)
        self.status_code = status_code
        self.response_data = response_data or {}


class SpoonacularAuthError(SpoonacularError):
    """Authentication/authorization error (401, 403)"""
    pass


class SpoonacularRateLimitError(SpoonacularError):
    """Rate limit exceeded error (429)"""
    
    def __init__(self, message: str, retry_after: int = None, **kwargs):
        super().__init__(message, **kwargs)
        self.retry_after = retry_after


class SpoonacularNotFoundError(SpoonacularError):
    """Resource not found error (404)"""
    pass


class SpoonacularNetworkError(SpoonacularError):
    """Network/connectivity error"""
    pass


class SpoonacularConfigError(SpoonacularError):
    """Configuration error"""
    pass