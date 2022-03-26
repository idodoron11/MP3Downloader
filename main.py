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
import shutil
import glob
import deezer

# settings
logging.basicConfig(format='%(asctime)s - %(levelname)s - %(message)s', level=logging.INFO)
MINIMUM_WAIT_AFTER_DOWNLOAD = 20  # increase this number if you experience crushes
WAIT_ENGINE_DEFAULT_RESET_INTERMAL = 15  # after every x minutes the wait engine will require a long break
SHORT_WAIT_GAMMA_PARAMETERS = (2, 2.2)  # first parameter is k and the second is theta
LONG_WAIT_GAMMA_PARAMETERS = (6, 60)  # see: https://www.medcalc.org/manual/gamma-distribution-functions.php
DOWNLOAD_DIR = os.path.join(os.environ['USERPROFILE'], "Downloads", "Music")
USET_CHOISE_TIMEOUT = 10  # how much time the user is given to choose a search result manually


class WaitEngine:
    def __init__(self):
        self.lastReset = self.nextReset = None
        self.resetInterval = WAIT_ENGINE_DEFAULT_RESET_INTERMAL
        self.bypassWait = False
        self.lastPause = None
        self.reset()

    def reset(self):
        self.lastPause = self.lastReset = datetime.datetime.now()
        self.nextReset = self.lastReset + datetime.timedelta(minutes=self.resetInterval)
        logging.info(f"Wait engine has been reset. Next reset will be in {self.resetInterval} minutes.")

    def pause(self):
        self.lastPause = datetime.datetime.now()

    def resume(self):
        delta = datetime.datetime.now() - self.lastPause
        self.nextReset += delta
        self.lastPause = None

    def wait(self, minimum=0, message=""):
        if self.lastPause is not None:
            return
        if message is not None and message != "":
            print(message)
        current_time = datetime.datetime.now()
        if self.bypassWait:
            logging.info(f"Waiting {minimum} seconds.")
            sleep(minimum)
        elif current_time >= self.nextReset:
            k, theta = LONG_WAIT_GAMMA_PARAMETERS
            penalty = max(minimum, np.random.gamma(k, theta))
            logging.info(f"Waiting {penalty} seconds.")
            sleep(penalty)
            self.reset()
        else:
            k, theta = SHORT_WAIT_GAMMA_PARAMETERS
            penalty = max(minimum, np.random.gamma(k, theta))
            logging.info(f"Waiting {penalty} seconds.")
            sleep(penalty)


class Downloader:
    def __init__(self, format="mp3"):
        self.wait_engine = WaitEngine()
        self.wait_engine.pause()
        # self.wait_engine.bypassWait = True # uncomment to prevent waiting between actions
        if format in ["flac", "mp3"]:
            self.format = format
        else:
            self.format = "mp3"
        logging.info("Opening a new browser window")
        options = Options()
        self.download_path = DOWNLOAD_DIR
        options.set_preference("browser.download.dir", self.download_path)
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
        link_row = self.browser.find_element_by_xpath("/html/body/main/div/div[2]/div/table/tbody/tr[1]")
        self.browser.execute_script("arguments[0].setAttribute(argument[1], argument[2])", link_row, "style",
                                    "background: orange;")
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
                self.wait_engine.pause()
                input("Please solve the CAPTCHA challenge before proceeding.\n"
                      "Press ENTER to proceed.")
                self.wait_engine.resume()
        # format_selector.click()
        download_btn = self.browser.find_element_by_class_name("dl")
        self.wait_engine.wait()
        download_btn.click()
        self.wait_engine.wait(MINIMUM_WAIT_AFTER_DOWNLOAD)

    def download(self, query):
        self.wait_engine.resume()
        self.search_for(query)
        try:
            self.wait_engine.wait(USET_CHOISE_TIMEOUT, f"You have a {USET_CHOISE_TIMEOUT} seconds opportunity to "
                                                       f"manually choose which song to download.")
            if not self.browser.current_url.startswith("https://free-mp3-download.net/download.php"):
                self.choose_first_result()
            self.process_download_page()
        except selenium.common.exceptions.NoSuchElementException:
            logging.error(f"Could not download {query}.")
        finally:
            self.wait_engine.pause()

    def download_list(self, list):
        for index, item in enumerate(list):
            self.download(item)

    def tidy_up_downloaded_files(self, subfolder1, subfolder2):
        target_dir = os.path.join(self.download_path, subfolder1)
        if not os.path.exists(target_dir):
            os.makedirs(target_dir)
        target_dir = os.path.join(target_dir, subfolder2)
        if not os.path.exists(target_dir):
            os.makedirs(target_dir)
        files = glob.glob(os.path.join(self.download_path, "*.*"))
        files = [(os.path.basename(filepath), filepath) for filepath in files]
        files.sort(key=lambda item: os.path.getmtime(item[1]))
        for index, (filename, filepath) in enumerate(files):
            new_filepath = os.path.join(self.download_path, f"{index + 1:02} {filename}")
            shutil.move(filepath, new_filepath)
            shutil.move(new_filepath, target_dir)


def process_deezer_url(url):
    client = deezer.Client()
    if url.startswith("https://www.deezer.com/us/album/"):
        album_id = int(url[len("https://www.deezer.com/us/album/"):])
        album = client.get_album(album_id)
        artist = album.get_artist()
        return artist.name, album.title, [f"{artist.name} - {track.title}" for track in
                                          client.get_album(album_id).get_tracks()]
    elif url.startswith("https://www.deezer.com/us/track/"):
        track_id = int(url[len("https://www.deezer.com/us/track/"):])
        track = client.get_track(track_id)
        artist = track.get_artist()
        album = track.get_album()
        return artist.name, album.title, [f"{artist.name} - {track.title}"]
    elif url.startswith("https://www.deezer.com/us/playlist/"):
        playlist_id = int(url[len("https://www.deezer.com/us/playlist/"):])
        playlist = client.get_playlist(playlist_id)
        return "Playlists", playlist.title, [f"{track.get_artist().name} - {track.title}" for track in
                                             playlist.get_tracks()]


def main():
    user_format = input("Choose a format (mp3 / flac): ")
    downloader = Downloader(user_format)

    while 1:
        deezer_url = input("Enter a deezer url: ")
        artist, album, song_list = process_deezer_url(deezer_url)
        downloader.download_list(song_list)
        downloader.tidy_up_downloaded_files(artist, album)
        stay_in_loop = input("Would you like to download more stuff? (yes / no): ")
        if stay_in_loop.lower() == "no":
            break
        elif stay_in_loop.lower() != "yes":
            print("I'm assuming that was a \"yes\".")


main()
