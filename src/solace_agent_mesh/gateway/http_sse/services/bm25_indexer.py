"""
BM25 Document Indexer - Creates individual indexes for each document

This module demonstrates how to:
1. Convert binary files (PDF, DOCX) to text using MarkItDown
2. Chunk documents properly for indexing
3. Create separate BM25 indexes for each document
4. Store metadata for retrieval and citation
"""

import os
import logging
from pathlib import Path
from typing import List, Dict, Any, Tuple, Optional
import json
import pickle
import bm25s
import Stemmer
from markitdown import MarkItDown
# pdfminer installed from markitdown[all]
from pdfminer.high_level import extract_pages
from pdfminer.layout import LTTextContainer

PDF_SUPPORT = 'pdfminer'

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class DocumentChunker:
    """
    Handles intelligent document chunking for BM25 indexing.
    
    Chunking Strategy:
    - Split documents into semantic chunks (paragraphs or sections)
    - Maintain overlap between chunks for context continuity
    - Preserve metadata for citation and source tracking
    """
    
    def __init__(
        self,
        chunk_size: int = 512,
        chunk_overlap: int = 128,
        min_chunk_size: int = 50
    ):
        """
        Initialize the document chunker.
        
        Args:
            chunk_size: Target size for each chunk (in characters)
            chunk_overlap: Number of characters to overlap between chunks
            min_chunk_size: Minimum chunk size to keep (avoid tiny chunks)
        """
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.min_chunk_size = min_chunk_size
    
    def chunk_text(
        self, 
        text: str, 
        doc_metadata: Dict[str, Any],
        page_map: Optional[List[Tuple[int, int, int]]] = None
    ) -> List[Dict[str, Any]]:
        """
        Split text into overlapping chunks with metadata.
        
        Args:
            text: The text content to chunk
            doc_metadata: Metadata about the source document
            page_map: Optional list of (page_num, char_start, char_end) tuples mapping 
                     character positions to page numbers
            
        Returns:
            List of chunk dictionaries with text and metadata
        """
        chunks = []
        
        # Split by paragraphs first (better semantic boundaries)
        paragraphs = text.split('\n\n')
        
        current_chunk = ""
        chunk_index = 0
        
        for para in paragraphs:
            para = para.strip()
            if not para:
                continue
            
            # If adding this paragraph exceeds chunk size, save current chunk
            if len(current_chunk) + len(para) > self.chunk_size and current_chunk:
                if len(current_chunk) >= self.min_chunk_size:
                    char_start = len(''.join([c['text'] for c in chunks]))
                    char_end = char_start + len(current_chunk)
                    
                    # Determine page number(s) for this chunk
                    page_numbers = self._get_page_numbers(char_start, char_end, page_map)
                    
                    chunk_data = {
                        'text': current_chunk.strip(),
                        'chunk_index': chunk_index,
                        'doc_name': doc_metadata['filename'],
                        'doc_path': doc_metadata['filepath'],
                        'file_type': doc_metadata['file_type'],
                        'char_start': char_start,
                        'char_end': char_end
                    }
                    
                    # Add page number information if available
                    if page_numbers:
                        chunk_data['page_numbers'] = page_numbers
                        chunk_data['page_start'] = page_numbers[0]
                        chunk_data['page_end'] = page_numbers[-1]
                    
                    chunks.append(chunk_data)
                    chunk_index += 1
                
                # Start new chunk with overlap
                overlap_text = current_chunk[-self.chunk_overlap:] if len(current_chunk) > self.chunk_overlap else current_chunk
                current_chunk = overlap_text + "\n\n" + para
            else:
                # Add paragraph to current chunk
                if current_chunk:
                    current_chunk += "\n\n" + para
                else:
                    current_chunk = para
        
        # Add the last chunk
        if current_chunk and len(current_chunk) >= self.min_chunk_size:
            char_start = len(''.join([c['text'] for c in chunks]))
            char_end = char_start + len(current_chunk)
            
            # Determine page number(s) for this chunk
            page_numbers = self._get_page_numbers(char_start, char_end, page_map)
            
            chunk_data = {
                'text': current_chunk.strip(),
                'chunk_index': chunk_index,
                'doc_name': doc_metadata['filename'],
                'doc_path': doc_metadata['filepath'],
                'file_type': doc_metadata['file_type'],
                'char_start': char_start,
                'char_end': char_end
            }
            
            # Add page number information if available
            if page_numbers:
                chunk_data['page_numbers'] = page_numbers
                chunk_data['page_start'] = page_numbers[0]
                chunk_data['page_end'] = page_numbers[-1]
            
            chunks.append(chunk_data)
        
        logger.info(f"Created {len(chunks)} chunks from {doc_metadata['filename']}")
        return chunks
    
    def _get_page_numbers(
        self, 
        char_start: int, 
        char_end: int, 
        page_map: Optional[List[Tuple[int, int, int]]]
    ) -> Optional[List[int]]:
        """
        Determine which page(s) a chunk spans based on character positions.
        
        Args:
            char_start: Starting character position of the chunk
            char_end: Ending character position of the chunk
            page_map: List of (page_num, char_start, char_end) tuples
            
        Returns:
            List of page numbers the chunk spans, or None if no page map available
        """
        if not page_map:
            return None
        
        pages = set()
        for page_num, page_start, page_end in page_map:
            # Check if chunk overlaps with this page
            if not (char_end <= page_start or char_start >= page_end):
                pages.add(page_num)
        
        return sorted(list(pages)) if pages else None


class BM25DocumentIndexer:
    """
    Creates and manages individual BM25 indexes for each document.
    
    Key Features:
    - Converts binary files (PDF, DOCX) to text using MarkItDown
    - Creates separate index for each document (isolated corpus)
    - Uses stemming for better keyword matching
    - Stores metadata for citation and source tracking
    """
    
    def __init__(
        self,
        #doc_path: str,
        #index_base_dir: str,
        chunk_size: int = 1024,
        chunk_overlap: int = 128
    ):
        """
        Initialize the BM25 indexer.
        
        Args:
            doc_path: Path to the document to index
            index_base_dir: Base directory to store individual indexes
            chunk_size: Size of text chunks for indexing
            chunk_overlap: Overlap between chunks
        """
        #self.doc_path = Path(doc_path)
        #self.index_base_dir = Path(index_base_dir)
        #self.index_base_dir.mkdir(parents=True, exist_ok=True)
        
        self.chunker = DocumentChunker(chunk_size, chunk_overlap)
        self.converter = MarkItDown()
        
        # Initialize stemmer for better keyword matching
        self.stemmer = Stemmer.Stemmer("english")
        
        # Supported file extensions
        self.supported_extensions = {
            '.txt', '.md', '.pdf', '.docx', '.doc', 
            '.csv', '.html', '.htm', '.json', '.xml'
        }
    
    def extract_pdf_with_pages(self, file_path: Path) -> Tuple[str, List[Tuple[int, int, int]], int]:
        """
        Extract text from PDF page by page and create a page mapping.
        
        Args:
            file_path: Path to the PDF file
            
        Returns:
            Tuple of (full_text, page_map, total_pages) where:
            - full_text: Combined text from all pages
            - page_map: List of (page_num, char_start, char_end) tuples
            - total_pages: Total number of pages in the PDF
        """
        if not PDF_SUPPORT:
            logger.warning("No PDF library available for page tracking.")
            return "", [], 0
        
        try:
            if PDF_SUPPORT == 'pdfminer':
                # Use pdfminer.six for page-by-page extraction
                full_text = ""
                page_map = []
                page_num = 0
                
                def extract_text_from_element(element):
                    """Recursively extract text from layout elements."""
                    text = ""
                    if isinstance(element, LTTextContainer):
                        text += element.get_text()
                    elif hasattr(element, '__iter__'):
                        for child in element:
                            text += extract_text_from_element(child)
                    return text
                
                for page_layout in extract_pages(str(file_path)):
                    page_num += 1
                    page_text = extract_text_from_element(page_layout)
                    
                    char_start = len(full_text)
                    full_text += page_text
                    char_end = len(full_text)
                    
                    # Add page mapping (page_num, char_start, char_end)
                    page_map.append((page_num, char_start, char_end))
                    
                    # Add separator between pages
                    full_text += "\n\n"
                
                logger.info(f"Extracted {page_num} pages from {file_path.name} with page tracking")
                return full_text, page_map, page_num
                
            elif PDF_SUPPORT == 'PyPDF2':
                reader = PyPDF2.PdfReader(str(file_path))
                full_text = ""
                page_map = []
                total_pages = len(reader.pages)
                
                for page_num, page in enumerate(reader.pages, start=1):
                    page_text = page.extract_text()
                    char_start = len(full_text)
                    full_text += page_text
                    char_end = len(full_text)
                    
                    # Add page mapping (page_num, char_start, char_end)
                    page_map.append((page_num, char_start, char_end))
                    
                    # Add separator between pages
                    full_text += "\n\n"
                
                logger.info(f"Extracted {total_pages} pages from {file_path.name}")
                return full_text, page_map, total_pages
                
            else:  # pypdf
                import pypdf
                reader = pypdf.PdfReader(str(file_path))
                full_text = ""
                page_map = []
                total_pages = len(reader.pages)
                
                for page_num, page in enumerate(reader.pages, start=1):
                    page_text = page.extract_text()
                    char_start = len(full_text)
                    full_text += page_text
                    char_end = len(full_text)
                    
                    # Add page mapping (page_num, char_start, char_end)
                    page_map.append((page_num, char_start, char_end))
                    
                    # Add separator between pages
                    full_text += "\n\n"
                
                logger.info(f"Extracted {total_pages} pages from {file_path.name}")
                return full_text, page_map, total_pages
            
        except Exception as e:
            logger.error(f"Error extracting PDF pages from {file_path.name}: {e}")
            return "", [], 0
    
    def convert_to_text(self, file_path: Path, mime_type: Optional[str] = None) -> Tuple[str, str, Optional[List[Tuple[int, int, int]]], Optional[int]]:
        """
        Convert a file to text using MarkItDown.
        
        Args:
            file_path: Path to the file
            mime_type: Optional MIME type of the file (used when file extension is not available)
            
        Returns:
            Tuple of (text_content, file_type, page_map, total_pages) where:
            - text_content: The extracted text
            - file_type: File extension or MIME type
            - page_map: Optional page mapping for PDFs (list of (page_num, char_start, char_end))
            - total_pages: Optional total page count for PDFs
        """
        file_ext = file_path.suffix.lower()
        
        # Determine if this is a PDF based on extension or MIME type
        is_pdf = (file_ext == '.pdf') or (mime_type and mime_type.lower() == 'application/pdf')
        
        # Determine if this is a text file based on extension or MIME type
        is_text = (file_ext in {'.txt', '.md', '.csv'}) or (
            mime_type and mime_type.lower() in {'text/plain', 'text/markdown', 'text/csv'}
        )
        
        # For text files, read directly
        if is_text:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                return f.read(), file_ext or mime_type, None, None
        
        # For PDFs, try to extract with page information
        if is_pdf and PDF_SUPPORT:
            text_content, page_map, total_pages = self.extract_pdf_with_pages(file_path)
            if text_content:
                return text_content, file_ext or mime_type, page_map, total_pages
        
        # For binary files (or PDF fallback), use MarkItDown
        try:
            result = self.converter.convert(str(file_path))
            text_content = result.text_content if result else ""
            logger.info(f"Converted {file_path.name} to text ({len(text_content)} chars)")
            return text_content, file_ext or mime_type, None, None
        except Exception as e:
            logger.error(f"Error converting {file_path.name}: {e}")
            return "", file_ext or mime_type, None, None
    
    def create_document_index(self, file_path: Path, index_dir: Path, description: str, mime_type: Optional[str] = None) -> Dict[str, Any]:
        """
        Create a BM25 index for a single document.
        
        Args:
            file_path: Path to the document
            index_dir: Directory to store the index
            description: Description of the document
            mime_type: Optional MIME type of the file (used when file extension is not available)
            
        Returns:
            Dictionary with index information
        """
        logger.info(f"Processing document: {file_path.name}")
        
        # Convert to text (with page tracking for PDFs)
        text_content, file_type, page_map, total_pages = self.convert_to_text(file_path, mime_type)
        
        if not text_content:
            logger.warning(f"No content extracted from {file_path.name}")
            return None
        
        # Create metadata
        doc_metadata = {
            'filename': file_path.name,
            'filepath': str(file_path),
            'file_type': file_type,
            'size_bytes': file_path.stat().st_size
        }
        
        # Add page count if available
        if total_pages:
            doc_metadata['total_pages'] = total_pages
        
        # Add description to document metadata - mandatory as positional argument
        doc_metadata['description'] = description
        
        # Chunk the document (with page mapping if available)
        chunks = self.chunker.chunk_text(text_content, doc_metadata, page_map)
        
        if not chunks:
            logger.warning(f"No chunks created from {file_path.name}")
            return None
        
        # Extract text from chunks for indexing
        corpus_texts = [chunk['text'] for chunk in chunks]
        
        # Tokenize the corpus (BM25s requires tokenized input)
        # We'll use simple whitespace tokenization with stemming
        corpus_tokens = bm25s.tokenize(
            corpus_texts,
            stemmer=self.stemmer,
            stopwords="en"  # Remove common English stopwords
        )
        
        # Create BM25 index
        retriever = bm25s.BM25()
        retriever.index(corpus_tokens)
        
        # Save the index
        retriever.save(str(index_dir))
        
        # Save metadata and chunks
        metadata = {
            'document': doc_metadata,
            'chunks': chunks,
            'num_chunks': len(chunks),
            'total_chars': len(text_content),
            'index_dir': str(index_dir)
        }
        
        with open(index_dir / "metadata.json", 'w') as f:
            json.dump(metadata, f, indent=2)
        
        # Save corpus for reference
        with open(index_dir / "corpus.pkl", 'wb') as f:
            pickle.dump(corpus_texts, f)
        
        logger.info(f"Created index for {file_path.name} with {len(chunks)} chunks")
        logger.info(f"Index saved to: {index_dir}")
        
        return metadata

def main():
    """
    Main function to demonstrate document indexing.
    """
    # Configuration
    __DIR__ = os.path.dirname(os.path.abspath(__file__))
    doc_path = os.path.join(__DIR__, "docs/bedrock-ug.pdf")
    index_dir = os.path.join(__DIR__, "indexes/bedrock-ug")
    
    # Create indexer
    indexer = BM25DocumentIndexer(
        #doc_path=doc_path,
        #index_base_dir=index_dir,
        chunk_size=1024,
        chunk_overlap=128
    )
    
    # Index all documents
    # results = indexer.index_all_documents()

    # Index single document
    meta_data = indexer.create_document_index(Path(doc_path), Path(index_dir), description="")

    print("\n" + "="*80)
    print("INDEXING COMPLETE")
    print("="*80)
    print(f"\nTotal chunks indexed: {meta_data['num_chunks']}")
    print(f"Index saved to: {index_dir}")


if __name__ == "__main__":
    main()
