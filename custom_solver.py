from typing import Optional

from selenium.common import TimeoutException, ElementClickInterceptedException
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as ec
from selenium.webdriver.support.wait import WebDriverWait
from selenium_recaptcha_solver import RecaptchaSolver
from selenium.webdriver.remote.webelement import WebElement

class CustomRecaptchaSolver(RecaptchaSolver):
    def solve_recaptcha_v2_challenge(self, iframe: WebElement) -> None:
        self._driver.switch_to.frame(iframe)

        # If the captcha image audio is available, locate it. Otherwise, skip to the next line of code.

        try:
            verified_icon = self._wait_for_element(
                by=By.CSS_SELECTOR,
                locator=".recaptcha-checkbox-checkmark",
                timeout=10
            )
            self._driver.switch_to.parent_frame()
            return
        except TimeoutException:
            pass

        try:
            audio_btn = self._wait_for_element(by=By.XPATH, locator='//*[@id="recaptcha-audio-button"]', timeout=1, )
            audio_btn.click()

        except TimeoutException:
            pass
        except ElementClickInterceptedException:
            self._driver.execute_script("arguments[0].click();", audio_btn)
        except Exception as e:
            pass

        self._solve_audio_challenge(self._language)

        # Locate verify button and click it via JavaScript
        verify_button = self._wait_for_element(
            by=By.ID,
            locator='recaptcha-verify-button',
            timeout=5,
        )

        self._js_click(verify_button)

        if self._delay_config:
            self._delay_config.delay_after_click_verify_button()

        try:
            self._wait_for_element(
                by=By.XPATH,
                locator='//div[normalize-space()="Multiple correct solutions required - please solve more."]',
                timeout=1,
            )

            self._solve_audio_challenge(self._language)

            # Locate verify button again to avoid stale element reference and click it via JavaScript
            second_verify_button = self._wait_for_element(
                by=By.ID,
                locator='recaptcha-verify-button',
                timeout=5,
            )

            self._js_click(second_verify_button)

        except TimeoutException:
            pass

        self._driver.switch_to.parent_frame()

    def click_recaptcha_v2(self, iframe: WebElement, by_selector: Optional[str] = None) -> None:
        if isinstance(iframe, str):
            WebDriverWait(self._driver, 10).until(
                ec.frame_to_be_available_and_switch_to_it((by_selector, iframe)))

        else:
            self._driver.switch_to.frame(iframe)

        checkbox = self._wait_for_element(
            by='id',
            locator='recaptcha-anchor',
            timeout=10,
        )

        self._js_click(checkbox)

        if checkbox.get_attribute('aria-checked') == 'true':
            return

        if self._delay_config:
            self._delay_config.delay_after_click_checkbox()

        self._driver.switch_to.parent_frame()

        captcha_challenge = self._wait_for_element(
            by=By.XPATH,
            locator='//iframe[contains(@src, "recaptcha") and (contains(@src, "bframe") or contains(@src, "anchor"))]',
            timeout=20,
        )

        self.solve_recaptcha_v2_challenge(iframe=captcha_challenge)