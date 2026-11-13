from backend.src.application.lecturer_reply_service import (
    LecturerReplyService,
)
from backend.src.infrastructure.database.in_memory_reply_repository import (
    InMemoryReplyRepository,
)

repository = InMemoryReplyRepository()

reply_service = LecturerReplyService(repository)

def get_reply_service():
    return reply_service