from robocorp import workitems
from robocorp.workitems import BusinessException, ApplicationException
from robocorp.tasks import task
from datetime import datetime, timedelta
import json
import logging
from robocorp import browser
import time
import re
import random
from dateutil.relativedelta import relativedelta
import requests
from urllib.parse import urlparse
import os
import shutil
@task
def handle_all_items():
    
    directory_path = "output/images/"

    # Remove the directory if it exists, then recreate it
    if os.path.exists(directory_path):
        shutil.rmtree(directory_path)
    os.makedirs(directory_path)
    
    for item in workitems.inputs:
        try:
            payload = {
                "topic": "automation",
                "category": "Lifestyle",
                "months": "24"
            }
            worktitem = workitems.outputs.create(payload)
            validate_data(worktitem)
            extract_news_data(worktitem)
        except BusinessException as e:
            logging.error(f"Business error occurred: {e}")
            # Handle business logic failure, e.g., by setting the work item to fail
            item.fail(code=e.code, message=e.message)
        except ApplicationException as e:
            logging.error(f"Application error occurred: {e}")
            # Handle application failure, e.g., by setting the work item to fail
            item.fail(code="APPLICATION_ERROR", message=str(e))
        except Exception as e:
            logging.error(f"Unexpected error occurred: {e}")
            # Handle unexpected errors
            item.fail(code="UNEXPECTED_ERROR", message="An unexpected error occurred.")
        # with item:  # This context manager automatically handles reserving and releasing the item
        #     print("Received payload:", item.payload)
        #     # Process the item here
        #     # Example: Modify the payload or perform actions based on its content
        #     # extract_news_data(item)
        
def validate_data(workitem):
    """Validate the data in the work item payload."""
    required_keys = ["topic", "category", "months"]
    valid_categories = [
        "All", "World", "Business", "Legal", "Markets", "Breakingviews", 
        "Technology", "Sustainability", "Science", "Sports", "Lifestyle",
    ]
      
    # Identify missing keys
    missing_keys = [key for key in required_keys if key not in workitem.payload]
    if missing_keys:
        missing_keys_str = ", ".join(missing_keys)
        raise BusinessException(
            code="MISSING_KEYS",
            message=f"Invalid work item payload. Missing keys: {missing_keys_str}."
        )
    
    # Check if the category is valid
    category = workitem.payload.get("category")
    if category not in valid_categories:
        raise BusinessException(
            code="INVALID_CATEGORY",
            message=f"Invalid category: {category}. Must be one of {', '.join(valid_categories)}."
        )
    
    # Check if the topic has less than 100 characters
    topic = workitem.payload.get("topic", "")
    if len(topic) >= 100:
        raise BusinessException(
            code="INVALID_TOPIC_LENGTH",
            message="Invalid topic. The topic must have less than 100 characters."
        )
    
    # Check if the months is a numeric value
    months = workitem.payload.get("months", "")
    if not str(months).isdigit():
        raise BusinessException(
            code="INVALID_MONTHS_VALUE",
            message="Invalid months value. The months must be a numeric value."
        )
    
def extract_news_data(workitem):
    search_phrase = workitem.payload.get("topic")
    news_category = workitem.payload.get("category")
    number_of_months = workitem.payload.get("months", 0)
    
    # Example function to fetch news data (to be implemented)
    news_data = fetch_news(search_phrase, news_category, number_of_months)
    
    # # Writing the fetched news data to the /output directory as JSON
    # output_path = "/output/news_data.json"
    # with open(output_path, "w") as file:
    #     json.dump(news_data, file)
    
    # # Creating an output work item with the path to the saved news data
    # workitems.outputs.create(payload={"news_data_path": output_path})

def fetch_news(search_phrase, category, months):
    date_pattern = r"(\w+)\s(\d{1,2}),\s(\d{4})"
    # Calculate the date range for the news articles
    end_date = datetime.now()
    start_date = end_date - relativedelta(months=int(months))
    
    # Initialize the browser and open Reuters.com
    browser.configure(slowmo=100)
    page = browser.page()
    page.goto("https://www.reuters.com/")
    
    # Introduce a human-like delay
    
    
    # Accept cookies if necessary
    try:
        page.locator("#onetrust-accept-btn-handler").click()
    except Exception:
        pass  # If the popup doesn't show up, ignore
    
    # Navigate to the search page and enter the search phrase
    #Click on search icon
    page.click("//*[name()='path' and contains(@fill-rule,'evenodd')]")
    
    
    input_locator = page.locator("//*[@data-testid='FormField:input']")
    for char in search_phrase:
        input_locator.type(char)
        time.sleep(0.1)  # Adjust the delay as needed
    page.press("//*[@data-testid='FormField:input']", "Enter")

    #     #Get paggination text
    # pagination_locator = page.locator("//div[contains(@class, 'search-results__pagination__')]")
    # pagination_text = pagination_locator.text_content()
    # right_arrow_locator = page.locator("#SvgChevronRight")
    
    #Select category
    page.click(f"(//*[@data-testid='EnhancedSelect'])[1]")
    page.click(f"(//*[@data-testid='EnhancedSelect'])[1]//span[text()='{category}']")
    time.sleep(5)
    search_next_page = True
    list_items = []

    
    while search_next_page:
        # Use a CSS selector with a partial match for the class name to find the <ul>
        # and then select all <li> elements within it
        list_items_locator = page.locator("//ul[contains(@class, 'search-results__list__')]/li")
        
        # Extracting the text from each list item and storing in a list

        for item in list_items_locator.element_handles(): 
            text = item.inner_text()
            match = re.search(date_pattern, text)
            if match:
                title, extracted_date = extract_info(text)
                if extracted_date.date() < start_date.date():
                    search_next_page = False
                    break
            # print("Selector "+item.query_selector("img").inner_html())
            # page.wait_for_selector(item.query_selector("img"), timeout=timedelta(seconds=30))   
            img_src = item.query_selector("img").get_attribute("src")
            print(img_src)
            parsed_url = urlparse(img_src)
            filename = "output/images/"+os.path.basename(parsed_url.path)
            download_image(img_src, filename)
            list_items.append(text)
        
        if not search_next_page:
            break         
        # Check if the right arrow button is disabled      
        right_arrow_button_locator = page.locator("//*[@data-testid='SvgChevronRight']/ancestor::button[1]")

        if right_arrow_button_locator.is_disabled():
            search_next_page = False
        else:
            right_arrow_button_locator.click()
        time.sleep(random.randint(5, 10))
    print(list_items)    

# Function to extract title, date, and description
def extract_info(text):
    date_match = re.search(r"(\w+)\s(\d{1,2}),\s(\d{4})", text)
    if date_match:
        # Extract the date components
        month, day, year = date_match.groups()
        # Convert the extracted date to a datetime object
        extracted_date = datetime.strptime(f"{day} {month} {year}", "%d %B %Y")
        
        #Extracted title
        parts = text.split('\n')
        title = parts[1] if len(parts) > 1 else ''
        
        return title, extracted_date,
    return '', ''

def download_image(url: str, filename: str ): 
    """
    Downloads an image from the specified URL and saves it as a file.

    Args:
        url: The URL of the image to download.
        filename: The name of the file to save the image to.
    """

    response = requests.get(url)
    response.raise_for_status()  # Ensure the request was successful
    with open(filename, 'wb') as file:
        file.write(response.content)