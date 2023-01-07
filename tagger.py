import io
from abc import ABC, abstractmethod
import deezer
from deezer import Track, Album, Artist
import music_tag
import requests
import logging

logging.basicConfig(format='%(asctime)s - %(levelname)s - %(message)s', level=logging.INFO)


class TagsStruct:
    def __int__(self):
        self.title = None
        self.artists = None
        self.album_artist = None
        self.album = None
        self.track_position = None
        self.total_tracks = None
        self.disc_number = None
        self.release_date = None
        self.album_artwork = None
        self.genres = None
        self.isrc = None


class Tagger(ABC):
    @abstractmethod
    def tag(self, filepath, track):
        pass


class DeezerTagger(Tagger):
    def __init__(self):
        self.filepath = None
        self.track = None
        self.file = None
        self.image_downloader = ImageDownloader()

    def _set_state(self, filepath: str, track: Track):
        self.filepath = filepath
        self.track = track
        self.rollback()

    def tag(self, filepath: str, track: Track):
        self._set_state(filepath, track)
        tags = self.get_tags_from_track()
        self.clear_tags()
        self.override_tag("title", tags.title)
        self.override_tag("artist", tags.artists)
        self.override_tag("albumartist", tags.album_artist)
        self.override_tag("album", tags.album)
        self.override_tag("tracknumber", tags.track_position)
        self.override_tag("totaltracks", tags.total_tracks)
        self.override_tag("discnumber", tags.disc_number)
        self.override_tag("year", tags.release_date.strftime("%Y-%m-%d"))
        self._set_artwork(tags.album_artwork)
        self.override_tag("genre", tags.genres)
        self.override_tag("isrc", tags.isrc)

    def commit(self):
        self.file.save()

    def rollback(self):
        self.file = music_tag.load_file(self.filepath)

    def override_tag(self, tag, values, force=False):
        self.file.remove_tag(tag)
        if force:
            self.file.raw[tag] = values
        elif isinstance(values, list):
            for value in values:
                self.file.append_tag(tag, value)
        else:
            self.file.set(tag, values)

    def clear_tags(self):
        for tag in filter(lambda x: not x.startswith('#'), self.file.tag_map):
            self.file.remove_tag(tag)

    def get_tags_from_track(self) -> TagsStruct:
        tags = TagsStruct()
        tags.title = self.track.title
        tags.artists = [artist.name for artist in self.track.contributors]
        tags.album_artist = self.track.artist.name
        tags.album = self.track.album.title
        tags.track_position = self.track.track_position
        tags.total_tracks = self.track.album.nb_tracks
        tags.disc_number = self.track.disk_number
        tags.release_date = self.track.album.release_date
        tags.album_artwork = self.track.album.cover_xl
        tags.genres = [genre.name for genre in self.track.album.genres]
        tags.isrc = self.track.isrc
        return tags

    def _set_artwork(self, url):
        r = self.image_downloader.download(url)
        with io.BytesIO(r.content) as buf:
            self.file['artwork'] = buf.read()


class Cache:
    def __init__(self, size=5):
        self.size = size
        if self.size < 0:
            self.size = 5
        self.keys = [None for i in range(size)]
        self.values = [None for i in range(size)]
        self.head = -1

    def search(self, key):
        if self.head == -1:
            return None
        index = self.get_key_index(key)
        if index != -1:
            return self.values[index]
        else:
            return None

    def get_key_index(self, key):
        for i in range(self.size):
            if key == self.keys[i]:
                return i
        return -1

    def put(self, key, value):
        index = self.get_key_index(key)
        if index == -1:
            index = (self.head + 1) % self.size
        self.keys[index] = key
        self.values[index] = value
        self.head = (self.head + 1) % self.size


class ImageDownloader:
    def __init__(self):
        self.image_cache = Cache(size=5)

    def download(self, url):
        result = self.image_cache.search(url)
        if result is None:
            logging.debug("Cache miss")
            result = requests.get(url, stream=True)
            result.raw.decode_content = True
            self.image_cache.put(url, result)
            return result
        else:
            logging.debug("Cache hit")
            return result


deezer_client = deezer.Client()
downloaded_files = dict()
downloaded_files[
    '/Users/idodoron/Downloads/Music/Avicii/The Days / Nights (EP)/1-01 Avicii - The Days.flac'] = deezer_client.get_track(
    90632835)
downloaded_files[
    '/Users/idodoron/Downloads/Music/Avicii/The Days / Nights (EP)/1-02 Avicii - The Nights.flac'] = deezer_client.get_track(
    90632837)
downloaded_files[
    '/Users/idodoron/Downloads/Music/Avicii/The Days / Nights (EP)/1-03 Avicii - The Days (Henrik B Remix).flac'] = deezer_client.get_track(
    90632839)
downloaded_files[
    '/Users/idodoron/Downloads/Music/Avicii/The Days / Nights (EP)/1-04 Avicii - The Nights (Felix Jaehn Remix).flac'] = deezer_client.get_track(
    90632841)
tagger = DeezerTagger()
for filepath, track in downloaded_files.items():
    tagger.tag(filepath, track)
    tagger.commit()
