import logging
import os
from pathlib import Path
import json
import pprint
from datetime import datetime

"""
BM25 Document Retriever - Searches across individual document indexes

This module demonstrates how to:
1. Load BM25 indexes for documents
2. Perform keyword-based search using BM25
3. Understand what BM25 returns (scores and ranked results)
4. Retrieve relevant chunks with metadata for RAG
"""

import logging
from pathlib import Path
from typing import List, Dict, Any, Tuple
import json
import pickle
import bm25s
import Stemmer
import numpy as np

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class BM25Retriever:
    """
    Retrieves relevant document chunks using BM25 keyword search.
    
    How BM25 Works:
    ---------------
    BM25 (Best Matching 25) is a ranking function used for keyword-based search.
    
    1. TOKENIZATION: Query and documents are tokenized into words
    2. STEMMING: Words are reduced to root forms (e.g., "running" -> "run")
    3. SCORING: Each document chunk is scored based on:
       - Term Frequency (TF): How often query terms appear in the chunk
       - Inverse Document Frequency (IDF): How rare/important the terms are
       - Document Length Normalization: Adjusts for chunk length
    
    What BM25 Returns:
    ------------------
    - Ranked list of document chunks (by relevance score)
    - BM25 scores (higher = more relevant)
    - Document indices (which chunks matched)
    
    The scores are NOT probabilities - they're relative rankings.
    Typical scores range from 0 to ~20+, with higher being better.
    """
    
    def __init__(self, index_base_dir: str):
        """
        Initialize the retriever.
        
        Args:
            index_base_dir: Base directory containing document indexes
        """
        self.index_base_dir = Path(index_base_dir)
        self.stemmer = Stemmer.Stemmer("english")
    
    def _format_location(
        self, 
        file_type: str, 
        page_start: int, 
        page_end: int, 
        page_numbers: List[int]
    ) -> str:
        """
        Format location information based on file type.
        
        Args:
            file_type: File extension or MIME type
            page_start: Starting page/slide/line number
            page_end: Ending page/slide/line number
            page_numbers: List of all page/slide/line numbers spanned
            
        Returns:
            Human-readable location string
        """
        if not page_start:
            return "Location not available"
        
        # Determine the type of location based on file type
        if file_type in ['.pptx', '.ppt', 'application/vnd.openxmlformats-officedocument.presentationml.presentation', 'application/vnd.ms-powerpoint']:
            location_type = "slide"
        elif file_type in ['.txt', '.md', '.csv', '.html', '.htm', '.json', '.xml', 'text/plain', 'text/markdown', 'text/csv', 'text/html', 'application/json', 'application/xml']:
            location_type = "line"
        else:
            # PDF, DOCX, and other binary formats use "page"
            location_type = "page"
        
        # Format the location string
        if page_start == page_end:
            return f"{location_type.capitalize()} {page_start}"
        else:
            return f"{location_type.capitalize()}s {page_start}-{page_end}"
    
    def load_document_index(self) -> Tuple[bm25s.BM25, List[str], Dict]:
        """
        Load a BM25 index for a specific document.
        
        Args:
            doc_path: Path of the document
            
        Returns:
            Tuple of (retriever, corpus, metadata)
        """
        
        # Load the BM25 index
        retriever = bm25s.BM25.load(self.index_base_dir, mmap=True)
        
        # Load corpus
        with open(self.index_base_dir / "corpus.pkl", 'rb') as f:
            corpus = pickle.load(f)
        
        # Load metadata
        with open(self.index_base_dir / "metadata.json", 'r') as f:
            metadata = json.load(f)
        
        return retriever, corpus, metadata
    
    def search_single_document(
        self,
        query: str,
        top_k: int = 10,
        min_score: float = 0.0
    ) -> List[Dict[str, Any]]:
        """
        Search within a single specific document.
        
        Args:
            doc_path: path of the document to search
            query: Search query
            top_k: Number of top results to return
            min_score: Minimum BM25 score threshold
            
        Returns:
            List of search results from the specified document
        """

        # Load the index
        retriever, corpus, metadata = self.load_document_index()
        
        # Tokenize the query (same preprocessing as indexing)
        query_tokens = bm25s.tokenize(
            query,
            stemmer=self.stemmer,
            stopwords="en"
        )
        
        # Perform BM25 search
        # Returns: (results, scores) where results are chunk indices
        results, scores = retriever.retrieve(query_tokens, k=top_k)
        
        # Format results with metadata
        search_results = []
        for idx, score in zip(results[0], scores[0]):
            chunk_metadata = metadata['chunks'][idx]
            
            # Determine the type of position tracking based on file type
            file_type = chunk_metadata['file_type']
            
            # Extract position information - check for all possible field names
            position_numbers = (chunk_metadata.get('page_numbers') or 
                              chunk_metadata.get('slide_numbers') or 
                              chunk_metadata.get('line_numbers') or [])
            position_start = (chunk_metadata.get('page_start') or 
                            chunk_metadata.get('slide_start') or 
                            chunk_metadata.get('line_start'))
            position_end = (chunk_metadata.get('page_end') or 
                          chunk_metadata.get('slide_end') or 
                          chunk_metadata.get('line_end'))
            
            # Create a human-readable location string
            location_info = self._format_location(file_type, position_start, position_end, position_numbers)
            
            result_data = {
                'text': corpus[idx],
                'score': float(score),
                'chunk_index': chunk_metadata['chunk_index'],
                'doc_name': chunk_metadata['doc_name'],
                'doc_path': chunk_metadata['doc_path'],
                'file_type': file_type,
                'char_start': chunk_metadata['char_start'],
                'char_end': chunk_metadata['char_end'],
                'location': location_info  # Human-readable location
            }
            
            # Add the appropriate position fields based on what's available
            if 'page_numbers' in chunk_metadata:
                result_data['page_numbers'] = chunk_metadata['page_numbers']
                result_data['page_start'] = chunk_metadata.get('page_start')
                result_data['page_end'] = chunk_metadata.get('page_end')
            elif 'slide_numbers' in chunk_metadata:
                result_data['slide_numbers'] = chunk_metadata['slide_numbers']
                result_data['slide_start'] = chunk_metadata.get('slide_start')
                result_data['slide_end'] = chunk_metadata.get('slide_end')
            elif 'line_numbers' in chunk_metadata:
                result_data['line_numbers'] = chunk_metadata['line_numbers']
                result_data['line_start'] = chunk_metadata.get('line_start')
                result_data['line_end'] = chunk_metadata.get('line_end')
            
            search_results.append(result_data)
        
        logger.info(f"Found {len(search_results)} results for query: '{query}'")
        
        # Filter by minimum score
        filtered_results = [r for r in search_results if r['score'] >= min_score]
        
        return filtered_results

def retrieve(index_base_dir: str, query: str, top_k: int =10, min_score: float=0.0):

    retriever = BM25Retriever(index_base_dir)
    results = retriever.search_single_document(
            query=query,
            top_k=top_k,
            min_score=min_score
        )
        
    if not results:
        return {
            'question': query,
            'answer': f"I couldn't find any relevant information to answer this question.",
            'sources': [],
            'retrieval_stats': {
                'chunks_retrieved': 0,
                'documents_searched': 1,
                'document_path': None
            }
        }
    
    # Step 2: Format context
    context_for_llm = []
    sources_citation_for_llm = []
    
    #return results

    for i, result in enumerate(results, 1):
        context_for_llm.append({
            f"Source {i}": result['text']
        })
        
        # Build citation with appropriate position fields
        citation = {
            'source_id': i,
            'document': result['doc_name'],
            'chunk_index': result['chunk_index'],
            'score': result['score'],
            'file_type': result['file_type'],
            'doc_path': result['doc_path'],
            'text': result['text'],
            'location': result.get('location', 'Location not available')  # Human-readable location
        }
        
        # Add the appropriate position fields based on what's available
        if 'page_numbers' in result:
            citation['page_numbers'] = result['page_numbers']
            citation['page_start'] = result.get('page_start')
            citation['page_end'] = result.get('page_end')
        elif 'slide_numbers' in result:
            citation['slide_numbers'] = result['slide_numbers']
            citation['slide_start'] = result.get('slide_start')
            citation['slide_end'] = result.get('slide_end')
        elif 'line_numbers' in result:
            citation['line_numbers'] = result['line_numbers']
            citation['line_start'] = result.get('line_start')
            citation['line_end'] = result.get('line_end')
        
        sources_citation_for_llm.append(citation)
    
    return {
            'context_for_llm': context_for_llm,
            'num_chunks': len(results),
            'sources_citation_for_llm': sources_citation_for_llm,
            'score_range': {
                'max': results[0]['score'] if results else 0,
                'min': results[-1]['score'] if results else 0
            }
        }
