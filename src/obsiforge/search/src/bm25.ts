/**
 * BM25 keyword search engine.
 *
 * Implements Okapi BM25 for ranking documents by keyword relevance.
 * This is the "keyword half" of hybrid search — it catches exact term
 * matches that embeddings can miss.
 */

export interface BM25Document {
  id: string;
  content: string;
}

export interface BM25Result {
  id: string;
  score: number;
}

// Default BM25 parameters (from Robertson & Walker)
const DEFAULT_K1 = 1.2;
const DEFAULT_B = 0.75;

export class BM25Engine {
  private k1: number;
  private b: number;
  private documents: Map<string, string> = new Map(); // id -> raw content
  private termFreqs: Map<string, Map<string, number>> = new Map(); // id -> term -> count
  private docLengths: Map<string, number> = new Map(); // id -> word count
  private idf: Map<string, number> = new Map(); // term -> IDF value
  private avgDocLength: number = 0;
  private docCount: number = 0;
  private built: boolean = false;

  constructor(k1: number = DEFAULT_K1, b: number = DEFAULT_B) {
    this.k1 = k1;
    this.b = b;
  }

  /**
   * Add a document to the index.
   */
  addDocument(id: string, content: string): void {
    this.documents.set(id, content);
    this.built = false;
  }

  /**
   * Build the index from all added documents.
   * Must be called before search().
   */
  build(): void {
    this.docCount = this.documents.size;
    if (this.docCount === 0) return;

    // Reset index
    this.termFreqs.clear();
    this.docLengths.clear();
    this.idf.clear();

    // Calculate term frequencies and document lengths
    let totalLength = 0;
    const docFrequency: Map<string, number> = new Map(); // term -> number of docs containing it

    for (const [id, content] of this.documents) {
      const terms = this.tokenize(content);
      this.docLengths.set(id, terms.length);
      totalLength += terms.length;

      const freqs = new Map<string, number>();
      for (const term of terms) {
        freqs.set(term, (freqs.get(term) || 0) + 1);
      }
      this.termFreqs.set(id, freqs);

      // Track which documents contain each term
      for (const term of new Set(terms)) {
        docFrequency.set(term, (docFrequency.get(term) || 0) + 1);
      }
    }

    this.avgDocLength = totalLength / this.docCount;

    // Calculate IDF using BM25+ variant: IDF(t) = max(0, ln((N - df + 0.5) / (df + 0.5)) + 1)
    // This ensures non-negative IDF scores even for common terms.
    // Standard BM25 can produce negative IDF when df > N/2, which
    // causes relevant documents to score below 0 and get filtered out.
    for (const [term, df] of docFrequency) {
      const rawIdf = Math.log((this.docCount - df + 0.5) / (df + 0.5));
      this.idf.set(term, Math.max(0, rawIdf + 1));
    }

    this.built = true;
  }

  /**
   * Search for documents matching the query using BM25.
   */
  search(query: string, limit: number = 10): BM25Result[] {
    if (!this.built) {
      throw new Error('Index not built. Call build() before search().');
    }

    const queryTerms = this.tokenize(query);
    if (queryTerms.length === 0) return [];

    const scores: Map<string, number> = new Map();

    for (const [id, freqs] of this.termFreqs) {
      let score = 0;
      const docLength = this.docLengths.get(id) || 0;

      for (const term of queryTerms) {
        const tf = freqs.get(term);
        if (!tf) continue;

        const idf = this.idf.get(term) || 0;
        // BM25 term score: IDF * (tf * (k1 + 1)) / (tf + k1 * (1 - b + b * docLen/avgDocLen))
        const numerator = tf * (this.k1 + 1);
        const denominator = tf + this.k1 * (1 - this.b + this.b * (docLength / this.avgDocLength));
        score += idf * (numerator / denominator);
      }

      if (score > 0) {
        scores.set(id, score);
      }
    }

    return Array.from(scores.entries())
      .map(([id, score]) => ({ id, score }))
      .sort((a, b) => b.score - a.score)
      .slice(0, limit);
  }

  /**
   * Tokenize text for BM25 indexing/search.
   * Lowercases, removes punctuation, splits on whitespace and camelCase.
   */
  private tokenize(text: string): string[] {
    return text
      .toLowerCase()
      .replace(/[^\w\s]/g, ' ')
      .replace(/([a-z])([A-Z])/g, '$1 $2') // camelCase split
      .split(/\s+/)
      .filter(term => term.length > 1); // Skip single-char terms
  }
}