import pytest
from playwright.sync_api import expect

from alphatonic import Study
from tests.integration.test_http_server import running_server

pytestmark = pytest.mark.browser


def test_served_board_sort_and_lazy_tearsheet(page, panel, config, tmp_path):
    study = Study(tmp_path, name="Browser research")
    trial = study.evaluate(*panel, config, signal="Browser signal")
    errors = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    with running_server(study) as address:
        url = f"http://{address[0]}:{address[1]}"
        page.goto(url + "/?sort=cs_ic&order=desc")
        expect(page.get_by_role("region", name="Trials")).to_be_visible()
        expect(page.get_by_text("Browser signal", exact=True).first).to_be_visible()
        page.goto(url + f"/{trial.id}/tearsheet.html")
        expect(page.locator('svg[role="img"]').first).to_be_visible(timeout=30000)
        with page.expect_download() as event:
            page.get_by_role("button", name="Download", exact=True).click()
        assert event.value.suggested_filename == f"{trial.id}-tearsheet.html"
    assert not errors
