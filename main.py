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
    def __init__(self):
        self.wait_engine = WaitEngine()
        logging.info("Opening a new browser window")
        self.browser = webdriver.Firefox()
        logging.info("Navigating to https://free-mp3-download.net/")
        self.browser.get("https://free-mp3-download.net/")
        self.wait_engine.quick_wait()

    def search_for(self, query):
        search_box = self.browser.find_element_by_id("q")
        self.wait_engine.wait()
        search_box.clear()
        self.wait_engine.quick_wait()
        search_box.send_keys(query)
        self.wait_engine.quick_wait()
        search_btn = self.browser.find_element_by_id("snd")
        logging.info(f"Searching for {query}.")
        search_btn.click()


search_terms = ["1", "2", "3", "4", "5", "6", "7", "8", "9", "10"]
downloader = Downloader()
for query in search_terms:
    downloader.search_for(query)
