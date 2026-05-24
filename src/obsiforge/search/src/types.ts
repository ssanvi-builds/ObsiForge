/**
 * Type definitions for ObsiForge Search MCP Server
 */

export interface SmartSource {
  path: string;
  embeddings: {
    [modelKey: string]: {
      vec: number[];
      last_embed: {
        hash: string;
        tokens: number;
      };
    };
  };
  last_read: {
    hash: string;
    at: number;
  };
  class_name: string;
  last_import: {
    mtime: number;
    size: number;
    at: number;
    hash: string;
  };
  blocks: {
    [heading: string]: [number, number]; // [start_line, end_line]
  };
}

export interface SmartEnvConfig {
  is_obsidian_vault: boolean;
  smart_blocks: {
    embed_blocks: boolean;
    min_chars: number;
  };
  smart_sources: {
    single_file_data_path: string;
    min_chars: number;
    embed_model: {
      adapter: string;
      [key: string]: unknown;
    };
    excluded_headings: string;
    file_exclusions: string;
    folder_exclusions: string;
  };
  smart_chat_threads?: {
    chat_model: {
      adapter: string;
      [key: string]: unknown;
    };
    active_thread_key?: string;
  };
}

export interface SearchResult {
  path: string;
  similarity: number;
  bm25_score?: number;
  rrf_score?: number;
  blocks?: string[];
  snippet?: string;
}

export interface HybridSearchResult extends SearchResult {
  semantic_rank: number;
  keyword_rank: number;
  rrf_score: number;
}

export interface SearchStats {
  totalNotes: number;
  totalBlocks: number;
  embeddingDimension: number;
  modelKey: string;
  indexedAt: number;
  vaultPath: string;
}