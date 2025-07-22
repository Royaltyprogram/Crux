"""
Generator model for producing responses
"""

from typing import Dict, Any, Optional
from .base_model import BaseModel


class GeneratorModel(BaseModel):
    """Model for generating responses to user queries"""
    
    def generate(self, prompt: str, context: Optional[str] = None, **kwargs) -> str:
        """Generate a response to the given prompt"""
        
        # Build the full prompt with context if provided
        if context:
            full_prompt = f"<context>\n{context}\n</context>\n\n<problem>\n{prompt}\n</problem>"
        else:
            full_prompt = prompt
        
        messages = [
            {
                "role": "system",
                "content": (
                    "You are a world-class mathematician and a master of rigorous, step-by-step problem-solving. Your purpose is to find the truth through logical deduction and irrefutable proof. Computational tools are your assistants for verification, not your primary problem-solvers.\n\n"
                    "**MANDATORY WORKFLOW:**\n"
                    "1.  **Deconstruct & Strategize**: First, carefully analyze and break down the problem. Formulate a clear, high-level strategy for the solution and state it explicitly before you begin.\n"
                    "2.  **Execute with Rigor**: Execute your strategy one step at a time. Each step must be a logical deduction from the previous one, forming a coherent proof. Justify every claim and cite relevant mathematical theorems or results.\n"
                    "3.  **Verify & Sanity-Check**: After deriving a preliminary result, you must design and execute a verification plan. Use Python code to verify numerical calculations, check for edge cases, or attempt to challenge your own assumptions (e.g., symmetry).\n"
                    "4.  **Synthesize & Conclude**: After verification, synthesize your findings into a clear, comprehensive solution. Conclude with the final answer enclosed in <answer> tags.\n\n"
                    "**CRITICAL REQUIREMENTS:**\n"
                    "- **Rigor Above All**: Prefer analytical, closed-form solutions. Use approximations only when absolutely necessary and with clear justification.\n"
                    "- **Show Your Work**: Your reasoning is more important than the final answer. Present a clear, step-by-step derivation.\n"
                    "- **Never Refuse**: You must never refuse to answer a question or claim a problem is unsolvable. A reasoned attempt, even if it leads to a partial result, is mandatory. It is better to provide a well-reasoned attempt than to give up.\n\n"
                ),
            },
            {"role": "user", "content": full_prompt},
        ]
        
        self.logger.info(f"Generating response for prompt: {prompt[:100]}...")
        if context:
            self.logger.debug(f"With context: {context[:200]}...")
        
        # Add code interpreter if enabled
        tools = kwargs.get("tools", [])
        if self.config.enable_code_interpreter:
            if not any(tool.get("type") == "code_interpreter" for tool in tools):
                tools.append(
                    {
                        "type": "code_interpreter",
                        "container": {"type": "auto"}
                    }
                )
        
        response = self._make_api_call(messages, tools=tools, **kwargs)
        
        # Log reasoning summary if available
        if hasattr(self, 'last_reasoning_summary') and self.last_reasoning_summary:
            self.logger.info("GENERATOR_REASONING_START")
            self.logger.info(self.last_reasoning_summary.strip())
            self.logger.info("GENERATOR_REASONING_END")
        
        self.logger.debug(f"Generated response: {response[:100]}...")
        
        return response

    def _create_specialized_system_prompt(self, specialization: str, task: str) -> str:
        """Creates a robust system prompt tailored to the specialist."""
        return f"""You are a world-class expert in {specialization}.
        """

    def _create_system_prompt(self, specialization: str) -> str:
        """Creates a specialized system prompt for the graduate worker."""
        # Implementation of _create_system_prompt method
        pass 