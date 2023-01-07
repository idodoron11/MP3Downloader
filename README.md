# MP3 Downloader
I wrote this script to automate music download from https://free-mp3-download.net.

## Requirements
1. Python 3
2. You will need to have chromedriver installed. The path to the chromedriver binaries should be in the PATH environment variable.
2. You will need to install several python modules, listed in the `requirements.txt` file. Use this command to install them: 
    ```bash
    pip install -r requirements.txt
    ```
## How To Use
### Interactive Mode
1. Run `main.py` using python.
2. You will be prompt to choose which format to download (MP3 or FLAC).
3. A Chrome window will open up.
4. You will be prompt to provide an url to a Deezer track, album or public playlist.
5. The automation will start downloading all the tracks in the url.
   - The automation may pause if it encounters a CAPTCHA challenge. When it happens, you should manually solve the CAPTCHA challenge, and then return to the console and press ENTER to proceed.
6. Once all the files have been downloaded, the program will try to tag them using Deezer metadata.
7. When the process ends, the user is may either exit the program or provide another Deezer url to process

### CLI Mode
1. Run the program using
    ```bash
    python3 ./main.py <format> <deezer url>
    ```
   - `<format>`  may be `flac`, `mp3-320` or `mp3-128`
   - `<deezer url>` is an url to the deezer page of a track, album or public playlist
2. A Chrome window will open up and the automation will start downloading all the tracks in the url.
    - The automation may pause if it encounters a CAPTCHA challenge. When it happens, you should manually solve the CAPTCHA challenge, and then return to the console and press ENTER to proceed.
3. Once all the files have been downloaded, the program will try to tag them using Deezer metadata.