from langchain_community.vectorstores import Weaviate
import weaviate
import openai

# Initialize the Weaviate client
weaviate_client = weaviate.Client("http://localhost:8090")

# Set up Weaviate as the vector store for LangChain
vectorstore = Weaviate(client=weaviate_client, index_name="my_index", text_key="content")

# Example documents to add to Weaviate
documents = [
    {"content": "Weaviate is an open-source vector search engine."},
    {"content": "It allows semantic search using machine learning models."},
    {"content": "Weaviate integrates well with LangChain for AI-driven applications."}
]

# Add documents to the index
vectorstore.add_texts(texts=[doc["content"] for doc in documents])

# Use OpenAI to get vector representation for the query
openai.api_key = "your-openai-api-key"  # Replace with your actual OpenAI API key

query = "What is Weaviate?"
response = openai.Embedding.create(
    input=query,
    model="text-embedding-ada-002"
)
query_vector = response['data'][0]['embedding']

# Perform similarity search using nearVector
retriever = vectorstore.as_retriever(search_type="similarity", search_kwargs={"k": 2, "vector": query_vector})

# Execute the query using the correct method
try:
    query_result = retriever.invoke(query)
    print("Query Results:", query_result)
except ValueError as e:
    print(f"An error occurred: {e}")
