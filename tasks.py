from robocorp import workitems
from robocorp.tasks import task
from datetime import datetime, timedelta
import json
@task
def handle_all_items():
    for item in workitems.inputs:
        with item:  # This context manager automatically handles reserving and releasing the item
            print("Received payload:", item.payload)
            # Process the item here
            # Example: Modify the payload or perform actions based on its content
            # extract_news_data(item)


def extract_news_data(workitem):
    # Assuming the current work item has the required parameters
    item = workitems.inputs.current
    search_phrase = item.payload.get("topic")
    news_category = item.payload.get("category")
    number_of_months = item.payload.get("months", 0)
    
    # Example function to fetch news data (to be implemented)
    news_data = fetch_news(search_phrase, news_category, number_of_months)
    
    # Writing the fetched news data to the /output directory as JSON
    output_path = "/output/news_data.json"
    with open(output_path, "w") as file:
        json.dump(news_data, file)
    
    # Creating an output work item with the path to the saved news data
    workitems.outputs.create(payload={"news_data_path": output_path})

def fetch_news(search_phrase, category, months):
    # Placeholder for the logic to fetch news data based on the parameters
    # This could involve web scraping, using an API, etc.
    # For the sake of this example, we'll return an empty dictionary
    return {}
