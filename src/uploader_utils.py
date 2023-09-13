import os

import httplib2
import pyperclip
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
import autoit

from src.utils import Config

RETRIABLE_EXCEPTIONS = (httplib2.HttpLib2Error, IOError)
RETRIABLE_STATUS_CODES = [500, 502, 503, 504]
YOUTUBE_UPLOAD_SCOPE = "https://www.googleapis.com/auth/youtube.upload"
YOUTUBE_API_SERVICE_NAME = "youtube"
YOUTUBE_API_VERSION = "v3"
MAX_RETRIES = 10

def upload_youtube_video(file_path, client_secret_path, title=" ", description=" ", category="24", keywords="",
                         privacy_status="private", schedule=True, schedule_day="14", schedule_time="16:30"):
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

    time.sleep(10)

    #then schedule it
    options = webdriver.ChromeOptions()
    options.add_argument("--allow-running-insecure-content")
    options.add_argument("--disable-web-security")
    options.add_argument(
        "--disable-features=CrossSiteDocumentBlockingIfIsolating,CrossSiteDocumentBlockingAlways,IsolateOrigins,site-per-process")
    config = Config()
    options.add_argument(f"--user-data-dir={config.user_data_dir}")
    # provide the profile name with which we want to open browser
    options.add_argument(rf'--profile-directory={config.user_profile_dir_youtube}')
    options.add_argument("--disable-blink-features=AutomationControlled")
    # Adding argument to disable the AutomationControlled flag
    options.add_argument("--disable-blink-features=AutomationControlled")
    # Exclude the collection of enable-automation switches
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    # Turn-off userAutomationExtension
    options.add_experimental_option("useAutomationExtension", False)
    driver = webdriver.Chrome(options=options)
    # Open yt
    driver.get(
        f"https://studio.youtube.com/channel/{config.youtube_channel_id}/videos/upload?filter=%5B%5D&sort=%7B%22columnType%22%3A%22date%22%2C%22sortOrder%22%3A%22DESCENDING%22%7D")
    time.sleep(5)  # Wait for the page to load*

    wait = WebDriverWait(driver, 10)
    target_div = wait.until(
        EC.presence_of_element_located((By.XPATH, f'//div[@id="row-container"][.//*[contains(., "{title}")]]')))
    driver.execute_script("arguments[0].scrollIntoView({block: 'center', inline: 'center'});", target_div)
    time.sleep(1)

    # Find the clickable button within target_div
    button_to_click = target_div.find_element(By.CLASS_NAME, 'editable')
    # Click the button
    driver.execute_script("arguments[0].click();", button_to_click)
    time.sleep(2)
    if schedule:
        # Wait until the container is present
        container = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.ID, "second-container"))
        )
        # Now find the radio button within the container
        radio_button = container.find_element(By.XPATH, './/tp-yt-paper-radio-button[@id="schedule-radio-button"]')
        # Click the radio button
        radio_button.click()
        time.sleep(0.3)
        # Now locate the dropdown within that container
        dropdown = container.find_element(By.CSS_SELECTOR, ".container.style-scope.ytcp-dropdown-trigger")
        dropdown.click()
        time.sleep(0.3)
        # Find the first selectable calendar day that contains the text "14"

        selectable_day = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.XPATH,
                                            "//span[contains(@class, 'calendar-day') and not(contains(@class, 'disabled')) and not(contains(@class, 'invisible')) and contains(., '{}')]".format(
                                                schedule_day)))
        )

        # Scroll the day into view
        actions = ActionChains(driver)
        actions.move_to_element(selectable_day).perform()
        # Click the day
        time.sleep(0.5)
        selectable_day.click()
        time.sleep(1)

        # Find the input element within the container and click it
        input_element = container.find_element(By.CSS_SELECTOR, "input.style-scope.tp-yt-paper-input")
        input_element.click()
        # Round minutes to the nearest 15
        hour = int(schedule_time.split(':')[0])
        minutes = int(schedule_time.split(':')[1])
        rounded_minutes = round(minutes / 15) * 15
        # If rounding minutes exceeds 59, increment the hour and set minutes to 0
        if rounded_minutes == 60:
            rounded_minutes = 0
            hour += 1
        # If hour exceeds 23, reset it to 0 (start of the day)
        if hour > 23:
            hour = 0
        # Convert to 24-hour format time string
        closest_time = f"{hour:02d}:{rounded_minutes:02d}"
        # Wait and then click on the closest time
        time_to_click = WebDriverWait(container, 10).until(
            EC.presence_of_element_located((By.XPATH, f"//tp-yt-paper-item[text()='{closest_time}']"))
        )
        # Scroll the day into view
        actions = ActionChains(driver)
        actions.move_to_element(time_to_click).perform()
        time.sleep(1)  # Sleep to mimic human interaction
        time_to_click.click()
        time.sleep(2)
        # Find the button with id 'save-button' and text 'Programmer' and click it
        button = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.XPATH, "//ytcp-button[@id='save-button']/div[text()='Programmer' or "
                                                      "text()='Schedule']"))
        )
        time.sleep(1)  # Sleep to mimic human interaction
        button.click()
    else:
        # Locate the 'first-container'
        first_container = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.ID, "first-container"))
        )

        # Find the radio button with the label 'Publique' or 'Public' within the 'first-container' and click it
        radio_button = first_container.find_element(By.XPATH,
                                                    ".//tp-yt-paper-radio-button[div[@id='radioLabel'][contains(text("
                                                    "), 'Publique') or contains(text(), 'Public')]]")
        radio_button.click()
        time.sleep(1.2)
        # Find the button with id 'save-button' and text 'Programmer' and click it
        button = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.XPATH, "//ytcp-button[@id='save-button']/div[text()='Enregistrer' or "
                                                      "text()='Save']"))
        )
        time.sleep(1)  # Sleep to mimic human interaction
        button.click()
    time.sleep(4)
    driver.quit()


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
    # Type description
    pyperclip.copy(description)  # Copy to clipboard (to be more human-like)
    # Paste the copied text
    ActionChains(driver).click(content_editable_div).key_down(Keys.CONTROL).send_keys('v').key_up(Keys.CONTROL).perform()


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
    time.sleep(8)
    # Locate the button within its parent div by class name 'btn-post' and click
    button_element = driver.find_element(By.CSS_SELECTOR, "div.btn-post > button")
    button_element.click()
    time.sleep(10)
    driver.quit()


def upload_to_meta(file_path, description, schedule=True, schedule_day="13", schedule_time="16:30"):
    options = webdriver.ChromeOptions()
    options.add_argument("--allow-running-insecure-content")
    options.add_argument("--disable-web-security")
    options.add_argument(
        "--disable-features=CrossSiteDocumentBlockingIfIsolating,CrossSiteDocumentBlockingAlways,IsolateOrigins,site-per-process")
    config = Config()
    options.add_argument(f"--user-data-dir={config.user_data_dir}")

    # provide the profile name with which we want to open browser
    options.add_argument(rf'--profile-directory={config.user_profile_dir_fb}')
    options.add_argument("--disable-blink-features=AutomationControlled")

    # Adding argument to disable the AutomationControlled flag
    options.add_argument("--disable-blink-features=AutomationControlled")

    # Exclude the collection of enable-automation switches
    options.add_experimental_option("excludeSwitches", ["enable-automation"])

    # Turn-off userAutomationExtension
    options.add_experimental_option("useAutomationExtension", False)

    driver = webdriver.Chrome(options=options)
    # Open TikTok
    driver.get(f"https://business.facebook.com/latest/home?asset_id={config.fb_asset_id}&"
               f"business_id={config.fb_business_id}")
    time.sleep(5)

    # Wait for the page to load
    wait = WebDriverWait(driver, 10)
    # Locate the button based on its role and the text it contains
    create_reel_button = wait.until(EC.presence_of_element_located(
        (By.XPATH, "//div[@role='button'][.//*[contains(text(), 'reel') or contains(text(), 'Reel')]]")))
    # Scroll the button into view (optional but recommended)
    driver.execute_script("arguments[0].scrollIntoView();", create_reel_button)
    # Wait for a moment to let the UI catch up (optional but recommended)
    time.sleep(1)
    # Click the button
    create_reel_button.click()
    # Use AutoIt to interact with the file dialog
    # Check which window is active and act accordingly
    # Wait for the page to load
    time.sleep(3)
    wait = WebDriverWait(driver, 10)
    # Locate the button for adding a video based on its role and the text in its descendants
    add_video_button = wait.until(EC.presence_of_element_located((By.XPATH,
                                                                  "//div[@role='button'][.//*[contains(text(), 'Ajouter une vidéo') or contains(text(), 'Add a video') or contains(text(), 'Upload a video')]]")))
    # Scroll the button into view (optional but recommended)
    driver.execute_script("arguments[0].scrollIntoView();", add_video_button)
    # Wait for a moment to let the UI catch up (optional but recommended)
    time.sleep(1)
    # Click the button to add a video
    add_video_button.click()
    time.sleep(4)
    if autoit.win_exists("[REGEXPTITLE:(Open|Ouvrir)]"):
        autoit.win_wait_active("[REGEXPTITLE:(Open|Ouvrir)]")
        autoit.control_send("[REGEXPTITLE:(Open|Ouvrir)]", "Edit1", os.path.abspath(file_path))
        autoit.control_click("[REGEXPTITLE:(Open|Ouvrir)]", "Button1")
    else:
        print("Unexpected file dialog.")
    time.sleep(6)
    # Locate the content-editable element
    content_editable = driver.find_element(By.CSS_SELECTOR, '.notranslate._5rpu[contenteditable="true"]')
    # Click to focus
    ActionChains(driver).click(content_editable).key_down(Keys.CONTROL).send_keys('a').key_up(
        Keys.CONTROL).send_keys(Keys.DELETE).perform()
    content_editable.click()
    time.sleep(1)  # Let the click action take effect
    # Type description
    pyperclip.copy(description)  # Copy to clipboard
    # Paste the copied text
    ActionChains(driver).click(content_editable).key_down(Keys.CONTROL).send_keys('v').key_up(Keys.CONTROL).perform()

    # Next *2
    next_buttons = driver.find_elements(By.XPATH, "//div[@role='button'][.//*[text()='Suivant' or text()='Next']]")
    driver.execute_script("arguments[0].scrollIntoView();", next_buttons[-1])
    actions = ActionChains(driver)
    actions.move_to_element(next_buttons[-1]).click().perform()

    time.sleep(2)

    next_buttons = driver.find_elements(By.XPATH, "//div[@role='button'][.//*[text()='Suivant' or text()='Next']]")
    driver.execute_script("arguments[0].scrollIntoView();", next_buttons[-1])
    actions = ActionChains(driver)
    actions.move_to_element(next_buttons[-1]).click().perform()

    time.sleep(1.5)
    if schedule:
        button = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located(
                (By.XPATH, "//div[@role='button'][.//*[text()='Programmer' or text()='Schedule']]"))
        )
        # Click the button
        button.click()
        # Numeric Format
        date_input = driver.find_element(By.XPATH, "//input[@placeholder='jj/mm/aaaa']")
        date_input.click()

        # Function to select a date
        def select_date(day):
            try:
                # Find the date button that is not disabled
                date_button = driver.find_element(By.XPATH,
                                                  f'//div[@role="button"][text()="{day}"][@aria-disabled="false"]')
                time.sleep(1)
                date_button.click()
                return True
            except:
                return False

        # Try to select the 2nd day of the month
        if not select_date(schedule_day):
            # Click the 'Next Month' button and try again (replace with the actual selector)
            next_button = driver.find_element(By.XPATH,
                                              "//div[@role='button'][.//*[text()='Mois suivant' or text()='Next month']]")
            next_button.click()
            select_date(schedule_day)

        time.sleep(0.5)

        def select_time(hour, minute, meridian):
            # Find the hour input element and set the hour
            hour_input = driver.find_element(By.XPATH, '//input[@aria-label="heures"]')
            hour_input.clear()
            hour_input.send_keys(hour)
            time.sleep(0.7)
            # Find the minute input element and set the minute
            # Modify this part if your specific website handles minute input differently
            minute_input = driver.find_element(By.XPATH,
                                               '//input[@aria-label="minutes"]')  # Replace with the actual selector
            minute_input.clear()
            minute_input.send_keys(minute)
            time.sleep(0.5)
            # Find the AM/PM input element and set it
            meridian_input = driver.find_element(By.XPATH, '//input[@aria-label="méridien"]')
            meridian_input.clear()
            meridian_input.send_keys(meridian)

        # Function to convert 24-hour time to 12-hour time with AM/PM
        def convert_to_12_hour_format(hour, minute):
            # Initialize the AM/PM variable
            am_pm = "AM"
            # Convert the hour and minute to integers
            hour = int(hour)
            minute = int(minute)
            # Convert to 12-hour format
            if hour >= 12:
                if hour > 12:
                    hour -= 12
                am_pm = "PM"
            elif hour == 0:
                hour = 12
            # Add leading zero to hour and minute if needed
            hour_str = str(hour).zfill(2)
            minute_str = str(minute).zfill(2)
            return hour_str, minute_str, am_pm

        hour, minutes, am_pm = convert_to_12_hour_format(schedule_time.split(':')[0], schedule_time.split(':')[1])
        select_time(hour, minutes, am_pm)
        time.sleep(1.1)
        schedule_buttons = driver.find_elements(By.XPATH, "//div[@role='button'][.//*[text()='Programmer' or text()='Schedule']]")
        driver.execute_script("arguments[0].scrollIntoView();", schedule_buttons[-1])
        actions = ActionChains(driver)
        actions.move_to_element(schedule_buttons[-1]).click().perform()
    else:
        schedule_buttons = driver.find_elements(By.XPATH,
                                                "//div[@role='button'][.//*[text()='Partager' or text()='Share']]")
        driver.execute_script("arguments[0].scrollIntoView();", schedule_buttons[-1])
        actions = ActionChains(driver)
        actions.move_to_element(schedule_buttons[-1]).click().perform()
    time.sleep(3.7)
    driver.quit()
