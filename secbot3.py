import requests
import os
from bs4 import BeautifulSoup
from transformers import pipeline
from selenium import webdriver
from selenium.webdriver.common.keys import Keys
from selenium.common.exceptions import NoSuchElementException
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
import time

# Log into Twitter

def login_to_twitter(browser, twitter_username, twitter_password):
    browser.get('https://twitter.com/login')
    time.sleep(2)

   # Locate the username input field and enter the username
    username_field =  browser.find_element(By.NAME, "text")
    username_field.send_keys(twitter_username)

    # Locate the "Next" button and click it
    username_field.send_keys(Keys.RETURN)

    # Wait for the password input field to load
    WebDriverWait(browser, 10).until(
        EC.presence_of_element_located((By.NAME, "password"))
    )

    # Locate the password input field and enter the password
    password_field = browser.find_element(By.NAME, "password")
    password_field.send_keys(twitter_password)

    # Click the "Log in" button
    password_field.send_keys(Keys.RETURN)

    time.sleep(2)

# Tweet with Selenium

def tweet_with_selenium(browser, tweet):
    try:
        browser.get('https://twitter.com/compose/tweet')

        # Locate the Tweet Box 
        wait = WebDriverWait(browser, 5)
        tweet_box = wait.until(EC.visibility_of_element_located((By.XPATH, '//div[@aria-label="Tweet text"][@contenteditable="true"]')))
        tweet_box.click()

        # Enter the Tweet Text

        tweet_box.send_keys(tweet)
        time.sleep(2)

        # Locate the Tweet button
        tweet_button = wait.until((EC.element_to_be_clickable((By.XPATH, '//div[@data-testid="tweetButton"]'))))
        tweet_button.click()
        time.sleep(2)
        print("Tweet successfully posted.")
    except NoSuchElementException as e:
        print(f"Failed to tweet: {e}")

# Find the press releases from the SEC website

def get_press_release_links(url, limit=3):
    print("Fetching press release links...")
    response = requests.get(url)
    print("Response status code:", response.status_code)
    soup = BeautifulSoup(response.text, 'html.parser')
    headlines = soup.select('td.views-field.views-field-field-display-title a')
    print("Number of headlines found:", len(headlines))
    links = ['https://www.sec.gov' + headline.get('href') for headline in headlines[:limit]]
    return links

# Bitly URL Shortener

def shorten_url(url, api_key):
    headers = {
        'Authorization': f'Bearer {api_key}',
        'Content-Type': 'application/json',
    }
    data = {
        'long_url': url,
    }
    response = requests.post('https://api-ssl.bitly.com/v4/shorten', headers=headers, json=data)
    if response.status_code == 200 or response.status_code == 201:
        return response.json()['link']
    else:
        print(f"Error shortening URL: {response.text}")
        return url

# Grab the content from the press releases

def get_press_release_content(url):
    print("Fetching press release content...")
    response = requests.get(url)

    # For purposes of debuggin get_press_release:

    if response.status_code != 200:
            print("Failed to fetch the page.")
            return []

    soup = BeautifulSoup(response.text, 'html.parser')
    content = soup.find('div', class_='article-content')
    if content:
        return content.get_text()
    return ''

# Load processed links from a file
def load_processed_links(file_path):
    if os.path.exists(file_path):
        with open(file_path, 'r') as file:
            return set(line.strip() for line in file)
    return set()

# Save processed links to a file
def save_processed_link(file_path, link):
    with open(file_path, 'a') as file:
        file.write(f"{link}\n")

# Summarize the press release content

def summarize(text, url, tweet_length=140):
    print("Summarizing content...")
    model_name = 'sshleifer/distilbart-cnn-12-6'
    model_revision = 'a4f8f3e'
    summarizer = pipeline('summarization', model=model_name, revision=model_revision)
    summary = summarizer(text, max_length=140, min_length=80, do_sample=False)
    full_summary = summary[0]['summary_text']

    remaining_length = len(full_summary)
    num_tweets = (remaining_length + tweet_length - len(url) - 1) // (tweet_length - len(url) - 1)
    tweets = []
    start = 0

    for i in range(num_tweets):
        end = start + tweet_length - len(url) - 2
        end = min(end, remaining_length)
        tweet = full_summary[start:end].rsplit(' ', 1)[0]

        if len(tweet) == 0:
            break

        start += len(tweet)
        remaining_length -= len(tweet)

        if i == num_tweets - 1:  # Check if it's the last tweet
            tweet = tweet.strip()
            if tweet[-1] != '.':  # Check if there's already a period at the end of the last tweet
                tweet += '.'
            tweet += " " + url  # Add the URL only to the last tweet
        tweets.append(tweet)

    return tweets

if __name__ == '__main__':
    twitter_username = "USERNAME"
    twitter_password = "PASSWORD"

    chrome_driver_path = "D:\Coding\secbot3\chromedriver_win32\chromedriver.exe"  # Update this with the path to your ChromeDriver
    browser = webdriver.Chrome(executable_path=chrome_driver_path)

    login_to_twitter(browser, twitter_username, twitter_password)

    sleep_duration = 3600

    base_url = 'https://www.sec.gov/news/pressreleases'
    limit = 3  # Change this value to limit the number of headlines processed

    processed_links_file = "processed_links.txt"
    processed_links = load_processed_links(processed_links_file)
    print(f"Loaded {len(processed_links)} processed links from {processed_links_file}")

    try:
        while True:
            links = get_press_release_links(base_url, limit)
            print("Press release links:", links)  # Debug print

            for i, link in enumerate(links, start=1):
                if link in processed_links:
                    print(f"Skipping link {i}: {link} (already processed)")
                    continue
                
                print(f"Processing link {i}: {link}")  # Debug print
                content = get_press_release_content(link)
                if content:
                    print("Content fetched. Starting summarization...")  # Debug print
                    shortened_url = shorten_url(link, api_key)
                    tweets = summarize(content, shortened_url)
                    for j, tweet in enumerate(tweets, start=1):
                        if j == 1:
                            print("SEC NEWS:")
                        print(tweet)
                        print('\n')

                        # Tweet the summarized content
                        tweet_with_selenium(browser, tweet)
                        print(f"Tweet {j} successfully posted.")

                else:
                    print(f'No content found for {link}\n')

                print(f"Finished processing link {i}\n")  # Debug print
                save_processed_link(processed_links_file, link)
                processed_links.add(link)
                print(f"Saved processed link {i} to {processed_links_file}\n")  # Debug print

            print(f"Sleeping for {sleep_duration} seconds before the next iteration.")
            time.sleep(sleep_duration)
    except KeyboardInterrupt:
        print("Exiting...")
        browser.quit()







