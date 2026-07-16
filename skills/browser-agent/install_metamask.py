import playwright
from playwright.sync_api import sync_playwright

def run(playwright):
    browser = playwright.chromium.launch()
    context = browser.new_context()
    page = context.new_page()
    page.goto("https://chrome.google.com/webstore/detail/metamask/nkbihfbeogaeaoehlefnkodbefgpgknn")
    page.click("#details-button")
    page.click("#install-button")
    page.wait_for_timeout(10000)
    browser.close()

with sync_playwright() as p:
    run(p)
