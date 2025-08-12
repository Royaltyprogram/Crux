#!/usr/bin/env python3
"""
Example demonstrating environment-based context limit configuration.

This shows how to easily switch between different context limits (32K, 64K, etc.)
by changing environment variables in your .env file.
"""

import os
import sys

# Add the project root to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from app.settings import settings


def show_current_configuration():
    """Display the current context configuration from environment variables."""
    
    print("=== Current Context Configuration ===")
    print(f"Context Limit: {settings.lmstudio_context_limit:,} tokens")
    print(f"Response Reserve: {settings.lmstudio_response_reserve:,} tokens")
    print(f"Summarization Threshold: {settings.lmstudio_summarization_threshold:.1%}")
    print(f"Available for Context: {settings.lmstudio_context_limit - settings.lmstudio_response_reserve:,} tokens")
    
    # Show what this means in practice
    available = settings.lmstudio_context_limit - settings.lmstudio_response_reserve
    threshold_usage = int(available * settings.lmstudio_summarization_threshold)
    
    print(f"\nContext Management Behavior:")
    print(f"- Uses full context up to {available:,} tokens")
    print(f"- Warns at high usage when > {threshold_usage:,} tokens ({settings.lmstudio_summarization_threshold:.0%})")
    print(f"- Triggers intelligent summarization when exceeding {available:,} tokens")


def show_environment_examples():
    """Show examples of different .env configurations."""
    
    print("\n=== Environment Configuration Examples ===")
    
    configs = [
        {
            "name": "Standard (32K tokens)",
            "context_limit": 32768,
            "use_case": "Most LMStudio setups, good for moderate complexity",
            "description": "Default configuration"
        },
        {
            "name": "Large (64K tokens)", 
            "context_limit": 65536,
            "use_case": "High-end GPUs with plenty of VRAM",
            "description": "Handles very complex problems with deep reasoning"
        },
        {
            "name": "Extra Large (128K tokens)",
            "context_limit": 131072,
            "use_case": "Specialized setups with massive context needs",
            "description": "For extremely complex multi-step problems"
        },
        {
            "name": "Compact (16K tokens)",
            "context_limit": 16384,
            "use_case": "Limited VRAM or faster responses",
            "description": "More aggressive summarization, faster processing"
        }
    ]
    
    for config in configs:
        available = config["context_limit"] - 1000  # Assuming 1000 token reserve
        print(f"\n{config['name']}:")
        print(f"  .env setting: LMSTUDIO_CONTEXT_LIMIT={config['context_limit']}")
        print(f"  Available context: {available:,} tokens")
        print(f"  Use case: {config['use_case']}")
        print(f"  Description: {config['description']}")


def show_switching_instructions():
    """Show how to switch between different configurations."""
    
    print("\n=== How to Switch Context Limits ===")
    
    print("1. Edit your .env file:")
    print("   # Change this line:")
    print("   LMSTUDIO_CONTEXT_LIMIT=32768")
    print("   # To one of:")
    print("   LMSTUDIO_CONTEXT_LIMIT=65536    # For 64K context")
    print("   LMSTUDIO_CONTEXT_LIMIT=131072   # For 128K context")
    print("   LMSTUDIO_CONTEXT_LIMIT=16384    # For 16K context")
    
    print("\n2. Make sure your LMStudio server is configured to match:")
    print("   - Open LMStudio")
    print("   - Go to model settings/configuration")
    print("   - Set 'Context Length' or 'n_ctx' to the same value")
    print("   - Restart your model if needed")
    
    print("\n3. Restart your Crux Agent application to pick up the new settings")
    
    print("\n4. Monitor the logs to see context management in action:")
    print("   - Look for: 'Context usage high: X/Y tokens'")
    print("   - Look for: 'LLM summarization: X -> Y tokens'")
    print("   - Look for: 'Context management: Kept X/Y reasoning summaries'")


def demonstrate_calculation():
    """Show how the context calculations work."""
    
    print("\n=== Context Calculation Example ===")
    
    # Example scenario
    question_tokens = 500
    reasoning_per_iteration = 25000  # Your typical large reasoning
    
    available = settings.lmstudio_context_limit - settings.lmstudio_response_reserve
    
    print(f"Scenario: Question ({question_tokens} tokens) + Large reasoning ({reasoning_per_iteration:,} tokens/iteration)")
    print(f"Available context space: {available:,} tokens")
    
    # Calculate how many full iterations fit
    space_for_reasoning = available - question_tokens
    full_iterations = space_for_reasoning // reasoning_per_iteration
    
    print(f"Space for reasoning: {space_for_reasoning:,} tokens")
    print(f"Full iterations that fit: {full_iterations}")
    
    if full_iterations < 2:
        print("⚠️  After 1-2 iterations, context management will kick in:")
        print("   - Most recent reasoning kept intact")
        print("   - Older reasoning intelligently summarized")
        print("   - System continues running smoothly")
    else:
        print(f"✅ Can handle {full_iterations} iterations before needing context management")


def show_advanced_tuning():
    """Show advanced tuning options."""
    
    print("\n=== Advanced Tuning Options ===")
    
    print("Optional .env settings for fine-tuning:")
    print("# Trigger summarization earlier (default 0.8 = 80%)")
    print("LMSTUDIO_SUMMARIZATION_THRESHOLD=0.6  # Summarize at 60% usage")
    print("")
    print("# Reserve more/less space for responses (default 1000)")
    print("LMSTUDIO_RESPONSE_RESERVE=2000  # More conservative")
    print("LMSTUDIO_RESPONSE_RESERVE=500   # More aggressive")
    
    print("\nWhat these do:")
    print("- Lower threshold = Earlier summarization, more room for new reasoning")
    print("- Higher reserve = Safer but less context space")
    print("- Lower reserve = More context but risk of truncated responses")


if __name__ == "__main__":
    print("Crux Agent - Environment-Based Context Configuration")
    print("=" * 55)
    
    show_current_configuration()
    show_environment_examples()
    show_switching_instructions()
    demonstrate_calculation()
    show_advanced_tuning()
    
    print(f"\n{'=' * 55}")
    print("Ready to handle large reasoning with intelligent context management!")
    print("Simply change LMSTUDIO_CONTEXT_LIMIT in your .env file to switch between configurations.")
