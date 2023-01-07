import io
from abc import ABC, abstractmethod

import deezer
from deezer import Track, Album, Artist
import music_tag
import requests
import shutil
from PIL import Image


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

    def _set_state(self, filepath: str, track: Track):
        self.filepath = filepath
        self.track = track
        self.rollback()

    def tag(self, filepath: str, track: Track):
        self._set_state(filepath, track)
        tags = self.get_tags_from_track()
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
        r = requests.get(url, stream=True)
        r.raw.decode_content = True
        with io.BytesIO(r.content) as buf:
            self.file['artwork'] = buf.read()

deezer_client = deezer.Client()
downloaded_files = dict()
downloaded_files['/Users/idodoron/Downloads/Music/Avicii/The Days / Nights (EP)/1-01 Avicii - The Days.flac'] = deezer_client.get_track(90632835)
downloaded_files['/Users/idodoron/Downloads/Music/Avicii/The Days / Nights (EP)/1-02 Avicii - The Nights.flac'] = deezer_client.get_track(90632837)
downloaded_files['/Users/idodoron/Downloads/Music/Avicii/The Days / Nights (EP)/1-03 Avicii - The Days (Henrik B Remix).flac'] = deezer_client.get_track(90632839)
downloaded_files['/Users/idodoron/Downloads/Music/Avicii/The Days / Nights (EP)/1-04 Avicii - The Nights (Felix Jaehn Remix).flac'] = deezer_client.get_track(90632841)
tagger = DeezerTagger()
for filepath, track in downloaded_files.items():
    tagger.tag(filepath, track)
    tagger.commit()