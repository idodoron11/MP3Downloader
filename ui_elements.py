from selenium.webdriver.common.by import By

HOME_PAGE = {
    "search_btn": (By.XPATH, '//button[@id="snd"]')
}

DOWNLOAD_PAGE = {
    "download_btn": (By.CLASS_NAME, "dl"),
    "mp3_128_radio_btn": (By.ID, "mp3-128"),
    "mp3_320_radio_btn": (By.ID, "mp3-320"),
    "flac_radio_btn": (By.ID, "flac"),
    "captcha": (By.XPATH, '//iframe[@title="reCAPTCHA"]')
}