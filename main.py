import requests
from bs4 import BeautifulSoup
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from tqdm import tqdm

class Scraper:
    def __init__(self, provider):
        self.session = requests.Session()
        self.provider = provider.lower()
        self.base_url = f"https://www.examtopics.com/discussions/{self.provider}/"

    def get_num_pages(self):
        """Retrieve the number of pages for the provider."""
        try:
            response = self.session.get(f"{self.base_url}")
            soup = BeautifulSoup(response.content, "html.parser")
            return int(soup.find("span", {"class": "discussion-list-page-indicator"}).find_all("strong")[1].text.strip())
        except Exception as e:
            print(f"Error fetching page count: {e}")
            return 0

    def fetch_page_links(self, page, search_string):
        """Fetch links from a single page."""
        try:
            response = self.session.get(f"{self.base_url}{page}/")
            soup = BeautifulSoup(response.content, "html.parser")
            discussions = soup.find_all("a", {"class": "discussion-link"})
            links = [
                discussion["href"].replace("/discussions", "https://www.examtopics.com/discussions", 1)
                for discussion in discussions if search_string.lower() in discussion.text.lower() # MODIFIED LINE
            ]
            return links
        except Exception as e:
            print(f"\nError on page {page}: {e}")
            return []

    def get_discussion_links(self, num_pages, search_string):
        """Retrieve discussion links that include the search string, using parallel requests."""
        links = []

        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(self.fetch_page_links, page, search_string) for page in range(1, num_pages + 1)]
            with tqdm(total=num_pages, desc="Fetching Links", unit="page") as pbar:
                for future in as_completed(futures):
                    page_links = future.result()
                    links.extend(page_links)
                    pbar.update(1)
        return links

def extract_topic_question(link):
    """Extract topic and question numbers from a link."""
    match = re.search(r'topic-(\d+)-question-(\d+)', link)
    return (int(match.group(1)), int(match.group(2))) if match else (None, None)

def write_grouped_links_to_file(filename, links):
    """
    Groups links by topic and writes them to a file,
    after filtering out invalid links and sorting them.
    """
    grouped_links = {}
    
    # --- Start of new logic ---

    # 1. Process links and filter out any that don't have a topic number.
    #    This creates a list of dictionaries, making it easier to sort.
    valid_links_to_process = []
    for link in links:
        # Call the extraction function only ONCE per link
        topic, question = extract_topic_question(link)
        
        # If the topic is None, it's not a valid question link, so we skip it.
        if topic is not None:
            valid_links_to_process.append({'key': (topic, question), 'link': link})

    # 2. Sort the list of valid links based on the key (topic, then question).
    #    This is now safe because all keys are tuples of integers.
    sorted_links = sorted(valid_links_to_process, key=lambda item: item['key'])

    # 3. Group the pre-sorted links by topic number.
    for item in sorted_links:
        topic = item['key'][0]
        link = item['link']
        grouped_links.setdefault(topic, []).append(link)
        
    # --- End of new logic ---

    # 4. Write the grouped links to the file.
    #    The topics will already be in order because we sorted before grouping.
    with open(filename, 'w') as f:
        for topic, topic_links in grouped_links.items():
            f.write(f'Topic {topic}:\n')
            for link in topic_links:
                f.write(f' - {link}\n')
            print(f"Topic {topic} links added to file.")

def main():
    provider = input("Enter provider name: ")
    scraper = Scraper(provider)
    num_pages = scraper.get_num_pages()
    print("Total Pages:",num_pages)
    if num_pages > 0:
        search_string = input("Enter exam code or enter QUIT to exit: ") # MODIFIED LINE
        if search_string.lower() != 'quit':
            links = scraper.get_discussion_links(num_pages, search_string)
            filename = f'{search_string} dumps.txt'
            print(f"\nYour file will be named {filename}")
            write_grouped_links_to_file(filename, links)
            print("File generation complete.")
        else:
            return
    else:
        print("No pages found for the provider.")

if __name__ == "__main__":
    main()