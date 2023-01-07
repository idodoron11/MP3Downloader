import io
from abc import ABC, abstractmethod
import mutagen
from mutagen.flac import FLAC
from mutagen.easyid3 import EasyID3
from deezer import Track, Album, Artist
import music_tag
import requests
import logging


class TagsStruct:
    def __init__(self):
        self.title = None
        self.artists = None
        self.album_artist = None
        self.album = None
        self.track_position = None
        self.total_tracks = None
        self.disc_number = None
        self.total_discs = None
        self.release_date = None
        self.album_artwork = None
        self.genres = None
        self.isrc = None
        self.label = None


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
        self.tag_engine = "music_tag"

    def _set_state(self, filepath: str, track: Track):
        self.filepath = filepath
        self.track = track
        self.clear_tags()

    def tag(self, filepath: str, track: Track):
        try:
            self._set_state(filepath, track)
            tags = self.get_tags_from_track()

            self._open_file("music_tag")
            self._add_conventional_tag("title", tags.title)
            self._add_conventional_tag("artist", tags.artists)
            self._add_conventional_tag("albumartist", tags.album_artist)
            self._add_conventional_tag("album", tags.album)
            self._add_conventional_tag("tracknumber", tags.track_position)
            self._add_conventional_tag("totaltracks", tags.total_tracks)
            self._add_conventional_tag("discnumber", tags.disc_number)
            self._add_conventional_tag("totaldiscs", tags.total_discs)
            self._add_conventional_tag("year", tags.release_date.strftime("%Y"))
            self._set_artwork(tags.album_artwork)
            self._add_conventional_tag("genre", tags.genres)
            self._add_conventional_tag("isrc", tags.isrc)
            self._commit()

            self._open_file("mutagen")
            self._add_custom_tag("date", tags.release_date.strftime("%Y-%m-%d"))
            self._add_custom_tag("organization", tags.label)
            self._commit()
        except Exception as e:
            self._rollback()
            raise e

    def _commit(self):
        self.file.save()

    def _rollback(self):
        self._open_file(self.tag_engine)

    def _open_file(self, tag_engine):
        self.tag_engine = tag_engine
        if tag_engine == "mutagen":
            try:
                self.file = EasyID3(self.filepath)
            except:
                self.file = mutagen.File(self.filepath)
        elif tag_engine == "music_tag":
            self.file = music_tag.load_file(self.filepath)

    def _add_conventional_tag(self, tag, values, override=False, raw=False):
        if override:
            self.file.remove_tag(tag)
        if raw:
            self.file.raw[tag] = values
        elif isinstance(values, list):
            for value in values:
                self.file.append_tag(tag, value)
        else:
            self.file.set(tag, values)

    def _add_custom_tag(self, tag, value):
        if isinstance(value, list):
            self.file[tag] = value
        else:
            if tag in self.file:
                values = list(self.file[tag])
                values.append(value)
            else:
                values = [value]
            self.file[tag] = values

    def clear_tags(self):
        orig_tag_engine = self.tag_engine
        self._open_file("mutagen")
        self.file.delete()
        if isinstance(self.file, FLAC):
            for picture in self.file.pictures:
                picture.data = b''
        self.file.save()
        self.tag_engine = orig_tag_engine

    def get_tags_from_track(self) -> TagsStruct:
        tags = TagsStruct()
        tags.title = self.track.title
        tags.artists = [artist.name for artist in self.track.contributors]
        tags.album_artist = self.track.artist.name
        tags.album = self.track.album.title
        tags.track_position = self.track.track_position
        tags.total_tracks = self.track.album.nb_tracks
        tags.disc_number = self.track.disk_number
        tags.total_discs = max(track.disk_number for track in self.track.album.tracks)
        tags.release_date = self.track.album.release_date
        tags.album_artwork = self.track.album.cover_xl
        tags.genres = [genre.name for genre in self.track.album.genres]
        tags.isrc = self.track.isrc
        tags.label = self.track.album.label
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
