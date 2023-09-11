import os

import httplib2
import random
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaFileUpload
import time
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.keys import Keys
from selenium.common.exceptions import NoSuchElementException

from src.utils import Config

RETRIABLE_EXCEPTIONS = (httplib2.HttpLib2Error, IOError)
RETRIABLE_STATUS_CODES = [500, 502, 503, 504]
YOUTUBE_UPLOAD_SCOPE = "https://www.googleapis.com/auth/youtube.upload"
YOUTUBE_API_SERVICE_NAME = "youtube"
YOUTUBE_API_VERSION = "v3"
MAX_RETRIES = 10


def upload_youtube_video(file_path, client_secret_path, title=" ", description=" ", category="24", keywords="",
                         privacy_status="private"):
    # Authenticate and construct service.
    flow = InstalledAppFlow.from_client_secrets_file(client_secret_path, scopes=[YOUTUBE_UPLOAD_SCOPE])
    credentials = flow.run_local_server()
    youtube = build(YOUTUBE_API_SERVICE_NAME, YOUTUBE_API_VERSION, credentials=credentials)

    body = {
        'snippet': {
            'title': title,
            'description': description,
            'tags': keywords.split(","),
            'categoryId': category
        },
        'status': {
            'privacyStatus': privacy_status,
            'selfDeclaredMadeForKids': False
        }
    }

    insert_request = youtube.videos().insert(
        part=",".join(body.keys()),
        body=body,
        media_body=MediaFileUpload(file_path, chunksize=-1, resumable=True)
    )

    resumable_upload(insert_request)


def resumable_upload(request):
    response = None
    error = None
    retry = 0

    while response is None:
        try:
            print("Uploading file...")
            status, response = request.next_chunk()

            if 'id' in response:
                print(f"Video id '{response['id']}' was successfully uploaded.")
            else:
                print(f"The upload failed with an unexpected response: {response}")
        except HttpError as e:
            if e.resp.status in RETRIABLE_STATUS_CODES:
                error = f"A retriable HTTP error {e.resp.status} occurred:\n{e.content.decode('utf-8')}"
            else:
                raise
        except RETRIABLE_EXCEPTIONS as e:
            error = f"A retriable error occurred: {e}"

        if error is not None:
            print(error)
            retry += 1
            if retry > MAX_RETRIES:
                print("No longer attempting to retry.")
                return

            sleep_seconds = random.random() * (2 ** retry)
            print(f"Sleeping {sleep_seconds} seconds and then retrying...")
            time.sleep(sleep_seconds)


def upload_to_tiktok(file_path, description, schedule=True, schedule_day="13", schedule_time="16:30"):
    options = webdriver.ChromeOptions()
    options.add_argument("--allow-running-insecure-content")
    options.add_argument("--disable-web-security")
    options.add_argument(
        "--disable-features=CrossSiteDocumentBlockingIfIsolating,CrossSiteDocumentBlockingAlways,IsolateOrigins,site-per-process")
    config = Config()
    options.add_argument(f"--user-data-dir={config.user_data_dir}")

    # provide the profile name with which we want to open browser
    options.add_argument(rf'--profile-directory={config.user_profile_dir_tiktok}')
    options.add_argument("--disable-blink-features=AutomationControlled")

    # Adding argument to disable the AutomationControlled flag
    options.add_argument("--disable-blink-features=AutomationControlled")

    # Exclude the collection of enable-automation switches
    options.add_experimental_option("excludeSwitches", ["enable-automation"])

    # Turn-off userAutomationExtension
    options.add_experimental_option("useAutomationExtension", False)

    driver = webdriver.Chrome(options=options)
    # Open TikTok
    driver.get("https://www.tiktok.com/")
    time.sleep(5)  # Wait for the page to load*
    # Wait for the element to be clickable
    upload_button = WebDriverWait(driver, 10).until(
        EC.element_to_be_clickable((By.XPATH, "//a[contains(@aria-label, 'Upload a video') and contains(., 'Upload')]"))
    )

    # Click on the element
    upload_button.click()
    time.sleep(5)
    driver.switch_to.frame(0)
    file_input = WebDriverWait(driver, 10).until(
        EC.presence_of_element_located((By.XPATH, "//input[@type='file'][@accept='video/*']"))
    )

    # Send the path of the file to upload
    file_input.send_keys(os.path.abspath(file_path))
    time.sleep(5)
    # Locate the content-editable div
    content_editable_div = driver.find_element(By.XPATH, "//div[@data-contents='true']")
    # Clear the existing text
    ActionChains(driver).click(content_editable_div).key_down(Keys.CONTROL).send_keys('a').key_up(
        Keys.CONTROL).send_keys(Keys.DELETE).perform()
    # Write 'content' inside
    ActionChains(driver).click(content_editable_div).send_keys(description).perform()

    if schedule:
        # Locate the schedule switch input
        switch_input = driver.find_element(By.CSS_SELECTOR, "input[data-tux-switch-input='true']")
        # Click on the switch
        switch_input.click()

        # Find the date picker element
        date_picker_element = driver.find_element(By.XPATH, "//div[contains(@class, 'date-picker-input')]")
        # Click on the date picker to open it
        date_picker_element.click()

        # Function to find and click on a date in the calendar
        def click_valid_date(day):
            try:
                # Try to find a valid date element in the calendar
                date_element = driver.find_element(By.XPATH,
                                                   f"//span[contains(@class, 'day') and contains(@class, 'valid') and text()='{day}']")
                driver.execute_script("arguments[0].scrollIntoView();", date_element)

                date_element.click()
                return True
            except NoSuchElementException:
                return False

        # Check if the valid date "14" is available
        if not click_valid_date(schedule_day):
            # If date is not valid, click the arrow to go to the next month
            arrow_element = driver.find_element(By.XPATH, "//span[contains(@class, 'arrow')][2]")
            arrow_element.click()
            click_valid_date(schedule_day)

        hour, minutes = schedule_time.split(':')
        # Click on the time picker input to open the dropdown (you may need to adjust this selector)
        time_picker_element = driver.find_element(By.XPATH, "//div[contains(@class, 'time-picker-input')]")
        time_picker_element.click()
        # Find the element with the hour
        hour_element = driver.find_element(By.XPATH,
                                           f"//div[contains(@class, 'tiktok-timepicker-option-item')]//span[contains(text(), '{hour}')]")
        # Scroll the hour element into view
        driver.execute_script("arguments[0].scrollIntoView();", hour_element)
        # Wait for a moment (optional but recommended)
        time.sleep(1)
        # Click the hour element
        hour_element.click()
        # Find and click the element with the minute
        minute_element = driver.find_element(By.XPATH,
                                             f"//div[contains(@class, 'tiktok-timepicker-option-item')]//span[contains(text(), '{minutes}')]")
        # Scroll the minute element into view
        driver.execute_script("arguments[0].scrollIntoView();", minute_element)
        # Wait for a moment (optional but recommended)
        time.sleep(1)
        # Click the minute element
        minute_element.click()

    time.sleep(2)
    switch_element = driver.find_element(By.ID, "tux-4")
    switch_element.click()
    time.sleep(5)
    # Locate the button within its parent div by class name 'btn-post' and click
    button_element = driver.find_element(By.CSS_SELECTOR, "div.btn-post > button")
    button_element.click()
    time.sleep(10)
    driver.quit()
