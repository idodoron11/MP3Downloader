import selenium.common.exceptions
from selenium import webdriver
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.by import By
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from time import sleep
import datetime
import numpy as np
import logging
import os
import deezer

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

    def wait(self, minimum = 0):
        current_time = datetime.datetime.now()
        if self.bypassWait:
            logging.info(f"Waiting 3 seconds.")
            sleep(3)
        elif current_time >= self.nextReset:
            # see: https://www.medcalc.org/manual/gamma-distribution-functions.php
            penalty = max(minimum, np.random.gamma(6, 60))
            logging.info(f"Waiting {penalty} seconds.")
            sleep(penalty)
            self.reset()
        else:
            # see: https://www.medcalc.org/manual/gamma-distribution-functions.php
            penalty = max(minimum, np.random.gamma(2, 2.2))
            logging.info(f"Waiting {penalty} seconds.")
            sleep(penalty)


class Downloader:
    def __init__(self, format="mp3"):
        self.wait_engine = WaitEngine()
        if format in ["flac", "mp3"]:
            self.format = format
        else:
            self.format = "mp3"
        logging.info("Opening a new browser window")
        options = Options()
        download_path = os.path.join(os.environ['USERPROFILE'], "Downloads", "Music")
        options.set_preference("browser.download.dir", download_path)
        options.set_preference("browser.download.folderList", 2)
        content_types = "audio/x-flac;audio/flac;application/flac;audio/x-ogg-flac; audio/x-oggflac; audio/mp3; " \
                        "audio/mpeg; audio/mpeg3; audio/mpg; audio/x-mp3; audio/x-mpeg; audio/x-mpeg3; " \
                        "audio/x-mpegaudio; audio/x-mpg; "
        options.set_preference("browser.helperApps.neverAsk.saveToDisk", content_types)
        options.set_preference("browser.download.manager.showWhenStarting", False)
        options.set_preference("browser.helperApps.alwaysAsk.force", False)
        options.set_preference("browser.download.manager.useWindow", False)
        options.set_preference("browser.download.manager.focusWhenStarting", False)
        options.set_preference("browser.download.manager.closeWhenDone", True)
        self.browser = webdriver.Firefox(options=options)
        self.browser.install_addon(os.path.abspath("ublock_origin-1.40.8-an+fx.xpi"))

    def search_for(self, query):
        logging.info("Navigating to https://free-mp3-download.net/")
        self.browser.get("https://free-mp3-download.net/")
        self.wait_engine.wait()
        search_box = self.browser.find_element_by_id("q")
        search_box.clear()
        search_box.send_keys(query)
        search_btn = self.browser.find_element_by_id("snd")
        logging.info(f"Searching for {query}.")
        search_btn.click()

    def choose_first_result(self):
        self.wait_engine.wait()
        result_link = self.browser.find_element_by_xpath("/html/body/main/div/div[2]/div/table/tbody/tr[1]/td["
                                                         "3]/a/button")
        result_link.click()
        self.wait_engine.wait()
        # logging.info("Closing advertisement.")
        # webdriver.ActionChains(self.browser).send_keys(Keys.ESCAPE).perform()
        # WebDriverWait(self.browser, 10).until(
        #     EC.url_contains("download.php")
        # )

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
        self.wait_engine.wait()
        download_btn.click()
        self.wait_engine.wait(15)

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


def process_deezer_url(url):
    client = deezer.Client()
    if url.startswith("https://www.deezer.com/us/album/"):
        album_id = int(url[len("https://www.deezer.com/us/album/"):])
        artist = client.get_album(album_id).get_artist()
        return [f"{artist.name} - {track.title}" for track in client.get_album(album_id).get_tracks()]
    elif url.startswith("https://www.deezer.com/us/track/"):
        track_id = int(url[len("https://www.deezer.com/us/track/"):])
        track = client.get_track(track_id)
        artist = track.get_artist()
        return [f"{artist.name} - {track.title}"]
    elif url.startswith("https://www.deezer.com/us/playlist/"):
        playlist_id = int(url[len("https://www.deezer.com/us/playlist/"):])
        return [f"{track.get_artist().name} - {track.title}" for track in client.get_playlist(playlist_id).get_tracks()]


def main():
    deezer_url = input("Enter a deezer url: ")
    song_list = process_deezer_url(deezer_url)
    downloader = Downloader("flac")
    downloader.download_list(song_list)


main()
