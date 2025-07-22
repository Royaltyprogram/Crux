"""
Enhance prompts with context
"""

from typing import Optional, List
from ..utils.logger import get_logger


class ContextEnhancer:
    """Enhance prompts with evaluation context"""
    
    def __init__(self):
        self.logger = get_logger(self.__class__.__name__)
    
    def enhance_prompt(
        self, 
        original_question: str, 
        context: str,
        previous_contexts: Optional[str] = None
    ) -> str:
        """Enhance the original question with context"""
        
        self.logger.info("Enhancing prompt with context")
        
        # Build the enhanced prompt
        enhanced_parts = []
        
        # Add previous contexts if available
        if previous_contexts:
            enhanced_parts.append("<previous_contexts>")
            enhanced_parts.append(previous_contexts)
            enhanced_parts.append("</previous_contexts>")
            enhanced_parts.append("")
        
        # Add current context
        enhanced_parts.append("<current_context>")
        enhanced_parts.append(context)
        enhanced_parts.append("</current_context>")
        enhanced_parts.append("")
        
        # Add the original question
        enhanced_parts.append("Based on the context above, please answer the following question:")
        enhanced_parts.append(original_question)
        
        enhanced_prompt = "\n".join(enhanced_parts)
        
        self.logger.debug(f"Enhanced prompt: {enhanced_prompt[:300]}...")
        
        return enhanced_prompt 