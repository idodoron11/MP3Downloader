class DownloaderException(Exception):
    pass

class UnsupportedFormatException(DownloaderException):
    pass

class UnsupportedBitrateException(DownloaderException):
    pass

class UIException(Exception):
    pass


class TaggerException(Exception):
    pass

class InvalidInput(ValueError):
    pass