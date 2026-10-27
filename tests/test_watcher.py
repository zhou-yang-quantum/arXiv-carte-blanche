import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest


@unittest.skipUnless(shutil.which('powershell.exe'), 'Windows watcher requires PowerShell')
class WatcherProcessTests(unittest.TestCase):
    def test_native_warning_and_large_stderr_do_not_abort_or_deadlock(self):
        self.check_process(0)

    def test_native_failure_is_reported_by_exit_code(self):
        self.check_process(7)

    def check_process(self, exit_code):
        bridge = Path(__file__).resolve().parents[1] / 'tools/controller-process.ps1'
        with tempfile.TemporaryDirectory(prefix='watcher path ') as folder:
            folder = Path(folder)
            script = folder / 'controller.py'
            script.write_text('import sys,warnings\n'
                              'warnings.warn("informational warning")\n'
                              'sys.stderr.write("x" * 200000)\n'
                              'print("completed \\u03bb", flush=True)\n'
                              f'sys.exit({exit_code})\n', encoding='utf-8')
            runner = folder / 'invoke.ps1'
            runner.write_text('param($bridge,$pythonPath,$scriptPath)\n'
                              "$ErrorActionPreference='Stop'\n. $bridge\n"
                              '$result = Invoke-ArxivController $pythonPath $scriptPath\n'
                              '$result | ConvertTo-Json -Compress\n', encoding='utf-8')
            result = subprocess.run(['powershell.exe', '-NoProfile', '-File', str(runner),
                                     str(bridge), sys.executable, str(script)],
                                    capture_output=True, encoding='utf-8', timeout=30)
            self.assertEqual(result.returncode, 0, result.stderr)
            output = json.loads(result.stdout)
            self.assertEqual(output['ExitCode'], exit_code)
            self.assertIn('completed λ', output['Stdout'])
            self.assertIn('informational warning', output['Stderr'])
            self.assertGreater(len(output['Stderr']), 200000)


if __name__ == '__main__':
    unittest.main()
