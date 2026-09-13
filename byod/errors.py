"""Public, fixed error messages; never expose exception or provider bodies."""

MESSAGES = {
    "FILE_NOT_FOUND": "File moved or deleted. Re-add it.",
    "UNSUPPORTED_TYPE": "Only PDF, DOCX, and PPTX are supported.",
    "PARSE_FAILED": "Couldn't read this file. It may be corrupt or password-protected.",
    "SCANNED_PDF": "This PDF has no text layer. OCR isn't included yet.",
    "EMPTY_DOCUMENT": "No readable text found. Add a document with selectable text.",
    "BLOCK_TOO_LARGE": "A table or heading is too large. Shorten it in the source and re-add it.",
    "MODEL_DOWNLOAD_FAILED": "Couldn't download the model. Check your connection and retry.",
    "INGEST_FAILED": "Couldn't index this file. Check the file and retry.",
    "STALE_INDEX": "The embedding model changed. Re-index to use these documents.",
}


class ByodError(Exception):
    def __init__(self, code: str) -> None:
        self.code = code
        self.message = MESSAGES[code]
        super().__init__(self.message)
