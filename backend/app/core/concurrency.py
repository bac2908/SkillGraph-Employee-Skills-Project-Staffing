"""Opaque mutation versions. Legacy graph records start at version '0'."""

from app.repositories.errors import RepositoryError


class VersionConflict(RepositoryError):
    status = 409

    def __init__(self):
        super().__init__(
            "Dữ liệu đã thay đổi hoặc bị xóa từ khi bạn mở biểu mẫu. "
            "Bản nháp chưa bị mất. Hãy xem dữ liệu mới trước khi lưu lại."
        )


class VersionRequired(VersionConflict):
    status = 428

    def __init__(self):
        RepositoryError.__init__(
            self, "Cần expected_version của bản ghi đã đọc trước khi cập nhật."
        )


def check_version(before: dict | None, expected: str | None) -> None:
    if before is None:
        if expected not in (None, "absent"):
            raise VersionConflict()
        return
    if expected is None:
        raise VersionRequired()
    if expected != before.get("version", "0"):
        raise VersionConflict()
