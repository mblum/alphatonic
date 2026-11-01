import pytest
from playwright.sync_api import expect

pytestmark = pytest.mark.browser


def test_offline_tearsheet_charts_tabs_keyboard_and_print(page, result, tmp_path):
    errors = []
    requests = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    page.on(
        "console", lambda message: errors.append(message.text) if message.type == "error" else None
    )

    def block(route):
        requests.append(route.request.url)
        route.abort()

    page.route("http://**/*", block)
    page.route("https://**/*", block)
    path = result.tearsheet(tmp_path / "offline.html")
    page.goto(path.as_uri())
    expect(page.locator('svg[role="img"]').first).to_be_visible()
    tabs = page.get_by_role("tab")
    tabs.nth(1).click()
    expect(tabs.nth(1)).to_have_attribute("aria-selected", "true")
    tabs.nth(1).press("ArrowLeft")
    expect(tabs.nth(0)).to_have_attribute("aria-selected", "true")
    disclosures = page.locator("details")
    disclosures.first.locator("summary").click()
    expect(disclosures.first).to_have_attribute("open", "")
    original = disclosures.evaluate_all("nodes => nodes.map(n => n.open)")
    hidden = page.get_by_role("tabpanel", include_hidden=True).evaluate_all(
        "nodes => nodes.map(n => n.hidden)"
    )
    page.evaluate("window.dispatchEvent(new Event('beforeprint'))")
    assert all(disclosures.evaluate_all("nodes => nodes.map(n => n.open)"))
    assert not any(
        page.get_by_role("tabpanel", include_hidden=True).evaluate_all(
            "nodes => nodes.map(n => n.hidden)"
        )
    )
    page.evaluate("window.dispatchEvent(new Event('afterprint'))")
    assert disclosures.evaluate_all("nodes => nodes.map(n => n.open)") == original
    assert (
        page.get_by_role("tabpanel", include_hidden=True).evaluate_all(
            "nodes => nodes.map(n => n.hidden)"
        )
        == hidden
    )
    page.set_viewport_size({"width": 390, "height": 844})
    page.emulate_media(color_scheme="dark")
    page.emulate_media(media="print")
    page.emulate_media(media="screen", color_scheme="light")
    assert not errors and not requests
    assert page.get_by_text("Chart could not be drawn", exact=False).count() == 0
