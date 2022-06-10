from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

class PlaywrightDriver:
    def __init__(self) -> None:
        
        self.playwright = None
        
        self.browser = None
        
        self.page = None
        
        self.headless = False
    
    def start(self):
        
        self.playwright = sync_playwright().start()
        
        self.browser = self.playwright.chromium.launch(headless=self.headless)
        
        self.page = self.browser.new_page(user_agent="Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/99.0.4844.51 Safari/537.36")
    
    def stop(self):
        
        self.browser.close()
        
        self.playwright.stop()
    
    def get_soup(self):
        try:
            soup = BeautifulSoup(self.page.content(),features="html.parser")
            return soup
        except Exception as e:
            print(f'error : {str(e)}')
            return None
        