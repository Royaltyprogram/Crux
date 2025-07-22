"""
Example usage of the Context-Based Iterative LLM Framework
"""

import os
import json
from datetime import datetime
from ..config import FrameworkConfig, ModelConfig
from ..models import GeneratorModel, EvaluatorModel
from ..orchestrator import IterationManager
from ..utils import setup_logging


def openai_example():
    """Example with the OpenAI second letter question using prompt refinement"""
    
    # Setup structured JSON logging
    setup_logging(log_level="INFO", log_file="./tooliense/logs/openai_example.jsonl", json_logs=True)
    
    # Configure models
    config = FrameworkConfig(
        generator_config=ModelConfig(
            api_key=os.getenv("OPENAI_API_KEY"),
            model_name=os.getenv("GENERATOR_MODEL", "o3"),
            enable_code_interpreter=True,
        ),
        evaluator_config=ModelConfig(
            api_key=os.getenv("OPENAI_API_KEY"),
            model_name=os.getenv("EVALUATOR_MODEL", "o3"),
            enable_code_interpreter=True,
        ),
        max_iterations=5
    )
    
    # Initialize components
    generator = GeneratorModel(config.generator_config)
    evaluator = EvaluatorModel(config.evaluator_config)
    
    # Create iteration manager with AI-based prompt refinement
    manager = IterationManager(generator, evaluator, config, use_ai_refiner=True)
    
    # Run example
    # Load problem from XML file
    try:
        with open("./tooliense/examples/problems/frontier_math_hard.xml", "r", encoding="utf-8") as f:
            question = f.read()
            question:str = question + "solve this problem with consulting the graduate_specialist and perfect mathematical rigor."
    except FileNotFoundError:
        print("Warning: ./examples/problems/usamo_problem1.xml not found. Using default problem.")
        question = """
<problem id="ord_density" points="4">
    <statement>
        For a positive integer <var>n</var>, let 
        <math><![CDATA[v_p(n)]]></math> denote the largest integer 
        <math><![CDATA[v]]></math> such that 
        <math><![CDATA[p^{\,v}\mid n]]></math>.  
        For a prime <var>p</var> and an integer <var>a</var> with 
        <math><![CDATA[a \not\equiv 0 \pmod{p}]]></math>, let 
        <math><![CDATA[\operatorname{ord}_p(a)]]></math> denote the smallest positive integer 
        <math><![CDATA[o]]></math> such that 
        <math><![CDATA[a^{\,o}\equiv 1 \pmod{p}]]></math>.  
        <br/><br/>
        For <math><![CDATA[x>0]]></math>, define
        <math><![CDATA[
            \operatorname{ord}_{p,x}(a)\;=\;
            \prod_{\substack{q\le x\\ q\text{ prime}}} q^{\,v_q\bigl(\operatorname{ord}_p(a)\bigr)}
            \;\;\prod_{\substack{q> x\\ q\text{ prime}}} q^{\,v_q(p-1)}\,.
        ]]></math>
        <br/><br/>
        Let <math><![CDATA[S_x]]></math> be the set of primes <var>p</var> satisfying
        <math><![CDATA[
            \operatorname{ord}_{p,x}(2)\;>\;\operatorname{ord}_{p,x}(3).
        ]]></math>
        <br/><br/>
        Denote by <math><![CDATA[d_x]]></math> the natural density of <math><![CDATA[S_x]]></math> in the primes,
        <math><![CDATA[
            d_x \;=\;
            \lim_{t\to\infty}\;
            \frac{\bigl|\{\,p\le t : p\in S_x\}\bigr|}
                 {\bigl|\{\,p\le t : p\text{ prime}\}\bigr|}.
        ]]></math>
        Define
        <math><![CDATA[
            d_\infty \;=\; \lim_{x\to\infty} d_x.
        ]]></math>
    </statement>

    <target>
        <expression><![CDATA[
            \bigl\lfloor 10^{6}\,d_\infty \bigr\rfloor
        ]]></expression>
    </target>
</problem>
"""
    
    print(f"Question: {question}")
    print("-" * 50)
    
    # Run iterative improvement with prompt refinement
    session = manager.run_iterative_improvement(question)
    
    # --- Save session results to JSON file ---
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_path = f"./tooliense/logs/openai_example_session_{timestamp}.json"
    try:
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(session.to_dict(), f, ensure_ascii=False, indent=2)
        print(f"Session results saved to {output_path}")
    except Exception as e:
        print(f"[Warning] Failed to save session results: {e}")
    
    # Display results
    print(f"\nFinal Answer: {session.final_answer}")
    print(f"Total Iterations: {session.total_iterations}")
    
    # Show iteration details with prompt refinement
    print(f"\nIteration Details:")
    for iteration in session.iterations:
        print(f"\n--- Iteration {iteration.iteration} ---")
        
        # Show refined prompt if available
        if iteration.refined_question:
            print(f"Refined Prompt: {iteration.refined_question[:300]}...")
        else:
            print("Using original prompt")
            
        print(f"Answer: {iteration.answer[:300]}...")
        print(f"Evaluation Feedback: {iteration.evaluation_feedback[:300]}...")
    
    # Show prompt refinement history
    print("\n\n=== Prompt Refinement History ===")
    refinement_history = manager.prompt_refiner.get_refinement_history()
    if refinement_history:
        for refinement in refinement_history:
            print(f"\nIteration {refinement['iteration']}:")
            print(f"Based on feedback: {refinement['feedback'][:200]}...")
            print(f"Refined to: {refinement['refined'][:400]}...")
    else:
        print("No prompt refinements were made.")


if __name__ == "__main__":
    # Run examples
    print("=== OpenAI Example ===")
    openai_example()
