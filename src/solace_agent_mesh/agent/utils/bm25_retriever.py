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
            search_results.append({
                'text': corpus[idx],
                'score': float(score),
                'chunk_index': chunk_metadata['chunk_index'],
                'doc_name': chunk_metadata['doc_name'],
                'doc_path': chunk_metadata['doc_path'],
                'file_type': chunk_metadata['file_type'],
                'char_start': chunk_metadata['char_start'],
                'char_end': chunk_metadata['char_end'],
                'page_numbers': chunk_metadata.get('page_numbers', []),
                'page_start': chunk_metadata.get('page_start', None),
                'page_end': chunk_metadata.get('page_end', None)
            })
        
        logger.info(f"Found {len(search_results)} results for query: '{query}'")
        
        # Filter by minimum score
        filtered_results = [r for r in search_results if r['score'] >= min_score]
        
        return filtered_results
    
    def explain_bm25_scores(self, results: List[Dict[str, Any]]) -> str:
        """
        Generate a human-readable explanation of BM25 scores.
        
        Args:
            results: Search results with scores
            
        Returns:
            Explanation string
        """
        if not results:
            return "No results to explain."
        
        scores = [r['score'] for r in results]
        
        explanation = f"""
BM25 Score Explanation:
-----------------------
Total Results: {len(results)}
Score Range: {min(scores):.2f} to {max(scores):.2f}
Average Score: {np.mean(scores):.2f}

Score Interpretation:
- Scores > 10: Highly relevant (multiple query terms, good frequency)
- Scores 5-10: Moderately relevant (some query terms present)
- Scores 1-5: Weakly relevant (few query terms or low frequency)
- Scores < 1: Marginally relevant (rare terms or poor match)

Note: BM25 scores are relative rankings, not probabilities.
Higher scores indicate better keyword matches with the query.
"""
        return explanation


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
        
        sources_citation_for_llm.append({
            'source_id': i,
            'document': result['doc_name'],
            'chunk_index': result['chunk_index'],
            'score': result['score'],
            'file_type': result['file_type'],
            'doc_path': result['doc_path'],
            'text': result['text'],
            'page_numbers': result['page_numbers']
        })
    
    return {
            'context_for_llm': context_for_llm,
            'num_chunks': len(results),
            'sources_citation_for_llm': sources_citation_for_llm,
            'score_range': {
                'max': results[0]['score'] if results else 0,
                'min': results[-1]['score'] if results else 0
            }
        }

if __name__ == "__main__":
    
    # Configuration
    __DIR__ = os.path.dirname(os.path.abspath(__file__))
    doc_path = os.path.join(__DIR__, "docs/bedrock-ug.pdf")
    index_base_dir = os.path.join(__DIR__, "indexes/bedrock-ug")
    query = "what are the prerequisites for using amazon bedrock?"
    
    results = retrieve(index_base_dir, query)
    pprint.pprint(f"results: {results}")
    
    # Save results to JSON file
    output_path = os.path.join(__DIR__, "retrieval_results.json")
    
    # Ensure output directory exists
    output_dir = os.path.dirname(output_path)
    if output_dir and not os.path.exists(output_dir):
        os.makedirs(output_dir, exist_ok=True)
    
    # Save to JSON with nice formatting
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

    print(f"\n✓ Results saved to: {output_path}")
