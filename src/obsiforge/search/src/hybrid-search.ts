/**
 * Hybrid search engine combining BM25 keyword search + semantic embeddings
 * with Reciprocal Rank Fusion (RRF) for result merging.
 *
 * This is the core differentiator of ObsiForge Search.
 */

import type { SmartSource, SearchResult, HybridSearchResult } from './types.js';
import type { SmartConnectionsLoader } from './loader.js';
import { BM25Engine } from './bm25.js';
import { cosineSimilarity } from './embed-utils.js';
import { generateEmbedding } from './embed-generator.js';

const DEFAULT_K_RRF = 60; // RRF constant (standard value from literature)
const DEFAULT_SEMANTIC_WEIGHT = 0.7; // Weight for semantic results in hybrid
const DEFAULT_KEYWORD_WEIGHT = 0.3; // Weight for keyword results in hybrid

export class HybridSearchEngine {
  private loader: SmartConnectionsLoader;
  private embeddingModelKey: string;
  private bm25: BM25Engine;
  private bm25Built: boolean = false;

  constructor(loader: SmartConnectionsLoader) {
    this.loader = loader;
    this.embeddingModelKey = loader.getEmbeddingModelKey();
    this.bm25 = new BM25Engine();
  }

  /**
   * Initialize the BM25 index from all loaded sources.
   * Must be called before hybrid search.
   */
  async buildBM25Index(): Promise<void> {
    const sources = this.loader.getSources();

    for (const [notePath, source] of sources) {
      const content = this.loader.getNoteContentSafe(notePath);
      if (content) {
        this.bm25.addDocument(notePath, content);
      }
    }

    this.bm25.build();
    this.bm25Built = true;
    console.error(`ObsiForge Search: BM25 index built with ${sources.size} documents`);
  }

  /**
   * Pure semantic search using embeddings.
   * Generates an embedding for the query and finds nearest neighbors by cosine similarity.
   */
  async semanticSearch(
    query: string,
    limit: number = 10,
    threshold: number = 0.3,
  ): Promise<SearchResult[]> {
    const queryVec = await generateEmbedding(query, this.embeddingModelKey);
    const sources = this.loader.getSources();

    const results: SearchResult[] = [];
    for (const [notePath, source] of sources) {
      const emb = source.embeddings[this.embeddingModelKey];
      if (!emb?.vec) continue;

      const similarity = cosineSimilarity(queryVec, emb.vec);
      if (similarity >= threshold) {
        results.push({
          path: notePath,
          similarity,
          blocks: Object.keys(source.blocks || {}),
        });
      }
    }

    return results
      .sort((a, b) => b.similarity - a.similarity)
      .slice(0, limit);
  }

  /**
   * Pure keyword search using BM25.
   */
  keywordSearch(query: string, limit: number = 10): SearchResult[] {
    if (!this.bm25Built) {
      throw new Error('BM25 index not built. Call buildBM25Index() first.');
    }

    const bm25Results = this.bm25.search(query, limit);

    return bm25Results.map(result => ({
      path: result.id,
      similarity: 0, // BM25 scores are not comparable to cosine similarity
      bm25_score: result.score,
      blocks: this.getBlockHeadings(result.id),
    }));
  }

  /**
   * Hybrid search combining BM25 + semantic search with Reciprocal Rank Fusion.
   *
   * RRF formula: score = 1/(k + rank_i)
   * where k is a constant (default 60) and rank_i is the position in result list i.
   *
   * This gives better results than either method alone because:
   * - BM25 catches exact keyword matches that embeddings miss
   * - Embeddings catch conceptual matches that keywords miss
   * - RRF merges them without needing score normalization
   */
  async hybridSearch(
    query: string,
    limit: number = 10,
    semanticWeight: number = DEFAULT_SEMANTIC_WEIGHT,
    keywordWeight: number = DEFAULT_KEYWORD_WEIGHT,
    kRRF: number = DEFAULT_K_RRF,
    semanticThreshold: number = 0.2,
  ): Promise<HybridSearchResult[]> {
    // Run both searches in parallel
    const [semanticResults, keywordResults] = await Promise.all([
      this.semanticSearch(query, limit * 3, semanticThreshold).catch(() => []),
      Promise.resolve(this.bm25Built ? this.keywordSearch(query, limit * 3) : []),
    ]);

    // Build rank maps and similarity lookup
    const semanticRanks = new Map<string, number>();
    const semanticSimilarity = new Map<string, number>();

    semanticResults.forEach((result, index) => {
      semanticRanks.set(result.path, index + 1);
      semanticSimilarity.set(result.path, result.similarity);
    });

    const keywordRanks = new Map<string, number>();

    keywordResults.forEach((result, index) => {
      keywordRanks.set(result.path, index + 1);
    });

    // Collect all unique document IDs
    const allIds = new Set([...semanticRanks.keys(), ...keywordRanks.keys()]);

    // Calculate RRF scores
    const rrfScores: Map<string, HybridSearchResult> = new Map();

    for (const id of allIds) {
      const semRank = semanticRanks.get(id);
      const kwRank = keywordRanks.get(id);

      let rrfScore = 0;
      let simScore = 0;

      // Semantic contribution
      if (semRank !== undefined) {
        rrfScore += semanticWeight / (kRRF + semRank);
        simScore = semanticSimilarity.get(id) || 0;
      }

      // Keyword contribution
      if (kwRank !== undefined) {
        rrfScore += keywordWeight / (kRRF + kwRank);
      }

      const source = this.loader.getSource(id);
      rrfScores.set(id, {
        path: id,
        similarity: simScore,
        semantic_rank: semRank || 0,
        keyword_rank: kwRank || 0,
        rrf_score: rrfScore,
        blocks: source ? Object.keys(source.blocks || {}) : [],
        snippet: this.getSnippet(id, query),
      });
    }

    return Array.from(rrfScores.values())
      .sort((a, b) => b.rrf_score - a.rrf_score)
      .slice(0, limit);
  }

  /**
   * Get similar notes to a given note path.
   * Uses pure semantic search (same as smart-connections-mcp for backcompat).
   */
  getSimilarNotes(
    notePath: string,
    threshold: number = 0.5,
    limit: number = 10,
  ): SearchResult[] {
    const source = this.loader.getSource(notePath);
    if (!source) {
      throw new Error(`Note not found: ${notePath}`);
    }

    const embeddings = source.embeddings[this.embeddingModelKey];
    if (!embeddings?.vec) {
      throw new Error(`No embeddings found for note: ${notePath}`);
    }

    const sources = this.loader.getSources();
    const results: SearchResult[] = [];

    for (const [path, src] of sources) {
      if (path === notePath) continue;
      const emb = src.embeddings[this.embeddingModelKey];
      if (!emb?.vec) continue;

      const similarity = cosineSimilarity(embeddings.vec, emb.vec);
      if (similarity >= threshold) {
        results.push({
          path,
          similarity,
          blocks: Object.keys(src.blocks || {}),
        });
      }
    }

    return results
      .sort((a, b) => b.similarity - a.similarity)
      .slice(0, limit);
  }

  /**
   * Get a text snippet around the first match of query terms.
   */
  private getSnippet(notePath: string, query: string, maxLen: number = 150): string {
    const content = this.loader.getNoteContentSafe(notePath);
    if (!content) return '';

    const lowerContent = content.toLowerCase();
    const lowerQuery = query.toLowerCase();
    const terms = lowerQuery.split(/\s+/).filter(t => t.length > 1);

    for (const term of terms) {
      const idx = lowerContent.indexOf(term);
      if (idx !== -1) {
        // Use [...string] slicing to avoid splitting multi-byte characters
        const chars = [...content];
        const lowerChars = [...lowerContent];
        const charIdx = lowerChars.slice(0, idx).join('').length;
        const start = Math.max(0, charIdx - 50);
        const end = Math.min(chars.length, charIdx + [...term].length + 100);
        let snippet = chars.slice(start, end).join('').replace(/\n/g, ' ');
        if (start > 0) snippet = '...' + snippet;
        if (end < chars.length) snippet = snippet + '...';
        return snippet.slice(0, maxLen);
      }
    }

    return [...content].slice(0, maxLen).join('').replace(/\n/g, ' ') + '...';
  }

  /**
   * Get block headings for a note path.
   */
  private getBlockHeadings(notePath: string): string[] {
    const source = this.loader.getSource(notePath);
    return source ? Object.keys(source.blocks || {}) : [];
  }

  /**
   * Get stats about the search index.
   */
  getStats(): {
    totalNotes: number;
    totalBlocks: number;
    embeddingDimension: number;
    modelKey: string;
    bm25Indexed: boolean;
    bm25DocCount: number;
  } {
    const sources = this.loader.getSources();
    let totalBlocks = 0;
    let embeddingDim = 0;

    for (const source of sources.values()) {
      totalBlocks += Object.keys(source.blocks || {}).length;
      if (embeddingDim === 0) {
        const emb = source.embeddings[this.embeddingModelKey];
        if (emb?.vec) {
          embeddingDim = emb.vec.length;
        }
      }
    }

    return {
      totalNotes: sources.size,
      totalBlocks,
      embeddingDimension: embeddingDim,
      modelKey: this.embeddingModelKey,
      bm25Indexed: this.bm25Built,
      bm25DocCount: this.bm25Built ? sources.size : 0,
    };
  }
}