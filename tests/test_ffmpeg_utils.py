import unittest
from unittest.mock import patch, MagicMock, mock_open, call
from pathlib import Path
import os # For os.stat_result and utime constants

# Functions to test
from src.core.ffmpeg_utils import run_ffmpeg, has_ffmpeg_errors, get_video_duration, preserve_timestamp

class TestFfmpegUtils(unittest.TestCase):

    @patch('subprocess.run')
    def test_run_ffmpeg_success(self, mock_subprocess_run):
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_subprocess_run.return_value = mock_result

        cmd = ['ffmpeg', '-i', 'input.mp4', 'output.mp4']
        self.assertTrue(run_ffmpeg(cmd))
        mock_subprocess_run.assert_called_once_with(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    @patch('subprocess.run')
    def test_run_ffmpeg_success_with_logfile(self, mock_subprocess_run):
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_subprocess_run.return_value = mock_result

        cmd = ['ffmpeg', '-i', 'input.mp4', 'output.mp4']
        log_file = Path('test.log')

        # Use mock_open for the log file context manager
        with patch('builtins.open', mock_open()) as mock_file:
            self.assertTrue(run_ffmpeg(cmd, log_file=log_file))
            mock_file.assert_called_once_with(log_file, 'w')
            mock_subprocess_run.assert_called_once_with(cmd, stdout=mock_file(), stderr=mock_file())

    @patch('subprocess.run')
    def test_run_ffmpeg_failure_returncode(self, mock_subprocess_run):
        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_subprocess_run.return_value = mock_result

        cmd = ['ffmpeg', '-i', 'input.mp4', 'output.mp4']
        self.assertFalse(run_ffmpeg(cmd))

    @patch('subprocess.run')
    def test_run_ffmpeg_exception(self, mock_subprocess_run):
        mock_subprocess_run.side_effect = Exception("Subprocess error")

        cmd = ['ffmpeg', '-i', 'input.mp4', 'output.mp4']
        # We also need to patch 'print' if we want to check its output, or just ensure False is returned
        with patch('builtins.print') as mock_print:
            self.assertFalse(run_ffmpeg(cmd))
            mock_print.assert_called_once() # Check if the error message was printed

    @patch('subprocess.run')
    def test_has_ffmpeg_errors_no_errors(self, mock_subprocess_run):
        # Mock results for both ffmpeg calls in has_ffmpeg_errors
        mock_result_error_check = MagicMock()
        mock_result_error_check.stderr = b'' # No error output

        mock_result_dts_check = MagicMock()
        mock_result_dts_check.stderr = b'Some normal output without DTS errors'

        mock_subprocess_run.side_effect = [mock_result_error_check, mock_result_dts_check]

        self.assertFalse(has_ffmpeg_errors(Path('test.mp4')))
        expected_calls = [
            call(['ffmpeg', '-v', 'error', '-i', 'test.mp4', '-f', 'null', '-'], stdout=subprocess.PIPE, stderr=subprocess.PIPE),
            call(['ffmpeg', '-i', 'test.mp4', '-c', 'copy', '-f', 'null', '-'], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        ]
        mock_subprocess_run.assert_has_calls(expected_calls)


    @patch('subprocess.run')
    @patch('builtins.print') # To suppress print output during test
    def test_has_ffmpeg_errors_basic_errors(self, mock_print, mock_subprocess_run):
        mock_result_error_check = MagicMock()
        mock_result_error_check.stderr = b'Error: Something went wrong'

        mock_result_dts_check = MagicMock()
        mock_result_dts_check.stderr = b'' # No DTS errors specifically

        mock_subprocess_run.side_effect = [mock_result_error_check, mock_result_dts_check]

        self.assertTrue(has_ffmpeg_errors(Path('test.mp4')))
        mock_print.assert_called() # Check if errors were printed

    @patch('subprocess.run')
    @patch('builtins.print')
    def test_has_ffmpeg_errors_dts_pts_errors(self, mock_print, mock_subprocess_run):
        mock_result_error_check = MagicMock()
        mock_result_error_check.stderr = b''

        mock_result_dts_check = MagicMock()
        mock_result_dts_check.stderr = b'non monotonically increasing dts' # DTS error

        mock_subprocess_run.side_effect = [mock_result_error_check, mock_result_dts_check]

        self.assertTrue(has_ffmpeg_errors(Path('test.mp4')))
        mock_print.assert_called()

    @patch('subprocess.run')
    def test_get_video_duration_success(self, mock_subprocess_run):
        mock_result = MagicMock()
        mock_result.stdout = "123.45\n" # ffprobe output
        mock_subprocess_run.return_value = mock_result

        duration = get_video_duration(Path('test.mp4'))
        self.assertEqual(duration, 123.45)
        mock_subprocess_run.assert_called_once_with(
            ['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'default=noprint_wrappers=1:nokey=1', 'test.mp4'],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=True
        )

    @patch('subprocess.run')
    @patch('builtins.print')
    def test_get_video_duration_ffprobe_error(self, mock_print, mock_subprocess_run):
        mock_subprocess_run.side_effect = subprocess.CalledProcessError(1, "cmd", stderr="ffprobe error")

        duration = get_video_duration(Path('test.mp4'))
        self.assertIsNone(duration)
        mock_print.assert_called() # Check if error was printed

    @patch('subprocess.run')
    @patch('builtins.print')
    def test_get_video_duration_value_error(self, mock_print, mock_subprocess_run):
        mock_result = MagicMock()
        mock_result.stdout = "not a float"
        mock_subprocess_run.return_value = mock_result

        duration = get_video_duration(Path('test.mp4'))
        self.assertIsNone(duration)
        mock_print.assert_called()

    @patch('os.utime')
    @patch('os.stat')
    def test_preserve_timestamp(self, mock_os_stat, mock_os_utime):
        source_file = Path('source.txt')
        target_file = Path('target.txt')

        # Create a mock stat_result object
        mock_stat_result = MagicMock(spec=os.stat_result)
        mock_stat_result.st_atime = 1670000000.0 # Example access time
        mock_stat_result.st_mtime = 1670000001.0 # Example modification time
        mock_os_stat.return_value = mock_stat_result

        preserve_timestamp(source_file, target_file)

        mock_os_stat.assert_called_once_with(str(source_file))
        mock_os_utime.assert_called_once_with(str(target_file), (mock_stat_result.st_atime, mock_stat_result.st_mtime))

if __name__ == '__main__':
    unittest.main()
