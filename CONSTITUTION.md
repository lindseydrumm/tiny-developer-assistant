# AGENT CONSTITUTION: CODE EXPLAINER PROJECT

## I. PURPOSE & CORE DIRECTIVES
1. **Mission:** Build a modular Python application for developers and content teams that takes a code snippet, requests an analysis from an LLM API, and outputs structured documentation, explanations, and suggested improvements.
2. **Architecture Primacy:** Maintain strict separation of concerns. Interface, application logic, and LLM communication must remain decoupled at all times.

---

## II. SYSTEM BOUNDARIES & BEHAVIORAL GUARDS
1. **API Key Security:**
   * NEVER hardcode API keys or secrets in source code, default arguments, or tests.
   * Access configuration strictly via environment variables (e.g., using `pydantic-settings` or `python-dotenv`).
   * Include a `.env.example` file with placeholder keys; never commit actual `.env` files.
2. **Structured Output Enforcement:**
   * All LLM interaction layers MUST request and validate structured outputs (JSON/Pydantic schemas). 
   * NEVER process un-validated raw text string outputs in core logic.
3. **Execution Safety:**
   * The agent MUST NOT execute or run user-provided code snippets under any circumstances. Treat code strictly as static text inputs.

---

## III. IMPLEMENTATION & CODE QUALITY STANDARDS
1. **Modularity Requirements:**
   * `core/llm_client.py`: Handles provider instantiation, API retries, and schema validation.
   * `core/prompts.py`: Houses system prompts and schema definitions exclusively.
   * `core/analyzer.py`: Orchestrates business logic without UI dependencies.
   * `interface/`: Contains entry points for CLI
2. **Error Handling & Resilience:**
   * Gracefully handle network timeouts, rate limits, and invalid API keys.
   * Intercept schema validation failures from the LLM and return clear, actionable user feedback rather than raw stack traces.
3. **Dependencies:**
   * Keep external dependencies minimal. Standard library preferred except for core tasks (`pydantic`, `streamlit`/`typer`, `openai`/`google-genai`).

---

## IV. ACCEPTANCE CRITERIA
* [ ] The repository includes a clear `README.md` and a working `.env.example`.
* [ ] Output reliably breaks down: **Code Summary**, **Line-by-Line / Block Documentation**, and **Suggested Refactorings**.
* [ ] Code adheres to PEP 8, includes type hints across all functions, and passes basic unit tests for response parsing.
