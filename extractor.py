import time
from bs4 import BeautifulSoup

# Selenium imports are used to control a real web browser
from selenium import webdriver
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager

def extract_question_from_link(url):
    """
    Uses Selenium to open a real browser, load a single page, wait for anti-bot
    scripts to finish, and then extracts the question and answer choices.
    """
    print("Initializing browser...")
    
    # --- Browser Setup ---
    chrome_options = Options()
    # Run in "headless" mode so no browser window pops up. Remove this line if you want to see the browser.
    chrome_options.add_argument("--headless") 
    chrome_options.add_argument("--window-size=1920,1080")
    # Set a common user-agent to appear like a normal user
    chrome_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36")
    
    # Automatically downloads and manages the driver for your version of Chrome
    service = ChromeService(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=chrome_options)
    
    print(f"Navigating to the link: {url}")
    
    try:
        # 1. Go to the URL
        driver.get(url)

        # 2. CRITICAL STEP: Wait for the page to load completely.
        # This gives time for JavaScript, redirects, and anti-bot checks to finish.
        # 5 seconds is a safe number. You can increase it if it still fails.
        print("Waiting for page to load and anti-bot checks to complete...")
        time.sleep(5)

        # 3. Get the final HTML source code after everything has loaded
        page_source = driver.page_source
        
        # 4. Use BeautifulSoup to parse the final HTML
        soup = BeautifulSoup(page_source, "html.parser")

        # --- Data Extraction ---
        
        # Find the main question body div
        question_body_div = soup.find("div", class_="question-body")
        
        # If this div doesn't exist, the page likely didn't load correctly or we were blocked.
        if not question_body_div:
            print("\n--- EXTRACTION FAILED ---")
            print("Could not find the 'question-body' element on the page.")
            print("This usually means the script was blocked by a CAPTCHA.")
            # Save a screenshot and the HTML for debugging
            driver.save_screenshot("debug_screenshot.png")
            with open("debug_page_source.html", "w", encoding="utf-8") as f:
                f.write(page_source)
            print("Saved 'debug_screenshot.png' and 'debug_page_source.html' for you to inspect.")
            return None, None

        # Extract the question text from the <p> tag
        question_p = question_body_div.find("p", class_="card-text")
        question_text = question_p.get_text(separator='\n', strip=True) if question_p else "Question text not found."

        # Extract the answer choices from the list items
        choices = []
        choices_container = soup.find("div", class_="question-choices-container")
        if choices_container:
            choice_items = choices_container.find_all("li", class_="multi-choice-item")
            for item in choice_items:
                # Clean up the text for each choice
                clean_text = ' '.join(item.get_text(strip=True).split())
                choices.append(clean_text)
        
        return question_text, choices

    except Exception as e:
        print(f"\nAn unexpected error occurred: {e}")
        return None, None
    finally:
        # 5. IMPORTANT: Always close the browser to free up resources
        print("Closing browser.")
        driver.quit()


if __name__ == "__main__":
    # Get the link from the user
    link_to_scrape = input("Please enter the full link to the Examtopics question page: ")

    if not link_to_scrape.startswith("http"):
        print("Invalid URL. Please make sure it starts with 'http' or 'https'.")
    else:
        # Call the main extraction function
        question, answers = extract_question_from_link(link_to_scrape)

        # Print the results in a clean format
        if question and answers:
            print("\n" + "="*25)
            print("   EXTRACTION SUCCESSFUL")
            print("="*25 + "\n")
            print("QUESTION:\n")
            print(question)
            print("\nCHOICES:\n")
            for answer in answers:
                print(f"• {answer}")
            print("\n" + "="*25)
        else:
            print("\nCould not extract the question and answers from the provided link.")