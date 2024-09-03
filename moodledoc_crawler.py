import requests
from bs4 import BeautifulSoup
from urllib.parse import urlparse, urljoin
from concurrent.futures import ThreadPoolExecutor, as_completed
import sys
import os
import time
import threading

# Globals for progress tracking
total_pages = 0
completed_pages = 0
lock = threading.Lock()

def scrape_text(url):
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
    except requests.exceptions.RequestException as e:
        return ""
    soup = BeautifulSoup(response.text, 'html.parser')
    remove = soup.select('li a')
    for e in remove:
        e.decompose()
    texts = []
    content = soup.select('div#content p, div#content li, div#content img')
    for tag in content:
        # TODO for future add more than just picture description
        if tag.name == 'img' and 'alt' in tag.attrs:
            texts.append(tag['alt'])
        else:
            texts.append(tag.get_text(strip=True))

    text = ' '.join(texts)
    return text

def get_subpages(url):
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
    except requests.exceptions.RequestException as e:
        return []

    soup = BeautifulSoup(response.text, 'html.parser')
    subpages = []

    for link in soup.find_all('a'):
        href = link.get('href')
        if href:
            absolute_url = urljoin(url, href)
            if urlparse(absolute_url).netloc == urlparse(url).netloc:
                subpages.append(absolute_url)

    return list(set(subpages))  # Remove duplicates

def update_progress():
    global completed_pages, total_pages
    with lock:
        progress = (completed_pages / total_pages) * 100 if total_pages > 0 else 100
        sys.stdout.write(f"\rProgress: {progress:.2f}% ({completed_pages}/{total_pages}) pages completed.")
        sys.stdout.flush()

def scrape_website(url, visited=None, max_workers=10, depth=10):
    global total_pages, completed_pages
    if visited is None:
        visited = set()  # Keep track of visited URLs

    pages_to_scrape = [url]
    results = []
    
    while pages_to_scrape:
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {}
            for page in pages_to_scrape:
                if page not in visited:
                    visited.add(page)
                    futures[executor.submit(scrape_and_collect, page)] = page

            # Update total pages to reflect the new pages that need to be scraped
            total_pages += len(futures)

            pages_to_scrape = []
            for future in as_completed(futures):
                if depth==0:
                    return '\n'.join([f"# Page: {url}\n\n{text}\n" for url, text in results])
                subpages, text = future.result()
                depth = depth - 1;
                results.append((futures[future], text))
                completed_pages += 1  # Mark this page as completed
                update_progress()
                for subpage in subpages:
                    if subpage not in visited:
                        pages_to_scrape.append(subpage)

    return '\n'.join([f"# Page: {url}\n\n{text}\n" for url, text in results])

def scrape_and_collect(url):
    text = scrape_text(url)
    subpages = get_subpages(url)
    return subpages, text

def generate_output_filename(url):
    parsed_url = urlparse(url)
    domain = parsed_url.netloc.replace("www.", "")
    path = parsed_url.path.replace("/", "_").strip("_")
    filename = f"{domain}_{path}.md" if path else f"{domain}.md"
    return filename

def main():
    if len(sys.argv) > 1:
        website_url = sys.argv[1]
    else:
        website_url = input("Geben Sie eine Webseite ein, um das Scraping zu beginnen: ")

    output_file = generate_output_filename(website_url)

    print(f"Starting the scraping process for: {website_url}")
    start_time = time.time()
    scraped_text = scrape_website(website_url)

    with open(output_file, 'w', encoding='utf-8') as file:
        file.write(scraped_text)

    elapsed_time = time.time() - start_time
    print(f"\nScraped text has been saved to {output_file}")
    print(f"Total time taken: {elapsed_time:.2f} seconds")

if __name__ == "__main__":
    main()