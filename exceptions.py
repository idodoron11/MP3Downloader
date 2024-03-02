class DownloaderException(Exception):
    pass

class UnsupportedFormatException(DownloaderException):
    pass

class UnsupportedBitrateException(DownloaderException):
    pass

class DownloadTimeoutException(DownloaderException):
    pass

class ServerError(DownloaderException):
    pass

class UIException(Exception):
    pass


class TaggerException(Exception):
    pass

class InvalidInput(ValueError):
    pass