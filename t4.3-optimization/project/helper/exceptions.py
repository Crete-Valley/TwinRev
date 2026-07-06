class OptimizationError(Exception):
    """Raised when the optimization model fails to converge."""
    pass

class PriceValidationError(Exception):
    """Raised when price data from Excel is invalid or malformed."""
    pass

class ResourceReadingError(Exception):
    """Raised when a resource cannot be correctly read."""
    pass

class ResourceInitializationError(Exception):
    """Raised when a resource cannot be correctly initialized."""
    pass

class DataLoadingError(Exception):
    """Raised when loading data files fails."""
    pass