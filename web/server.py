#!/usr/bin/env python3
"""Simple web server for the Outreach Bot control panel."""

import asyncio
import json
import subprocess
from pathlib import Path
from http.server import HTTPServer, SimpleHTTPRequestHandler
import sys

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
                # Execute command
                result = subprocess.run(
                    command,
                    shell=True,
                    capture_output=True,
                    text=True,
                    timeout=600  # 10 minute timeout
                )

                response = {
                    'success': result.returncode == 0,
                    'output': result.stdout,
                    'error': result.stderr
                }

            except subprocess.TimeoutExpired:
                response = {
                    'success': False,
                    'output': '',
                    'error': 'Command timed out after 10 minutes'
                }
            except Exception as e:
                response = {
                    'success': False,
                    'output': '',
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
