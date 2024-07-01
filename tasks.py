import logging
import os
import random
import re
import shutil
import time
from datetime import datetime
from urllib.parse import urlparse

import requests
from dateutil.relativedelta import relativedelta
from robocorp import browser, workitems
from robocorp.tasks import task
from robocorp.workitems import ApplicationException, BusinessException
from RPA.Excel.Files import Files
from RPA.Tables import Tables


@task
def main():
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
    )
    directory_path = "output/images/"

    # Remove the directory if it exists, then recreate it
    logging.info("Removing existing output files.")
    if os.path.exists(directory_path):

        shutil.rmtree(directory_path)
    os.makedirs(directory_path)

    file_path = "output/output.xlsx"

    # Remove the file if it exists
    if os.path.exists(file_path):
        os.remove(file_path)
    browser.configure(slowmo=100)
    page = browser.page()

    news_scrapper = NewsScrapper()

    for item in workitems.inputs:
        try:
            item = workitems.inputs.current
            logging.info(f"Processing item: {item}")
            item = workitems.inputs.current

            process(news_scrapper, item, page)
            item.done()
            logging.info(f"Item processed successfully: {item}")
        except BusinessException as e:
            logging.error(f"Business error occurred: {e}")
            # Handle business logic failure, e.g., by setting the work item to fail
            item.fail(code=e.code, message=e.message)
        except ApplicationException as e:
            logging.error(f"Application error occurred: {e}")
            page.screenshot(path="output/error_screenshot.png")
            # Handle application failure, e.g., by setting the work item to fail
            item.fail(code="APPLICATION_ERROR", message=str(e))
        except Exception as e:
            logging.error(f"Unexpected error occurred: {e}")
            page.screenshot(path="output/error_screenshot.png")
            # Handle unexpected errors
            item.fail(
                code="UNEXPECTED_ERROR",
                message="An unexpected error occurred.",
            )


def validate_data(workitem):
    """Validate the data in the work item payload."""
    required_keys = ["topic", "category", "months"]
    valid_categories = [
        "All",
        "World",
        "Business",
        "Legal",
        "Markets",
        "Breakingviews",
        "Technology",
        "Sustainability",
        "Science",
        "Sports",
        "Lifestyle",
    ]

    # Identify missing keys
    missing_keys = [
        key for key in required_keys if key not in workitem.payload
    ]
    if missing_keys:
        missing_keys_str = ", ".join(missing_keys)
        raise BusinessException(
            code="MISSING_KEYS",
            message=f"Invalid work item payload. Missing keys: {missing_keys_str}.",
        )

    # Check if the category is valid
    category = workitem.payload.get("category")
    if category not in valid_categories:
        raise BusinessException(
            code="INVALID_CATEGORY",
            message=f"Invalid category: {category}. Must be one of {', '.join(valid_categories)}.",
        )

    # Check if the topic has less than 100 characters
    topic = workitem.payload.get("topic", "")
    if len(topic) >= 100:
        raise BusinessException(
            code="INVALID_TOPIC_LENGTH",
            message="Invalid topic. The topic must have less than 100 characters.",
        )

    # Check if the months is a numeric value
    months = workitem.payload.get("months", "")
    if not str(months).isdigit():
        raise BusinessException(
            code="INVALID_MONTHS_VALUE",
            message="Invalid months value. The months must be a numeric value.",
        )


def process(news_scrapper, workitem, page):

    validate_data(workitem)
    # Extract the search phrase, category, and months from the work item payload
    search_phrase = workitem.payload.get("topic")
    category = workitem.payload.get("category")
    months = workitem.payload.get("months", 0)

    news_scrapper.open_browser(page)

    start_date = Utils.calculate_date_range(months)

    news_scrapper.accept_cookies(page)

    news_scrapper.navigate_and_search(page, search_phrase)

    news_scrapper.select_category(page, category)

    extracted_news_table = news_scrapper.process_search_results(
        page, start_date, search_phrase
    )

    Utils.save_to_excel(extracted_news_table, filename="output.xlsx")


class NewsScrapper:
    def __init__(self):
        pass

    def open_browser(self, page):
        page.goto("https://www.reuters.com/")
        logging.info("Opened Reuters.com")

    def accept_cookies(self, page):
        try:
            page.locator("#onetrust-accept-btn-handler").click()
            logging.info("Accepted cookies")
        except Exception:
            page.screenshot(path="output/error_screenshot.png")
            pass  # If the popup doesn't show up, ignore

    def navigate_and_search(self, page, search_phrase):
        # Navigate to the search page and enter the search phrase
        # Click on search icon
        logging.info("Clicked search icon")
        page.click("//*[name()='path' and contains(@fill-rule,'evenodd')]")

        logging.info(f"Searching for {search_phrase}")
        input_locator = page.locator("//*[@data-testid='FormField:input']")
        for char in search_phrase:
            input_locator.type(char)
            time.sleep(0.1)  # Adjust the delay as needed
        page.press("//*[@data-testid='FormField:input']", "Enter")

    def select_category(self, page, category):
        # Select category
        logging.info(f"Selecting category {category}")
        page.click("(//*[@data-testid='EnhancedSelect'])[1]")
        page.click(
            f"(//*[@data-testid='EnhancedSelect'])[1]//span[text()='{category}']"
        )
        time.sleep(5)

    def fetch_image_src_with_retry(self, item, retries=3):
        attempt = 0
        while attempt < retries:
            try:
                logging.info(
                    f"Attempt {attempt+1}: Trying to fetch image source"
                )
                # Use the Playwright API to interact with the web elements
                img_selector = item.wait_for_selector(
                    "//div[@data-testid='Image']//img"
                )

                img_src = img_selector.get_attribute("src")
                if img_src:
                    logging.info("Successfully fetched image source")
                    return img_src
            except Exception as e:
                logging.error(f"Attempt {attempt+1} failed with error: {e}")
                time.sleep(1)  # Wait a bit before retrying
                attempt += 1

        raise Exception(f"Failed to fetch image src after {retries} attempts")

    def extract_info(self, text, search_phrase):
        logging.info("Extracting information from text")
        date_match = re.search(r"(\w+)\s(\d{1,2}),\s(\d{4})", text)
        if date_match:
            # Extract the date components
            month, day, year = date_match.groups()
            # Convert the extracted date to a datetime object
            extracted_date = datetime.strptime(
                f"{day} {month} {year}", "%d %B %Y"
            )

            # Extracted title
            parts = text.split("\n")
            title = parts[1] if len(parts) > 1 else ""
            logging.info(f"Extracted title: {title}")

            count_search_phrase = title.lower().count(search_phrase.lower())
            logging.info(
                f"Count of search phrase '{search_phrase}' in title: {count_search_phrase}"
            )

            # Regular expression to match various money formats
            money_pattern = (
                r"(\$[0-9,]+(\.[0-9]{1,2})?)|([0-9]+ (dollars|USD))"
            )
            contains_money_pattern = bool(re.search(money_pattern, title))
            logging.info(f"Contains money pattern: {contains_money_pattern}")
            return (
                title,
                extracted_date,
                count_search_phrase,
                contains_money_pattern,
            )
        else:
            logging.error("Failed to extract date from text")
        return "", "", 0, False

    def process_search_results(self, page, start_date, search_phrase):
        logging.info("Starting to extract and download news")
        date_pattern = r"(\w+)\s(\d{1,2}),\s(\d{4})"
        search_next_page = True

        # Initialize the table to store the extracted news data
        headers = [
            "title",
            "date",
            "description",
            "picture filename",
            "count of search phrases",
            "contains money",
        ]
        extracted_news_table = Tables().create_table(columns=headers)

        while search_next_page:
            logging.info("Processing next page of search results")

            list_items_locator = page.query_selector_all(
                "//ul[contains(@class, 'search-results__list__')]/li"
            )

            for item in list_items_locator:
                item.scroll_into_view_if_needed()
                text = item.inner_text()
                match = re.search(date_pattern, text)
                if match:
                    (
                        title,
                        extracted_date,
                        count_search_phrase,
                        contains_money_pattern,
                    ) = self.extract_info(text, search_phrase)
                    if extracted_date.date() < start_date.date():
                        search_next_page = False
                        logging.info(
                            "Reached news older than start date, stopping search"
                        )
                        break

                img_selector = item.wait_for_selector(
                    "//div[@data-testid='Image']//img"
                )

                img_src = img_selector.get_attribute("src")

                parsed_url = urlparse(img_src)
                filename = "output/images/" + os.path.basename(parsed_url.path)
                logging.info(f"Downloading image from {img_src} to {filename}")
                Utils.download_image(img_src, filename)
                extracted_news_table.append_row(
                    [
                        title,
                        (
                            extracted_date.date().strftime("%d-%m-%Y")
                            if extracted_date
                            else ""
                        ),
                        "",
                        filename,
                        count_search_phrase,
                        contains_money_pattern,
                    ]
                )

            if not search_next_page:
                break
            # Check if the right arrow button is disabled
            right_arrow_button_locator = page.locator(
                "//*[@data-testid='SvgChevronRight']/ancestor::button[1]"
            )

            if right_arrow_button_locator.is_disabled():
                logging.info("No more pages to process")
                search_next_page = False
            else:
                right_arrow_button_locator.click()
                logging.info("Moving to the next page")
            time.sleep(random.randint(5, 10))
        return extracted_news_table


class Utils:
    def __init__(self):
        # Initialization code here, if needed
        pass

    @staticmethod
    def download_image(url, filename):
        """
        Downloads an image from the specified URL and saves it as a file.

        Args:
            url: The URL of the image to download.
            filename: The name of the file to save the image to.
        """

        response = requests.get(url)
        logging.info(f"Attempting to download content from {url}")
        response.raise_for_status()  # Ensure the request was successful

        with open(filename, "wb") as file:
            file.write(response.content)
            logging.info("Image download successful.")

    @staticmethod
    def save_to_excel(table, filename):

        logging.info(
            "Saving extracted news data to Excel workbook 'output/output.xlsx"
        )
        # Initialize the Excel file handler
        excel = Files()

        # Create a new Excel workbook and add a worksheet
        excel.create_workbook("output/output.xlsx")

        # Write the table to the first worksheet
        excel.append_rows_to_worksheet(table, header=True)

        # Save and close the workbook
        excel.save_workbook()
        logging.info("Closing the workbook")
        excel.close_workbook()

    @staticmethod
    def calculate_date_range(months):
        end_date = datetime.now()
        start_date = end_date - relativedelta(months=int(months))
        logging.info(f"Searching for news from {start_date} to {end_date}")
        return start_date
