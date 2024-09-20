from langchain_openai import OpenAIEmbeddings
from langchain_weaviate.vectorstores import WeaviateVectorStore
import weaviate

def create_retrievers():
    # todo work in progress -> Retriever selbst schreiben / vs query?
    return None, None, None
#     embeddings = OpenAIEmbeddings()
    
#     # Connect to the Weaviate instance on localhost at port 8090
#     client = weaviate.Client(
#         url="http://localhost:8090"  # Ensure the URL is correctly set
#     )

#     # Create vector stores for each index with required text_key parameter
#     chunks_vector_store = WeaviateVectorStore(
#         client=client, 
#         index_name="chunks_vector_store", 
#         embedding=embeddings, 
#         text_key="content"  # Replace "content" with the actual key used in your documents
#     )

#     chapter_summaries_vector_store = WeaviateVectorStore(
#         client=client, 
#         index_name="chapter_summaries_vector_store", 
#         embedding=embeddings, 
#         text_key="content"  # Replace with the correct key
#     )

#     quotes_vectorstore = WeaviateVectorStore(
#         client=client, 
#         index_name="quotes_vectorstore", 
#         embedding=embeddings, 
#         text_key="content"  # Replace with the correct key
#     )

#     # Create retrievers
#     chunks_query_retriever = chunks_vector_store.as_retriever(search_kwargs={"k": 1})     
#     chapter_summaries_query_retriever = chapter_summaries_vector_store.as_retriever(search_kwargs={"k": 1})
#     quotes_query_retriever = quotes_vectorstore.as_retriever(search_kwargs={"k": 10})
    
#     return chunks_query_retriever, chapter_summaries_query_retriever, quotes_query_retriever

# # Test the retrievers (Optional)
# chunks_retriever, chapter_summaries_retriever, quotes_retriever = create_retrievers()
# print("Retrievers created successfully.")
