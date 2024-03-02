import base64
import datetime
import glob
import logging
import os
import re
import shutil
import time
import traceback
from pathlib import Path
from time import sleep
from urllib.parse import quote

import click
import deezer
import numpy as np
from deezer import Track, Playlist, Album, Artist
from deezer.exceptions import DeezerAPIException
from selenium import webdriver
from selenium.common.exceptions import ElementClickInterceptedException, NoSuchElementException, TimeoutException
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from tabulate import tabulate

import ui_elements
from custom_solver import CustomRecaptchaSolver
from exceptions import UnsupportedFormatException, UnsupportedBitrateException, UIException, DownloaderException, \
    InvalidInput, DownloadTimeoutException, ServerError
from tagger import DeezerTagger

# logging setup
logger = logging.getLogger("mp3downloader")
logger.setLevel(logging.DEBUG)
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
file_handler = logging.FileHandler('mp3downloader.log', mode='w')
file_handler.setLevel(logging.DEBUG)
file_handler.setFormatter(formatter)
logger.addHandler(file_handler)
stdout_handler = logging.StreamHandler()
stdout_handler.setLevel(logging.INFO)
stdout_handler.setFormatter(formatter)
stdout_handler.propagate = False
logger.addHandler(stdout_handler)

# settings
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
        logger.debug(f"Wait engine has been reset. Next reset will be in {self.resetInterval} minutes.")

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
            if minimum > 0:
                logger.info(f"Waiting {minimum} seconds.")
                sleep(minimum)
            return

        if current_time >= self.nextReset:
            k, theta = LONG_WAIT_GAMMA_PARAMETERS
            penalty = max(minimum, np.random.gamma(k, theta))
            logger.info(f"Waiting {penalty} seconds.")
            sleep(penalty)
            self.reset()
        else:
            k, theta = SHORT_WAIT_GAMMA_PARAMETERS
            penalty = max(minimum, np.random.gamma(k, theta))
            logger.info(f"Waiting {penalty} seconds.")
            sleep(penalty)


class Downloader:
    supported_formats = ["mp3", "flac"]

    def __init__(self):
        self.wait_engine = WaitEngine()
        self.wait_engine.pause()
        self.bitrate = "320"
        self.format = "mp3"

        logger.info("Opening a new browser window")
        self.download_path = DOWNLOAD_DIR
        self.browser = None
        self.captcha_solver = None
        self.init_browser()

    def init_browser(self):
        options = webdriver.ChromeOptions()
        options.add_experimental_option("prefs", {
            "download.default_directory": self.download_path
        })
        options.add_experimental_option('excludeSwitches', ['enable-logging'])
        if self.browser is not None:
            self.browser.close()
        self.browser = webdriver.Chrome(options=options)
        self.captcha_solver = CustomRecaptchaSolver(driver=self.browser)

    def set_format(self, format, bitrate):
        if format is None or format not in Downloader.supported_formats:
            raise UnsupportedFormatException
        if format == "mp3":
            if bitrate not in ["128", "320"]:
                raise UnsupportedBitrateException
        elif format == "flac":
            bitrate = None
        self.format = format
        self.bitrate = bitrate

    def _open_download_page(self, track):
        logger.debug("Going back to homepage")
        self.browser.get("https://free-mp3-download.net/")
        try:
            WebDriverWait(self.browser, 30).until(
                EC.presence_of_element_located(ui_elements.HOME_PAGE["search_btn"])
            )
            logger.info(f"Opening the download page of track {track.id} ({track.artist.name} - {track.title})")
            query_parameter = quote(f"{track.artist.name} - {track.title}")
            encoded_query = base64.b64encode(query_parameter.encode()).decode()
            url = f"https://free-mp3-download.net/download.php?id={track.id}&q={encoded_query}"
            logger.info(f"Navigating to {url}")
            self.browser.execute_script(
                f'window.location.href = "{url}"')
            logger.debug("Waiting for page load")
            WebDriverWait(self.browser, 30).until(
                EC.presence_of_element_located(ui_elements.DOWNLOAD_PAGE["download_btn"])
            )
        except Exception as e:
            logger.error("Failed to load the download page")
            logger.debug(traceback.format_exc())

    def _get_format_selector(self):
        if self.format == "mp3":
            return self.browser.find_element(*ui_elements.DOWNLOAD_PAGE[f"mp3_{self.bitrate}_radio_btn"])
        elif self.format == "flac":
            return self.browser.find_element(*ui_elements.DOWNLOAD_PAGE["flac_radio_btn"])
        else:
            raise UIException("The requested format is unavailable")

    def _handle_captcha(self):
        recaptcha_iframe = self.browser.find_elements(*ui_elements.DOWNLOAD_PAGE["captcha"])
        if len(recaptcha_iframe) <= 0:
            return
        recaptcha_iframe = recaptcha_iframe[0]
        if not recaptcha_iframe.is_displayed():
            return

        self.wait_engine.pause()
        logger.debug("CAPTCHA challenge has been detected")
        try:
            self.captcha_solver.click_recaptcha_v2(iframe=recaptcha_iframe)
            logger.debug("CPATCHA challenge has been solved automatically")
        except:
            logger.debug("Could not solve recaptcha automatically. User has to solve it manually", exc_info=True)
            click.echo("Please solve the CAPTCHA challenge before proceeding.")
            click.confirm("Have you solved it?", default=True)
            logger.debug("The user reports that the CAPTCHA challenge has been solved")
        self.wait_engine.resume()

    def _process_download_page(self):
        format_selector = self._get_format_selector()
        self.browser.execute_script("arguments[0].click();", format_selector)
        self._handle_captcha()
        # format_selector.click()
        download_btn = WebDriverWait(self.browser, 30).until(
            EC.element_to_be_clickable(ui_elements.DOWNLOAD_PAGE["download_btn"])
        )
        self.wait_engine.wait()

        try:
            download_btn.click()
        except ElementClickInterceptedException as e:
            self.browser.execute_script("arguments[0].click();", download_btn)
        if self._is_error_toast_displayed():
            raise ServerError
        pass

    def _is_error_toast_displayed(self):
        try:
            WebDriverWait(self.browser, 10).until(
                EC.presence_of_element_located(ui_elements.DOWNLOAD_PAGE["error_toast"])
            )
            return True
        except (NoSuchElementException, TimeoutException):
            return False

    def _wait_for_download_finish(self, success_cb=lambda *args: None, wait_time=1):
        def _update_status(download_status):
            if _update_status.download_status == download_status:
                return
            _update_status.download_status = download_status
            if download_status == 0:
                logger.info("Waiting for download completion")
            elif download_status == 1:
                logger.debug("Download has not started yet")
            elif download_status == 2:
                logger.debug("Download started")

        _update_status.download_status = -1

        _update_status(0)
        wait_until = datetime.datetime.now() + datetime.timedelta(minutes=wait_time)
        while datetime.datetime.now() <= wait_until:
            dir_content = glob.glob(os.path.join(self.download_path, "*.*"))
            if len(dir_content) == 0:
                _update_status(1)
            else:
                try:
                    latest_file = max(dir_content, key=os.path.getctime)
                except FileNotFoundError as e:
                    # This exception may occur if one of the files in dir_content changed its name, was moved or
                    # removed. After download finish Chrome usually changes the file name, and if we don't have luck it
                    # could happen between dir_content creation to latest_file creation
                    logger.debug("Directory structure changed")
                    continue
                _, extension = os.path.splitext(latest_file)
                if extension[1:] not in Downloader.supported_formats:
                    _update_status(2)
                else:
                    return success_cb(latest_file)
            time.sleep(1)
        raise DownloadTimeoutException

    def get_track_save_location(self, track, extension, playlist_name=None, track_position=None, target_dir=None):
        artist = track.artist.name
        album = track.album.title
        if target_dir is None and playlist_name is not None and track_position is not None:
            target_dir = os.path.join(self.download_path, slugify(playlist_name))
        elif target_dir is None:
            target_dir = os.path.join(self.download_path, slugify(artist), slugify(album))
        if track_position is None:
            position = f"{track.disk_number}-{track.track_position:02}"
        else:
            position = f"{track_position:02}"
        new_filename = f"{position} {track.artist.name} - {track.title}"
        new_filename = slugify(new_filename)
        new_filepath = os.path.join(target_dir, f"{new_filename}{extension}")
        return new_filepath

    def download(self, track, playlist_name=None, track_position=None):
        def on_download_success(filepath):
            _, extension = os.path.splitext(filepath)
            new_filepath = self.get_track_save_location(track, extension, playlist_name=playlist_name,
                                                        track_position=track_position)
            target_dir = os.path.dirname(new_filepath)
            if not os.path.exists(target_dir):
                os.makedirs(target_dir)
            shutil.move(filepath, new_filepath)
            logger.info(f"Track {track.id} has been saved to {new_filepath}")
            return new_filepath



        filepath = self.get_track_save_location(track, "." + self.format, playlist_name=playlist_name,
                                                track_position=track_position)
        if os.path.exists(filepath):
            logger.info(f"Skipping track {track.id}, since it has already been downloaded to '{filepath}'")
            return filepath
        self.wait_engine.resume()
        self._open_download_page(track)
        try:
            self._process_download_page()
            filepath = self._wait_for_download_finish(success_cb=on_download_success)
            if filepath is not None:
                return filepath
        except DownloadTimeoutException as e:
            logger.error(f"Download timeout: {track.artist.name} - {track.title}", exc_info=e)
            self.on_download_tineout()
        except (NoSuchElementException, Exception) as e:
            logger.error(f"Could not download {track.artist.name} - {track.title}", exc_info=e)
        finally:
            self.wait_engine.pause()

    def on_download_tineout(self):
        logger.info("Closing browser and reopening, to ensure no files are being downloaded at the moment")
        self.init_browser()

    def download_tracks(self, deezer_entity):
        track_map = dict()
        logger.debug(f"User asked to download {deezer_entity.link}")
        if isinstance(deezer_entity, Playlist):
            track_list = deezer_entity.tracks
            for index, track in enumerate(track_list):
                filepath = self.download(track, playlist_name=deezer_entity.title, track_position=index + 1)
                if filepath is not None:
                    track_map[filepath] = track
            return track_map
        elif isinstance(deezer_entity, Track):
            track_list = [deezer_entity]
        elif isinstance(deezer_entity, Album):
            track_list = deezer_entity.tracks
        elif isinstance(deezer_entity, Artist):
            albums = deezer_entity.get_albums()
            track_list = list()
            for album in albums:
                for track in album.tracks:
                    track_list.append(track)
        else:
            raise DownloaderException("Unsupported Deezer entity")

        for index, track in enumerate(track_list):
            filepath = self.download(track)
            if filepath is not None:
                track_map[filepath] = track
        return track_map


def process_deezer_url(url):
    client = deezer.Client()
    match = re.match("^(https:\/\/www\.deezer\.com\/([^\/]*\/)?)(playlist|album|track|artist)\/(\d*)", url)
    if not match:
        raise InvalidInput("Invalid URL")
    urlType = match.group(3)
    urlId = match.group(4)
    try:
        if urlType == "album":
            album_id = urlId
            album = client.get_album(album_id)
            return album
        elif urlType == "track":
            track_id = urlId
            track = client.get_track(track_id)
            return track
        elif urlType == "playlist":
            playlist_id = urlId
            playlist = client.get_playlist(playlist_id)
            return playlist
        elif urlType == "artist":
            artist_id = urlId
            artist = client.get_artist(artist_id)
            return artist
    except DeezerAPIException as e:
        logger.error("A Deezer API error occurred", exc_info=e)
        raise DownloaderException("Cannot access the track(s) in the provided Deezer URL")


def tag_downloaded_files(downloaded_files: dict[str, Track]):
    tagger = DeezerTagger()
    for filepath, track in downloaded_files.items():
        try:
            filename = os.path.basename(filepath)
            logger.info(f"Adding the metadata tags of track {track.id} to {filename}")
            tagger.tag(filepath, track)
            tagger._commit()
        except:
            logger.error(f"Could not tag {filepath}")
            logger.debug(traceback.format_exc())
            tagger._rollback()


def slugify(string):
    def predicate(char):
        allow_list = "!@#$%^&()_+=,-';.[]"
        return str.isspace(char) or char in allow_list or str.isalnum(char)

    f = filter(predicate, string.strip('.'))
    return "".join(f)


def process_deezer_entity(downloader, format, bitrate, deezer_entity):
    downloader.set_format(format, bitrate)
    downloaded_files = downloader.download_tracks(deezer_entity)
    tag_downloaded_files(downloaded_files)


def process_user_search(query):
    print("What are we searching for?")
    print("(1) artist")
    print("(2) album")
    print("(3) track")
    type = click.prompt("", type=click.Choice(["1", "2", "3", "artist", "album", "track"]))
    client = deezer.Client()
    max_results_shown = 15
    if type == "1" or type == "artist":
        logger.debug("User searched by artist")
        results = client.search_artists(query)
        headers = ["Choice Number", "Artist"]
        data = [(index + 1, artist.name) for index, artist in enumerate(results[:max_results_shown])]
    elif type == "2" or type == "album":
        logger.debug("User searched by album")
        results = client.search_albums(query)
        headers = ["Choice Number", "Artist", "Album", "Year"]
        data = [(index + 1, album.artist.name, album.title, album.release_date.strftime("%Y")) for index, album in
                enumerate(results[:max_results_shown])]
    elif type == "3" or type == "track":
        logger.debug("User searched by track")
        results = client.search(query)
        headers = ["Choice Number", "Artist", "Title", "Track#", "Album", "Year"]
        data = [(index + 1, track.artist.name, track.title, track.track_position, track.album.title,
                 track.album.release_date.strftime("%Y")) for index, track in enumerate(results[:max_results_shown])]
    else:
        raise InvalidInput

    results_tbl_visual = tabulate(data, headers=headers)
    print(results_tbl_visual)
    logger.debug(f"User is presented the following results:\n{results_tbl_visual}")
    choice = click.prompt("Please choose the desired result by typing in its choice number", type=click.IntRange(0, len(data)))
    logger.debug(f"User chose result number {choice}")
    choice -= 1
    if choice < 0:
        raise InvalidInput("User didn't find what he wanted")
    return results[choice]


def interact_with_user(downloader, format=None, bitrate=None):
    format = click.prompt("Choose a format", type=click.Choice(["mp3", "flac"]), default=format)
    if format == "mp3":
        bitrate = click.prompt("Choose bitrate", type=click.Choice(["128", "320"]), default=bitrate)
    else:
        bitrate = None

    query = click.prompt("Enter a deezer url or a search query", type=str)
    logger.debug(f"User chose format={format}, bitrate={bitrate}, query={query}")
    is_url = re.match("^https?:\/\/(www\.)?([-a-zA-Z0-9@:%._\+~#=]{2,256})+\.[a-z]{2,4}(\/?([-a-zA-Z0-9@:%_\+.~#?&=]+)?)*$",
                      query)
    if is_url:
        deezer_entity = process_deezer_url(query)
    else:
        deezer_entity = process_user_search(query)
    process_deezer_entity(downloader, format, bitrate, deezer_entity)
    return format, bitrate

@click.command()
@click.option("--url", "-u", type=str, default=None, help="URL to a Deezer playlist, album, artist or track page")
@click.option("--format", "-f", type=click.Choice(["mp3", "flac"], case_sensitive=False), help="the audio format to download")
@click.option("--bitrate", "-b", type=click.Choice(["320", "128"]), help="the audio bitrate to download, if mp3 is chosen")
def main(url, format, bitrate):
    interactive_mode = url is None or format is None or (format == "mp3" and bitrate is None)
    downloader = Downloader()
    if interactive_mode:
        start_interactive_mode(downloader)
    else:
        start_cli_mode(downloader, url, format, bitrate)

def start_interactive_mode(downloader):
    logger.debug("MP3 Downloader started in interactive mode")
    format = None
    bitrate = None
    while 1:
        try:
            format, bitrate = interact_with_user(downloader, format, bitrate)
        except:
            logger.error("An error occurred during interaction. Read log for hints")
            logger.debug(traceback.format_exc())
        if not click.confirm("Would you like to download more stuff?"):
            break

def start_cli_mode(downloader, deezer_url, format, bitrate):
    logger.debug("MP3 Downloader started in CLI mode")
    logger.debug(f"User chose format={format}, bitrate={bitrate}, url={deezer_url}")
    if format != "mp3":
        bitrate = None
    deezer_entity = process_deezer_url(deezer_url)
    process_deezer_entity(downloader, format, bitrate, deezer_entity)


if __name__ == "__main__":
    main()
