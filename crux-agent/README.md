# Crux Agent

Production-ready FastAPI service implementing the Crux agent with Self-Evolve algorithm.

## Features

- **Two Execution Modes**: Basic and Enhanced modes with different complexity levels
- **Self-Evolve Algorithm**: Iterative improvement through generation, evaluation, and refinement
- **Provider-Agnostic**: Support for multiple LLM providers (OpenAI, OpenRouter, etc.)
- **Async Architecture**: FastAPI + Celery for scalable async processing
- **Parallel Execution**: Run multiple problem-solving tasks simultaneously without blocking
- **Interactive Gaming**: Play engaging games while waiting for long-running computations to complete

## Directory Structure

```
crux-agent/
├── app/                          # Main application package
│   ├── __init__.py
│   ├── main.py                   # FastAPI application entry point
│   ├── settings.py               # Application configuration
│   ├── api/                      # API layer
│   │   ├── __init__.py
│   │   ├── dependencies.py       # FastAPI dependency injection
│   │   └── routers/              # API route handlers
│   │       ├── __init__.py
│   │       ├── history.py        # Solution history endpoints
│   │       ├── jobs.py           # Job status endpoints
│   │       ├── keys.py           # API key management
│   │       └── solve.py          # Problem solving endpoints
│   ├── core/                     # Core business logic
│   │   ├── __init__.py
│   │   │   ├── agents/               # AI agent implementations
│   │   │   ├── __init__.py
│   │   │   ├── base.py           # Base agent interface
│   │   │   ├── evaluator.py      # Solution evaluation agent
│   │   │   ├── generator.py      # Solution generation agent
│   │   │   ├── professor.py      # Professor-level analysis agent
│   │   │   ├── refiner.py        # Solution refinement agent
│   │   │   ├── specialist.py     # Domain specialist agent
│   │   │   └── prompts/          # Agent-specific prompts
│   │   │       ├── evaluate_prompt.py
│   │   │       ├── generator_prompt.py
│   │   │       ├── graduate_worker_prompt.py
│   │   │       ├── professor_prompt.py
│   │   │       └── refiner_prompt.py
│   │   ├── engine/               # Self-evolve algorithm engine
│   │   │   ├── __init__.py
│   │   │   └── self_evolve.py    # Core self-evolution logic
│   │   ├── orchestrators/        # Workflow orchestration
│   │   │   ├── __init__.py
│   │   │   ├── basic.py          # Basic mode orchestrator
│   │   │   └── enhanced.py       # Enhanced mode orchestrator
│   │   └── providers/            # LLM provider abstractions
│   │       ├── __init__.py
│   │       ├── base.py           # Base provider interface
│   │       ├── factory.py        # Provider factory
│   │       ├── openai.py         # OpenAI provider
│   │       └── openrouter.py     # OpenRouter provider
│   ├── schemas/                  # Pydantic data models
│   │   ├── __init__.py
│   │   ├── request.py            # API request schemas
│   │   └── response.py           # API response schemas
│   └── utils/                    # Utility functions
│       ├── __init__.py
│       └── logging.py            # Logging configuration
├── crux-mvp/                     # Next.js frontend MVP
│   ├── app/                      # Next.js app directory
│   │   ├── dashboard/            # Dashboard page
│   │   ├── game/                 # Game interface
│   │   ├── new-task/             # Task creation
│   │   ├── profile/              # User profile
│   │   ├── settings/             # Settings page
│   │   ├── task/[id]/            # Task detail view
│   │   ├── globals.css           # Global styles
│   │   ├── layout.tsx            # Root layout
│   │   └── page.tsx              # Home page
│   ├── components/               # React components
│   │   ├── theme-provider.tsx    # Theme provider
│   │   └── ui/                   # UI component library (shadcn/ui)
│   │       ├── [various UI components].tsx
│   │       └── [game components].tsx
│   ├── hooks/                    # Custom React hooks
│   ├── lib/                      # Frontend utilities
│   ├── public/                   # Static assets
│   ├── styles/                   # Additional styles
│   ├── package.json              # Frontend dependencies
│   ├── tailwind.config.ts        # Tailwind configuration
│   └── tsconfig.json             # TypeScript configuration
├── problems/                     # Problem datasets
│   ├── 2025IMO/                  # International Mathematical Olympiad 2025
│   ├── AIME_2025_15.xml          # AIME problems
│   ├── HMMT_2025_C10.xml         # Harvard-MIT Math Tournament
│   ├── TTRL.xml                  # Test-Time Reasoning Learning
│   ├── usamo_problem*.xml        # USA Mathematical Olympiad
│   └── [other problem files]
├── sql/                          # Database schema
│   └── schema.sql                # Supabase database schema
├── tests/                        # Test suite
│   ├── __init__.py
│   └── test_api.py               # API endpoint tests
├── worker.py                     # Celery worker configuration
├── pyproject.toml                # Python project configuration
├── requirements.txt              # Python dependencies
├── .env.example                  # Environment variables template
├── .env.production.example       # Production environment template
└── README.md                     # This file
```

### Key Components

- **FastAPI Backend** (`app/`): RESTful API with async support
- **Self-Evolve Engine** (`app/core/engine/`): Iterative problem-solving algorithm
- **Multi-Agent System** (`app/core/agents/`): Specialized AI agents for different tasks
- **Provider Abstraction** (`app/core/providers/`): Support for multiple LLM backends
- **Next.js Frontend** (`crux-mvp/`): Modern React-based user interface
- **Problem Datasets** (`problems/`): Mathematical competition problems for testing
- **Async Processing** (`worker.py`): Celery-based background job processing

## Quick Start

1. Clone the repository:

```bash
git clone https://github.com/your-org/crux-agent.git
cd crux-agent
```

2. Create virtual environment:

```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:

```bash
pip install -r requirements.txt
```

4. Configure environment:

```bash
cp .env.example .env
# Edit .env with your API keys and settings
```

5. Run the application:

```bash
# Start Redis (required for Celery)
redis-server
# Or install Redis if not already installed:
# macOS: brew install redis
# Ubuntu: sudo apt-get install redis-server

# Start Celery worker
python worker.py

# Start FastAPI server
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

6. (Optional) Run the frontend:

```bash
# Navigate to frontend directory
cd crux-mvp

# Install dependencies
pnpm install
# Or use npm: npm install

# Start development server
pnpm dev
# Or use npm: npm run dev

# The frontend will be available at http://localhost:3000
```

## Retry Behavior

The Crux Agent includes robust retry mechanisms for resilient API interactions:

### Retry Types

- **HTTP Retry**: Automatically retries on network timeouts and server errors with exponential backoff (1-5 seconds).
- **JSON Parsing Retry**: Retries JSON parsing failures using fresh responses for improved success rates.
- **Function Argument Parsing**: Retries parsing of function calling arguments when malformed JSON is received.

### Error Types That Trigger Retries

- `httpx.TimeoutException`: Network timeouts
- `httpx.HTTPStatusError`: HTTP 4xx/5xx server errors (excluding permanent failures)
- `json.JSONDecodeError`: Malformed JSON responses
- `ProviderError`: General provider-level errors during API calls

### Configuration

Configure retry behavior using the `max_retries` parameter when initializing providers:

```python
from app.core.providers.openai import OpenAIProvider
from app.core.providers.openrouter import OpenRouterProvider

# Configure with custom retry count
openai_provider = OpenAIProvider(
    api_key="your-api-key",
    model="gpt-4o-mini",
    max_retries=5  # Increase retries for better resilience
)

openrouter_provider = OpenRouterProvider(
    api_key="your-api-key", 
    model="mistralai/mistral-7b-instruct",
    max_retries=2  # Reduce retries for faster failures
)
```

**Default Configuration:**
- Maximum retry attempts: 3
- Backoff strategy: Exponential with random jitter
- Retry delay range: 1-5 seconds
- Fresh responses: JSON parsing retries fetch new responses on each attempt

## API Endpoints

- `POST /api/v1/solve/basic` - Basic mode solving
- `POST /api/v1/solve/enhanced` - Enhanced mode with multi-agent orchestration
- `GET /api/v1/jobs/{id}` - Check job status and results

## Development

Run tests:

```bash
pytest
```

Format code:

```bash
black .
ruff . --fix
```

## Architecture

The system is built with a modular architecture:

- **Backend**: FastAPI + Celery for async task processing with parallel execution support
- **Frontend**: Next.js with Tailwind CSS and shadcn/ui components including interactive games
- **Cache**: Redis for job queuing and result caching
- **AI Providers**: Pluggable architecture supporting OpenAI, OpenRouter, and more
- **User Experience**: Non-blocking interface allowing users to play games while tasks run in parallel

## License

MIT License - see [LICENSE](LICENSE) file for details.

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.
