class DomainError(Exception):
    """Base class for all domain-level errors."""


class DocumentParsingError(DomainError):
    """Raised when a PDF/DOCX cannot be parsed or is structurally invalid."""


class RetrievalError(DomainError):
    """Raised when vector retrieval fails or returns no usable results."""


class GroundingViolationError(DomainError):
    """
    Raised when the Validation Agent detects the LLM produced a claim that
    cannot be traced to any retrieved chunk. This should short-circuit the
    graph into the 'insufficient information' response path, not just log.
    """


class PromptInjectionDetectedError(DomainError):
    """Raised by the security layer when user input matches injection heuristics."""


class ConfigurationError(DomainError):
    """Raised on missing/invalid environment configuration at startup."""
