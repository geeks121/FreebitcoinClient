import logging
import random
import re
import time

from collections import namedtuple

from selenium import webdriver
from selenium.webdriver.chrome.options import Options as ChromeOptions
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
from selenium.common.exceptions import TimeoutException
from selenium.common.exceptions import NoSuchElementException


class RewardType:
    _RewardDefinition = namedtuple('RewardType', ['name', 'bonus_id'])

    Points = _RewardDefinition('Rewards Points Booster', 'free_points')
    Lottery = _RewardDefinition('Free Lottery Tickets', 'free_lott')
    FreeBTC = _RewardDefinition('Free BTC Booster', 'fp_bonus')


def check_login(func):
    def wrapper(*args, **kwargs):
        self = args[0]
        try:
            self._driver.find_element_by_id('balance')
            return func(*args, **kwargs)
        except NoSuchElementException:
            self._logger.error('You are not logged in')

    return wrapper


class Client:
    _URL = 'https://freebitco.in'

    def __init__(self):
        self._logger = logging.getLogger('root.fbclient')
        self._timeout = 15
        options = ChromeOptions()
        options.add_argument('--headless')
        options.add_argument('--window-size=1280,1024')
        options.add_argument('--no-sandbox')
        self._driver = None
        try:
            self._driver = webdriver.Chrome(chrome_options=options)
            self._driver.get(self._URL)
        except:
            self._logger.exception('Error')
            self.close()
            raise

    def login(self, username, password, two_factor_auth=None):
        self._logger.info('Starting login')
        user_field = self._driver.find_element_by_id('login_form_btc_address')
        self._driver.execute_script('arguments[0].value = "%s"' % username, user_field)
        password_field = self._driver.find_element_by_id('login_form_password')
        self._driver.execute_script('arguments[0].value = "%s"' % password, password_field)
        if two_factor_auth:
            two_factor_auth_field = self._driver.find_element_by_id('login_form_2fa')
            self._driver.execute_script('arguments[0].value = "%s"' % two_factor_auth, two_factor_auth_field)
        login_button = self._driver.find_element_by_id('login_button')
        self._driver.execute_script('arguments[0].click()', login_button)

        start = time.time()
        while (time.time() - start) < self._timeout:
            try:
                WebDriverWait(self._driver, 0.1).until(EC.presence_of_element_located((By.ID, 'balance')))
                self._logger.info('Login successful')
                return True
            except TimeoutException:
                pass

            try:
                error = WebDriverWait(self._driver, 0.1).until(
                    EC.visibility_of_element_located((By.CSS_SELECTOR, "#reward_point_redeem_result_container_div > p.reward_point_redeem_result_error > span.reward_point_redeem_result")))
                self._logger.error('Unable to login: %s' % error.text)
                return False
            except TimeoutException:
                pass

        self._logger.error('Login failed, unknown error')
        return False

    def _activate_bonus(self, reward_type, amount):
        self._logger.info('Activating: %s %d bonus' % (reward_type.name, amount))
        container = 'bonus_container_%s' % reward_type.bonus_id

        try:
            WebDriverWait(self._driver, self._timeout).until(EC.invisibility_of_element_located((By.ID, container)))
        except TimeoutException:
            self._logger.error('Bonus is already active')
            return False

        self._driver.execute_script('RedeemRPProduct("%s_%d");' % (reward_type.bonus_id, amount))

        start = time.time()
        while (time.time() - start) < self._timeout:
            try:
                WebDriverWait(self._driver, 0.1).until(EC.visibility_of_element_located((By.ID, container)))
                self._logger.info('Bonus claim successful')
                return True
            except TimeoutException:
                pass

            try:
                error = WebDriverWait(self._driver, 0.1).until(
                    EC.visibility_of_element_located((By.CSS_SELECTOR, "#reward_point_redeem_result_container_div > p.reward_point_redeem_result_error > span.reward_point_redeem_result")))

                if error.is_displayed():
                    self._logger.error('Bonus claim failed: %s' % error.text)
                    return False
            except TimeoutException:
                pass

        self._logger.error('Bonus claim unsuccessful, unknown error')
        return False

    @check_login
    def activate_rp_bonus(self, amount=10): #ubah jika memenuhi syarat
        return self._activate_bonus(RewardType.Points, amount)

    @check_login
    def activate_lottery_bonus(self, amount=100):
        return self._activate_bonus(RewardType.Lottery, amount)

    @check_login
    def activate_btc_bonus(self, amount=1000):
        return self._activate_bonus(RewardType.FreeBTC, amount)

    def _get_roll_number(self):
        digits = (
            self._driver.find_element_by_id('free_play_first_digit').text,
            self._driver.find_element_by_id('free_play_second_digit').text,
            self._driver.find_element_by_id('free_play_third_digit').text,
            self._driver.find_element_by_id('free_play_fourth_digit').text,
            self._driver.find_element_by_id('free_play_fifth_digit').text,
        )
        return ''.join(digits)

    def _randomise_seed(self, length=64):
        chars = 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ01234567890!@#$%^&*()'
        seed = str.join('', (random.choice(chars) for i in range(length)))
        seed_field = self._driver.find_element_by_id('next_client_seed')
        self._driver.execute_script('arguments[0].value = "%s"' % seed, seed_field)
        self._logger.debug('Seed: %s' % seed)

    @check_login
    def roll(self):
        self._logger.info('Rolling')

        try:
            WebDriverWait(self._driver, self._timeout).until(EC.invisibility_of_element_located((By.ID, 'time_remaining')))
        except TimeoutException:
            self._logger.error('Roll failed, timer running')
            return False

        try:
            WebDriverWait(self._driver, self._timeout).until(EC.visibility_of_element_located((By.ID, 'free_play_form_button')))
        except TimeoutException:
            self._logger.error('Roll failed, button not available')
            return False

        play_wo_captcha_button = self._driver.find_element_by_id('play_without_captchas_button')
        self._driver.execute_script('arguments[0].click()', play_wo_captcha_button)

        self._randomise_seed()
        free_play_button = self._driver.find_element_by_id('free_play_form_button')
        self._driver.execute_script('arguments[0].click()', free_play_button)

        start = time.time()
        while (time.time() - start) < self._timeout:
            try:
                roll_result = WebDriverWait(self._driver, 0.1).until(
                    EC.visibility_of_element_located((By.CSS_SELECTOR, '#free_play_result > div')))
                self._logger.info('Rolled number: %s' % self._get_roll_number())
                self._logger.info('Rolled result: %s' % roll_result.text)

                # Close annoying popup
                modal = self._driver.find_element_by_css_selector('#myModal22 > a')
                self._driver.execute_script('arguments[0].click()', modal)

                return True
            except (TimeoutException, NoSuchElementException):
                pass

            try:
                error = WebDriverWait(self._driver, 0.1).until(
                    EC.visibility_of_element_located((By.CSS_SELECTOR, "#reward_point_redeem_result_container_div > p.reward_point_redeem_result_error > span.reward_point_redeem_result")))
                self._logger.error('Roll failed: %s' % error.text)
                return False
            except TimeoutException:
                pass

        self._logger.error('Roll failed, unknown error')
        return False

    @check_login
    def get_roll_timer(self):
        self._logger.debug('Checking roll timer')
        try:
            timer = self._get_timer_element('#time_remaining').text
            timer = timer.replace('\r', ' ').replace('\n', ' ')
            self._logger.debug('Roll timer: %s' % timer)
            match = re.match('(\d{1,2})\s*Minutes\s*(\d{1,2})\s*Seconds', timer)
            secs = int(match.group(1)) *  60 + int(match.group(2))
            return secs
        except NoSuchElementException:
            self._logger.debug('Timer not running')
        except (ValueError, IndexError, AttributeError):
            self._logger.error('Timer cannot be parsed')

        return 0

    @check_login
    def get_balance(self):
        self._logger.info('Getting balance')
        try:
            balance = self._driver.find_element_by_id('balance').get_attribute('textContent')
            self._logger.debug('Balance: %s' % balance)
            return float(balance)
        except NoSuchElementException:
            self._logger.error('Unable to retrieve balance')
        except ValueError:
            self._logger.error('Points balance does not appear to be a number')

        return None

    def _get_rewards_timer(self, reward_type):
        self._logger.debug('Checking %s timer' % reward_type.name)
        span = '#bonus_span_%s' % reward_type.bonus_id

        try:
            timer = self._get_timer_element(span).text
            self._logger.debug('Timer: %s' % timer)
            timer = timer.split(':')
            secs = int(timer[0]) * 3600 + int(timer[1]) * 60 + int(timer[2])
            return secs
        except NoSuchElementException:
            self._logger.debug('Timer not running, bonus is inactive')
        except (IndexError, ValueError):
            self._logger.error('Timer cannot be parsed')

        return 0

    def _get_timer_element(self, selector):
        """ Timers on the page may require multiple attempts to successfully capture
        due to their dynamic nature """
        start = time.time()
        while (time.time() - start) < 1:
            element = self._driver.find_element_by_css_selector(selector)
            if element.is_displayed:
                if element.text:
                    return element
            else:
                # element hidden
                raise NoSuchElementException()

        raise NoSuchElementException()

    @check_login
    def get_rp_bonus_timer(self):
        return self._get_rewards_timer(RewardType.Points)

    @check_login
    def get_lottery_bonus_timer(self):
        return self._get_rewards_timer(RewardType.Lottery)

    @check_login
    def get_btc_bonus_timer(self):
        return self._get_rewards_timer(RewardType.FreeBTC)

    @check_login
    def get_rewards_balance(self):
        self._logger.info('Getting rewards points balance')
        try:
            points = self._driver\
                .find_element_by_css_selector(
                    '#rewards_tab > div:nth-child(2) > div > div.reward_table_box.br_0_0_5_5.user_reward_points.font_bold')\
                .get_attribute('textContent')
            self._logger.debug('Points balance: %s' % points)

            return int(points.replace(',', ''))
        except NoSuchElementException:
            self._logger.error('Unable to retrieve bonus points balance')
        except ValueError:
            self._logger.error('Points balance does not appear to be a number')

        return None

    def close(self):
        if self._driver:
            self._logger.info('Stopping selenium driver')
            self._driver.quit()
