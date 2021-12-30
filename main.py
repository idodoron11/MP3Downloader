import selenium.common.exceptions
from selenium import webdriver
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from time import sleep
import datetime
import numpy as np
import logging
import os

logging.basicConfig(format='%(asctime)s - %(levelname)s - %(message)s', level=logging.INFO)


class WaitEngine:
    def __init__(self):
        self.lastReset = self.nextReset = None
        self.resetInterval = 10
        self.bypassWait = False
        self.reset()

    def reset(self):
        self.lastReset = datetime.datetime.now()
        self.nextReset = self.lastReset + datetime.timedelta(minutes=self.resetInterval)
        logging.info(f"Wait engine was reset. Next reset will be in {self.resetInterval} minutes.")

    def wait(self, quick_wait=False):
        current_time = datetime.datetime.now()
        if self.bypassWait:
            logging.info(f"Waiting 3 seconds.")
            sleep(3)
        elif current_time >= self.nextReset:
            penalty = np.random.randint(120, 601)
            logging.info(f"Waiting {penalty} seconds.")
            sleep(penalty)
            self.reset()
        else:
            coin = np.random.choice([0, 1], p=[0.9, 0.1])
            if quick_wait or coin == 0:
                penalty = np.random.randint(2, 16)
            else:
                penalty = np.random.randint(16, 61)
            logging.info(f"Waiting {penalty} seconds.")
            sleep(penalty)

    def quick_wait(self):
        self.wait(True)


class Downloader:
    def __init__(self, format="mp3"):
        self.wait_engine = WaitEngine()
        self.wait_engine.bypassWait = True
        if format in ["flac", "mp3"]:
            self.format = format
        else:
            self.format = "mp3"
        logging.info("Opening a new browser window")
        profile = webdriver.FirefoxProfile()
        download_path = os.path.join(os.environ['USERPROFILE'], "Downloads", "Music")
        profile.set_preference("browser.download.dir", download_path)
        profile.set_preference("browser.download.folderList", 2)
        content_types = "audio/x-flac;audio/flac;application/flac;audio/x-ogg-flac; audio/x-oggflac; audio/mp3; " \
                        "audio/mpeg; audio/mpeg3; audio/mpg; audio/x-mp3; audio/x-mpeg; audio/x-mpeg3; " \
                        "audio/x-mpegaudio; audio/x-mpg; "
        profile.set_preference("browser.helperApps.neverAsk.saveToDisk", content_types)
        profile.set_preference("browser.download.manager.showWhenStarting", False)
        profile.set_preference("browser.helperApps.alwaysAsk.force", False)
        profile.set_preference("browser.download.manager.useWindow", False)
        profile.set_preference("browser.download.manager.focusWhenStarting", False)
        profile.set_preference("browser.download.manager.closeWhenDone", True)
        self.browser = webdriver.Firefox(firefox_profile=profile)

    def search_for(self, query):
        self.wait_engine.wait()
        logging.info("Navigating to https://free-mp3-download.net/")
        self.browser.get("https://free-mp3-download.net/")
        self.wait_engine.quick_wait()
        search_box = self.browser.find_element_by_id("q")
        search_box.clear()
        search_box.send_keys(query)
        search_btn = self.browser.find_element_by_id("snd")
        logging.info(f"Searching for {query}.")
        search_btn.click()

    def choose_first_result(self):
        self.wait_engine.quick_wait()
        result_link = self.browser.find_element_by_xpath("/html/body/main/div/div[2]/div/table/tbody/tr[1]/td["
                                                         "3]/a/button")
        result_link.click()
        self.wait_engine.quick_wait()
        logging.info("Closing advertisement.")
        webdriver.ActionChains(self.browser).send_keys(Keys.ESCAPE).perform()
        WebDriverWait(self.browser, 10).until(
            EC.url_contains("download.php")
        )

    def process_download_page(self):
        format_selector = self.browser.find_element_by_id(self.format)
        self.browser.execute_script("arguments[0].click();", format_selector)
        captcha = self.browser.find_elements_by_id("captcha")
        if len(captcha) > 0:
            captcha = captcha[0]
            if captcha.is_displayed():
                input("Please solve the CAPTCHA challenge before proceeding\n")
        # format_selector.click()
        download_btn = self.browser.find_element_by_class_name("dl")
        self.wait_engine.quick_wait()
        download_btn.click()

    def download(self, query):
        self.search_for(query)
        try:
            self.choose_first_result()
            self.process_download_page()
        except selenium.common.exceptions.NoSuchElementException:
            logging.error(f"Could not download {query}.")

    def download_list(self, list):
        for item in list:
            self.download(item)


downloader = Downloader("flac")
downloader.download_list(["Elton John Tiny Dancer", "Coldplay The Scientist"])
