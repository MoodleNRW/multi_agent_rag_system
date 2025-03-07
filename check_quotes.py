import weaviate
from weaviate.connect import ConnectionParams

def check_quotes():
    client = weaviate.WeaviateClient(ConnectionParams.from_url('http://localhost:8090', grpc_port=50051))
    try:
        # Verbinde den Client
        client.connect()
        
        # Prüfe, ob die Quote-Collection existiert
        quote_collection = client.collections.get('Quote')
        quotes = quote_collection.query.fetch_objects(limit=10)
        
        print(f'Anzahl der gefundenen Quotes: {len(quotes.objects)}')
        
        if len(quotes.objects) > 0:
            for i, quote in enumerate(quotes.objects):
                print(f'Quote {i+1}: {quote.properties.get("content", "Kein Inhalt")}')
                print(f'  Quelle: {quote.properties.get("source", "Keine Quelle")}')
                print(f'  URL: {quote.properties.get("url", "Keine URL")}')
                print('-' * 80)
        else:
            print('Keine Quotes gefunden.')
    except Exception as e:
        print(f'Fehler: {str(e)}')
    finally:
        client.close()

if __name__ == "__main__":
    check_quotes() 