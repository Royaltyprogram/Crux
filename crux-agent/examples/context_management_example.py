#!/usr/bin/env python3
"""
Example demonstrating token-aware context management in the Crux Agent system.

This example shows how to:
1. Set custom context limits
2. Monitor context usage
3. Test rolling window behavior with long iterations
"""

import os
import sys

# Add the project root to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from app.core.providers.lmstudio import LMStudioProvider
from crux.self_evolve.models.generator_model import GeneratorModel
from crux.self_evolve.models.evaluator_model import EvaluatorModel
from crux.self_evolve.orchestrator.iteration_manager import IterationManager
from crux.self_evolve.config import FrameworkConfig, ModelConfig


def create_test_config():
    """Create configuration for testing context management."""
    return FrameworkConfig(
        max_iterations=10,  # Allow more iterations to test context limits
        generator_config=ModelConfig(
            api_key="test-key",  # LMStudio often doesn't need a real key
            model_name="your-model-name",  # Replace with your actual model
            temperature=0.7
        ),
        evaluator_config=ModelConfig(
            api_key="test-key",
            model_name="your-model-name",  # Replace with your actual model
            temperature=0.3
        )
    )


def test_context_management():
    """Test the token-aware context management system."""
    
    print("=== Context Management Test ===")
    
    # Create configuration
    config = create_test_config()
    
    # Create models
    generator = GeneratorModel(config.generator_config)
    evaluator = EvaluatorModel(config.evaluator_config)
    
    # Test different context limits
    context_limits = [
        5000,   # Very small - should truncate quickly
        15000,  # Small - should truncate after a few iterations
        30000,  # Default - should handle moderate iterations
        50000,  # Large - should handle many iterations
    ]
    
    test_question = """
    Explain the concept of quantum entanglement in detail, including:
    1. The basic physics principles
    2. How entanglement is created
    3. Applications in quantum computing
    4. Current research challenges
    
    Please provide a comprehensive answer with examples.
    """
    
    for limit in context_limits:
        print(f"\n--- Testing with {limit:,} token limit ---")
        
        # Create iteration manager with specific context limit
        iteration_manager = IterationManager(
            generator=generator,
            evaluator=evaluator,
            config=config,
            max_context_tokens=limit
        )
        
        # Log the context limit being used
        print(f"Context limit set to: {iteration_manager.max_context_tokens:,} tokens")
        
        try:
            # Run a few iterations to test context management
            session = iteration_manager.run_iterative_improvement(test_question)
            
            print(f"Completed {session.total_iterations} iterations successfully")
            print(f"Final answer length: {len(session.final_answer)} characters")
            
        except Exception as e:
            print(f"Error with {limit:,} token limit: {e}")
            continue


def test_context_increase():
    """Test increasing LMStudio context limit and continuing past normal limits."""
    
    print("\n=== Testing Context Limit Increase ===")
    
    # You can increase your LMStudio context limit like this:
    print("""
    To increase your LMStudio context limit:
    
    1. Open LMStudio
    2. Go to the model settings/configuration
    3. Look for 'Context Length' or 'Max Context' setting
    4. Increase from 32,768 to 65,536 (or higher if your GPU allows)
    5. Note: Higher context uses more VRAM and runs slower
    
    Then update this script to use the higher limit:
    """)
    
    # Example with higher context limit
    config = create_test_config()
    generator = GeneratorModel(config.generator_config)
    evaluator = EvaluatorModel(config.evaluator_config)
    
    # Use 90% of 64K tokens (if you increased LMStudio to 64K)
    high_context_manager = IterationManager(
        generator=generator,
        evaluator=evaluator,
        config=config,
        max_context_tokens=int(65536 * 0.9)  # ~59K tokens
    )
    
    print(f"High context limit: {high_context_manager.max_context_tokens:,} tokens")
    
    # This should allow many more iterations before context management kicks in
    complex_question = """
    Design a complete machine learning system for predicting stock prices, including:
    1. Data collection and preprocessing strategies
    2. Feature engineering approaches
    3. Model selection (traditional ML vs deep learning)
    4. Backtesting methodology
    5. Risk management considerations
    6. Deployment architecture
    7. Monitoring and maintenance procedures
    
    Provide detailed explanations for each component with code examples where appropriate.
    """
    
    print("Running with high context limit (this may take longer)...")
    try:
        session = high_context_manager.run_iterative_improvement(complex_question)
        print(f"High context test completed: {session.total_iterations} iterations")
    except Exception as e:
        print(f"High context test failed: {e}")


def monitor_token_usage():
    """Example of how to monitor token usage during iterations."""
    
    print("\n=== Token Usage Monitoring Example ===")
    
    config = create_test_config()
    generator = GeneratorModel(config.generator_config)
    
    # Test the token counting method
    test_texts = [
        "Short text",
        "This is a medium length text that should consume a moderate number of tokens for testing purposes.",
        """This is a very long text passage that would be typical of the kind of reasoning summaries
        and context that accumulates during iterative improvement sessions. It includes detailed
        explanations, multiple sentences, and complex vocabulary that would translate to a
        significant number of tokens when processed by the language model. This type of content
        is exactly what the context management system needs to handle efficiently."""
    ]
    
    print("Token counting examples:")
    for i, text in enumerate(test_texts, 1):
        # Test token counting via the iteration manager's method
        iteration_manager = IterationManager(
            generator=generator,
            evaluator=None,  # Not needed for token counting
            config=config
        )
        
        token_count = iteration_manager._count_tokens(text)
        print(f"Text {i}: {len(text)} chars → {token_count} tokens (ratio: {len(text)/token_count:.1f})")


if __name__ == "__main__":
    print("Crux Agent Context Management Example")
    print("=====================================")
    
    # Note: Update the model names in create_test_config() before running
    print("\nBefore running this example:")
    print("1. Make sure LMStudio is running")
    print("2. Update model names in create_test_config()")
    print("3. Optionally increase LMStudio context limit in settings")
    
    # Uncomment the tests you want to run:
    
    # Test basic token counting
    monitor_token_usage()
    
    # Test context management with different limits
    # test_context_management()
    
    # Test with increased context limit
    # test_context_increase()
    
    print("\nExample completed!")
