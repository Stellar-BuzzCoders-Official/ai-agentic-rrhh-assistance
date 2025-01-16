from src.ports.output_ports.chromadb_repository_port import ChromaDbRepositoryPort
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import Chroma
from langchain_community.embeddings import OllamaEmbeddings
import chromadb
from typing import List
import ollama 
import uuid
import os

class ChromaRepository(ChromaDbRepositoryPort):
    def __init__(self):
        chroma_server_host = os.environ.get('CHROMA_SERVER_HOST', 'localhost')
        chroma_server_http_port = os.environ.get('CHROMA_SERVER_HTTP_PORT', '8000')
        
        print(f"[INIT] ChromaRepository - chroma_server_host: {chroma_server_host}")
        print(f"[INIT] ChromaRepository - chroma_server_http_port: {chroma_server_http_port}")
        
        self.chroma_client = chromadb.HttpClient(host=chroma_server_host, port=chroma_server_http_port)
        self.context_collection = self.chroma_client.get_or_create_collection("business_context")
        self.vector_db = None

    def get_context_by_conversation_id(self, conversation_id: str):
        print(f"[GET_CONTEXT_BY_CONVERSATION_ID] Buscando contexto para conversation_id: {conversation_id}")
        
        # Realiza una consulta a ChromaDB usando el conversation_id
        results = self.context_collection.query(
            query_embeddings=[conversation_id],
            n_results=1
        )
        
        if results['documents']:
            print(f"[GET_CONTEXT_BY_CONVERSATION_ID] Contexto encontrado: {results['documents'][0][0]}")
            return results['documents'][0][0]  # Ajusta esto según tu estructura
        else:
            print("[GET_CONTEXT_BY_CONVERSATION_ID] No se encontró contexto.")
            return None
    
    def process_document(self, text: str):
        print(f"[PROCESS_DOCUMENT] Iniciando procesamiento del documento con texto de longitud: {len(text)}")
        
        text_splitter = RecursiveCharacterTextSplitter(chunk_size=512, chunk_overlap=100)
        chunks = text_splitter.split_text(text)
        
        print(f"[PROCESS_DOCUMENT] Chunks generados: {chunks}")
        
        self.vector_db = Chroma.from_texts(
            texts=chunks,
            embedding=OllamaEmbeddings(model="nomic-embed-text", show_progress=False),
            collection_name="local-rag",
            client=self.chroma_client
        )
        print(f"[PROCESS_DOCUMENT] Chunks procesados y guardados en vector_db.")

    def similarity_search(self, query: str, k: int) -> List[str]:
        print(f"[SIMILARITY_SEARCH] Iniciando búsqueda de similitud para query: {query}")
        
        if not self.vector_db:
            print("[SIMILARITY_SEARCH] Error: vector_db no está inicializado.")
            return []
        
        embedding = OllamaEmbeddings(model="nomic-embed-text", show_progress=False)
        vector = embedding.embed_query(query)
        
        print(f"[SIMILARITY_SEARCH] Vector de query generado: {vector}")
        
        results = self.vector_db.similarity_search(query, k=k)
        print(f"[SIMILARITY_SEARCH] Resultados obtenidos: {results}")
        return [doc.page_content for doc in results]
    
    def save_to_chroma(self, text: str, metadata: dict):
        print(f"[SAVE_TO_CHROMA] Intentando guardar el texto: {text} con metadata: {metadata}")
        
        if not text:
            print(f"[SAVE_TO_CHROMA] No se guardó el texto ya que es None o vacío.")
            return
        
        try:
            embedding = OllamaEmbeddings(model="nomic-embed-text", show_progress=False)
            
            # Genera el vector de embeddings
            vector = embedding.embed_query(text)
            
            if vector is None or not isinstance(vector, list):
                print(f"[SAVE_TO_CHROMA] Error: El vector de embeddings es None o no es una lista.")
                return
            
            doc_id = str(uuid.uuid4())
            
            # Guardar en ChromaDB
            self.context_collection.add(
                documents=[text],
                metadatas=[metadata],
                embeddings=[vector],
                ids=[doc_id]
            )
            print(f"[SAVE_TO_CHROMA] Texto guardado exitosamente en ChromaDB con ID {doc_id}.")
            
        except Exception as e:
            print(f"[SAVE_TO_CHROMA] Ocurrió un error al intentar guardar en ChromaDB: {e}")

            
    def retrieve_from_chroma(self, query: str) -> str:
        print(f"[RETRIEVE_FROM_CHROMA] Recuperando documento con el query: {query}")

        # Verifica que vector_db esté inicializado
        if not self.vector_db:
            print("[RETRIEVE_FROM_CHROMA] Error: vector_db no está inicializado. Asegúrate de llamar a process_document primero.")
            return None

        embedding = OllamaEmbeddings(model="nomic-embed-text", show_progress=False)
        vector = embedding.embed_query(query)

        print(f"[RETRIEVE_FROM_CHROMA] Vector generado para el query: {vector}")

        results = self.context_collection.query(
            query_embeddings=[vector],
            n_results=1
        )
        print(f"[RETRIEVE_FROM_CHROMA] Resultados obtenidos: {results}")

        if results['documents']:
            print(f"[RETRIEVE_FROM_CHROMA] Documento encontrado: {results['documents'][0][0]}")
            return results['documents'][0][0]

        print("[RETRIEVE_FROM_CHROMA] No se encontraron documentos.")
        return None

