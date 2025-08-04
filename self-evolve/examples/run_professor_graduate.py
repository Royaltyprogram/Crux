#!/usr/bin/env python3
"""
Run Professor + Graduate Self-Evolve System with Responses API
Updated to support the new enhanced system
"""

import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def main():
    """Main execution function with enhanced error handling"""
    try:
        from ..examples.professor_graduate_example import (
            professor_graduate_example,
        )
        
        # Check for required environment variables
        if not os.getenv("OPENAI_API_KEY"):
            print("❌ Error: OPENAI_API_KEY environment variable is required")
            print("Please set it with: export OPENAI_API_KEY='your-api-key'")
            sys.exit(1)
        
        else:
            # Run full example
            print("🚀 Running full Professor + Graduate Self-Evolve System...")
            print("💡 This uses o3 models by default and may take several minutes")
            professor_graduate_example()
            
    except ImportError as e:
        print(f"❌ Import Error: {e}")
        print("💡 Make sure you're running this from the correct directory")
        print("💡 Try: python -m self-evolve.examples.run_professor_graduate")
        sys.exit(1)
        
    except KeyboardInterrupt:
        print("\n⏹️ Interrupted by user")
        sys.exit(0)
        
    except Exception as e:
        print(f"❌ Error: {e}")
        print(f"💡 Error type: {type(e).__name__}")
        sys.exit(1)


def print_help():
    """Print usage information"""
    print("""
📖 Professor + Graduate Self-Evolve System

Usage:
    python run_professor_graduate.py [options]

Options:
    (none)     Run full example with o3 models (default)

Environment Variables:
    OPENAI_API_KEY       Required: Your OpenAI API key
    PROFESSOR_MODEL      Optional: Model for Professor (default: o3)
    EVALUATOR_MODEL      Optional: Model for Evaluator (default: o3)
    SIMPLE_MODEL         Optional: Model for simple tests (default: gpt-4o)
    PROBLEM_FILE         Optional: Custom problem file path

Examples:
    # Full system with o3 models
    export OPENAI_API_KEY="your-key"
    python run_professor_graduate.py

    # Quick test with gpt-4o
    python run_professor_graduate.py --simple

    # Test basic functionality
    python run_professor_graduate.py --test

    # Use custom models
    export PROFESSOR_MODEL="gpt-4o"
    export EVALUATOR_MODEL="gpt-4o"
    python run_professor_graduate.py

Features:
    ✅ OpenAI Responses API integration
    ✅ Stateful conversation management
    ✅ Native function calling
    ✅ Code interpreter integration
    ✅ Self-evolving specialists
    ✅ Performance metrics
    ✅ Comprehensive logging

For more information, see: examples/professor_graduate_README.md
""")


if __name__ == "__main__":
    main() 