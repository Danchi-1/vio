from copy import deepcopy
from backend.src.domain.lecturer_reply import LecturerReplyCase

class InMemoryReplyRepository:

    def __init__(self):
        self._cases = {}

    def save(self, case: LecturerReplyCase):
        if case.reply_case_id in self._cases:
            raise ValueError("Reply case already exists.")

        self._cases[case.reply_case_id] = deepcopy(case)

    def get(self, reply_case_id: str):
        case = self._cases.get(reply_case_id)

        if case is None:
            return None

        return deepcopy(case)

    def update(self, case: LecturerReplyCase):
        if case.reply_case_id not in self._cases:
            raise ValueError("Reply case does not exist.")

        self._cases[case.reply_case_id] = deepcopy(case)

    def list_cases(self):
        return [
            deepcopy(case)
            for case in self._cases.values()
        ]
