import sys
import time
import traceback
import selenium.common.exceptions
from deezer import Track
from selenium import webdriver
from selenium.webdriver.common.by import By
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
from pathlib import Path
import re
from tagger import DeezerTagger

# settings
logging.basicConfig(format='%(asctime)s - %(levelname)s - %(message)s', level=logging.INFO)
WAIT_ENGINE_DEFAULT_RESET_INTERMAL = 15  # after every x minutes the wait engine will require a long break
SHORT_WAIT_GAMMA_PARAMETERS = (2, 2.2)  # first parameter is k and the second is theta
LONG_WAIT_GAMMA_PARAMETERS = (6, 60)  # see: https://www.medcalc.org/manual/gamma-distribution-functions.php
_HOME_DIR = Path.home()
DOWNLOAD_DIR = os.path.join(_HOME_DIR, "Downloads", "Music")
BYPASS_WAIT = True  # determines whether the wait engine should wait between actions


class WaitEngine:
    def __init__(self):
        self.lastReset = self.nextReset = None
        self.resetInterval = WAIT_ENGINE_DEFAULT_RESET_INTERMAL
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
        if BYPASS_WAIT:
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
    def __init__(self, format="mp3-320"):
        self.wait_engine = WaitEngine()
        self.wait_engine.pause()
        if format in ["flac", "mp3-128", "mp3-320"]:
            self.format = format
        else:
            self.format = "mp3-320"

        logging.info("Opening a new browser window")
        self.download_path = DOWNLOAD_DIR
        options = webdriver.ChromeOptions()
        options.add_experimental_option("prefs", {
            "download.default_directory": self.download_path
        })
        self.browser = webdriver.Chrome(options=options)

    def open_download_page(self, track):
        logging.info("Going back to homepage")
        self.browser.get("https://free-mp3-download.net/")
        try:
            WebDriverWait(self.browser, 30).until(
                EC.presence_of_element_located((By.XPATH, '//button[@id="snd"]'))
            )
            logging.info(f"Opening the download page of track {track.id}")
            self.browser.execute_script(f'window.location.href = "https://free-mp3-download.net/download.php?id={track.id}"')
            logging.debug("Waiting for page load")
            WebDriverWait(self.browser, 30).until(
                EC.presence_of_element_located((By.CLASS_NAME, "dl"))
            )
        except Exception as e:
            logging.error("Failed to load the download page")
            logging.error(traceback.format_exc())

    def process_download_page(self):
        format_selector = self.browser.find_element(By.ID, self.format)
        self.browser.execute_script("arguments[0].click();", format_selector)
        captcha = self.browser.find_elements(By.ID, "captcha")
        if len(captcha) > 0:
            captcha = captcha[0]
            if captcha.is_displayed():
                self.wait_engine.pause()
                input("Please solve the CAPTCHA challenge before proceeding.\n"
                      "Press ENTER to proceed.")
                self.wait_engine.resume()
        # format_selector.click()
        download_btn = self.browser.find_element(By.CLASS_NAME, "dl")
        self.wait_engine.wait()
        download_btn.click()

    def wait_for_download_finish(self, success_cb=lambda *args: None, failure_cb=lambda *args: None, wait_time=1):
        logging.info("Waiting for download completion")
        wait_until = datetime.datetime.now() + datetime.timedelta(minutes=wait_time)
        while datetime.datetime.now() <= wait_until:
            dir_content = glob.glob(os.path.join(self.download_path, "*.*"))
            if len(dir_content) == 0:
                logging.debug("Download has not started yet")
            else:
                latest_file = max(dir_content, key=os.path.getctime)
                _, extension = os.path.splitext(latest_file)
                if extension == ".crdownload":
                    logging.debug("Download has not finished yet")
                else:
                    return success_cb(latest_file)
            time.sleep(1)
        return failure_cb()

    def download(self, track):
        def on_download_success(filepath, target_dir=None):
            artist = track.artist.name
            album = track.album.title
            if target_dir is None:
                target_dir = os.path.join(self.download_path, artist, album)
            if not os.path.exists(target_dir):
                os.makedirs(target_dir)
            new_filepath = os.path.join(target_dir, f"{track.disk_number}-{track.track_position:02} {track.artist.name} - {track.title}.{self.format}")
            shutil.move(filepath, new_filepath)
            logging.info(f"Track {track.id} has been saved to {new_filepath}")
            return new_filepath

        def on_download_failure():
            raise Exception("Download failure")

        self.wait_engine.resume()
        self.open_download_page(track)
        try:
            self.process_download_page()
            filepath = self.wait_for_download_finish(success_cb=on_download_success, failure_cb=on_download_failure)
            if filepath is not None:
                return filepath
        except (selenium.common.exceptions.NoSuchElementException, Exception) as e:
            logging.error(f"Could not download {track.artist.name} - {track.title}.")
            logging.error(traceback.format_exc())
        finally:
            self.wait_engine.pause()

    def download_tracks(self, track_list):
        track_map = dict()
        for index, track in enumerate(track_list):
            filepath = self.download(track)
            if filepath is not None:
                track_map[filepath] = track
        return track_map


def process_deezer_url(url):
    client = deezer.Client()
    match = re.match("^(https:\/\/www\.deezer\.com\/[^\/]*\/)(playlist|album|track)\/(\d*)", url)
    if not match:
        raise Exception("Invalid URL")
    urlType = match.group(2)
    urlId = match.group(3)
    if urlType == "album":
        album_id = urlId
        album = client.get_album(album_id)
        artist = album.get_artist()
        return artist.name, album.title, client.get_album(album_id).get_tracks()
    elif urlType == "track":
        track_id = urlId
        track = client.get_track(track_id)
        artist = track.get_artist()
        album = track.get_album()
        return artist.name, album.title, track
    elif urlType == "playlist":
        playlist_id = urlId
        playlist = client.get_playlist(playlist_id)
        return "Playlists", playlist.title, playlist.get_tracks()



def tag_downloaded_files(downloaded_files: dict[str, Track]):
    tagger = DeezerTagger()
    for filepath, track in downloaded_files.items():
        try:
            tagger.tag(filepath, track)
            tagger._commit()
        except:
            logging.error(f"Could not tag {filepath}")
            logging.error(traceback.format_exc())
            tagger._rollback()

def main():
    is_interactive = len(sys.argv) != 3
    user_format = input("Choose a format (mp3-128 / mp3-320 / flac): ") if is_interactive else sys.argv[1]
    downloader = Downloader(user_format)

    while 1:
        deezer_url = input("Enter a deezer url: ") if is_interactive else sys.argv[2]
        artist, album, tracks = process_deezer_url(deezer_url)
        downloaded_files = downloader.download_tracks(tracks)
        tag_downloaded_files(downloaded_files)
        if not is_interactive:
            break
        stay_in_loop = input("Would you like to download more stuff? (yes / no): ")
        if stay_in_loop.lower() == "no":
            break
        elif stay_in_loop.lower() != "yes":
            print("I'm assuming that was a \"yes\".")


main()
