# Tiny Developer Assistant Documentation

## Configuration
### Structures

**Settings**: strict pydantic settings that configure model with default or user-defined parameters, including:
- `model_config`: from env file
- `gemini_api_key`: required for model access
- `gemini_model`: default is `gemini-3.6-flash`
- `request_timeout`: per-request timeout in seconds
- `max_retries`: retry attempts for throttling and server-side failures
- `max_snippet_chars`: rejects snippets larger than specified limit

### Dependencies

**pydantic**: used for data validation and strict type-enforcing
- `Field`: used to customize validation constraints and attach metadata
- `ValidationError`: catches data validation errors

**pydantic_settings**:
- `BaseSettings`: used to create our `Settings` class
- `SettingsConfigDict`: reads settings from system environment variables 

**core.errors**: our errors library
- `ConfigurationError`: thrown if env vars are not set up properly

### Functions
`load_settings`: builds the settings and allows command-line flags to override default model in `interface/cli.py`

`describe`: returns error message and setup instructions if `ValidationError` is raised

# Core
## LLM Client
### Structures

**StructuredLLMClient**: defines structure for the LLM agent, including system instructions, prompt, and response. 

**GeminiClient**: initializes connections to Google Gemini models

### Dependencies
**httpx**: used to handle API requests, Gemini APIs in this case

**typing**: used to define schema type placeholder and define class object without strict inheritance constraints

**genai**: official Google GenAI SDK for integrating Gemini models with structured data types and error classes

**pydantic**: `BaseModel` class used to define and validate schema for our model

**config Settings**: our model configuration settings

**core.errors**: our error library used to map genai errors

### Functions
`translate_api_error`: translates error from genai library into our defined errors i.e. `AuthenticationError`, `RateLimitError`, and `ServiceError`, and returns readable message to user

`extract`: use SDK to verify a validated response from provider; if SDK fails, validate raw JSON or throw an error if response is empty

`reject_blocked_prompt`: checks that response passes safety filters in `extract()`, otherwise raises a validation error

`reject_truncated`: checks if response is empty or was truncated due to reaching token limit, otherwise raises an error

`describe_invalid`: specifies validation error, either the model did not respond in JSON or the JSON response did not match the expected structure

`excerpt`: returns a small preview of response body use in `describe_body` error messages

`build_client`: initializes a Gemini client with model configuration settings

## Analyzer
### Structures
**AnalysisRequest**: contains the user's code snippet and any context (language, filename, focus question) 

**CodeAnalyzer**: contains LLM client info and converts `AnalysisRequest` into `CodeAnalysis` class 
- `analyze` helper function handles `AnalysisRequest` instance, builds user prompt, and returns an LLM client containing instructions, prompt, and CodeAnalysis schema
- `validate` helper function checks for empty input or max character violations

### Dependencies
**__future__.annotations**: allows forward references by converting type hints into strings

**dataclasses**: simplifies class definitions

**.config**: need config `Settings` class

**.errors**: our error library

**llm_client**: `StructuredLLMClient` protocol 

**prompts**: essential functions and prompt strings from `prompts.py`
- `SYSTEM_PROMPT`
- `CodeAnalysis`
- `build_user_prompt`

### Functions
`build_analyzer`: takes config settings and outputs CodeAnalyzer instance

## Errors
Contains exit code for every kind of error, including:
- `CodeExplainerError`: base class for defined errors of this application
- `ConfigurationError`
- `InputValidationError`
- `LLMError`: base class for errors involving LLM
- `AuthenticationError`
- `RateLimitError`
- `TimeoutError`
- `ServiceError`
- `ResponseValidationError`

(see descriptions in `core/errors.py` file)

## Prompts
### Structures
**Severity**: used to identify how strongly refactoring methods are recommended

**DocumentedBlock**: structures the documentation pieces as having the range of line numbers, a short heading label of the block, and the explanation of what the block does

**Refactoring**: structures the refactoring pieces as having a short title summary, a severity, the range of lines being referred to (if applicable), and a suggestion for changes

**CodeAnalysis**: the complete analysis structure, including the language detected, short summary/description of the code, a few key points, documentation blocks, and refactorings

### Dependencies
**enum**: enumeration library
- `Enum`: used in `Severity` class to determine refactoring recommendations

### Functions
`build_user_prompt`: takes code snippet and arguments (if they are specified) to build prompt for provider

`number_lines`: indexes code with line numbers for reference in documentation

## Interface
### Structures

### Dependencies
**sys**: handles command-line input

**textwrap**: handles text filling and wrapping for CLI view

**pathlib**: handles path tracing for user file inputs

**typing**: used for command-line arguments, takes either a specific type or None

**typer**: used to intialize CLI application and handle formatting and command-line arguments

### Functions
`version_callback`: simply prints app version if prompted by user and exits stdout

`explain`: the main function of the CLI application; takes one argument (file path or stdin), accepts optional flags, reads the code input, builds an analyzer, and submits an `AnalysisRequest` with the code and additional context

`read_source`: checks for user input and ensures that it is readable, otherwise raises an error or prompts helpful user message for incomplete entry; returns code and source name

`render`: formats and prints readable text output including all sections

`heading`: specifies text format for output heading

`section`: specifies text format for section headers

`paragraph`: specifies text format for descriptive paragraphs

`bullet`: specifies format for bullet-pointed text

## Testing
