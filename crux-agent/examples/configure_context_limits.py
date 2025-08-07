#!/usr/bin/env python3
"""
Configuration helper for setting up context limits in Crux Agent.

This script helps you:
1. Determine appropriate context limits for your setup
2. Test your current LMStudio configuration
3. Configure optimal settings
"""

import os
import sys

# Add the project root to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))


def detect_lmstudio_context_limit():
    """Try to detect the current LMStudio context limit."""
    
    print("=== LMStudio Context Limit Detection ===")
    
    try:
        from app.core.providers.lmstudio import LMStudioProvider
        
        # Create a test provider
        provider = LMStudioProvider(
            api_key="test",
            model="test-model"
        )
        
        # Try to get model information
        print("Attempting to connect to LMStudio...")
        
        # Note: This would require LMStudio to be running
        print("To detect your context limit:")
        print("1. Check LMStudio UI settings")
        print("2. Look for 'Context Length' or 'n_ctx' parameter")
        print("3. Common values: 2048, 4096, 8192, 16384, 32768, 65536")
        
    except Exception as e:
        print(f"Could not connect to LMStudio: {e}")
        print("Make sure LMStudio is running and accessible")


def recommend_context_settings():
    """Recommend context settings based on use case."""
    
    print("\n=== Context Limit Recommendations ===")
    
    recommendations = [
        {
            "use_case": "Simple Q&A (1-2 iterations)",
            "context_limit": 8192,
            "description": "Basic questions with minimal context accumulation"
        },
        {
            "use_case": "Standard iterative improvement (3-5 iterations)",
            "context_limit": 16384,
            "description": "Normal use case with moderate reasoning context"
        },
        {
            "use_case": "Complex problems (5-8 iterations)",
            "context_limit": 32768,
            "description": "Complex questions requiring extensive reasoning"
        },
        {
            "use_case": "Very complex problems (8+ iterations)",
            "context_limit": 65536,
            "description": "Highly complex problems with deep iterative reasoning"
        }
    ]
    
    print("Recommended settings by use case:")
    print("-" * 60)
    
    for rec in recommendations:
        print(f"Use Case: {rec['use_case']}")
        print(f"Context Limit: {rec['context_limit']:,} tokens")
        print(f"Description: {rec['description']}")
        print(f"Crux Agent Setting: max_context_tokens={int(rec['context_limit'] * 0.9)}")
        print("-" * 60)


def calculate_optimal_settings():
    """Calculate optimal settings based on your hardware."""
    
    print("\n=== Hardware-Based Recommendations ===")
    
    gpu_configs = [
        {
            "gpu": "RTX 3060/4060 (12GB VRAM)",
            "max_context": 16384,
            "recommended": 8192,
            "note": "Conservative setting for mid-range GPUs"
        },
        {
            "gpu": "RTX 3070/4070 (16GB+ VRAM)",
            "max_context": 32768,
            "recommended": 16384,
            "note": "Good balance of performance and capability"
        },
        {
            "gpu": "RTX 3080/4080/4090 (20GB+ VRAM)",
            "max_context": 65536,
            "recommended": 32768,
            "note": "High-end GPUs can handle larger contexts"
        },
        {
            "gpu": "CPU-only inference",
            "max_context": 8192,
            "recommended": 4096,
            "note": "CPU inference is slower, use smaller contexts"
        }
    ]
    
    print("Hardware-based context limit recommendations:")
    print("-" * 70)
    
    for config in gpu_configs:
        print(f"Hardware: {config['gpu']}")
        print(f"Maximum Context: {config['max_context']:,} tokens")
        print(f"Recommended: {config['recommended']:,} tokens")
        print(f"Crux Agent: max_context_tokens={int(config['recommended'] * 0.9)}")
        print(f"Note: {config['note']}")
        print("-" * 70)


def create_config_template():
    """Create a configuration template."""
    
    print("\n=== Configuration Template ===")
    
    template = '''
# Example configuration for different context limits

# Conservative (good for most setups)
iteration_manager = IterationManager(
    generator=generator,
    evaluator=evaluator,
    config=config,
    max_context_tokens=14745  # 90% of 16K tokens
)

# Standard (recommended for RTX 3070+ class GPUs)
iteration_manager = IterationManager(
    generator=generator,
    evaluator=evaluator,
    config=config,
    max_context_tokens=29491  # 90% of 32K tokens
)

# High-end (RTX 4080/4090 with plenty of VRAM)
iteration_manager = IterationManager(
    generator=generator,
    evaluator=evaluator,
    config=config,
    max_context_tokens=58982  # 90% of 64K tokens
)

# Auto-detect (uses default based on typical LMStudio setup)
iteration_manager = IterationManager(
    generator=generator,
    evaluator=evaluator,
    config=config
    # max_context_tokens defaults to 90% of 32K = 29,491 tokens
)
'''
    
    print(template)


def test_configuration():
    """Test a specific configuration."""
    
    print("\n=== Configuration Testing ===")
    
    print("To test your configuration:")
    print("1. Set your desired max_context_tokens value")
    print("2. Run a test with a complex question")
    print("3. Monitor the logs for context management messages")
    print("4. Look for lines like:")
    print("   'Context management: Kept X/Y reasoning summaries'")
    print("5. Adjust as needed based on your use case")
    
    print("\nExample test configuration:")
    print("""
from crux.self_evolve.orchestrator.iteration_manager import IterationManager

# Test with your desired limit
test_limit = 20000  # Adjust this value

iteration_manager = IterationManager(
    generator=your_generator,
    evaluator=your_evaluator,
    config=your_config,
    max_context_tokens=test_limit
)

# Monitor the logs during execution
session = iteration_manager.run_iterative_improvement("Your test question")
""")


if __name__ == "__main__":
    print("Crux Agent Context Limit Configuration Helper")
    print("=" * 50)
    
    # Run all recommendation functions
    detect_lmstudio_context_limit()
    recommend_context_settings()
    calculate_optimal_settings()
    create_config_template()
    test_configuration()
    
    print("\n" + "=" * 50)
    print("Configuration complete!")
    print("Remember to:")
    print("1. Increase LMStudio's context limit in settings if needed")
    print("2. Test with your specific use case")
    print("3. Monitor performance and adjust as needed")
