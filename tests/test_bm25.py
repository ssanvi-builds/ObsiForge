"""Tests for the ObsiForge Search MCP server — BM25 engine."""

import json
import subprocess
import sys
from pathlib import Path

# BM25 is pure TypeScript, so we test the compiled JS directly
SEARCH_DIR = Path(__file__).parent.parent / "src" / "obsiforge" / "search"
DIST_DIR = SEARCH_DIR / "dist"


def test_bm25_basic():
    """BM25 should rank documents by keyword relevance."""
    # Import compiled JS via subprocess
    test_script = f"""
    const {{ BM25Engine }} = require('{DIST_DIR}/bm25.js');
    const engine = new BM25Engine();

    engine.addDocument('note1.md', 'Python testing with pytest and unittest');
    engine.addDocument('note2.md', 'JavaScript testing with jest and mocha');
    engine.addDocument('note3.md', 'Python web development with fastapi');
    engine.addDocument('note4.md', 'Cooking recipes for dinner');
    engine.build();

    const results = engine.search('Python testing', 3);
    const paths = results.map(r => r.id);

    // Python testing should be top result
    if (paths[0] !== 'note1.md') {{
        console.error('Expected note1.md as top result, got:', paths[0]);
        process.exit(1);
    }}

    // Cooking should not appear
    if (paths.includes('note4.md')) {{
        console.error('Cooking doc should not match Python testing');
        process.exit(1);
    }}

    console.log(JSON.stringify({{ok: true, results: paths}}));
    """

    result = subprocess.run(
        ["node", "-e", test_script],
        capture_output=True,
        text=True,
        timeout=30,
    )

    assert result.returncode == 0, f"BM25 test failed: {result.stderr}"
    data = json.loads(result.stdout.strip())
    assert data["ok"], "BM25 test did not return ok"
    assert "note1.md" in data["results"], "note1.md should be in results"


def test_bm25_empty_query():
    """BM25 should return empty results for empty query."""
    test_script = f"""
    const {{ BM25Engine }} = require('{DIST_DIR}/bm25.js');
    const engine = new BM25Engine();
    engine.addDocument('note1.md', 'some content');
    engine.build();
    const results = engine.search('', 10);
    console.log(JSON.stringify({{ok: true, count: results.length}}));
    """

    result = subprocess.run(
        ["node", "-e", test_script],
        capture_output=True,
        text=True,
        timeout=30,
    )

    assert result.returncode == 0, f"Empty query test failed: {result.stderr}"
    data = json.loads(result.stdout.strip())
    assert data["count"] == 0, "Empty query should return 0 results"


def test_bm25_camel_case():
    """BM25 should split camelCase terms for better matching."""
    test_script = f"""
    const {{ BM25Engine }} = require('{DIST_DIR}/bm25.js');
    const engine = new BM25Engine();
    engine.addDocument('note1.md', 'The FastAPI framework for Python');
    engine.addDocument('note2.md', 'Regular API design patterns');
    engine.build();
    const results = engine.search('fastapi', 2);
    console.log(JSON.stringify({{ok: true, paths: results.map(r => r.id)}}));
    """

    result = subprocess.run(
        ["node", "-e", test_script],
        capture_output=True,
        text=True,
        timeout=30,
    )

    assert result.returncode == 0, f"CamelCase test failed: {result.stderr}"
    data = json.loads(result.stdout.strip())
    assert data["ok"], "CamelCase test did not return ok"
    assert "note1.md" in data["paths"], "CamelCase split should match note1.md"


def test_cosine_similarity():
    """Cosine similarity should return 1 for identical vectors."""
    test_script = f"""
    const {{ cosineSimilarity }} = require('{DIST_DIR}/embed-utils.js');
    const a = [1, 0, 0];
    const b = [1, 0, 0];
    const sim = cosineSimilarity(a, b);
    console.log(JSON.stringify({{ok: Math.abs(sim - 1.0) < 0.001, similarity: sim}}));
    """

    result = subprocess.run(
        ["node", "-e", test_script],
        capture_output=True,
        text=True,
        timeout=30,
    )

    assert result.returncode == 0, f"Cosine similarity test failed: {result.stderr}"
    data = json.loads(result.stdout.strip())
    assert data["ok"], f"Identical vectors should have similarity ~1.0, got {data['similarity']}"


def test_cosine_similarity_orthogonal():
    """Orthogonal vectors should have similarity 0."""
    test_script = f"""
    const {{ cosineSimilarity }} = require('{DIST_DIR}/embed-utils.js');
    const a = [1, 0, 0];
    const b = [0, 1, 0];
    const sim = cosineSimilarity(a, b);
    console.log(JSON.stringify({{ok: Math.abs(sim) < 0.001, similarity: sim}}));
    """

    result = subprocess.run(
        ["node", "-e", test_script],
        capture_output=True,
        text=True,
        timeout=30,
    )

    assert result.returncode == 0, f"Orthogonal test failed: {result.stderr}"
    data = json.loads(result.stdout.strip())
    assert data["ok"], f"Orthogonal vectors should have similarity ~0.0, got {data['similarity']}"


if __name__ == "__main__":
    test_bm25_basic()
    test_bm25_empty_query()
    test_bm25_camel_case()
    test_cosine_similarity()
    test_cosine_similarity_orthogonal()
    print("All BM25 tests passed!")