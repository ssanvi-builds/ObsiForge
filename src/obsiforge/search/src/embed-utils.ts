/**
 * Embedding utilities — cosine similarity and nearest neighbor search.
 * Same interface as smart-connections-mcp for backcompat.
 */

export function cosineSimilarity(vecA: number[], vecB: number[]): number {
  if (vecA.length !== vecB.length) {
    throw new Error(`Vector dimension mismatch: ${vecA.length} vs ${vecB.length}`);
  }

  let dotProduct = 0;
  let normA = 0;
  let normB = 0;

  for (let i = 0; i < vecA.length; i++) {
    dotProduct += vecA[i] * vecB[i];
    normA += vecA[i] * vecA[i];
    normB += vecB[i] * vecB[i];
  }

  const magnitude = Math.sqrt(normA) * Math.sqrt(normB);
  if (magnitude === 0) return 0;

  return dotProduct / magnitude;
}

export function findNearestNeighbors(
  queryVec: number[],
  vectors: Array<{ id: string; vec: number[]; metadata?: unknown }>,
  k: number,
  threshold: number = 0.0,
): Array<{ id: string; similarity: number; metadata?: unknown }> {
  const similarities = vectors.map(item => ({
    id: item.id,
    similarity: cosineSimilarity(queryVec, item.vec),
    metadata: item.metadata,
  }));

  return similarities
    .filter(item => item.similarity >= threshold)
    .sort((a, b) => b.similarity - a.similarity)
    .slice(0, k);
}