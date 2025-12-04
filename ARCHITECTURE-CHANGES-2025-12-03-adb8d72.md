# Architecture Changes Analysis

**Comparing against**: ARCHITECTURE.md (documented at commit `3b9b9dd`)
**Latest main commit**: `adb8d72` (2025-12-03)
**Analysis date**: 2025-12-04

## Summary

The main branch has received **7 significant pull requests** since the architecture documentation was created. These changes introduce new features, refactor core rendering logic, and add comprehensive test infrastructure. While the fundamental architecture remains intact, there are important additions and refinements that affect how messages are processed, rendered, and tested.

## Key Architectural Changes

### 1. Slash Command Support (PR #50)

**Impact Level**: 🟡 Medium - New Feature

**What Changed**:
- Added support for rendering slash command expanded prompts (e.g., `/init`, `/context`)
- Slash commands have `isMeta=True` and are LLM-generated prompt expansions
- New visual styling to distinguish slash commands from regular user messages

**Architectural Implications**:

#### Data Model Changes
- **Deduplication key expanded**: Now uses `(type, timestamp, isMeta, sessionId)` instead of `(type, timestamp)`
  - `isMeta`: Prevents slash command prompts from being deduplicated with their parent messages
  - `sessionId`: Prevents cross-session deduplication in multi-session reports

**Location in ARCHITECTURE.md**: Section 5.6 (Renderer)

**What Needs Updating**:
```diff
Deduplication key:
- (message.type, timestamp)
+ (message.type, timestamp, isMeta, sessionId)
```

#### Renderer Changes
- New helper functions for collapsible content:
  - `render_markdown_collapsible()` - For long markdown content (Task prompts, assistant messages, thinking)
  - `render_collapsible_code()` - For code blocks
  - `render_file_content_collapsible()` - For file content (Write/Read/Edit tools)

**Collapsible Content Thresholds**:
| Content Type | Threshold | Preview Lines |
|--------------|-----------|---------------|
| Task prompts | 20 lines | 5 lines |
| Task results | 20 lines | 5 lines |
| Compacted conversations | 30 lines | 10 lines |
| Assistant messages | 30 lines | 10 lines |
| Thinking content | 10 lines | 5 lines |
| Command output | 12 lines | 5 lines |

**Location in ARCHITECTURE.md**: Section 5.6 (Renderer) - HTML Output Features

**What Needs Adding**:
- Document collapsible rendering system
- Document slash command rendering with dimmed styling
- Document `/context` table rendering support

### 2. Parallel Sidechain Rendering (PR #54)

**Impact Level**: 🔴 High - Core Architecture Change

**What Changed**:
Major refactoring of message ordering and hierarchy logic to correctly interleave parallel sub-agent (sidechain) messages.

**Problem Solved**:
- **Before**: Task A → Task B → all sidechains A → all sidechains B (incorrect)
- **After**: Task A → sidechains A → Task B → sidechains B (correct)

**Architectural Implications**:

#### Data Model Changes
```python
# Added to BaseTranscriptEntry
agentId: Optional[str] = None  # Agent ID for sidechain messages
```

This is a **significant change** because `agentId` is now part of the base transcript entry model, not just present in nested structures.

**Location in ARCHITECTURE.md**: Section 5.2 (Models)

**What Needs Updating**:
```diff
class BaseTranscriptEntry(BaseModel):
    parentUuid: Optional[str]
    isSidechain: bool
    userType: str
    cwd: str
    sessionId: str
    version: str
    uuid: str
    timestamp: str
    isMeta: Optional[bool] = None
+   agentId: Optional[str] = None  # For sidechain message tracking
```

#### Renderer Changes - New Message Ordering System

The renderer now has a **multi-stage message processing pipeline**:

```
1. Parse messages (parser.py)
   ↓
2. Initial template message creation
   ↓
3. Message reordering stages (NEW):
   a. _reorder_paired_messages() - Group tool_use with tool_result
   b. _reorder_sidechain_template_messages() - Insert sidechains after Task results
   c. _reorder_session_template_messages() - Group resumed session messages
   ↓
4. _build_message_hierarchy() - Rebuild message IDs and ancestry
   ↓
5. Template rendering
```

**New Functions**:
- `_reorder_sidechain_template_messages()` - Groups sidechains by `agent_id`, inserts after matching Task result
- `_reorder_session_template_messages()` - Groups messages by `session_id`, prevents interleaving in resumed sessions
- `_build_message_hierarchy()` - Rebuilds message IDs and ancestry based on final display order

**Removed Functions**:
- `_resolve_uuid_links()` - No longer needed with new ordering system
- Initial hierarchy determination in `_process_messages_loop()` - Now done once at the end

**Location in ARCHITECTURE.md**: Section 5.6 (Renderer) - Should add new subsection

**What Needs Adding**:
```markdown
### Message Ordering Pipeline

The renderer uses a multi-stage ordering system to ensure messages appear in the correct visual hierarchy:

1. **Pair Reordering**: Tool use/result pairs are grouped together
2. **Sidechain Reordering**: Sub-agent messages are inserted after their triggering Tool result
3. **Session Reordering**: Resumed session messages are grouped under their session header
4. **Hierarchy Rebuild**: Message IDs and parent-child relationships are recalculated

This ensures:
- Parallel sub-agents display correctly interleaved
- Resumed sessions don't have messages scattered across sessions
- Tool use/result pairs stay together visually
```

#### Internal Data Structure
```python
# New field in TemplateMessage (internal renderer structure)
agent_id: Optional[str] = None  # For late-stage sidechain reordering
```

**Location in ARCHITECTURE.md**: Section 5.6 (Renderer)

### 3. Cross-Session Tool Pairing (PR #56)

**Impact Level**: 🟡 Medium - Bug Fix with Architectural Implications

**What Changed**:
Fixed tool pairing logic to handle session resumption correctly.

**Problem Solved**:
When session B resumes session A, both JSONL files may contain messages with the same `tool_use_id`. The pairing logic was using only `tool_use_id` as the key, causing incorrect pairing across sessions.

**Architectural Implications**:

#### Renderer Changes
```diff
# Tool pairing dictionary keys
- tool_use_map[tool_use_id] = message
+ tool_use_map[(session_id, tool_use_id)] = message

- tool_result_map[tool_use_id] = message
+ tool_result_map[(session_id, tool_use_id)] = message
```

Functions affected:
- `_identify_message_pairs()` - Now uses `(session_id, tool_use_id)` tuples
- `_reorder_paired_messages()` - Now uses `(session_id, tool_use_id)` tuples

**Location in ARCHITECTURE.md**: Section 5.6 (Renderer) - Message Ordering Pipeline

**What Needs Updating**:
Document that tool pairing is session-scoped to handle resumed sessions.

### 4. Integration Tests (PR #52)

**Impact Level**: 🟢 Low - Testing Infrastructure (doesn't affect runtime architecture)

**What Changed**:
- Added comprehensive integration tests using real Claude Code project logs
- Introduced snapshot testing with Syrupy library
- Added test data directory with realistic JSONL files

**New Test Infrastructure**:
```
test/
├── test_data/
│   ├── -src-deep-manifest/           # Real project logs
│   │   ├── *.jsonl                   # Session files
│   │   └── agent-*.jsonl             # Agent files
│   ├── other-test-projects/
│   └── ...
├── __snapshots__/
│   └── test_snapshot_html.ambr       # HTML output snapshots
├── snapshot_serializers.py           # Custom serializers for Syrupy
└── test_*.py                         # Test files
```

**New Test Types**:
- `test_integration_realistic.py` - End-to-end tests with real data
- `test_snapshot_html.py` - HTML output regression testing
- `test_performance.py` - Performance benchmarks
- `test_askuserquestion_rendering.py` - Specific message type tests
- `test_exitplanmode_rendering.py` - Exit plan mode rendering tests

**Location in ARCHITECTURE.md**: Not currently documented (testing is outside core architecture)

**What Could Be Added**:
Optional section on testing strategy and snapshot testing approach.

### 5. CSS Styles Cleanup (PR #53)

**Impact Level**: 🟢 Low - Visual/UI Only

**What Changed**:
- Reorganized CSS component files for better maintainability
- No architectural changes to data flow or processing

**Files Affected**:
- `components/filter_styles.css`
- `components/global_styles.css`
- `components/message_styles.css`
- `components/project_card_styles.css`
- `components/search_styles.css`
- `components/session_nav_styles.css`
- `components/timeline_styles.css`
- `components/todo_styles.css`

**Location in ARCHITECTURE.md**: Not applicable (CSS styling doesn't affect architecture)

### 6. Review and Polish (PR #51)

**Impact Level**: 🟢 Low - General Cleanup

**What Changed**:
- General code cleanup and polishing for 0.8dev release
- Documentation improvements
- Minor bug fixes

**Location in ARCHITECTURE.md**: Not applicable (no architectural impact)

### 7. Test and Lint Fixes (PR #55)

**Impact Level**: 🟢 Low - Bug Fixes

**What Changed**:
- Fixed test failures
- Fixed linting issues
- Added Claude Code hooks for development

**New Development Files**:
```
.claude/settings.json  # Claude Code configuration
```

**Location in ARCHITECTURE.md**: Not applicable (development tooling)

## Detailed File Change Analysis

### Core Architecture Files

| File | Changes | Impact |
|------|---------|--------|
| `models.py` | +1 line: `agentId` field | 🔴 High - Data model change |
| `renderer.py` | +408/-218 lines | 🔴 High - Major refactoring |
| `parser.py` | No changes | ✅ No impact |
| `converter.py` | +14 lines | 🟡 Medium - Minor changes |
| `cache.py` | No changes | ✅ No impact |
| `cli.py` | +61 lines | 🟡 Medium - CLI improvements |
| `tui.py` | +12 lines | 🟢 Low - Minor updates |

### Template Files

| File | Changes | Impact |
|------|---------|--------|
| `templates/transcript.html` | +17 lines | 🟢 Low - Template updates |
| `templates/index.html` | +4 lines | 🟢 Low - Template updates |
| `templates/components/*.css` | Multiple files | 🟢 Low - Styling only |
| `templates/components/session_nav.html` | +8 lines | 🟢 Low - Navigation fixes |

### Test Infrastructure

| File | Changes | Impact |
|------|---------|--------|
| `test/test_*.py` | Multiple new tests | Testing only |
| `test/__snapshots__/*.ambr` | Snapshot data | Testing only |
| `test/test_data/` | Real JSONL data | Testing only |
| `.github/workflows/ci.yml` | CI updates | DevOps only |

## What ARCHITECTURE.md Needs

### Required Updates

1. **Section 5.2 (Models)**:
   - Add `agentId: Optional[str]` to `BaseTranscriptEntry` documentation

2. **Section 5.6 (Renderer)**:
   - Document new message ordering pipeline with 3 reordering stages
   - Document collapsible content rendering system
   - Document slash command rendering
   - Update deduplication key to include `isMeta` and `sessionId`
   - Document session-scoped tool pairing

### Recommended Additions

3. **New Section: Message Ordering and Hierarchy**:
   ```markdown
   ## Message Ordering and Hierarchy

   The renderer employs a multi-stage ordering system to ensure correct visual hierarchy:

   ### Stage 1: Pair Reordering
   Groups tool_use and tool_result messages together using (session_id, tool_use_id) keys.

   ### Stage 2: Sidechain Reordering
   Inserts sub-agent (sidechain) messages after their triggering Task tool_result.
   Uses agent_id to group parallel sub-agent messages correctly.

   ### Stage 3: Session Reordering
   Groups messages from resumed sessions under their session header.

   ### Stage 4: Hierarchy Rebuild
   Recalculates message IDs and parent-child relationships based on final order.
   ```

4. **New Section: Collapsible Content Rendering**:
   Document the thresholds and preview rendering system for long content.

5. **Update Section 3 (Data Flow)**:
   Add details about the new rendering stages between "Converter" and "Templates"

### Optional Additions

6. **Testing Strategy Section**:
   - Document snapshot testing approach
   - Explain test data organization
   - Describe integration test methodology

## Impact Summary by Architecture Layer

| Layer | Impact Level | Key Changes |
|-------|-------------|-------------|
| **Data Models** | 🔴 High | Added `agentId` to `BaseTranscriptEntry` |
| **Parser** | ✅ None | No changes |
| **Cache** | ✅ None | No changes |
| **Converter** | 🟢 Low | Minor improvements to CLI handling |
| **Renderer** | 🔴 High | Major refactoring of message ordering and rendering |
| **Templates** | 🟡 Medium | New features (slash commands, collapsible content) |
| **TUI** | 🟢 Low | Minor updates |
| **Testing** | 🟢 New | Comprehensive integration and snapshot tests |

## Migration Notes

If you're implementing features based on the original ARCHITECTURE.md, be aware:

1. **Message ordering is now multi-stage**: Don't assume messages appear in parse order
2. **agentId is now a first-class field**: Available on all transcript entries, not just nested in tool results
3. **Deduplication logic has changed**: Must account for `isMeta` and `sessionId`
4. **Tool pairing is session-scoped**: Same `tool_use_id` can exist in different sessions
5. **Hierarchy is built late**: Message IDs and ancestry are calculated after all reordering

## Compatibility Notes

### Breaking Changes
None of these changes break the external API or data formats:
- JSONL input format unchanged
- HTML output format unchanged (enhanced with new features)
- Cache format unchanged
- CLI interface unchanged (new features are additive)

### Internal API Changes
If you're extending the renderer:
- `_process_messages_loop()` no longer builds hierarchy initially
- New reordering functions must be called in correct order
- `TemplateMessage` now has `agent_id` field

## Conclusion

The architecture documented in ARCHITECTURE.md remains **fundamentally correct**, but the following areas have evolved significantly:

1. **Message ordering** is now a sophisticated multi-stage process
2. **Data models** have gained `agentId` as a first-class field
3. **Rendering** has new collapsible content helpers
4. **Slash command support** is a new feature category
5. **Testing** has comprehensive integration test coverage

The core pipeline (Input → Parser → Cache → Converter → Renderer → Output) is unchanged, but the **Renderer** component has been significantly enhanced to handle complex message hierarchies, parallel sub-agents, and resumed sessions correctly.

## Recommendations

For maintaining ARCHITECTURE.md going forward:

1. ✅ Keep the high-level architecture diagram (still accurate)
2. 🔄 Update the Renderer section with new ordering stages
3. 🔄 Update the Models section with `agentId` field
4. ➕ Add a "Message Ordering and Hierarchy" section
5. ➕ Add a "Collapsible Content Rendering" section
6. 🤔 Consider adding a "Testing Strategy" section (optional)

The existing workflow examples and cache system documentation remain accurate and valuable.
