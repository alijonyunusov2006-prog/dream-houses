from jarviscore.phone import find_url, set_menu


def test_find_tunnel_url_in_cloudflared_log():
    line = "2026-10-21T00:00:00Z INF |  https://quiet-river-sun-moon.trycloudflare.com                        |"
    assert find_url(line) == "https://quiet-river-sun-moon.trycloudflare.com"
    assert find_url("INF Requesting new quick Tunnel on trycloudflare.com...") is None
    assert find_url("https://evil.com/?x=trycloudflare.com") is None


def test_menu_button_points_to_window_and_resets():
    calls = []

    class TG:
        def call(self, method, **kw):
            calls.append((method, kw))
    set_menu(TG(), 42, "https://a-b.trycloudflare.com")
    set_menu(TG(), 42, None)
    assert calls[0] == ("setChatMenuButton", {"chat_id": 42, "menu_button": {
        "type": "web_app", "text": "JARVIS", "web_app": {"url": "https://a-b.trycloudflare.com"}}})
    assert calls[1][1]["menu_button"] == {"type": "default"}
