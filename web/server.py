#!/usr/bin/env python3
"""Simple web server for the Outreach Bot control panel.

Security notes:
- Only accepts structured parameters, not raw commands
- Uses shell=False with subprocess (eliminates shell injection entirely)
- All file paths are validated and restricted to project/home directories
- Binds only to localhost by default
- No wildcard CORS
- Request size limits enforced
"""

import json
import os
import signal
import subprocess
import sys
from http.server import HTTPServer, SimpleHTTPRequestHandler
from pathlib import Path

# Global dictionary to track running processes
running_processes = {}

# Allowed base directory for file operations
PROJECT_ROOT = Path(__file__).parent.parent.resolve()

def validate_csv_path(filepath: str) -> tuple[bool, str]:
    """
    Validate that a CSV path is safe to use.

    Returns:
        Tuple of (is_valid, error_message_or_safe_path)
    """
    if not filepath:
        return False, "File path is required"

    # Remove any null bytes or other dangerous characters
    filepath = filepath.replace('\x00', '')

    # Check for obvious shell injection attempts
    dangerous_patterns = [';', '&&', '||', '|', '`', '$', '>', '<', '\n', '\r']
    for pattern in dangerous_patterns:
        if pattern in filepath:
            return False, f"Invalid character in file path: {pattern}"

    # Resolve the path
    try:
        path = Path(filepath)

        # If it's a relative path, resolve it relative to PROJECT_ROOT
        if not path.is_absolute():
            path = PROJECT_ROOT / path

        path = path.resolve()

        # Ensure the path is within the project root or a safe location
        # Allow paths within the project root
        try:
            path.relative_to(PROJECT_ROOT)
        except ValueError:
            # Also allow paths in user's home directory
            home = Path.home()
            try:
                path.relative_to(home)
            except ValueError:
                return False, f"File path must be within project directory or home folder"

        # Ensure it has .csv extension
        if path.suffix.lower() != '.csv':
            return False, "File must have .csv extension"

        return True, str(path)

    except Exception as e:
        return False, f"Invalid file path: {e}"


def validate_integer(value: str, min_val: int = None, max_val: int = None, default: int = None) -> tuple[bool, int | str]:
    """Validate an integer value is within bounds."""
    if not value or value == '':
        if default is not None:
            return True, default
        return True, None

    try:
        val = int(value)
        if min_val is not None and val < min_val:
            return False, f"Value must be at least {min_val}"
        if max_val is not None and val > max_val:
            return False, f"Value must be at most {max_val}"
        return True, val
    except ValueError:
        return False, "Value must be a valid integer"


def build_command_args(params: dict) -> tuple[bool, list[str] | str]:
    """
    Build a safe command argument list from validated parameters.

    Returns:
        Tuple of (success, args_list_or_error_message)

    Security: Returns a list of arguments to be used with shell=False,
    which eliminates shell injection vulnerabilities entirely.
    """
    # Validate input CSV (required)
    input_csv = params.get('inputCsv', '').strip()
    valid, result = validate_csv_path(input_csv)
    if not valid:
        return False, f"Input CSV error: {result}"
    input_csv_path = result

    # Validate output CSV (optional)
    output_csv = params.get('outputCsv', '').strip()
    output_csv_path = None
    if output_csv:
        valid, result = validate_csv_path(output_csv)
        if not valid:
            return False, f"Output CSV error: {result}"
        output_csv_path = result

    # Validate limit (optional, positive integer)
    limit = params.get('limit', '')
    valid, result = validate_integer(limit, min_val=1, max_val=100000)
    if not valid:
        return False, f"Limit error: {result}"
    limit_val = result

    # Validate quality threshold (0-100)
    quality_threshold = params.get('qualityThreshold', '70')
    valid, result = validate_integer(quality_threshold, min_val=0, max_val=100, default=70)
    if not valid:
        return False, f"Quality threshold error: {result}"
    quality_val = result

    # Validate max retries (0-10)
    max_retries = params.get('maxRetries', '3')
    valid, result = validate_integer(max_retries, min_val=0, max_val=10, default=3)
    if not valid:
        return False, f"Max retries error: {result}"
    retries_val = result

    # Boolean flags
    resume = params.get('resume', True)
    if isinstance(resume, str):
        resume = resume.lower() in ('true', '1', 'yes')

    skip_evaluation = params.get('skipEvaluation', False)
    if isinstance(skip_evaluation, str):
        skip_evaluation = skip_evaluation.lower() in ('true', '1', 'yes')

    verbose = params.get('verbose', False)
    if isinstance(verbose, str):
        verbose = verbose.lower() in ('true', '1', 'yes')

    # Build command as argument list (NO shell=True needed)
    # Use the venv Python directly to avoid needing shell activation
    venv_python = PROJECT_ROOT / '.venv' / 'bin' / 'python'

    if not venv_python.exists():
        return False, f"Virtual environment not found at {venv_python}"

    args = [
        str(venv_python),
        '-m', 'outreach_bot.cli',
        'run',
        input_csv_path,
    ]

    if output_csv_path:
        args.extend(['--output', output_csv_path])

    if limit_val is not None:
        args.extend(['--limit', str(limit_val)])

    if quality_val != 70:
        args.extend(['--quality-threshold', str(quality_val)])

    if retries_val != 3:
        args.extend(['--max-retries', str(retries_val)])

    if not resume:
        args.append('--no-resume')

    if skip_evaluation:
        args.append('--skip-evaluation')

    if verbose:
        args.append('--verbose')

    return True, args


class OutreachBotHandler(SimpleHTTPRequestHandler):
    """Custom handler for the outreach bot web interface."""

    def do_GET(self):
        """Handle GET requests."""
        # Only serve files from the web directory
        if self.path == '/' or self.path == '/index.html':
            self.path = '/index.html'

        # Prevent directory traversal
        if '..' in self.path:
            self.send_error(403, "Forbidden")
            return

        return SimpleHTTPRequestHandler.do_GET(self)

    def do_POST(self):
        """Handle POST requests to run commands."""
        # Only allow requests from localhost
        client_host = self.client_address[0]
        if client_host not in ('127.0.0.1', '::1', 'localhost'):
            self.send_error(403, "Forbidden: Only localhost connections allowed")
            return

        if self.path == '/api/run':
            content_length = int(self.headers.get('Content-Length', 0))
            if content_length > 10000:  # Limit request size
                self.send_error(413, "Request too large")
                return

            post_data = self.rfile.read(content_length)

            try:
                data = json.loads(post_data.decode('utf-8'))
            except json.JSONDecodeError:
                self.send_error(400, "Invalid JSON")
                return

            # Build command from structured parameters (NOT raw command)
            success, result = build_command_args(data)

            if not success:
                response = {
                    'success': False,
                    'output': '',
                    'error': result,
                    'pid': None
                }
                self._send_json_response(response)
                return

            args = result

            try:
                # Execute command using Popen with shell=False (secure)
                # Using start_new_session=True instead of deprecated preexec_fn
                process = subprocess.Popen(
                    args,
                    shell=False,  # Security: never use shell=True
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    cwd=str(PROJECT_ROOT),
                    start_new_session=True  # Create new process group (replaces preexec_fn)
                )

                # Store process in global dict
                running_processes[process.pid] = process

                # Wait for process to complete (with timeout)
                try:
                    stdout, stderr = process.communicate(timeout=600)
                    returncode = process.returncode
                except subprocess.TimeoutExpired:
                    # Kill the process group if timeout
                    os.killpg(os.getpgid(process.pid), signal.SIGTERM)
                    stdout, stderr = process.communicate()
                    returncode = -1
                    stderr = 'Command timed out after 10 minutes\n' + stderr

                # Remove from tracking
                running_processes.pop(process.pid, None)

                response = {
                    'success': returncode == 0,
                    'output': stdout,
                    'error': stderr,
                    'pid': process.pid
                }

            except Exception as e:
                response = {
                    'success': False,
                    'output': '',
                    'error': str(e),
                    'pid': None
                }

            self._send_json_response(response)

        elif self.path == '/api/stop':
            content_length = int(self.headers.get('Content-Length', 0))
            if content_length > 1000:
                self.send_error(413, "Request too large")
                return

            post_data = self.rfile.read(content_length)

            try:
                data = json.loads(post_data.decode('utf-8'))
            except json.JSONDecodeError:
                self.send_error(400, "Invalid JSON")
                return

            pid = data.get('pid')

            # Validate PID is an integer
            if not isinstance(pid, int) or pid <= 0:
                response = {
                    'success': False,
                    'error': 'Invalid process ID'
                }
                self._send_json_response(response)
                return

            try:
                if pid in running_processes:
                    process = running_processes[pid]
                    # Kill the entire process group
                    os.killpg(os.getpgid(pid), signal.SIGTERM)
                    process.wait(timeout=5)
                    running_processes.pop(pid, None)
                    response = {
                        'success': True,
                        'message': f'Process {pid} stopped'
                    }
                else:
                    response = {
                        'success': False,
                        'error': f'Process {pid} not found or not tracked by this server'
                    }

            except ProcessLookupError:
                response = {
                    'success': False,
                    'error': f'Process {pid} not found or already stopped'
                }
            except Exception as e:
                response = {
                    'success': False,
                    'error': str(e)
                }

            self._send_json_response(response)

        else:
            self.send_error(404)

    def _send_json_response(self, response: dict, status: int = 200):
        """Send a JSON response."""
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        # No CORS headers - only allow same-origin requests
        self.end_headers()
        self.wfile.write(json.dumps(response).encode('utf-8'))

    def do_OPTIONS(self):
        """Handle OPTIONS requests - deny CORS preflight."""
        self.send_error(403, "CORS not allowed")


def run_server(port=8000, host='127.0.0.1'):
    """Run the web server."""
    # Change to the web directory
    web_dir = Path(__file__).parent
    os.chdir(web_dir)

    server_address = (host, port)
    httpd = HTTPServer(server_address, OutreachBotHandler)

    print(f"""
+-----------------------------------------------------------------+
|  Outreach Bot Control Panel                                     |
|                                                                 |
|  Server running at: http://{host}:{port}                        |
|                                                                 |
|  Security: Accepting connections from localhost only            |
|                                                                 |
|  Press Ctrl+C to stop                                           |
+-----------------------------------------------------------------+
    """)

    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n\nShutting down server...")
        httpd.shutdown()


if __name__ == '__main__':
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8000
    run_server(port)
