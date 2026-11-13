from backend.src.domain.notice_verification import ClassNotice

class InMemoryNoticeRepository:

    def __init__(self):
        self._notices = {}

    def save(self, notice: ClassNotice):
        if notice.notice_id in self._notices:
            raise ValueError("Notice already exists.")

        self._notices[notice.notice_id] = notice

    def find_for_incident(
        self,
        course_id: str,
        incident_date,
    ):
        return [
            notice
            for notice in self._notices.values()
            if (
                notice.course_id == course_id
                and notice.for_date == incident_date
            )
        ]
