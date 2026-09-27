import re
import logging
from typing import List, Tuple
from fastapi import HTTPException
from adapters.base import ChatMessage
from config import settings

logger = logging.getLogger("gateway.middleware.guardrails")

# Common PII Regex Patterns
EMAIL_PATTERN = re.compile(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,7}\b')
PHONE_PATTERN = re.compile(r'\b(?:\+?\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b')
SSN_PATTERN = re.compile(r'\b\d{3}-\d{2}-\d{4}\b')
CREDIT_CARD_PATTERN = re.compile(r'\b(?:\d{4}[-\s]?){3}\d{4}\b')

# Prompt Injection & Jailbreak Heuristics
INJECTION_PATTERNS = [
    re.compile(r'ignore\s+(all\s+)?(previous|prior|above)\s+instructions', re.IGNORECASE),
    re.compile(r'you\s+are\s+now\s+in\s+developer\s+mode', re.IGNORECASE),
    re.compile(r'disregard\s+(all\s+)?(safety|system)\s+guidelines', re.IGNORECASE),
    re.compile(r'jailbreak\s+mode', re.IGNORECASE),
    re.compile(r'act\s+as\s+DAN', re.IGNORECASE),
    re.compile(r'bypass\s+(all\s+)?content\s+filters', re.IGNORECASE),
]

class Guardrails:
    def sanitize_pii(self, text: str) -> Tuple[str, bool]:
        """Redacts sensitive PII from prompt text"""
        modified = False

        if EMAIL_PATTERN.search(text):
            text = EMAIL_PATTERN.sub("[EMAIL_REDACTED]", text)
            modified = True

        if PHONE_PATTERN.search(text):
            text = PHONE_PATTERN.sub("[PHONE_REDACTED]", text)
            modified = True

        if SSN_PATTERN.search(text):
            text = SSN_PATTERN.sub("[SSN_REDACTED]", text)
            modified = True

        if CREDIT_CARD_PATTERN.search(text):
            text = CREDIT_CARD_PATTERN.sub("[CARD_REDACTED]", text)
            modified = True

        return text, modified

    def check_prompt_injection(self, text: str) -> bool:
        """Returns True if potential prompt injection detected"""
        for pattern in INJECTION_PATTERNS:
            if pattern.search(text):
                return True
        return False

    def process_messages(self, messages: List[ChatMessage]) -> Tuple[List[ChatMessage], bool]:
        """
        Validates messages for safety and redacts PII.
        Raises HTTPException 400 if prompt injection is detected.
        """
        if not settings.GUARDRAILS_ENABLED:
            return messages, False

        processed_messages = []
        any_pii_redacted = False

        for msg in messages:
            content = msg.content

            # Prompt injection check
            if self.check_prompt_injection(content):
                logger.warning(f"Prompt injection pattern detected in input: {content[:100]}...")
                raise HTTPException(
                    status_code=400,
                    detail="Guardrails Violation: Prompt injection or jailbreak attempt detected in request input."
                )

            # PII Redaction
            sanitized_content, redacted = self.sanitize_pii(content)
            if redacted:
                any_pii_redacted = True

            processed_messages.append(
                ChatMessage(
                    role=msg.role,
                    content=sanitized_content,
                    name=msg.name
                )
            )

        return processed_messages, any_pii_redacted

guardrails = Guardrails()
