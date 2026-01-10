"""Unit tests for copyable text extraction and ANSI code stripping."""

import json

from claude_code_log.models import (
    ImageContent,
    ImageSource,
    TextContent,
    ThinkingContent,
    ToolResultContent,
    ToolUseContent,
)
from claude_code_log.renderer import _strip_ansi_codes, extract_copyable_text


class TestStripAnsiCodes:
    """Tests for _strip_ansi_codes function."""

    def test_strips_standard_color_codes(self):
        text = "\x1b[31mRed text\x1b[0m"
        result = _strip_ansi_codes(text)
        assert result == "Red text"

    def test_strips_bold_and_style_codes(self):
        text = "\x1b[1mBold\x1b[22m normal \x1b[3mitalic\x1b[23m"
        result = _strip_ansi_codes(text)
        assert result == "Bold normal italic"

    def test_strips_rgb_color_codes(self):
        text = "\x1b[38;2;255;0;0mRGB red\x1b[0m"
        result = _strip_ansi_codes(text)
        assert result == "RGB red"

    def test_strips_cursor_movement_codes(self):
        text = "\x1b[1A\x1b[2KCleared line"
        result = _strip_ansi_codes(text)
        assert result == "Cleared line"

    def test_strips_multiple_ansi_sequences(self):
        text = "\x1b[31mRed\x1b[0m \x1b[32mGreen\x1b[0m \x1b[33mYellow\x1b[0m"
        result = _strip_ansi_codes(text)
        assert result == "Red Green Yellow"

    def test_preserves_regular_text(self):
        text = "Plain text without any codes"
        result = _strip_ansi_codes(text)
        assert result == "Plain text without any codes"

    def test_empty_string(self):
        text = ""
        result = _strip_ansi_codes(text)
        assert result == ""

    def test_only_ansi_codes(self):
        text = "\x1b[31m\x1b[0m\x1b[32m\x1b[0m"
        result = _strip_ansi_codes(text)
        assert result == ""

    def test_preserves_unicode(self):
        text = "\x1b[31m你好\x1b[0m 🎨 émojis"
        result = _strip_ansi_codes(text)
        assert result == "你好 🎨 émojis"


class TestExtractCopyableText:
    """Tests for extract_copyable_text function."""

    # Basic content type tests

    def test_text_content_strips_ansi(self):
        content = [TextContent(type="text", text="\x1b[31mRed\x1b[0m text")]
        result = extract_copyable_text(content, "user")
        assert result == "Red text"

    def test_text_content_preserves_markdown(self):
        content = [TextContent(type="text", text="# Header\n**bold** text")]
        result = extract_copyable_text(content, "user")
        assert result == "# Header\n**bold** text"

    def test_tool_use_content_returns_json(self):
        content = [
            ToolUseContent(
                type="tool_use", id="tool_123", name="Bash", input={"command": "ls -la"}
            )
        ]
        result = extract_copyable_text(content, "assistant")
        expected_json = json.dumps(
            {"name": "Bash", "input": {"command": "ls -la"}}, indent=2
        )
        assert result == expected_json

    def test_thinking_content_preserved(self):
        content = [ThinkingContent(type="thinking", thinking="Analyzing the code...")]
        result = extract_copyable_text(content, "assistant")
        assert result == "Analyzing the code..."

    def test_image_content_skipped(self):
        content = [
            ImageContent(
                type="image",
                source=ImageSource(
                    type="base64", media_type="image/png", data="fake_base64_data"
                ),
            )
        ]
        result = extract_copyable_text(content, "user")
        assert result == ""

    # ToolResultContent tests

    def test_tool_result_string_strips_ansi(self):
        content = [
            ToolResultContent(
                type="tool_result",
                tool_use_id="tool_123",
                content="\x1b[32mSuccess\x1b[0m",
            )
        ]
        result = extract_copyable_text(content, "tool_result")
        assert result == "Success"

    def test_tool_result_list_extracts_text(self):
        content = [
            ToolResultContent(
                type="tool_result",
                tool_use_id="tool_123",
                content=[
                    {"type": "text", "text": "Line 1"},
                    {"type": "text", "text": "Line 2"},
                ],
            )
        ]
        result = extract_copyable_text(content, "tool_result")
        assert result == "Line 1\n\nLine 2"

    def test_tool_result_list_with_ansi_codes(self):
        content = [
            ToolResultContent(
                type="tool_result",
                tool_use_id="tool_123",
                content=[
                    {"type": "text", "text": "\x1b[31mError\x1b[0m"},
                    {"type": "text", "text": "\x1b[32mSuccess\x1b[0m"},
                ],
            )
        ]
        result = extract_copyable_text(content, "tool_result")
        assert result == "Error\n\nSuccess"

    def test_tool_result_list_non_text_items(self):
        content = [
            ToolResultContent(
                type="tool_result",
                tool_use_id="tool_123",
                content=[{"type": "data", "value": 123}],
            )
        ]
        result = extract_copyable_text(content, "tool_result")
        expected_json = json.dumps({"type": "data", "value": 123}, indent=2)
        assert result == expected_json

    def test_tool_result_empty_content(self):
        content = [
            ToolResultContent(type="tool_result", tool_use_id="tool_123", content="")
        ]
        result = extract_copyable_text(content, "tool_result")
        assert result == ""

    # Multiple content items tests

    def test_multiple_text_items_joined_with_double_newline(self):
        content = [
            TextContent(type="text", text="First paragraph"),
            TextContent(type="text", text="Second paragraph"),
            TextContent(type="text", text="Third paragraph"),
        ]
        result = extract_copyable_text(content, "user")
        assert result == "First paragraph\n\nSecond paragraph\n\nThird paragraph"

    def test_mixed_content_types(self):
        content = [
            TextContent(type="text", text="User message"),
            ToolUseContent(
                type="tool_use",
                id="tool_1",
                name="Read",
                input={"file_path": "/test.py"},
            ),
            ToolResultContent(
                type="tool_result", tool_use_id="tool_1", content="File contents"
            ),
            ThinkingContent(type="thinking", thinking="Analyzing..."),
        ]
        result = extract_copyable_text(content, "assistant")

        assert "User message" in result
        assert '"name": "Read"' in result
        assert "File contents" in result
        assert "Analyzing..." in result
        parts = result.split("\n\n")
        assert len(parts) == 4

    def test_empty_content_list(self):
        content = []
        result = extract_copyable_text(content, "user")
        assert result == ""

    def test_content_with_only_images(self):
        content = [
            ImageContent(
                type="image",
                source=ImageSource(type="base64", media_type="image/png", data="data1"),
            ),
            ImageContent(
                type="image",
                source=ImageSource(
                    type="base64", media_type="image/jpeg", data="data2"
                ),
            ),
        ]
        result = extract_copyable_text(content, "user")
        assert result == ""

    # Edge cases

    def test_unknown_content_type_with_text_attribute(self):
        class MockContent:
            def __init__(self):
                self.text = "Mock text content"

        content = [MockContent()]
        result = extract_copyable_text(content, "user")
        assert result == "Mock text content"

    def test_unknown_content_type_without_text_attribute(self):
        class MockContent:
            def __init__(self):
                self.value = "No text attribute"

        content = [MockContent()]
        result = extract_copyable_text(content, "user")
        assert result == ""

    def test_preserves_whitespace_and_newlines(self):
        content = [
            TextContent(type="text", text="Line 1\n  Indented line\n\nLine after blank")
        ]
        result = extract_copyable_text(content, "user")
        assert result == "Line 1\n  Indented line\n\nLine after blank"

    def test_tool_result_list_with_multiple_dicts(self):
        content = [
            ToolResultContent(
                type="tool_result",
                tool_use_id="tool_123",
                content=[
                    {"type": "text", "text": "Text item"},
                    {"type": "data", "value": "Some value"},
                ],
            )
        ]
        result = extract_copyable_text(content, "tool_result")
        assert "Text item" in result
        assert '"type": "data"' in result
