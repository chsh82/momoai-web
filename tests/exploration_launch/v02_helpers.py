"""Public UI paths through v02; never forge seen/preference/acknowledgement."""
from playwright.sync_api import expect


def visible_navigation(page):
    """Expose actual collapsed menu; failure to expose it is a product failure."""
    nav = page.locator('.nav')
    if not nav.is_visible():
        page.get_by_role('button', name='메뉴', exact=True).click()
        expect(nav).to_be_visible()
    return nav


def navigation(page, name):
    """Open responsive navigation before selecting its exact public label."""
    visible_navigation(page).get_by_role('button', name=name, exact=True).click()


def open_report(page):
    """Visit actual result content, then explicitly choose and confirm preference."""
    before = page.evaluate('JSON.stringify(dataForResult().s.result)')
    for tab in ['core', 'connections', 'second', 'third', 'compare']:
        page.locator('#tab-' + tab).click()
        expect(page.locator('#result-panel')).to_have_attribute('data-step', tab)
    page.get_by_role('button', name='전체 리포트 보기', exact=True).click()
    if page.locator('#festival-preference').count():
        expect(page.locator('#festival-confirm')).to_be_disabled()
        page.locator('.preference-card').first.click()
        expect(page.locator('.preference-card').first).to_have_attribute('aria-pressed', 'true')
        page.get_by_role('button', name='선택하고 리포트 보기', exact=True).click()
    expect(page.locator('#main .journey-report')).to_be_visible()
    assert page.evaluate('JSON.stringify(festivalActive().result)') == before
