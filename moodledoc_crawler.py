import requests
from bs4 import BeautifulSoup
from urllib.parse import urlparse, urljoin
from concurrent.futures import ThreadPoolExecutor, as_completed
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain.docstore.document import Document
from langchain.text_splitter import CharacterTextSplitter
from langchain_core.prompts import ChatPromptTemplate
from langchain.chains.combine_documents import create_stuff_documents_chain
import sys
import os
import time
import threading
import weaviate
from datetime import datetime
import dotenv
from models.models_wrapper import get_llm
dotenv.load_dotenv()

# Globals for progress tracking
total_pages = 0
completed_pages = 0
lock = threading.Lock()
API_KEY = os.getenv('OPENAI_API_KEY')

# Initialize the Weaviate client
weaviate_client = weaviate.Client("http://localhost:8090", additional_headers = {
        "X-OpenAI-Api-Key": API_KEY
    })

# Erstelle DB Collection wenn sie noch nicht existiert
if not weaviate_client.schema.exists("Content"):
    class_obj = {
        "class": "Content",
        "vectorizer": "text2vec-openai",  # If set to "none" you must always provide vectors yourself. Could be any other "text2vec-*" also.
        "moduleConfig": {
            "text2vec-openai": {},
            "generative-openai": {}  # Ensure the `generative-openai` module is used for generative queries
        }
    }
    weaviate_client.schema.create_class(class_obj)

if not weaviate_client.schema.exists("Content_chunk"):
    class_obj = {
        "class": "Content_chunk",
        "vectorizer": "text2vec-openai",  # If set to "none" you must always provide vectors yourself. Could be any other "text2vec-*" also.
        "moduleConfig": {
            "text2vec-openai": {},
            "generative-openai": {}  # Ensure the `generative-openai` module is used for generative queries
        }
    }
    weaviate_client.schema.create_class(class_obj)

if not weaviate_client.schema.exists("Content_summary"):
    class_obj = {
        "class": "Content_summary",
        "vectorizer": "text2vec-openai",  # If set to "none" you must always provide vectors yourself. Could be any other "text2vec-*" also.
        "moduleConfig": {
            "text2vec-openai": {},
            "generative-openai": {}  # Ensure the `generative-openai` module is used for generative queries
        }
    }
    weaviate_client.schema.create_class(class_obj)

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
                    break
                subpages, text = future.result()
                depth = depth - 1;
                results.append((futures[future], text))
                completed_pages += 1  # Mark this page as completed
                update_progress()
                for subpage in subpages:
                    if subpage not in visited:
                        pages_to_scrape.append(subpage)
            else:
                continue
            break
    

    # Save content in weaviate
    weaviate_client.batch.configure(batch_size=10)  # Configure batch
    with weaviate_client.batch as batch:  # Initialize a batch process
        for url, text in results:  # Batch import data
            # Content import
            print(f"importing content")
            where_filter = {
                "path": ["url"],
                "operator": "Equal",
                "valueString": url
            }
            # Check if url already exists
            obj = weaviate_client.query.get("Content","url").with_where(where_filter).with_additional('id').do()
            properties = {
                "url": url,
                "content": text,
                "date": datetime.now().isoformat(),
            }
            # if not create new object
            if 'errors' in obj or not obj['data']['Get']['Content']:
                batch.add_data_object(
                    data_object=properties,
                    class_name="Content"
                )
            # else update existing
            else:
                weaviate_client.data_object.update(
                    uuid=obj['data']['Get']['Content'][0]['_additional']['id'],
                    class_name="Content",
                    data_object={
                        "content": text,
                        "date": datetime.now().isoformat(),
                    },
                )

            # Chunk import 
            text_splitter = RecursiveCharacterTextSplitter(
                # Set a really small chunk size, just to show.
                chunk_size=1000,
                chunk_overlap=20,
                length_function=len,
                is_separator_regex=False,
            )
            texts = text_splitter.split_text(text)
            i=0
            for t in texts:
                where_filter = {
                    "operator": "And",
                    "operands": [{
                            "path": ["url"],
                            "operator": "Equal",
                            "valueString": url
                        }, {
                            "path": ["chunk_nr"],
                            "operator": "Equal",
                            "valueNumber": i,
                        }]
                }
                # Check if url already exists
                obj = weaviate_client.query.get("Content_chunk","url").with_where(where_filter).with_additional('id').do()
                print(obj)
                properties = {
                    "url": url,
                    "chunk_nr": i,
                    "content_chunk": t,
                    "date": datetime.now().isoformat(),
                }
                # if not create new object
                if 'errors' in obj or not obj['data']['Get']['Content_chunk']:
                    print("new chunk")
                    batch.add_data_object(
                        data_object=properties,
                        class_name="Content_chunk"
                    )
                # else update existing
                else:
                    print("update")
                    weaviate_client.data_object.update(
                        uuid=obj['data']['Get']['Content_chunk'][0]['_additional']['id'],
                        class_name="Content_chunk",
                        data_object={
                            "content_chunk": text,
                            "date": datetime.now().isoformat(),
                        },
                    )
                i = i + 1

            # Summary
            docs = [Document(page_content=text)]
            if not text:
                break
            llm = get_llm()
            # Define prompt
            prompt_template = "Summarize this content: {context}"
            prompt = ChatPromptTemplate.from_template(prompt_template)
            stuff_chain = create_stuff_documents_chain(llm, prompt)
            summary = stuff_chain.invoke({"context": docs})
            
            where_filter = {
                "path": ["url"],
                "operator": "Equal",
                "valueString": url
            }
            # Check if url already exists
            obj = weaviate_client.query.get("Content_summary","url").with_where(where_filter).with_additional('id').do()
            properties = {
                "url": url,
                "content_summary": summary,
                "date": datetime.now().isoformat(),
            }
            # if not create new object
            if 'errors' in obj or not obj['data']['Get']['Content_summary']:
                batch.add_data_object(
                    data_object=properties,
                    class_name="Content_summary"
                )
            # else update existing
            else:
                weaviate_client.data_object.update(
                    uuid=obj['data']['Get']['Content_summary'][0]['_additional']['id'],
                    class_name="Content_summary",
                    data_object={
                        "content_summary": text,
                        "date": datetime.now().isoformat(),
                    },
                )

    return ''
    #return '\n'.join([f"# Page: {url}\n\n{text}\n" for url, text in results])

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
        depth = int(input("Geben Sie eine maximale Anzahl an Seiten an die ausgelesen werden soll: "))

    #output_file = generate_output_filename(website_url)

    print(f"Starting the scraping process for: {website_url}")
    start_time = time.time()
    scrape_website(website_url, depth=depth)

    #with open(output_file, 'w', encoding='utf-8') as file:
    #    file.write(scraped_text)

    elapsed_time = time.time() - start_time
    #print(f"\nScraped text has been saved to {output_file}")
    print(f"Total time taken: {elapsed_time:.2f} seconds")

if __name__ == "__main__":
    main()