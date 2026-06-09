# Day 06 Lab Guide — eComBot v3 Knowledge Base with ChromaDB

## Metadata
- **Session:** Day 06
- **Focus:** RAG with ChromaDB, embeddings, metadata, chunking, and hallucination guards
- **Project State:** eComBot v3
- **Input State:** eComBot v2 with tools and Redis-based session state already working
- **Target State:** eComBot v3 that answers from a ChromaDB-backed PDF knowledge base using metadata-aware retrieval and graceful fallback
- **Scope:** ChromaDB only; PDF documents only; no OpenSearch
- **Reference Alignment:** This lab follows the Day 06 module mapping and capstone progression for eComBot [file:1][file:3]

## Purpose
In this lab, you will build the retrieval layer for eComBot by indexing PDF content into ChromaDB with useful metadata, then querying that index so the assistant answers only from grounded context. The main learning goal is to understand how chunking and metadata improve retrieval quality, and how to stop the assistant from guessing when the documents do not contain the answer [file:3].

## Starting Point
You should begin from the Day 05 / eComBot v2 foundation, where the repository already contains the basic project structure, tools, and session state support. For this lab, the RAG layer is introduced as the next progression in the capstone build, and the focus stays on ChromaDB-based retrieval only [file:1][file:3].

## Target Outcome
By the end of this lab, eComBot should be able to:
- Ingest PDF documents into ChromaDB.
- Split PDFs into meaningful chunks using a chunking strategy that respects headings and logical sections.
- Attach metadata to every chunk so results can be traced back to a source file, page, section, and document type.
- Retrieve the most relevant chunks for a user query.
- Generate answers only from retrieved context.
- Return a safe fallback when the knowledge base does not support the query [file:3].

## Prerequisites
Before starting, make sure you have:
- A working Python environment.
- The eComBot repository with `src/rag/`, `src/config/`, and `tests/` available.
- ChromaDB installed and ready to use.
- A PDF document that will serve as the knowledge source.
- Basic familiarity with reading PDF text and running Python scripts [file:3].

## What You Will Build
You will build a small PDF retrieval pipeline with these parts:
1. PDF text extraction.
2. Chunking with overlap.
3. Metadata enrichment.
4. ChromaDB indexing.
5. Retrieval and grounded answering.
6. Validation with matching and non-matching queries [file:3].

## Step 1: Inspect the PDF
Open the PDF and identify its structure before writing any chunking logic. Look for title pages, headings, subheadings, FAQs, and page boundaries so you can choose chunk boundaries that preserve meaning. Good chunking should keep related text together instead of splitting an explanation in the middle [file:3].

### Checkpoints
- Can you identify the main sections in the PDF?
- Can you point to which headings should become chunk boundaries?
- Can you explain why random chunking would hurt retrieval quality?

## Step 2: Extract and chunk the text
Extract text from the PDF and split it into chunks. Use overlap between chunks so that important context is not lost when a section spans multiple chunks. The goal is to make retrieval semantic and reliable without making chunks so small that they lose meaning [file:3].

### Chunking guidance
- Prefer section-aware chunking where possible.
- Use overlap to preserve continuity.
- Keep chunks readable and self-contained.
- Avoid splitting short question-and-answer pairs across chunk boundaries [file:3].

### Checkpoints
- Do the chunks preserve complete ideas?
- Does overlap help maintain context?
- Are the chunks manageable for semantic search?

## Step 3: Add metadata
Attach metadata to each chunk before sending it to ChromaDB. Metadata is essential because it helps trace an answer back to the exact source section and improves filtering when multiple documents contain similar language. At minimum, include `source_file`, `document_title`, `section`, `page`, and `doc_type` [file:3].

### Example metadata
```json
{
  "source_file": "ecom_faq.pdf",
  "document_title": "E-Commerce Support FAQ",
  "section": "Returns Policy",
  "page": 5,
  "doc_type": "pdf"
}
```

### Why metadata matters
- It improves traceability.
- It helps distinguish similar chunks.
- It allows filtered retrieval when the knowledge base grows.
- It makes debugging easier when a query returns the wrong result [file:3].

### Checkpoints
- Does every chunk include metadata?
- Can you trace a result back to a page or section?
- Does metadata help separate similar answers?

## Step 4: Store chunks in ChromaDB
Create or reuse a ChromaDB collection and insert the chunk text together with metadata. After indexing, verify that the collection contains the expected documents and that metadata is retrievable with the stored chunks. This is the core retrieval layer that later eComBot features will rely on [file:3].

### Checkpoints
- Are documents inserted successfully?
- Can you retrieve both content and metadata?
- Does the collection size match your expectations?

## Step 5: Query the knowledge base
Run retrieval queries against the indexed PDF content. Start with direct queries that should match clearly, then move to partial matches and broader questions. For eComBot, these should be support and product-knowledge questions, such as order help, product details, warranty language, returns policy, or shipping information [file:3].

### Example query types
- Direct match: “What is the return policy?”
- Partial match: “How long do I have to send something back?”
- Out-of-scope: “What is the weather tomorrow?”

### Checkpoints
- Do strong matches rank near the top?
- Do partial matches still surface relevant chunks?
- Do unrelated questions avoid false matches?

## Step 6: Ground the answer
Use the retrieved chunks as the only source for the assistant’s answer. If the retrieved context supports the question, answer clearly and concisely. If retrieval is weak or the answer is not in the index, the assistant should say it cannot find the information instead of guessing. This is a key RAG safety rule in the course [file:3].

### Fallback example
- “I couldn’t find that information in the current knowledge base.”

### Checkpoints
- Does the assistant avoid fabricated details?
- Does it stay faithful to the retrieved text?
- Does it fall back safely when the answer is missing?

## Step 7: Validate retrieval quality
Test the pipeline using a small set of questions that cover three cases: correct source match, partial source match, and no source match. This mirrors the course requirement to validate grounded retrieval and hallucination prevention. The purpose is not only to get the right answer, but also to know when the system should refuse to answer [file:3].

### Suggested validation set
- 3 questions with clear answers in the PDF.
- 3 questions with only partial wording overlap.
- 3 questions that are not covered by the PDF.

### Checkpoints
- Does the assistant respond correctly when the answer is present?
- Does it stay cautious when the match is weak?
- Does it refuse unsupported questions?

## Stretch Tasks
- Compare two different chunk sizes and see which one retrieves better.
- Add a `category` or `product_line` metadata field.
- Compare retrieval with and without metadata filters.
- Display the source metadata in a simple debug output [file:3].

## Completion Criteria
You can consider the lab complete when:
- PDF content is chunked and indexed in ChromaDB.
- Metadata is stored for every chunk.
- Retrieval returns relevant results for eComBot knowledge questions.
- Answers are grounded in retrieved text.
- Unsupported questions trigger a graceful fallback.
- The workflow matches the eComBot v3 knowledge-base milestone in the course progression [file:3].

## Capstone Relevance
This lab directly supports the capstone knowledge layer. The course outline describes eComBot v3 as the knowledge base milestone, where the assistant must ground answers in a product and FAQ corpus with hallucination prevention. What you build here becomes the retrieval foundation that later modules can reuse inside the larger eComBot system [file:3].
