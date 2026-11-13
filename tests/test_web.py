import http.client
import json
import threading

import pytest

from replay.web import create_server


@pytest.fixture
def server():
    server = create_server(port=0)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield server
    server.shutdown()
    server.server_close()
    thread.join(timeout=2)
    assert not thread.is_alive()


def request(server, method, path, body=None, headers=None):
    connection = http.client.HTTPConnection("127.0.0.1", server.server_port, timeout=10)
    try:
        connection.request(method, path, body=body, headers=headers or {})
        response = connection.getresponse()
        return response.status, dict(response.getheaders()), response.read()
    finally:
        connection.close()


def test_ui_and_assets_served_with_no_external_dependencies(server):
    for path, content in [("/", b"Exactly-One Action Replay"),
                          ("/app.js", b"dragstart"), ("/style.css", b"focus-visible")]:
        status, headers, body = request(server, "GET", path)
        assert status == 200
        assert content in body
        assert "default-src 'self'" in headers["Content-Security-Policy"]


def test_browser_replay_uses_real_runner(server):
    status, _, body = request(server, "POST", "/api/replay", body="{}",
                              headers={"Content-Type": "application/json"})
    assert status == 200
    assert json.loads(body)["safe_duplicates"] == 0
    assert json.loads(body)["naive_duplicates"] == 100


@pytest.mark.parametrize("path", ["/../DESIGN.md", "/api/replay", "/nope"])
def test_arbitrary_files_and_get_mutations_are_not_served(server, path):
    assert request(server, "GET", path)[0] == 404


@pytest.mark.parametrize("headers,body,expected", [
    ({"Origin": "https://evil.example", "Content-Type": "application/json"}, "{}", 403),
    ({"Host": "evil.example", "Content-Type": "application/json"}, "{}", 403),
    ({"Content-Type": "text/plain"}, "{}", 415),
    ({"Content-Type": "application/json"}, "{", 400),
    ({"Content-Type": "application/json"}, '{"count":1000000}', 400),
    ({"Content-Type": "application/json"}, "x" * 129, 413),
])
def test_untrusted_or_unbounded_requests_rejected(server, headers, body, expected):
    assert request(server, "POST", "/api/replay", body, headers)[0] == expected
