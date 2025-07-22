"""
Build context from evaluation feedback
"""

from typing import List, Optional
from ..utils.logger import get_logger


class ContextBuilder:
    """Build structured context from evaluator feedback"""
    
    def __init__(self):
        self.logger = get_logger(self.__class__.__name__)
        self.context_history = []
    
    def build_context(self, evaluation_feedback: str, iteration: int) -> str:
        """Build context from evaluation feedback"""
        
        self.logger.info(f"Building context for iteration {iteration}")
        
        # Create structured context from the feedback
        context_parts = []
        
        # Add the evaluation feedback
        context_parts.append(evaluation_feedback)
        
        # Combine into final context
        context = "\n".join(context_parts)
        
        # Store in history
        self.context_history.append({
            "iteration": iteration,
            "feedback": evaluation_feedback,
            "context": context
        })
        
        self.logger.debug(f"Built context: {context[:200]}...")
        
        return context
    
    def get_cumulative_context(self) -> str:
        """Get all context from previous iterations"""
        
        if not self.context_history:
            return ""
        
        context_parts = []
        for entry in self.context_history:
            context_parts.append(entry["context"])
        
        return "\n\n".join(context_parts)
    
    def clear_history(self):
        """Clear context history"""
        self.context_history = [] 