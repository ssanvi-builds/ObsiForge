/**
 * Embedding generator using the same model as Smart Connections (bge-micro-v2).
 * Lazy-loads the model on first use and caches it in memory.
 */

import { pipeline, FeatureExtractionPipeline } from '@xenova/transformers';

let embedder: FeatureExtractionPipeline | null = null;
let loadingPromise: Promise<FeatureExtractionPipeline> | null = null;

const DEFAULT_MODEL = 'TaylorAI/bge-micro-v2';

async function getEmbedder(modelName: string = DEFAULT_MODEL): Promise<FeatureExtractionPipeline> {
  if (embedder) return embedder;
  if (loadingPromise) return loadingPromise;

  loadingPromise = pipeline('feature-extraction', modelName, {
    quantized: true,
  }) as Promise<FeatureExtractionPipeline>;

  try {
    embedder = await loadingPromise;
    return embedder;
  } catch (error) {
    // Reset so a retry can succeed — don't brick the server on transient failures
    loadingPromise = null;
    embedder = null;
    throw error;
  }
}

/**
 * Generate an embedding vector from text.
 * Returns a 384-dimensional vector matching bge-micro-v2's output.
 */
export async function generateEmbedding(text: string, modelName?: string): Promise<number[]> {
  const pipe = await getEmbedder(modelName);

  const output = await pipe(text, {
    pooling: 'mean',
    normalize: true,
  });

  return Array.from(output.data) as number[];
}

/**
 * Preload the embedding model.
 */
export async function preloadModel(modelName?: string): Promise<void> {
  await getEmbedder(modelName);
  console.error('ObsiForge Search: Embedding model preloaded');
}

/**
 * Check if the model is loaded.
 */
export function isModelLoaded(): boolean {
  return embedder !== null;
}