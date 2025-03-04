from IPython.display import Image, display
import os

def display_graph(graph):
    graph_image_path = os.path.join("output", "graph_visualization.png")
    try:
        # Stellen Sie sicher, dass das Ausgabeverzeichnis existiert
        os.makedirs(os.path.dirname(graph_image_path), exist_ok=True)
        
        # Generieren Sie das Mermaid-PNG aus dem Graphen
        graph_image = graph.get_graph(xray=True).draw_mermaid_png()
        
        # Speichern Sie das Bild
        with open(graph_image_path, "wb") as f:
            f.write(graph_image)
            
        # Zeigen Sie das Bild in Jupiter Notebook an
        display(Image(graph_image))
        print(f"Graph visualisiert und als PNG unter '{graph_image_path}' gespeichert")
    except Exception as e:
        print(f"Fehler beim Erstellen oder Anzeigen des Graphen: {e}") 