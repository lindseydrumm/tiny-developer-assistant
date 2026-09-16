# Tiny Developer Assistant Documentation

## Configuration
### Structures

**Settings**: strict pydantic settings that configure model with default or user-defined parameters, including:
- `model_config`: from environment or .env file
- `gemini_api_key`: required for model access - no default for security reasons
- `gemini_model`: default is `gemini-3.6-flash`
- `request_timeout`: per-request timeout in seconds
- `max_retries`: max retry attempts for throttling and server-side failures
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

**StructuredLLMClient**: defines structure for the LLM agent which can be adapted to different models via subclasses
- includes system instructions, user prompt, and response schema

**GeminiClient**: initializes connections to Google Gemini models using `StructuredLLMClient` and Gemini SDK, raising errors when appropriate

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

**CodeAnalyzer**: contains LLM client info and converts `AnalysisRequest` into `CodeAnalysis` class from `prompts.py`, which is given back in the CLI output
- `analyze` helper function handles `AnalysisRequest` instance, builds user prompt, and returns an LLM client containing instructions, prompt, and CodeAnalysis schema
- `validate` helper function checks for empty input or max character violations

### Dependencies
**__future__.annotations**: allows forward references by converting type hints into strings

**dataclasses**: simplifies class definitions

**.config**: need config `Settings` class

**.errors**: our error library

**llm_client**: `StructuredLLMClient` protocol to connect to the analyzer

**prompts**: essential functions and prompt strings from `prompts.py`
- `SYSTEM_PROMPT`
- `CodeAnalysis`
- `build_user_prompt`

### Functions
`build_analyzer`: takes config settings and outputs a CodeAnalyzer object 

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
**Spinner**: a one-line status bar while provider is working, exits and erases when output or error message is generated


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
Robust tests are run on each module using assertion checks and `monkeypatch` for mock runs
To run all tests, use command
```
pytest
```
Additional testing was done with direct CLI input, using functions written in different languaages and local files.

`conftest.py`: Uses `pytest` library to initialize testing using valid analysis objects in clean environments (without env variables)

`helpers.py`: builders used by test modules without contacting network 
- `make_response`: uses `google.genai` type to construct real content response rather than mocks to be used in tests
- `analysis_payload`: a mock dict to test against CodeAnalysis class

`test_analyzer.py`: initializes a FakeClient object to run tests on data input and validation
- **TestAnalyze** checks that `CodeAnalyzer` correctly receives and passes along Client output, correctly takes in `SYSTEM_PROMPT` and schema, correctly passes along context into the prompt, and correctly numbers the lines of code
- **TestInputValidation** checks that blank or oversized is rejected before API call is made, and that proper input is accepted

`test_cli.py` uses `FakeStdin` and `StubAnalyzer` to run tests on CLI behavior
- **TestInput** checks that the CLI can read files, read stdin, recognize '-' signal for stdin, passes along input flags, overrides default settings when prompted, prompts user when waiting for stdin, and rejects unreadable files.
- **TestRendering** checks that the CLI output has all three sections, includes content, outputs proper JSON code, and handles an analysis that does not require refactoring.
- **TestErrorReporting** checks that the error exit codes match what is expected, error messages give guidance, and a missing API key is reported.

`test_config.py`: tests configuration loading and security
- **TestLoadSettings** checks for missing API key and subsequent setup instructions, API key loading from environment, API key loading from .env file, default free model use, overrides from environment, command-line preferences override defaults, empty .env key is rejected before API call, and invalid API parameters (max retries, request timeout, max snippet chars) are reported
- **TestSecretsBoundary** checks that the API key parameter in config settings is required (no default) and that the key is not in the `config.py` source code

`test_progress.py`: tests progress bar output using `FakeStream` for varying encoding and terminal settings
- **TestQuietWhenNotATerminal** checks that the spinner is properly silence (inactive) and does not crash when not in a terminal
- **TestDrawsOnATerminal** checks that the spinner animates and then erases for clean output
- **TestExceptionSafety** checks that the spinner erases and sends error message to user when an error is raised
- **TestFrameSelection** checks that fallback spinner frames are utilized on limited/unknown encoders

`test_prompts.py`: tests that the prompt is formatted correctly and contains all the important information
- **TestNumberLines** checks that lines are numbered and formatted correctly, empty input is handled, and blank lines and indentation are preserved
- **TestBuildUserPrompt** checks that the user prompt contains delimiters around code, infers unspecified language, states a supplied language, omits a filename when it is absent, and includes a focus question if supplied
- **TestSystemPrompt** checks that the system prompt forbids code execution
- **TestSchema** checks that the schema contains the three required output blocks, contains every field description, and that the provider is passed a JSON schema 

`test_response_parsing.py`: 
- **TestExtract** checks that `extract()` returns a SDK-parsed instance or valid JSON, rejects invalid JSON, rejects invalid refactoring enum value, rejects an invalid list of key points, rejects plain text prose, rejects an empty or truncated response, and rejects a blocked response for safety
- **TestTranslateApiError** checks that all genai API errors are translated into the specified actionable messages
- **TestExcerpt** checks `excerpt()` function from `llm_client.py` that code snippet is not empty, does not have extra whitespace, and is truncated with a limit

