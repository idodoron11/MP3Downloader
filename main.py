import selenium.common.exceptions
from selenium import webdriver
from time import sleep
import datetime
import numpy as np
import logging

logging.basicConfig(format='%(asctime)s - %(levelname)s - %(message)s', level=logging.INFO)


class WaitEngine:
    def __init__(self):
        self.lastReset = self.nextReset = None
        self.resetInterval = 10
        self.reset()

    def reset(self):
        self.lastReset = datetime.datetime.now()
        self.nextReset = self.lastReset + datetime.timedelta(minutes=self.resetInterval)
        logging.info(f"Wait engine was reset. Next reset will be in {self.resetInterval} minutes.")

    def wait(self, quick_wait=False):
        current_time = datetime.datetime.now()
        if current_time >= self.nextReset:
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
    def __init__(self, format = "mp3"):
        self.wait_engine = WaitEngine()
        self.download_pages = list()
        if format in ["flac", "mp3"]:
            self.format = format
        else:
            self.format = "mp3"
        logging.info("Opening a new browser window")
        self.browser = webdriver.Firefox()
        logging.info("Navigating to https://free-mp3-download.net/")
        self.browser.get("https://free-mp3-download.net/")
        self.wait_engine.quick_wait()

    def search_for(self, query):
        search_box = self.browser.find_element_by_id("q")
        self.wait_engine.wait()
        search_box.clear()
        search_box.send_keys(query)
        search_btn = self.browser.find_element_by_id("snd")
        logging.info(f"Searching for {query}.")
        search_btn.click()
        try:
            result_link = self.browser.find_element_by_xpath("/html/body/main/div/div[2]/div/table/tbody/tr[1]/td[3]/a")
            self.download_pages.append(result_link.get_attribute("href"))
        except selenium.common.exceptions.NoSuchElementException:
            logging.error(f"Could not find any results for {query}.")
            self.download_pages.append(None)

    def download_list(self, list):
        for item in list:
            self.search_for(item)

        for url in self.download_pages:
            if url is not None:
                logging.info(f"Navigating to {url}")
                self.browser.get(url)
                input("If you see a CAPTCHA test, please solve it before proceeding.")
                break

        for index, url in enumerate(self.download_pages):
            if url is not None:
                self.wait_engine.wait()
                logging.info(f"Navigating to {url}")
                self.browser.get(url)
                format_selector = self.browser.find_element_by_id(self.format)
                format_selector.click()
                download_btn = self.browser.find_element_by_class_name("dl")
                self.wait_engine.quick_wait()
                download_btn.click()


search_terms = ["fdlgjfldgkjdflkjlgkfl", "2", "3", "4"]
downloader = Downloader("flac")
downloader.download_list(search_terms)
