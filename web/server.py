#!/usr/bin/env python3
"""Simple web server for the Outreach Bot control panel."""

import asyncio
import json
import subprocess
import signal
import os
from pathlib import Path
from http.server import HTTPServer, SimpleHTTPRequestHandler
import sys

# Global dictionary to track running processes
running_processes = {}

class OutreachBotHandler(SimpleHTTPRequestHandler):
    """Custom handler for the outreach bot web interface."""

    def do_GET(self):
        """Handle GET requests."""
        if self.path == '/' or self.path == '/index.html':
            self.path = '/index.html'
        return SimpleHTTPRequestHandler.do_GET(self)

    def do_POST(self):
        """Handle POST requests to run commands."""
        if self.path == '/api/run':
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)
            data = json.loads(post_data.decode('utf-8'))

            command = data.get('command', '')

            try:
                # Execute command using Popen to get PID
                process = subprocess.Popen(
                    command,
                    shell=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    preexec_fn=os.setsid  # Create new process group
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

            # Send response
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(json.dumps(response).encode('utf-8'))

        elif self.path == '/api/stop':
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)
            data = json.loads(post_data.decode('utf-8'))

            pid = data.get('pid')

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
                    # Try to kill it anyway
                    try:
                        os.killpg(os.getpgid(pid), signal.SIGTERM)
                        response = {
                            'success': True,
                            'message': f'Process {pid} stopped (not tracked)'
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

            # Send response
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(json.dumps(response).encode('utf-8'))

        else:
            self.send_error(404)

    def do_OPTIONS(self):
        """Handle OPTIONS requests for CORS."""
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()


def run_server(port=8000):
    """Run the web server."""
    # Change to the web directory
    web_dir = Path(__file__).parent
    import os
    os.chdir(web_dir)

    server_address = ('', port)
    httpd = HTTPServer(server_address, OutreachBotHandler)

    print(f"""
╔══════════════════════════════════════════════════════════════╗
║  Outreach Bot Control Panel                                  ║
║                                                              ║
║  Server running at: http://localhost:{port}                   ║
║                                                              ║
║  Press Ctrl+C to stop                                        ║
╚══════════════════════════════════════════════════════════════╝
    """)

    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n\nShutting down server...")
        httpd.shutdown()


if __name__ == '__main__':
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8000
    run_server(port)
