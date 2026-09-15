# Tiny Developer Assistant Documentation

## Configuration
### Structures

**Settings**: strict pydantic settings that configure model with default or user-defined parameters, including:
- `model_config`: from env file
- `gemini_api_key`: required for model access
- `gemini_model`
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

## Core
### LLM Client
#### Structures

**StructuredLLMClient**: defines structure for the LLM agent, including system instructions, prompt, and response. 

**GeminiClient**:

#### Dependencies
**httpx**: used to handle Gemini requests

**genai**:

**pydantic**

**config Settings**

**core.errors** 

### Analyzer
#### Structures
**AnalysisRequest**

**CodeAnalyzer** 

### Errors
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

### Prompts
#### Structures
**Severity**

**DocumentedBlock**

**Refactoring**

**CodeAnalysis**

#### Dependencies
**enum**: enumeration library
- `Enum`: used in `Severity` class to determine refactoring recommendations

#### Functions
`build_user_prompt`

`number_lines`

## Interface

## Testing
