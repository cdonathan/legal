"""
Custom exceptions for the SeedJura Agreement Summary app.
Each carries a user-friendly message that can be shown in the UI.
"""


class ProcessingError(Exception):
    """Base class for all processing errors. Carries a user-friendly message."""
    def __init__(self, message: str, detail: str = ""):
        self.message = message
        self.detail = detail
        super().__init__(message)


class UnsupportedFileError(ProcessingError):
    """File type is not supported (e.g., legacy .doc, image files)."""
    pass


class EncryptedFileError(ProcessingError):
    """File is password-protected or encrypted."""
    pass


class CorruptFileError(ProcessingError):
    """File is damaged or cannot be opened."""
    pass


class OCRUnavailableError(ProcessingError):
    """Scanned document requires OCR but Tesseract is not available."""
    pass


class EmptyDocumentError(ProcessingError):
    """Document has no extractable text content."""
    pass


class AIServiceError(ProcessingError):
    """OpenAI API call failed (network, rate limit, auth, quota)."""
    pass


class TemplateError(ProcessingError):
    """Template file missing or could not be populated."""
    pass
