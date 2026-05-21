class LLMNotebookError(Exception):
    pass


class DuplicateDocumentError(LLMNotebookError):
    def __init__(self, existing_document_id: str):
        self.existing_document_id = existing_document_id
        super().__init__(f"Document already exists: {existing_document_id}")


class DocumentNotFoundError(LLMNotebookError):
    def __init__(self, document_id: str):
        self.document_id = document_id
        super().__init__(f"Document not found: {document_id}")


class ChunkNotFoundError(LLMNotebookError):
    def __init__(self, chunk_id: str):
        self.chunk_id = chunk_id
        super().__init__(f"Chunk not found: {chunk_id}")


class InvalidStatusTransitionError(LLMNotebookError):
    def __init__(self, current: str, target: str):
        super().__init__(f"Invalid status transition: {current} → {target}")


class DocumentProcessingError(LLMNotebookError):
    pass


class UnsupportedFileTypeError(LLMNotebookError):
    def __init__(self, mime_type: str):
        super().__init__(f"Unsupported file type: {mime_type}")


class FileTooLargeError(LLMNotebookError):
    def __init__(self, size_bytes: int, max_bytes: int):
        super().__init__(f"File too large: {size_bytes} bytes (max {max_bytes})")


class DocumentDeletionError(LLMNotebookError):
    pass


class ConversationNotFoundError(LLMNotebookError):
    def __init__(self, conversation_id: str):
        super().__init__(f"Conversation not found: {conversation_id}")


class ConversationCompactingError(LLMNotebookError):
    def __init__(self, conversation_id: str):
        super().__init__(f"Conversation {conversation_id} is currently compacting. Please wait.")


class AuthenticationError(LLMNotebookError):
    pass
