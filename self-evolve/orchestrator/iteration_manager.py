"""
Main orchestrator for iterative improvement using prompt refinement
"""

from typing import Dict, Any, Optional, List
from dataclasses import dataclass
from datetime import datetime
import json
import os
import re

from ..models.generator_model import GeneratorModel
from ..models.evaluator_model import EvaluatorModel
from ..context_manager import ContextBuilder, ContextEnhancer, PromptRefiner
from ..config import FrameworkConfig, ModelConfig
from ..utils.logger import get_logger


@dataclass
class IterationResult:
    """Result from a single iteration"""
    iteration: int
    question: str
    refined_question: Optional[str]
    answer: str
    reasoning_summary: Optional[str]  # Generator reasoning
    evaluation_feedback: str
    evaluator_reasoning_summary: Optional[str]  # Evaluator reasoning
    refiner_reasoning_summary: Optional[str]  # Prompt refiner reasoning
    timestamp: datetime
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "iteration": self.iteration,
            "question": self.question,
            "refined_question": self.refined_question,
            "answer": self.answer,
            "reasoning_summary": self.reasoning_summary,
            "evaluation_feedback": self.evaluation_feedback,
            "evaluator_reasoning_summary": self.evaluator_reasoning_summary,
            "refiner_reasoning_summary": self.refiner_reasoning_summary,
            "timestamp": self.timestamp.isoformat()
        }


@dataclass
class IterationSession:
    """Complete iteration session results"""
    original_question: str
    final_answer: str
    iterations: List[IterationResult]
    total_iterations: int
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "original_question": self.original_question,
            "final_answer": self.final_answer,
            "total_iterations": self.total_iterations,
            "iterations": [it.to_dict() for it in self.iterations]
        }


class IterationManager:
    """Manage the iterative improvement process using prompt refinement"""
    
    def __init__(
        self,
        generator: GeneratorModel,
        evaluator: EvaluatorModel,
        config: FrameworkConfig,
        use_ai_refiner: bool = True,
        constraints: Optional[str] = None
    ):
        self.generator = generator
        self.evaluator = evaluator
        self.config = config
        self.constraints = constraints
        self.context_builder = ContextBuilder()
        self.context_enhancer = ContextEnhancer()
        
        # Initialize prompt refiner
        if use_ai_refiner:
            # AI 기반 프롬프트 개선을 위해 별도 refiner_config를 우선 사용하고,
            # 없으면 evaluator_config를 fallback으로 사용
            if getattr(config, 'refiner_config', None):
                refiner_config = config.refiner_config
            else:
                refiner_config = ModelConfig(
                    api_key=config.evaluator_config.api_key,
                    model_name=config.evaluator_config.model_name,
                    temperature=0.7
                )
            from ..models.base_model import BaseModel
            # Create a minimal wrapper for the refiner
            class RefinerModel(BaseModel):
                def generate(self, prompt: str, **kwargs) -> str:
                    return ""  # Not used directly
            
            refiner_model = RefinerModel(refiner_config)
            self.prompt_refiner = PromptRefiner(refiner_model=refiner_model)
        else:
            # 규칙 기반 프롬프트 개선
            self.prompt_refiner = PromptRefiner()
        
        self.logger = get_logger(self.__class__.__name__)
    
    def run_iterative_improvement(
        self,
        question: str
    ) -> IterationSession:
        """Run the complete iterative improvement process with prompt refinement"""
        
        self.logger.info(f"Starting iterative improvement for: {question}")
        
        # Clear any previous context and refinement history
        self.context_builder.clear_history()
        self.prompt_refiner.clear_history()
        
        iterations = []
        current_question = question  # 현재 사용할 프롬프트
        original_question = question  # 원본 질문 보존
        current_answer = None
        
        # Track recent answers for convergence check
        recent_answer_values = []
        
        # Track reasoning summaries for cross-agent context
        accumulated_reasoning = []
        
        for i in range(self.config.max_iterations):
            self.logger.info(f"Starting iteration {i + 1}")
            
            # Build context from accumulated reasoning for Generator
            reasoning_context = ""
            if accumulated_reasoning:
                reasoning_context = "\n\n---PREVIOUS REASONING CONTEXT---\n" + "\n\n".join(accumulated_reasoning)
            
            # Generate answer with current prompt and reasoning context
            if reasoning_context:
                full_prompt = current_question + reasoning_context
            else:
                full_prompt = current_question
                
            # WORKAROUND: Force streaming to reliably capture reasoning summary.
            # The non-streaming path in base_model has a bug.
            answer = self.generator.generate(full_prompt, stream=True)
            reasoning_summary = self.generator.last_reasoning_summary
            current_answer = answer
            
            # Add generator reasoning to accumulated context
            if reasoning_summary:
                accumulated_reasoning.append(f"Generator Iteration {i+1}:\n{reasoning_summary}")
            
            # Build enhanced evaluation prompt with generator reasoning
            eval_context = ""
            if reasoning_summary:
                eval_context = f"\n\n---GENERATOR REASONING CONTEXT---\nThe generator's reasoning process for this answer:\n{reasoning_summary}"
            
            # Evaluate the Q&A pair with reasoning context
            enhanced_eval_prompt = f"Question: {original_question}\n\nAnswer: {answer}{eval_context}"
            evaluation_feedback = self.evaluator.evaluate(enhanced_eval_prompt, "", self.constraints)
            evaluator_reasoning = getattr(self.evaluator, 'last_reasoning_summary', '')
            
            # Add evaluator reasoning to accumulated context
            if evaluator_reasoning:
                accumulated_reasoning.append(f"Evaluator Iteration {i+1}:\n{evaluator_reasoning}")
            
            # Log QA pair with refined prompt info
            self.logger.info(json.dumps({
                "event": "qa_pair",
                "iteration": i + 1,
                "original_question": original_question,
                "refined_question": current_question if current_question != original_question else None,
                "answer": answer,
                "evaluation_feedback": evaluation_feedback
            }, ensure_ascii=False))
            
            # Initially no refiner reasoning for this iteration
            refiner_reasoning = ""
            
            # Store iteration result with proper reasoning summaries
            iterations.append(IterationResult(
                iteration=i + 1,
                question=original_question,
                refined_question=current_question if current_question != original_question else None,
                answer=answer,
                reasoning_summary=reasoning_summary,  # Generator reasoning
                evaluation_feedback=evaluation_feedback,
                evaluator_reasoning_summary=evaluator_reasoning,  # Evaluator reasoning
                refiner_reasoning_summary=refiner_reasoning,  # Will be updated later if refiner is used
                timestamp=datetime.now()
            ))
            
            # Stop if the evaluator says the answer is good enough
            if "<stop>" in evaluation_feedback:
                self.logger.info("Evaluator has indicated to stop. Halting iterations.")
                break
            
            # Extract answer value from <answer> tags
            answer_value = self._extract_answer_value(answer)
            if answer_value is not None:
                recent_answer_values.append(answer_value)
                # Keep only last 3 answer values
                if len(recent_answer_values) > 3:
                    recent_answer_values.pop(0)
                
                # Check for convergence: 3 consecutive same answers
                if len(recent_answer_values) >= 3 and len(set(recent_answer_values[-3:])) == 1:
                    self.logger.info(f"Answer converged to '{answer_value}' for 3 consecutive iterations, stopping")
                    break
            
            # Continue iterations if not converged and not at max iterations
            if i < self.config.max_iterations - 1:
                # Build context for prompt refiner with both generator and evaluator reasoning
                refiner_context = ""
                if reasoning_summary or evaluator_reasoning:
                    refiner_context += "\n\n---REASONING CONTEXT FOR REFINEMENT---"
                    if reasoning_summary:
                        refiner_context += f"\nGenerator's reasoning:\n{reasoning_summary}"
                    if evaluator_reasoning:
                        refiner_context += f"\nEvaluator's reasoning:\n{evaluator_reasoning}"
                
                # Refine the prompt based on evaluation feedback with reasoning context
                enhanced_refine_params = {
                    "original_question": original_question + refiner_context,
                    "current_answer": answer,
                    "evaluation_feedback": evaluation_feedback,
                    "iteration": i + 1
                }
                
                refined_prompt = self.prompt_refiner.refine_prompt(**enhanced_refine_params)
                
                # Update the last iteration with refiner reasoning
                current_refiner_reasoning = getattr(self.prompt_refiner, 'last_reasoning_summary', '')
                iterations[-1].refiner_reasoning_summary = current_refiner_reasoning
                
                # Add refiner reasoning to accumulated context
                if current_refiner_reasoning:
                    accumulated_reasoning.append(f"Prompt Refiner Iteration {i+1}:\n{current_refiner_reasoning}")
                
                # Update current question for next iteration
                current_question = refined_prompt
                
                self.logger.info(f"Iteration {i + 1} complete, prompt refined for next iteration")
                self.logger.debug(f"Refined prompt preview: {refined_prompt[:200]}...")
        
        # Use the last answer as final answer
        final_answer = current_answer if current_answer else "No answer generated"
        
        session = IterationSession(
            original_question=original_question,
            final_answer=final_answer,
            iterations=iterations,
            total_iterations=len(iterations)
        )
        
        self.logger.info(
            f"Completed iterative improvement. "
            f"Total iterations: {session.total_iterations}"
        )
        
        # Log refinement history
        refinement_history = self.prompt_refiner.get_refinement_history()
        if refinement_history:
            self.logger.info(json.dumps({
                "event": "refinement_history",
                "history": refinement_history
            }, ensure_ascii=False))
        
        # Persist results under examples/results/{exec_id}/iteration{n}/qa.md
        print("DEBUG: About to call _save_example_results")
        try:
            print("DEBUG: Entering _save_example_results try block")
            self._save_example_results(session)
            print("DEBUG: _save_example_results completed successfully")
        except Exception as e:
            print(f"DEBUG: Exception in _save_example_results: {e}")
            self.logger.warning(f"Failed to save example results: {e}")
        
        print("DEBUG: Returning session")
        return session
    
    def _extract_answer_value(self, answer: str) -> Optional[str]:
        """Extract the value from <answer> tags in the response"""
        # Look for <answer>...</answer> pattern
        match = re.search(r'<answer>(.*?)</answer>', answer, re.IGNORECASE | re.DOTALL)
        if match:
            return match.group(1).strip()
        return None
    
    def _save_example_results(self, session: "IterationSession") -> None:
        """Save per-iteration Q&A pairs into the examples/logs folder.

        Directory layout:
            examples/logs/{execution_id}/
                final_answer.md
                iteration1/qa.md
                iteration2/qa.md
                ...
        """
        print("DEBUG: _save_example_results function entered")
        print(f"DEBUG: Session has {len(session.iterations)} iterations")
        
        # Use the same path as tooliense.examples.logs
        results_root = "./tooliense/logs"
        print(f"DEBUG: results_root = {results_root}")
        
        print("DEBUG: Creating directories")
        os.makedirs(results_root, exist_ok=True)
        print(f"DEBUG: Directory created successfully: {results_root}")
        print(results_root)

        # Execution identifier (timestamp-based)
        exec_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        print(f"DEBUG: exec_id = {exec_id}")
        
        exec_dir = os.path.join(results_root, exec_id)
        print(f"DEBUG: exec_dir = {exec_dir}")
        
        os.makedirs(exec_dir, exist_ok=True)
        print(f"DEBUG: Created exec_dir successfully")

        # Save each iteration
        print(f"DEBUG: Starting to save {len(session.iterations)} iterations")
        for it in session.iterations:
            print(f"DEBUG: Processing iteration {it.iteration}")
            iter_dir = os.path.join(exec_dir, f"iteration{it.iteration}")
            print(f"DEBUG: iter_dir = {iter_dir}")
            
            os.makedirs(iter_dir, exist_ok=True)
            print(f"DEBUG: Created iter_dir successfully")
            
            md_content = f"# Iteration {it.iteration}\n\n"
            md_content += "## Question (Refined)\n\n"
            md_content += f"```\n{it.refined_question}\n```\n\n"
            md_content += "## Answer\n\n"
            md_content += f"```\n{it.answer}\n```\n\n"
            if it.reasoning_summary:
                md_content += "## Generator Reasoning Summary\n\n"
                md_content += f"```\n{it.reasoning_summary}\n```\n\n"
            md_content += "## Evaluation\n\n"
            md_content += f"```\n{it.evaluation_feedback}\n```\n\n"
            if it.evaluator_reasoning_summary:
                md_content += "## Evaluator Reasoning Summary\n\n"
                md_content += f"```\n{it.evaluator_reasoning_summary}\n```\n\n"
            if it.refiner_reasoning_summary:
                md_content += "## Prompt Refiner Reasoning Summary\n\n"
                md_content += f"```\n{it.refiner_reasoning_summary}\n```\n\n"

            # Save to file
            md_path = os.path.join(iter_dir, "qa.md")
            print(f"DEBUG: md_path = {md_path}")

            print(f"DEBUG: Writing to file: {md_path}")
            with open(md_path, "w", encoding="utf-8") as f:
                f.write(md_content)
            print(f"DEBUG: Successfully wrote iteration {it.iteration} file")

        # Save final answer summary
        print("DEBUG: Saving final answer summary")
        final_md_path = os.path.join(exec_dir, "final_answer.md")
        print(f"DEBUG: final_md_path = {final_md_path}")
        
        with open(final_md_path, "w", encoding="utf-8") as f:
            f.write("# Final Answer\n\n")
            f.write("```)\n")
            f.write(session.final_answer.strip())
            f.write("\n```)\n\n")
            f.write(f"_Total iterations_: {session.total_iterations}\n")
        
        print("DEBUG: Successfully wrote final_answer.md")
        print("DEBUG: _save_example_results function completed successfully") 