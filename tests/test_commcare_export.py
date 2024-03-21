import os
from commcare_export import logger_name_from_filepath, repo_root


class TestLoggerNameFromFilePath:

    @staticmethod
    def _file_path(rel_path):
        return os.path.join(repo_root, rel_path)

    def test_file_in_root(self):
        path = self._file_path("file.py")
        assert logger_name_from_filepath(path) == 'file'

    def test_file_in_subdirectory(self):
        path = self._file_path("subdir/file.py")
        assert logger_name_from_filepath(path) == 'subdir.file'

    def test_file_in_deeper_subdirectory(self):
        path = self._file_path("subdir/another_sub/file.py")
        assert logger_name_from_filepath(path) == 'subdir.another_sub.file'

    def test_file_contains_py(self):
        path = self._file_path("subdir/pytest.py")
        assert logger_name_from_filepath(path) == 'subdir.pytest'

    def test_file_dir_contains_periods(self):
        path = self._file_path("sub.dir/pytest.py")
        assert logger_name_from_filepath(path) == 'sub.dir.pytest'
