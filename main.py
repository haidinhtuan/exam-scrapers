import time
import re
import csv
import os
import sys
from tqdm import tqdm
from concurrent.futures import ThreadPoolExecutor, as_completed
from contextlib import contextmanager

# Selenium imports
from selenium import webdriver
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup

# --- CONFIGURATION ---
# Set the number of parallel browsers. 12 is aggressive but fine if your PC can handle it.
MAX_CONCURRENT_BROWSERS = 12

@contextmanager
def suppress_console_logs():
    """
    A context manager to temporarily redirect stderr to a null device,
    silencing all warnings and informational logs from ChromeDriver.
    """
    # Open the null device
    devnull = open(os.devnull, 'w')
    original_stderr = sys.stderr
    # Redirect stderr
    sys.stderr = devnull
    try:
        # Allow the code within the 'with' block to run
        yield
    finally:
        # Restore the original stderr, even if errors occur
        sys.stderr.close()
        sys.stderr = original_stderr


def get_all_discussion_links(provider, search_string):
    """
    Initializes a single Selenium instance to collect all relevant discussion links.
    """
    links = []
    driver = None
    try:
        print("Initializing browser to find all discussion links...")
        chrome_options = Options()
        chrome_options.add_argument("--headless")
        chrome_options.add_argument("--window-size=1920,1080")
        chrome_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36")
        
        # Apply the context manager to hide logs during browser initialization
        with suppress_console_logs():
            service = ChromeService(ChromeDriverManager().install())
            driver = webdriver.Chrome(service=service, options=chrome_options)
        
        base_url = f"https://www.examtopics.com/discussions/{provider.lower()}/"
        driver.get(base_url)
        time.sleep(3)
        
        page_indicator = driver.find_element(By.CLASS_NAME, "discussion-list-page-indicator")
        num_pages = int(page_indicator.find_elements(By.TAG_NAME, "strong")[1].text)
        print(f"Total pages found: {num_pages}")

        for page in tqdm(range(1, num_pages + 1), desc="Fetching Links", unit="page"):
            driver.get(f"{base_url}{page}/")
            time.sleep(2)
            for discussion in driver.find_elements(By.CLASS_NAME, "discussion-link"):
                if search_string.lower() in discussion.text.lower():
                    links.append(discussion.get_attribute('href'))
        
        return list(set(links))
    except Exception as e:
        print(f"An error occurred while getting links: {e}")
        return links
    finally:
        if driver:
            driver.quit()

def fetch_single_question_data(link_item):
    """
    This is the worker function for each thread. It creates its own browser instance,
    scrapes one link, and then closes itself.
    """
    link = link_item['link']
    driver = None
    try:
        chrome_options = Options()
        chrome_options.add_argument("--headless")
        chrome_options.add_argument("--window-size=1920,1080")
        chrome_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36")
        
        # Apply the context manager to hide logs during this thread's browser initialization
        with suppress_console_logs():
            service = ChromeService(ChromeDriverManager().install())
            driver = webdriver.Chrome(service=service, options=chrome_options)

        driver.get(link)
        time.sleep(5)

        soup = BeautifulSoup(driver.page_source, "html.parser")
        
        question_body_div = soup.find("div", class_="question-body")
        if not question_body_div:
            return {**link_item, 'question_text': 'Blocked or question not found', 'choices': [], 'suggested_answer': ''}

        question_p = question_body_div.find("p", class_="card-text")
        question_text = question_p.get_text(separator='\n', strip=True) if question_p else "Question text not found."

        choices = []
        choices_container = soup.find("div", class_="question-choices-container")
        if choices_container:
            for item in choices_container.find_all("li", class_="multi-choice-item"):
                full_text = item.get_text(strip=True)
                clean_text = ' '.join(full_text.replace("Most Voted", "").strip().split())
                choices.append(clean_text)

        suggested_answer = "Not found"
        answer_container = soup.find("div", class_="question-answer")
        if answer_container:
            correct_answer_span = answer_container.find("span", class_="correct-answer")
            if correct_answer_span:
                suggested_answer = correct_answer_span.get_text(strip=True)

        return {**link_item, 'question_text': question_text, 'choices': choices, 'suggested_answer': suggested_answer}
    except Exception:
        return {**link_item, 'question_text': 'Error during processing', 'choices': [], 'suggested_answer': ''}
    finally:
        if driver:
            driver.quit()

def extract_topic_question(link):
    """Uses regex to extract topic and question numbers from a URL."""
    match = re.search(r'topic-(\d+)-question-(\d+)', link)
    return (int(match.group(1)), int(match.group(2))) if match else (None, None)

def save_as_text_file(filename, all_question_data):
    """Writes the final collected data to a human-readable text file."""
    with open(f"{filename}.txt", 'w', encoding='utf-8') as f:
        for topic in sorted(all_question_data.keys()):
            f.write(f'{"-"*20}\nTopic {topic}\n{"-"*20}\n\n')
            sorted_questions = sorted(all_question_data[topic], key=lambda q: q['key'][1])
            for item in sorted_questions:
                f.write(f"Question {item['key'][1]}:\n")
                f.write(f"Link: {item['link']}\n\n")
                f.write(f"{item['question_text']}\n\n")
                f.write("Choices:\n")
                if item['choices']:
                    for choice in item['choices']:
                        f.write(f"• {choice}\n")
                else:
                    f.write("• No choices found.\n")
                f.write(f"\nSuggested Answer: {item.get('suggested_answer', 'Not found')}\n")
                f.write('\n' + "="*40 + '\n\n')
    print(f"\nSuccessfully saved results to '{filename}.txt'")

def save_as_anki_csv(filename, all_question_data):
    """Saves the data as a 2-column CSV file for easy Anki import."""
    with open(f"{filename}.csv", "w", encoding="utf-8", newline='') as f:
        writer = csv.writer(f)
        for topic in sorted(all_question_data.keys()):
            sorted_questions = sorted(all_question_data[topic], key=lambda q: q['key'][1])
            for item in sorted_questions:
                front_html = f"<div style='text-align: left;'>{item['question_text'].replace(chr(10), '<br>')}<br><br><b>Choices:</b><br>" + "<br>".join([f"• {c}" for c in item['choices']]) + "</div>"
                back_html = f"<div style='font-size: 20px;'><b>Suggested Answer:</b><br>{item['suggested_answer']}</div>"
                writer.writerow([front_html, back_html])
    
    print("\n" + "="*35)
    print("   ANKI EXPORT SUCCESSFUL")
    print("="*35)
    print(f"\nFlashcards saved to: '{filename}.csv'")
    print("\n--- How to Import into Anki ---")
    print("1. Open Anki.")
    print("2. Go to 'File' > 'Import...'")
    print(f"3. Select the file '{filename}.csv'.")
    print("4. Ensure 'Fields separated by' is set to 'Comma'.")
    print("5. IMPORTANT: Check the box for 'Allow HTML in fields'.")
    print("6. Click 'Import'.")
    print("="*35)

def main():
    """Main function to drive the scraping process."""
    try:
        provider = input("Enter provider name (e.g., 'google', 'microsoft'): ")
        search_string = input("Enter exam keyword (e.g., 'Cloud Architect') or 'QUIT': ")
        if search_string.lower() == 'quit': return
        
        links = get_all_discussion_links(provider, search_string)
        if not links:
            print("\nNo discussion links found matching your search term.")
            return

        valid_links_to_process = [{'key': extract_topic_question(link), 'link': link} for link in links if extract_topic_question(link)]
        
        if not valid_links_to_process:
            print("\nNo valid question pages found among the links.")
            return
            
        sorted_links = sorted(valid_links_to_process, key=lambda item: item['key'])
        print(f"\nFound {len(sorted_links)} question links. Now fetching details using up to {MAX_CONCURRENT_BROWSERS} parallel browsers...")
        
        all_results = []
        with ThreadPoolExecutor(max_workers=MAX_CONCURRENT_BROWSERS) as executor:
            futures = [executor.submit(fetch_single_question_data, item) for item in sorted_links]
            for future in tqdm(as_completed(futures), total=len(sorted_links), desc="Processing Questions"):
                all_results.append(future.result())

        all_question_data = {}
        for result in all_results:
            if result and result.get('key'):
                topic = result['key'][0]
                all_question_data.setdefault(topic, []).append(result)

        filename_base = f'{provider}_{search_string.replace(" ", "_")}'
        
        while True:
            print("\nHow would you like to save the results?")
            print("  1. Simple Text File (.txt)")
            print("  2. Anki Import File (.csv)")
            choice = input("Enter your choice (1 or 2): ")
            if choice == '1':
                save_as_text_file(filename_base, all_question_data)
                break
            elif choice == '2':
                save_as_anki_csv(filename_base, all_question_data)
                break
            else:
                print("Invalid choice. Please enter 1 or 2.")
        
        print("\nProcess complete.")

    except KeyboardInterrupt:
        print("\nProcess interrupted by user.")
    except Exception as e:
        print(f"\n--- A critical error occurred in main --- \nError: {e}")
    finally:
        print("Program finished.")

if __name__ == "__main__":
    main()