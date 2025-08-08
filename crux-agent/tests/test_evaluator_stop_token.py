"""
Unit tests for EvaluatorAgent._detect_stop_token method.

Tests the logic for detecting standalone <stop> tokens while ignoring
those embedded within sentences or when errors are present.
"""
import pytest
from unittest.mock import MagicMock

from app.core.agents.evaluator import EvaluatorAgent


class TestEvaluatorStopToken:
    """Test cases for the _detect_stop_token method."""

    def setup_method(self):
        """Set up test fixtures."""
        # Create a mock provider for the evaluator
        mock_provider = MagicMock()
        mock_provider.count_tokens.return_value = 100
        
        # Initialize evaluator with mock provider
        self.evaluator = EvaluatorAgent(provider=mock_provider)

    def test_detect_stop_token_standalone_should_stop(self):
        """Test that standalone <stop> token on its own line triggers stop."""
        text = "The answer is complete.\n<stop>"
        result = self.evaluator._detect_stop_token(text)
        assert result is True

    def test_detect_stop_token_with_whitespace_should_stop(self):
        """Test that <stop> token surrounded by whitespace triggers stop."""
        text = "The solution looks good. <stop> "
        result = self.evaluator._detect_stop_token(text)
        assert result is True

    def test_detect_stop_token_at_start_should_stop(self):
        """Test that <stop> token at the beginning triggers stop."""
        text = "<stop> - evaluation complete"
        result = self.evaluator._detect_stop_token(text)
        assert result is True

    def test_detect_stop_token_minimal_output_should_stop(self):
        """Test case (b): minimal output ending with <stop> should trigger stop."""
        text = "Good answer. <stop>"
        result = self.evaluator._detect_stop_token(text)
        assert result is True

    def test_detect_stop_token_embedded_in_sentence_should_not_stop(self):
        """Test case (a): echoed guideline with <stop> inside sentence should NOT stop."""
        text = "Remember to use <stop> token when evaluation is complete, but this is just guidance."
        result = self.evaluator._detect_stop_token(text)
        assert result is False

    def test_detect_stop_token_within_word_should_not_stop(self):
        """Test that <stop> token within a word should NOT trigger stop."""
        text = "The process is non<stop>ping and continuous."
        result = self.evaluator._detect_stop_token(text)
        assert result is False

    def test_detect_stop_token_with_error_should_not_stop(self):
        """Test that <stop> token with error mentioned should NOT trigger stop."""
        text = "There was an error in the calculation. <stop>"
        result = self.evaluator._detect_stop_token(text)
        assert result is False

    def test_detect_stop_token_with_error_uppercase_should_not_stop(self):
        """Test that <stop> token with ERROR (uppercase) should NOT trigger stop."""
        text = "Found an ERROR in the logic. <stop>"
        result = self.evaluator._detect_stop_token(text)
        assert result is False

    def test_detect_stop_token_with_error_mixed_case_should_not_stop(self):
        """Test that <stop> token with Error (mixed case) should NOT trigger stop."""
        text = "Detected an Error in processing. <stop>"
        result = self.evaluator._detect_stop_token(text)
        assert result is False

    def test_detect_stop_token_no_token_should_not_stop(self):
        """Test that text without <stop> token should NOT trigger stop."""
        text = "This is a complete evaluation without the stop token."
        result = self.evaluator._detect_stop_token(text)
        assert result is False

    def test_detect_stop_token_empty_text_should_not_stop(self):
        """Test that empty text should NOT trigger stop."""
        text = ""
        result = self.evaluator._detect_stop_token(text)
        assert result is False

    def test_detect_stop_token_whitespace_only_should_not_stop(self):
        """Test that whitespace-only text should NOT trigger stop."""
        text = "   \n\t  "
        result = self.evaluator._detect_stop_token(text)
        assert result is False

    def test_detect_stop_token_multiline_standalone_should_stop(self):
        """Test that <stop> token on its own line in multiline text triggers stop."""
        text = """The evaluation is complete.
All criteria have been met.

<stop>
"""
        result = self.evaluator._detect_stop_token(text)
        assert result is True

    def test_detect_stop_token_multiline_embedded_should_not_stop(self):
        """Test that <stop> token embedded in sentence within multiline text should NOT stop."""
        text = """The evaluation process requires you to use the <stop> token 
when you are finished, but for now we continue analyzing.
More content here."""
        result = self.evaluator._detect_stop_token(text)
        assert result is False

    def test_detect_stop_token_with_punctuation_should_stop(self):
        """Test that <stop> token followed by punctuation triggers stop."""
        text = "Evaluation finished <stop>."
        result = self.evaluator._detect_stop_token(text)
        assert result is True

    def test_detect_stop_token_with_comma_should_stop(self):
        """Test that <stop> token followed by comma triggers stop."""
        text = "Analysis complete <stop>, moving to next phase."
        result = self.evaluator._detect_stop_token(text)
        assert result is True

    def test_task_requirement_a_echoed_guideline_should_not_stop(self):
        """Test case from task: echoed guideline with <stop> inside a sentence → should_stop=False."""
        text = "Remember that you should use the <stop> token when evaluation is complete."
        result = self.evaluator._detect_stop_token(text)
        assert result is False

    def test_task_requirement_b_minimal_output_should_stop(self):
        """Test case from task: minimal output "…<stop>" → should_stop=True."""
        text = "Good evaluation. <stop>"
        result = self.evaluator._detect_stop_token(text)
        assert result is True


if __name__ == "__main__":
    # Allow running the test directly
    pytest.main([__file__, "-v"])
