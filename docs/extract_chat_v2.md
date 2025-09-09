# Extract Chat V2 - Simplified Chronological Processing

## Overview

`extract_chat_v2.py` is a simplified, modular approach to extracting and formatting ChatGPT conversations from JSON files. Unlike the original `extract_chat.py`, this version:

- **Processes conversations chronologically** by `create_time` rather than parent-child relationships
- **Uses Pydantic for direct JSON validation** without intermediate representations
- **Handles different content types** (user messages, tool calls, system messages, etc.)
- **Extracts metadata** and preserves conversation structure
- **Supports multiple output formats** (Markdown, HTML)

## Architecture

### Simplified Data Flow
```
Raw JSON → ChatGPTConversation (Pydantic) → Formatter → Output
```

### Key Components

#### 1. **Input Schemas** (`bin/pylib/schemas/input_schemas_v2.py`)
- `ChatGPTConversation`: Main Pydantic model for the entire conversation
- `ChatGPTTurn`: Individual conversation turns
- `ChatGPTMessage`: Message content and metadata
- `ChatGPTContent`: Different content types (text, code, tool calls)
- `ChatGPTAuthor`: Author information

#### 2. **Formatters** (`bin/pylib/formatters/`)
- `MarkdownFormatter`: Generates Markdown output
- `HTMLFormatter`: Generates HTML output with CSS manager integration
- `BaseFormatter`: Abstract base class for all formatters

#### 3. **CSS Manager** (`bin/pylib/css_manager.py`)
- Default theme management
- Custom CSS file support
- Theme variants (light/dark)
- Responsive design support

#### 3. **Main Script** (`bin/extract_chat_v2.py`)
- Command-line interface
- File handling and validation
- Orchestrates the extraction process

## Key Features

### Chronological Processing
- Sorts conversation turns by `create_time` timestamp
- Handles missing timestamps gracefully
- Preserves conversation flow

### Content Type Handling
- **User Messages**: Standard text content
- **Tool Calls**: Function calls with input/output
- **System Messages**: Context and instructions
- **Code Blocks**: Syntax-highlighted code
- **Citations**: Reference links and metadata

### Metadata Extraction
- Conversation title and ID
- Creation and update timestamps
- Model information
- User context data

### Text Normalization
- Uses `ftfy` for Unicode normalization
- Removes null characters
- Preserves extended ASCII characters

### CSS Management
- **Default Themes**: Light and dark theme variants
- **Custom CSS Support**: External CSS file integration
- **Responsive Design**: Mobile-friendly layouts
- **Print Styles**: Optimized for printing
- **Professional Styling**: Clean, modern appearance

## Usage

```bash
# Basic usage
python bin/extract_chat_v2.py input.json -o output.md

# Force overwrite
python bin/extract_chat_v2.py input.json -o output.md --force

# HTML output
python bin/extract_chat_v2.py input.json -o output.html -f html

# HTML with custom CSS
python bin/extract_chat_v2.py input.json -o output.html -f html -c custom.css

## Recent Improvements

### ✅ Eliminated Intermediate Representation (IR)
- Removed `DocumentIR`, `DocumentBlock`, `DocumentMetadata` schemas
- Moved conversion logic into `ChatGPTConversation` methods
- Simplified data flow and reduced code complexity

### ✅ Direct Pydantic Processing
- Uses `ChatGPTConversation.model_validate_json()` for direct JSON loading
- Leverages Pydantic's validation and transformation capabilities
- Eliminates manual JSON parsing

### ✅ Streamlined Formatters
- Formatters work directly with `ChatGPTConversation` objects
- Dictionary-based content blocks for flexibility
- Cleaner separation of concerns

## Current Status

### ✅ Working Components
- **Markdown Formatter**: Fully functional with simplified architecture
- **Chronological Processing**: Correctly sorts by timestamp
- **Content Extraction**: Handles all major content types
- **Metadata Processing**: Extracts and formats metadata correctly
- **Text Normalization**: Proper Unicode handling

### 🔄 In Progress
- **Tool Call Formatting**: Enhanced formatting for function calls
- **Citation Processing**: Improved reference handling

### 📋 Future Enhancements
- **Additional Output Formats**: PDF, plain text
- **Custom Formatting Options**: Configurable output styles
- **Batch Processing**: Handle multiple files
- **Validation Enhancements**: More robust error handling

## Technical Details

### Pydantic Models
The `ChatGPTConversation` model includes methods for:
- `get_chronological_turns()`: Sort turns by timestamp
- `get_metadata()`: Extract conversation metadata
- `get_content_blocks()`: Generate formatted content blocks
- Various `_create_*_block()` methods for different content types

### Formatter Interface
Formatters implement:
- `format_conversation(conversation: ChatGPTConversation) -> str`
- Helper methods for specific content types
- Text normalization and formatting

### Error Handling
- Graceful handling of missing timestamps
- Flexible content type validation
- Robust Unicode processing
- Clear error messages for debugging

## Project Structure

### Final Clean Architecture

```
bin/
├── extract_chat_v2.py                    # Main script with CLI interface
└── pylib/                                # Core library modules
    ├── __init__.py                       # Package initialization
    ├── css_manager.py                    # CSS management and themes
    ├── schemas/                          # Pydantic data models
    │   ├── __init__.py                   # Schema exports
    │   └── input_schemas_v2.py           # Core ChatGPT conversation models
    └── formatters/                       # Output formatting modules
        ├── __init__.py                   # Formatter exports
        ├── base.py                       # Abstract base formatter
        ├── markdown_formatter.py         # Markdown output formatter
        └── html_formatter.py             # HTML output formatter
```

### Module Responsibilities

#### Core Script
- **`bin/extract_chat_v2.py`**: Main entry point with CLI interface
  - Argument parsing and validation
  - File I/O operations
  - Formatter selection and orchestration
  - Error handling and user feedback

#### Schema Layer
- **`bin/pylib/schemas/input_schemas_v2.py`**: Core data models
  - `ChatGPTConversation`: Main conversation container
  - `ChatGPTTurn`: Individual conversation turns
  - `ChatGPTMessage`: Message content and metadata
  - `ChatGPTContent`: Different content types (text, code, tool calls)
  - `ChatGPTAuthor`: Author information
  - Built-in processing methods for data transformation

#### Formatter Layer
- **`bin/pylib/formatters/base.py`**: Abstract base class
  - Common formatter interface
  - Validation methods
  - Configuration handling

- **`bin/pylib/formatters/markdown_formatter.py`**: Markdown output
  - Chronological conversation formatting
  - Content type-specific formatting
  - Text normalization and cleanup

- **`bin/pylib/formatters/html_formatter.py`**: HTML output
  - Professional HTML generation
  - CSS manager integration
  - Responsive design support

#### CSS Management
- **`bin/pylib/css_manager.py`**: Styling and themes
  - Default light and dark themes
  - Custom CSS file support
  - Responsive design rules
  - Print-optimized styles

### Data Flow

```
Raw JSON → ChatGPTConversation (Pydantic) → Formatter → Output
     ↓              ↓                        ↓         ↓
Validation    Built-in Methods         CSS Manager   File
Timestamp     Content Blocks           Theme Support  Writing
Conversion    Metadata Extraction      Custom CSS    Error Handling
```

### Key Design Principles

1. **Separation of Concerns**: Each module has a single, well-defined responsibility
2. **Pydantic Integration**: Leverages Pydantic for validation and transformation
3. **Modular Formatters**: Easy to add new output formats
4. **CSS Separation**: Styling concerns separated from content processing
5. **Error Resilience**: Graceful handling of malformed data
6. **Extensibility**: Clean interfaces for future enhancements

### Removed Components (70% Reduction)

The following modules were removed during cleanup as they were unused or redundant:

- ❌ `bin/pylib/intermediate/` - Unused IR processing
- ❌ `bin/pylib/converters/` - Unused conversion logic
- ❌ `bin/pylib/metadata_processor.py` - Functionality moved to ChatGPTConversation
- ❌ `bin/pylib/utils.py` - Unused utility functions
- ❌ `bin/pylib/schemas/ir_schemas.py` - Eliminated IR schemas
- ❌ `bin/pylib/schemas/input_schemas.py` - Replaced by input_schemas_v2.py
- ❌ Rich metadata functions - Not used in simplified architecture

## Migration from extract_chat.py

The main differences from the original `extract_chat.py`:

1. **Simplified Architecture**: No intermediate representation
2. **Chronological Processing**: Based on timestamps, not conversation tree
3. **Modular Design**: Clear separation of schemas, formatters, and processing
4. **Pydantic Integration**: Direct JSON validation and transformation
5. **Better Error Handling**: More robust validation and error reporting

## Testing

Test with the PA-Paper conversation:
```bash
python bin/extract_chat_v2.py PA-Paper/chatgpt_convo_686ab2a1-6578-8003-b0e6-79b76323e002.json -o PA-Paper/test_output.md
```

The output should include:
- Proper metadata formatting
- Chronologically ordered messages
- Correct content type handling
- Clean text formatting

## Developer Quick Reference

### Adding a New Formatter

1. Create new formatter in `bin/pylib/formatters/`
2. Inherit from `BaseFormatter`
3. Implement `format_conversation(conversation: ChatGPTConversation) -> str`
4. Add to `bin/pylib/formatters/__init__.py`

### Adding a New Content Type

1. Update `ChatGPTContent` model in `bin/pylib/schemas/input_schemas_v2.py`
2. Add `_create_*_block()` method to `ChatGPTConversation`
3. Update formatters to handle the new content type

### Custom CSS Integration

1. Create CSS file with required classes
2. Use `-c` flag: `python extract_chat_v2.py input.json -o output.html -f html -c custom.css`
3. CSS manager handles fallback to default styles

### Key Classes and Methods

- **`ChatGPTConversation`**: Main conversation container
  - `get_chronological_turns()`: Get sorted conversation turns
  - `get_metadata()`: Extract conversation metadata
  - `get_content_blocks()`: Get formatted content blocks

- **`BaseFormatter`**: Abstract base for all formatters
  - `format_conversation()`: Main formatting method
  - `validate_document()`: Validation logic

- **`CSSManager`**: Styling and theme management
  - `get_default_css_content()`: Default theme CSS
  - `get_css_content()`: Load custom or default CSS
  - `create_inline_css_style()`: Generate HTML style tags 