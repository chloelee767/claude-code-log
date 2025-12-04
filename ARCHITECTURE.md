# Claude Code Log - Architecture Documentation

## Table of Contents

1. [Overview](#overview)
2. [High-Level Architecture](#high-level-architecture)
3. [Data Flow](#data-flow)
4. [File System Structure](#file-system-structure)
5. [Core Components](#core-components)
6. [Cache System](#cache-system)
7. [Processing Modes](#processing-modes)
8. [Workflow Examples](#workflow-examples)

## Overview

Claude Code Log is a Python CLI tool that converts Claude Code transcript files (JSONL format) into readable, interactive HTML pages. It features a sophisticated caching system, support for multiple projects, and an interactive TUI for browsing sessions.

### Key Design Principles

- **Cache-First Architecture**: Minimize redundant parsing by caching processed data
- **Incremental Processing**: Only reprocess files that have changed
- **Hierarchical Structure**: Support for project → sessions → messages
- **Lazy HTML Generation**: Only regenerate HTML when source data changes

## High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                           CLI Entry Point                        │
│                          (cli.py: main)                          │
└───────────────────────┬─────────────────────────────────────────┘
                        │
                        ├──► TUI Mode (--tui)
                        │    └──► Interactive session browser
                        │
                        ├──► Single File Mode
                        │    └──► Direct JSONL → HTML conversion
                        │
                        ├──► Directory Mode
                        │    └──► Combine multiple JSONL files
                        │
                        └──► All Projects Mode (--all-projects)
                             └──► Process entire ~/.claude/projects/

┌─────────────────────────────────────────────────────────────────┐
│                         Core Pipeline                            │
└─────────────────────────────────────────────────────────────────┘

Input (JSONL)  →  Parser  →  Cache  →  Converter  →  Renderer  →  Output (HTML)
                     ↓         ↕          ↓            ↓
                  Models   CacheManager  Sessions   Templates
```

## Data Flow

### 1. Input Phase

**Input Files**: Claude Code transcript files in JSONL format
- Location: `~/.claude/projects/<project-name>/*.jsonl`
- Format: One JSON object per line
- Types: User messages, assistant messages, summaries, system messages, tool use/results

**Agent Files**: Sub-agent transcripts referenced by main sessions
- Location: `~/.claude/projects/<project-name>/agent-<agent-id>.jsonl`
- Loaded recursively when referenced by main transcript

### 2. Processing Phase

```
┌──────────────────────────────────────────────────────────┐
│                    Processing Flow                        │
└──────────────────────────────────────────────────────────┘

1. Cache Check
   ├─ Check if cache exists and is valid
   ├─ Compare file modification times
   └─ Validate cache version compatibility

2. Parse JSONL (if cache miss or invalid)
   ├─ Read line-by-line from JSONL files
   ├─ Validate JSON structure
   ├─ Parse into Pydantic models (type-safe)
   ├─ Load agent files recursively
   └─ Sort messages chronologically

3. Cache Update
   ├─ Save parsed entries grouped by timestamp
   ├─ Update file modification time tracking
   ├─ Calculate session metadata
   ├─ Aggregate project statistics
   └─ Extract working directories

4. HTML Generation
   ├─ Check if HTML is outdated
   ├─ Deduplicate messages
   ├─ Process session summaries
   ├─ Render using Jinja2 templates
   ├─ Apply syntax highlighting
   └─ Write output files
```

### 3. Output Phase

**Output Files** (generated on-demand):
- `combined_transcripts.html` - All sessions in project
- `session-<session-id>.html` - Individual session pages
- `index.html` - Project index (for --all-projects mode)

## File System Structure

### Input Directory Structure

```
~/.claude/projects/
├── -path-to-project1/           # Project directory (path encoded)
│   ├── session1.jsonl            # Main session transcript
│   ├── session2.jsonl            # Another session
│   ├── agent-abc123.jsonl        # Sub-agent transcript
│   └── agent-def456.jsonl        # Another sub-agent
│
└── -path-to-project2/
    ├── session3.jsonl
    └── ...
```

### Cache Directory Structure

```
~/.claude/projects/-path-to-project/cache/
├── index.json                    # Project cache index
├── session1.json                 # Cached parsed data for session1.jsonl
├── session2.json                 # Cached parsed data for session2.jsonl
├── agent-abc123.json             # Cached sub-agent data
└── ...
```

### Output Directory Structure

```
~/.claude/projects/
├── index.html                           # Master project index
│
├── -path-to-project1/
│   ├── combined_transcripts.html        # All sessions
│   ├── session-<id1>.html               # Individual session
│   ├── session-<id2>.html               # Individual session
│   └── cache/                           # Cache directory
│       ├── index.json
│       └── *.json
│
└── -path-to-project2/
    └── ...
```

## Core Components

### 1. CLI (`cli.py`)

**Purpose**: Command-line interface and entry point

**Key Functions**:
- `main()` - Primary entry point with Click argument parsing
- `_launch_tui_with_cache_check()` - TUI mode with cache validation
- `find_projects_by_cwd()` - Smart project discovery based on current directory
- `convert_project_path_to_claude_dir()` - Path conversion to Claude's naming scheme

**Responsibilities**:
- Parse command-line arguments
- Determine processing mode (single file, directory, all projects, TUI)
- Handle cache/HTML clearing operations
- Launch TUI or conversion pipeline
- Project path conversion and discovery

### 2. Models (`models.py`)

**Purpose**: Type-safe data structures using Pydantic

**Key Models**:
- `TranscriptEntry` - Union type for all message types
- `UserTranscriptEntry` - User messages with tool results
- `AssistantTranscriptEntry` - Assistant responses with usage data
- `SummaryTranscriptEntry` - Session summaries (async generated)
- `ContentItem` - Union of text, tool use, tool result, thinking, image
- `UsageInfo` - Token consumption tracking

**Design**:
- Compatible with Anthropic's official types
- Strict validation during parsing
- Type-safe access throughout codebase

### 3. Parser (`parser.py`)

**Purpose**: Read and parse JSONL transcript files

**Key Functions**:
- `load_transcript()` - Parse single JSONL file with cache support
- `load_directory_transcripts()` - Combine multiple JSONL files
- `filter_messages_by_date()` - Apply date range filtering
- `extract_text_content()` - Extract readable text from content structures

**Features**:
- Line-by-line JSONL parsing with error recovery
- Recursive agent file loading (prevents infinite loops)
- Agent message insertion at point of use
- Chronological sorting across all files
- Cache-aware loading (skip parsing if cached)

**Agent File Handling**:
```
1. Parse main transcript
2. Collect agentId references
3. Load agent-<agentId>.jsonl files
4. Insert agent messages after referencing message
5. Handle nested agents recursively
```

### 4. Cache System (`cache.py`)

**Purpose**: Performance optimization through intelligent caching

**Key Classes**:
- `CacheManager` - Main cache operations
- `ProjectCache` - Top-level cache index
- `SessionCacheData` - Per-session metadata
- `CachedFileInfo` - File tracking information

**Cache Structure**:

```json
{
  "version": "0.4.0",
  "cache_created": "2025-12-04T10:00:00",
  "last_updated": "2025-12-04T10:30:00",
  "project_path": "/home/user/.claude/projects/-path-to-project",

  "cached_files": {
    "session1.jsonl": {
      "file_path": "/path/to/session1.jsonl",
      "source_mtime": 1733310000.0,
      "cached_mtime": 1733310100.0,
      "message_count": 150,
      "session_ids": ["abc123"]
    }
  },

  "sessions": {
    "abc123": {
      "session_id": "abc123",
      "summary": "Implement feature X",
      "first_timestamp": "2025-12-04T09:00:00Z",
      "last_timestamp": "2025-12-04T09:45:00Z",
      "message_count": 150,
      "first_user_message": "Can you help me...",
      "cwd": "/home/user/project",
      "total_input_tokens": 50000,
      "total_output_tokens": 10000
    }
  },

  "total_message_count": 150,
  "total_input_tokens": 50000,
  "total_output_tokens": 10000,
  "working_directories": ["/home/user/project"],
  "earliest_timestamp": "2025-12-04T09:00:00Z",
  "latest_timestamp": "2025-12-04T09:45:00Z"
}
```

**Cache Invalidation**:
- File modification time changes
- Library version incompatibility
- Manual cache clearing (`--clear-cache`)
- Date filtering (bypass cache)

### 5. Converter (`converter.py`)

**Purpose**: Orchestrate the conversion pipeline

**Key Functions**:
- `convert_jsonl_to_html()` - Main conversion entry point
- `ensure_fresh_cache()` - Cache validation and population
- `process_projects_hierarchy()` - Multi-project processing
- `_update_cache_with_session_data()` - Aggregate session data
- `_generate_individual_session_files()` - Generate per-session HTML

**Processing Strategy**:

```
Cache-First Approach:
1. Check if cache is fresh
   ├─ If stale: Parse and update cache
   └─ If fresh: Use cached data

2. Load messages (from cache when possible)
3. Apply date filtering (if specified)
4. Check if HTML regeneration needed
   ├─ HTML doesn't exist
   ├─ HTML is older than library version
   ├─ Cache was updated (source files changed)
   └─ Date filtering is active

5. Generate HTML if needed
6. Generate individual session files
```

### 6. Renderer (`renderer.py`)

**Purpose**: Generate HTML from processed data

**Key Functions**:
- `generate_html()` - Main transcript HTML generation
- `generate_session_html()` - Single session HTML
- `generate_projects_index_html()` - Master index page
- `is_html_outdated()` - Check if regeneration needed

**Template System**:
- Uses Jinja2 for HTML generation
- Server-side markdown rendering with mistune
- Syntax highlighting with Pygments
- Responsive design with embedded CSS/JavaScript

**HTML Output Features**:
- Interactive message filtering (user, assistant, tool use, etc.)
- Collapsible sections (thinking blocks, tool results)
- Timeline visualization (optional vis-timeline component)
- Session navigation with summaries
- Token usage tracking
- Date range display

### 7. TUI (`tui.py`)

**Purpose**: Interactive terminal interface for browsing sessions

**Features**:
- Session list with summaries, timestamps, message counts
- Quick actions: export to HTML, resume in Claude Code
- Project selector for multi-project navigation
- Working directory matching (auto-select relevant project)
- Real-time cache validation

**Key Components**:
- Built with Textual framework
- Keyboard navigation (arrow keys, Enter, q)
- Row expansion for detailed session info
- Cache-aware (uses cached metadata)

## Cache System

### Cache Lifecycle

```
┌─────────────────────────────────────────────────────┐
│                  Cache Lifecycle                     │
└─────────────────────────────────────────────────────┘

1. Initialization
   ├─ Create cache directory if needed
   ├─ Load index.json
   └─ Validate version compatibility

2. Validation
   ├─ Check file modification times
   ├─ Compare with cached mtimes
   └─ Identify stale entries

3. Update (on cache miss)
   ├─ Parse JSONL file
   ├─ Group entries by timestamp
   ├─ Save to cache/<filename>.json
   ├─ Update index.json with metadata
   └─ Calculate aggregates

4. Read (on cache hit)
   ├─ Load cache/<filename>.json
   ├─ Apply date filtering (if needed)
   ├─ Deserialize to Pydantic models
   └─ Return parsed entries

5. Invalidation
   ├─ File modification detected
   ├─ Library version incompatible
   ├─ Manual clearing
   └─ Delete cache files
```

### Cache File Format

**Individual Cache File** (`cache/<filename>.json`):
```json
{
  "2025-12-04T09:00:00Z": [
    {
      "type": "user",
      "message": {...},
      "sessionId": "abc123",
      "timestamp": "2025-12-04T09:00:00Z"
    }
  ],
  "2025-12-04T09:01:00Z": [
    {
      "type": "assistant",
      "message": {...},
      "sessionId": "abc123",
      "timestamp": "2025-12-04T09:01:00Z"
    }
  ],
  "_no_timestamp": [
    {
      "type": "summary",
      "summary": "...",
      "leafUuid": "xyz789"
    }
  ]
}
```

**Benefits of Timestamp-Keyed Structure**:
- Efficient date range filtering
- Skip irrelevant time periods without parsing
- Preserve chronological ordering
- Handle messages without timestamps (summaries)

### Cache Performance

**What Gets Cached**:
- ✅ Parsed JSONL entries (avoid re-parsing)
- ✅ Session metadata (summaries, timestamps, counts)
- ✅ Project aggregates (token usage, message counts)
- ✅ Working directories

**What Doesn't Get Cached**:
- ❌ HTML output (regenerated when needed)
- ❌ Template rendering
- ❌ Date-filtered results (computed on-demand)

**Cache Reuse Scenarios**:
- Same file processed multiple times → Parse once, read from cache
- TUI navigation → Use cached session metadata
- Date filtering → Filter cached data without re-parsing
- HTML regeneration → Use cached parsed data

## Processing Modes

### 1. Single File Mode

```bash
claude-code-log transcript.jsonl
```

**Flow**:
1. Parse single JSONL file (no caching)
2. Generate `transcript.html`
3. Exit

**Cache**: Not used (single file, overhead not worth it)

### 2. Directory Mode

```bash
claude-code-log /path/to/project
# or
claude-code-log project-name  # Auto-converts to ~/.claude/projects/
```

**Flow**:
1. Initialize CacheManager for directory
2. Check cache validity (file mtimes)
3. Parse modified files only
4. Load all files (from cache when possible)
5. Generate `combined_transcripts.html`
6. Generate individual `session-<id>.html` files
7. Exit

**Cache**: Fully utilized, updated incrementally

### 3. All Projects Mode

```bash
claude-code-log --all-projects
# or
claude-code-log  # Default behavior
```

**Flow**:
1. Scan `~/.claude/projects/` for project directories
2. For each project:
   - Initialize CacheManager
   - Ensure cache is fresh
   - Generate combined transcript
   - Generate individual session files
3. Collect project summaries from cache
4. Generate master `index.html`
5. Exit

**Cache**: One cache per project, aggregated for index

### 4. TUI Mode

```bash
claude-code-log --tui
```

**Flow**:
1. Find projects matching current directory (optional)
2. Build/validate cache (if needed)
3. Load session metadata from cache
4. Launch interactive session browser
5. User actions:
   - Export to HTML (generate on-demand)
   - Resume in Claude Code (spawn `claude -r <sessionId>`)
   - Refresh (rebuild cache and reload)
6. Exit on quit

**Cache**: Essential for fast TUI loading and navigation

## Workflow Examples

### Example 1: First-Time Processing

**Scenario**: User runs `claude-code-log --all-projects` for the first time

```
1. CLI Entry
   └─> process_projects_hierarchy()

2. For each project directory:
   ├─> Initialize CacheManager
   │   └─> Create cache/ directory
   │       └─> Initialize empty index.json
   │
   ├─> ensure_fresh_cache()
   │   ├─> Get list of *.jsonl files
   │   ├─> Check cache (no entries, cache miss)
   │   └─> Call load_directory_transcripts()
   │       ├─> For each JSONL file:
   │       │   ├─> Parse line by line
   │       │   ├─> Validate with Pydantic
   │       │   ├─> Load agent files recursively
   │       │   └─> save_cached_entries()
   │       │       └─> Write cache/<file>.json
   │       └─> Sort all messages chronologically
   │
   ├─> _update_cache_with_session_data()
   │   ├─> Map summaries to sessions
   │   ├─> Calculate token aggregates
   │   ├─> Update session metadata
   │   └─> Save index.json
   │
   ├─> convert_jsonl_to_html()
   │   ├─> Load messages (from fresh cache)
   │   ├─> generate_html()
   │   │   ├─> Deduplicate messages
   │   │   ├─> Process sessions
   │   │   ├─> Render Jinja2 template
   │   │   └─> Write combined_transcripts.html
   │   └─> _generate_individual_session_files()
   │       └─> For each session:
   │           └─> Write session-<id>.html
   │
   └─> Collect project summary for index

3. Generate Master Index
   ├─> generate_projects_index_html()
   └─> Write ~/.claude/projects/index.html
```

**Files Created**:
- `~/.claude/projects/index.html`
- `~/.claude/projects/<project>/combined_transcripts.html`
- `~/.claude/projects/<project>/session-*.html`
- `~/.claude/projects/<project>/cache/index.json`
- `~/.claude/projects/<project>/cache/*.json`

### Example 2: Subsequent Run (Cache Hit)

**Scenario**: User runs `claude-code-log --all-projects` again, no files changed

```
1. CLI Entry
   └─> process_projects_hierarchy()

2. For each project:
   ├─> Initialize CacheManager
   │   └─> Load existing index.json
   │
   ├─> ensure_fresh_cache()
   │   ├─> Get list of *.jsonl files
   │   ├─> Check modification times
   │   │   └─> All match cached mtimes
   │   └─> Return False (cache is fresh)
   │
   ├─> Load cached project data
   │   └─> Use data from index.json
   │
   ├─> Check if HTML needs regeneration
   │   ├─> HTML exists
   │   ├─> HTML version matches library version
   │   ├─> Cache was not updated
   │   └─> Skip HTML generation
   │
   └─> Collect project summary from cache

3. Check Master Index
   ├─> index.html exists
   ├─> Version matches
   ├─> No cache updates
   └─> Skip index generation

4. Output: "Index HTML is current, skipping regeneration"
```

**Performance**: ~100x faster (no parsing, no rendering)

### Example 3: Incremental Update

**Scenario**: User adds new session, runs `claude-code-log --all-projects`

```
1. CLI Entry
   └─> process_projects_hierarchy()

2. For project with new file:
   ├─> Initialize CacheManager
   │   └─> Load existing index.json
   │
   ├─> ensure_fresh_cache()
   │   ├─> Get list of *.jsonl files
   │   ├─> Find new-session.jsonl (not in cache)
   │   └─> Call load_directory_transcripts()
   │       ├─> For existing files:
   │       │   └─> load_cached_entries() [fast]
   │       └─> For new file:
   │           ├─> Parse JSONL [slow]
   │           └─> save_cached_entries()
   │
   ├─> _update_cache_with_session_data()
   │   └─> Update index.json with new session
   │
   ├─> convert_jsonl_to_html()
   │   ├─> Check if HTML needs regeneration
   │   │   └─> cache_was_updated = True
   │   ├─> Regenerate combined_transcripts.html
   │   └─> Generate new session-<id>.html
   │
   └─> Collect updated project summary

3. Regenerate Master Index
   ├─> cache_was_updated = True
   └─> Write index.html
```

**Performance**: Only parse new file, reuse cached data for existing files

### Example 4: TUI Session Browse

**Scenario**: User runs `claude-code-log --tui` in a project directory

```
1. CLI Entry (TUI mode)
   └─> _launch_tui_with_cache_check()

2. Cache Check
   ├─> Initialize CacheManager
   ├─> Check if cache needs rebuild
   │   ├─> If stale:
   │   │   └─> convert_jsonl_to_html(silent=True)
   │   │       └─> Build cache in background
   │   └─> If fresh:
   │       └─> "Cache up to date"
   │
   └─> Load cached project data

3. Launch TUI
   ├─> run_session_browser()
   ├─> Display session table
   │   ├─> Read from cache:
   │   │   ├─> Session summaries
   │   │   ├─> Message counts
   │   │   ├─> Timestamps
   │   │   └─> Token usage
   │   └─> Render interactive table
   │
   └─> User interactions:
       ├─> Export to HTML (h)
       │   └─> generate_session_html()
       │       └─> Open in browser
       ├─> Resume session (c)
       │   └─> Run `claude -r <sessionId>`
       └─> Refresh (r)
           └─> Rebuild cache and reload

4. Exit on quit (q)
```

**Performance**: Near-instant load using cached metadata

### Example 5: Date Filtering

**Scenario**: User runs `claude-code-log --from-date "yesterday"`

```
1. CLI Entry
   └─> convert_jsonl_to_html(from_date="yesterday")

2. Cache Check
   ├─> Initialize CacheManager
   └─> ensure_fresh_cache()
       └─> Check cache validity (ignore date filter)

3. Load Messages with Filtering
   ├─> load_directory_transcripts(from_date="yesterday")
   │   └─> For each file:
   │       └─> load_cached_entries_filtered()
   │           ├─> Parse "yesterday" → datetime
   │           ├─> Read cache file
   │           ├─> Filter by timestamp keys
   │           └─> Return matching entries only
   │
   └─> Apply filter_messages_by_date()

4. Generate HTML
   ├─> Always regenerate (date filter active)
   └─> Include date range in title

5. Output HTML with filtered content
```

**Performance**: Filter cached data (fast) vs. re-parse files (slow)

### Example 6: Cache Clearing

**Scenario**: User runs `claude-code-log --clear-cache --all-projects`

```
1. CLI Entry
   └─> _clear_caches(all_projects=True)

2. For each project:
   ├─> Initialize CacheManager
   ├─> clear_cache()
   │   ├─> Delete cache/*.json files
   │   ├─> Delete index.json
   │   └─> Reset in-memory cache
   └─> Output: "Cleared cache for <project>"

3. If no other flags:
   └─> Exit (cache cleared, no processing)

4. If other flags present (e.g., --from-date):
   └─> Continue with normal processing
       └─> Will rebuild cache from scratch
```

**Use Cases**:
- Debugging cache issues
- Force full reprocessing
- Recover from corrupted cache

## Summary

**Key Architectural Features**:

1. **Cache-First Processing**: Minimize redundant work by caching parsed data
2. **Incremental Updates**: Only reprocess changed files
3. **Smart Invalidation**: Detect when HTML regeneration is actually needed
4. **Type Safety**: Pydantic models throughout for robust data handling
5. **Hierarchical Organization**: Projects → Sessions → Messages
6. **Flexible Modes**: Single file, directory, all projects, TUI
7. **Date Filtering**: Efficient timestamp-based filtering on cached data
8. **Agent Support**: Recursive loading of sub-agent transcripts

**Performance Optimizations**:
- Timestamp-keyed cache structure for fast date filtering
- Modification time tracking to skip unchanged files
- Session metadata caching for TUI
- Lazy HTML generation (only when needed)
- Deduplication to handle message overlaps

**Scalability**:
- Handles projects with hundreds of sessions
- Efficient memory usage (streaming JSONL parsing)
- Parallel-friendly (independent project processing)
- Cache reduces 100+ second processing to <1 second on reruns
