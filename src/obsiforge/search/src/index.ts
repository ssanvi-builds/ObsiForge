#!/usr/bin/env node

/**
 * ObsiForge Search MCP Server
 *
 * Hybrid search for Obsidian vaults: BM25 + semantic embeddings + RRF fusion.
 * Drops into existing Smart Connections setups — reads the same .smart-env data.
 */

import { Server } from '@modelcontextprotocol/sdk/server/index.js';
import { StdioServerTransport } from '@modelcontextprotocol/sdk/server/stdio.js';
import {
  CallToolRequestSchema,
  ListToolsRequestSchema,
  Tool,
} from '@modelcontextprotocol/sdk/types.js';
import { z } from 'zod';
import { SmartConnectionsLoader } from './loader.js';
import { HybridSearchEngine } from './hybrid-search.js';
import { preloadModel } from './embed-generator.js';

// Environment variable for vault path
const VAULT_PATH = process.env.OBSIFORGE_VAULT_PATH || process.env.SMART_VAULT_PATH;

if (!VAULT_PATH) {
  console.error('Error: OBSIFORGE_VAULT_PATH or SMART_VAULT_PATH environment variable is required');
  process.exit(1);
}

// Initialize loader and search engine
const loader = new SmartConnectionsLoader(VAULT_PATH);
await loader.initialize();

const searchEngine = new HybridSearchEngine(loader);

// Build BM25 index from vault content
await searchEngine.buildBM25Index();

// Preload embedding model in background (don't block startup)
preloadModel().catch(err => {
  console.error('ObsiForge Search: Warning — model preloading failed:', err.message);
  console.error('Model will be loaded on first search query (expect ~5s delay).');
});

console.error(`ObsiForge Search MCP Server initialized`);
console.error(`Vault: ${VAULT_PATH}`);
console.error(`Notes: ${loader.getSources().size}`);
console.error(`BM25 index: built`);
console.error(`Embedding model: loading...`);

// Create MCP server
const server = new Server(
  {
    name: 'obsiforge-search',
    version: '0.1.0',
  },
  {
    capabilities: {
      tools: {},
    },
  }
);

// Tool schemas
const MAX_QUERY_LENGTH = 2000;

const SearchNotesSchema = z.object({
  query: z.string().max(MAX_QUERY_LENGTH).describe('Search query text'),
  limit: z.number().int().positive().default(10).describe('Maximum number of results'),
  threshold: z.number().min(0).max(1).default(0.3).describe('Minimum similarity threshold (0-1)'),
});

const HybridSearchSchema = z.object({
  query: z.string().max(MAX_QUERY_LENGTH).describe('Search query text'),
  limit: z.number().int().positive().default(10).describe('Maximum number of results'),
  semantic_weight: z.number().min(0).max(1).default(0.7).describe('Weight for semantic results (0-1)'),
  keyword_weight: z.number().min(0).max(1).default(0.3).describe('Weight for keyword results (0-1)'),
});

const KeywordSearchSchema = z.object({
  query: z.string().max(MAX_QUERY_LENGTH).describe('Keyword search query'),
  limit: z.number().int().positive().default(10).describe('Maximum number of results'),
});

const GetSimilarNotesSchema = z.object({
  note_path: z.string().describe('Path to the note'),
  threshold: z.number().min(0).max(1).default(0.5).describe('Similarity threshold (0-1)'),
  limit: z.number().int().positive().default(10).describe('Maximum number of results'),
});

const GetStatsSchema = z.object({});

// Tool definitions
const tools: Tool[] = [
  {
    name: 'search',
    description: 'Hybrid search combining semantic embeddings and BM25 keyword matching with Reciprocal Rank Fusion. This is the DEFAULT search method — always prefer this over keyword-only or semantic-only search. Returns results ranked by combined relevance.',
    inputSchema: {
      type: 'object',
      properties: {
        query: { type: 'string', description: 'Search query text' },
        limit: { type: 'number', description: 'Maximum number of results (default 10)', minimum: 1, default: 10 },
        semantic_weight: { type: 'number', description: 'Weight for semantic results (0-1, default 0.7)', minimum: 0, maximum: 1, default: 0.7 },
        keyword_weight: { type: 'number', description: 'Weight for keyword results (0-1, default 0.3)', minimum: 0, maximum: 1, default: 0.3 },
      },
      required: ['query'],
    },
  },
  {
    name: 'search_notes',
    description: 'Semantic-only search using embeddings. Use when you need pure conceptual similarity without keyword boosting. For general search, prefer the "search" tool instead.',
    inputSchema: {
      type: 'object',
      properties: {
        query: { type: 'string', description: 'Search query text' },
        limit: { type: 'number', description: 'Maximum number of results (default 10)', minimum: 1, default: 10 },
        threshold: { type: 'number', description: 'Similarity threshold (0-1, default 0.3)', minimum: 0, maximum: 1, default: 0.3 },
      },
      required: ['query'],
    },
  },
  {
    name: 'keyword_search',
    description: 'BM25 keyword-only search. Use when you need exact term matching (file names, code identifiers, specific phrases).',
    inputSchema: {
      type: 'object',
      properties: {
        query: { type: 'string', description: 'Keyword search query' },
        limit: { type: 'number', description: 'Maximum number of results (default 10)', minimum: 1, default: 10 },
      },
      required: ['query'],
    },
  },
  {
    name: 'get_similar_notes',
    description: 'Find notes semantically similar to a given note using embeddings.',
    inputSchema: {
      type: 'object',
      properties: {
        note_path: { type: 'string', description: 'Path to the note' },
        threshold: { type: 'number', description: 'Similarity threshold (0-1, default 0.5)', minimum: 0, maximum: 1, default: 0.5 },
        limit: { type: 'number', description: 'Maximum number of results (default 10)', minimum: 1, default: 10 },
      },
      required: ['note_path'],
    },
  },
  {
    name: 'get_stats',
    description: 'Get statistics about the search index (notes, blocks, embedding model, BM25 status).',
    inputSchema: {
      type: 'object',
      properties: {},
    },
  },
];

// Handle tool list requests
server.setRequestHandler(ListToolsRequestSchema, async () => {
  return { tools };
});

// Handle tool execution requests
server.setRequestHandler(CallToolRequestSchema, async (request) => {
  const { name, arguments: args } = request.params;

  try {
    switch (name) {
      case 'search': {
        const { query, limit, semantic_weight, keyword_weight } = HybridSearchSchema.parse(args);
        const results = await searchEngine.hybridSearch(query, limit, semantic_weight, keyword_weight);
        return {
          content: [{ type: 'text', text: JSON.stringify(results, null, 2) }],
        };
      }

      case 'search_notes': {
        const { query, limit, threshold } = SearchNotesSchema.parse(args);
        const results = await searchEngine.semanticSearch(query, limit, threshold);
        return {
          content: [{ type: 'text', text: JSON.stringify(results, null, 2) }],
        };
      }

      case 'keyword_search': {
        const { query, limit } = KeywordSearchSchema.parse(args);
        const results = searchEngine.keywordSearch(query, limit);
        return {
          content: [{ type: 'text', text: JSON.stringify(results, null, 2) }],
        };
      }

      case 'get_similar_notes': {
        const { note_path, threshold, limit } = GetSimilarNotesSchema.parse(args);
        const results = searchEngine.getSimilarNotes(note_path, threshold, limit);
        return {
          content: [{ type: 'text', text: JSON.stringify(results, null, 2) }],
        };
      }

      case 'get_stats': {
        GetStatsSchema.parse(args);
        const stats = searchEngine.getStats();
        return {
          content: [{ type: 'text', text: JSON.stringify(stats, null, 2) }],
        };
      }

      default:
        throw new Error(`Unknown tool: ${name}`);
    }
  } catch (error) {
    let errorMessage = error instanceof Error ? error.message : String(error);
    // Sanitize filesystem paths from error messages to avoid leaking server paths
    const pathPattern = /\/[^\s"']+(?:\/[^\s"']+)*/g;
    errorMessage = errorMessage.replace(pathPattern, (match) => {
      const basename = match.split('/').pop() || '';
      return `<path>/${basename}`;
    });
    return {
      content: [{ type: 'text', text: JSON.stringify({ error: errorMessage }, null, 2) }],
      isError: true,
    };
  }
});

// Start the server
const transport = new StdioServerTransport();
await server.connect(transport);
console.error('ObsiForge Search MCP Server running on stdio');