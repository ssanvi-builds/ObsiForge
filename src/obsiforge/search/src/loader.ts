/**
 * Loader for Smart Connections data from .smart-env directory.
 * Reads the same format as the original smart-connections-mcp.
 */

import * as fs from 'fs';
import * as path from 'path';
import type { SmartSource, SmartEnvConfig } from './types.js';

export class SmartConnectionsLoader {
  private vaultPath: string;
  private smartEnvPath: string;
  private config: SmartEnvConfig | null = null;
  private sources: Map<string, SmartSource> = new Map();
  private noteContentCache: Map<string, string> = new Map();

  constructor(vaultPath: string) {
    this.vaultPath = vaultPath;
    this.smartEnvPath = path.join(vaultPath, '.smart-env');
  }

  async initialize(): Promise<void> {
    if (!fs.existsSync(this.smartEnvPath)) {
      throw new Error(`Smart Connections directory not found at: ${this.smartEnvPath}`);
    }

    await this.loadConfig();
    await this.loadSources();
  }

  private async loadConfig(): Promise<void> {
    const configPath = path.join(this.smartEnvPath, 'smart_env.json');
    if (!fs.existsSync(configPath)) {
      throw new Error(`Configuration file not found at: ${configPath}`);
    }
    this.config = JSON.parse(fs.readFileSync(configPath, 'utf-8'));
  }

  private async loadSources(): Promise<void> {
    const multiPath = path.join(this.smartEnvPath, 'multi');
    if (!fs.existsSync(multiPath)) {
      throw new Error(`Multi directory not found at: ${multiPath}`);
    }

    const files = fs.readdirSync(multiPath).filter(f => f.endsWith('.ajson'));
    console.error(`ObsiForge Search: Loading ${files.length} source files...`);

    for (const file of files) {
      try {
        const content = fs.readFileSync(path.join(multiPath, file), 'utf-8');
        const lines = content.trim().split('\n');

        for (const line of lines) {
          if (!line.trim()) continue;
          try {
            const cleanedLine = line.replace(/,\s*$/, '');
            const obj = JSON.parse(`{${cleanedLine}}`);

            for (const key of Object.keys(obj)) {
              if (key.startsWith('smart_sources:')) {
                const sourceData: SmartSource = obj[key];
                if (sourceData?.path) {
                  this.sources.set(sourceData.path, sourceData);
                }
              }
            }
          } catch (parseErr) {
            console.error(`ObsiForge Search: Skipping unparseable line in ${file}:`, (parseErr as Error).message);
          }
        }
      } catch (error) {
        console.error(`Error loading ${file}:`, error);
      }
    }

    console.error(`ObsiForge Search: Loaded ${this.sources.size} notes`);
  }

  getSources(): Map<string, SmartSource> {
    return this.sources;
  }

  getSource(notePath: string): SmartSource | undefined {
    return this.sources.get(notePath);
  }

  getConfig(): SmartEnvConfig | null {
    return this.config;
  }

  getEmbeddingModelKey(): string {
    if (!this.config) {
      throw new Error('Configuration not loaded');
    }

    const embedModel = this.config.smart_sources.embed_model;
    const adapter = embedModel.adapter;

    if (adapter && adapter in embedModel && typeof (embedModel as Record<string, unknown>)[adapter] === 'object') {
      const adapterConfig = (embedModel as Record<string, unknown>)[adapter] as Record<string, unknown> | undefined;
      if (adapterConfig && 'model_key' in adapterConfig && typeof adapterConfig.model_key === 'string') {
        return adapterConfig.model_key;
      }
    }

    const modelKeys = Object.keys(embedModel).filter(k => k !== 'adapter' && typeof embedModel[k as keyof typeof embedModel] === 'object');
    if (modelKeys.length === 0) {
      throw new Error('No embedding model found in configuration');
    }
    return modelKeys[0];
  }

  getVaultPath(): string {
    return this.vaultPath;
  }

  readNoteContent(notePath: string): string {
    if (this.noteContentCache.has(notePath)) {
      return this.noteContentCache.get(notePath)!;
    }

    // Validate path stays within vault to prevent path traversal
    const fullPath = path.resolve(this.vaultPath, notePath);
    if (!fullPath.startsWith(path.resolve(this.vaultPath))) {
      throw new Error(`Path traversal detected: ${notePath}`);
    }
    if (!fs.existsSync(fullPath)) {
      throw new Error(`Note not found at: ${fullPath}`);
    }

    const content = fs.readFileSync(fullPath, 'utf-8');
    // Cache small files only (under 100KB) with max 500 entries
    if (content.length < 100_000) {
      if (this.noteContentCache.size >= 500) {
        // Evict oldest entry to prevent unbounded memory growth
        const firstKey = this.noteContentCache.keys().next().value;
        if (firstKey !== undefined) this.noteContentCache.delete(firstKey);
      }
      this.noteContentCache.set(notePath, content);
    }
    return content;
  }

  /**
   * Get all note paths with their content for keyword indexing.
   */
  getAllNotePaths(): string[] {
    return Array.from(this.sources.keys());
  }

  /**
   * Get note content for a path, with graceful fallback.
   */
  getNoteContentSafe(notePath: string): string {
    try {
      return this.readNoteContent(notePath);
    } catch (err) {
      console.error(`ObsiForge Search: Error reading ${notePath}:`, (err as Error).message);
      return '';
    }
  }
}