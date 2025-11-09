"""
Configurable Prompt Library for Dynamic Prompt Tree Generation
Allows SMEs to customize classification prompts without code changes
"""
import json
from pathlib import Path
from typing import Dict, List
from ..config import Config


class PromptLibrary:
    """Manages configurable prompt templates for classification"""

    def __init__(self, library_path: Path = None):
        """
        Initialize prompt library

        Args:
            library_path: Path to prompt library JSON file
        """
        if library_path is None:
            library_path = Config.POLICY_DIR / "prompt_library.json"

        self.library_path = library_path
        self.prompts = self._load_prompts()

    def _load_prompts(self) -> Dict:
        """Load prompts from configuration file"""
        if self.library_path.exists():
            with open(self.library_path, 'r') as f:
                return json.load(f)
        else:
            # Create default prompt library
            default_prompts = self._get_default_prompts()
            self._save_prompts(default_prompts)
            return default_prompts

    def _get_default_prompts(self) -> Dict:
        """Get default prompt templates"""
        return {
            "version": "1.0",
            "description": "Dynamic prompt library for document classification",
            "prompts": {
                "safety_check": {
                    "priority": 1,
                    "category": "UNSAFE",
                    "template": """
{policy_context}

VALIDATION PASS: {validation_pass}

TASK: Analyze the following document for UNSAFE content.

UNSAFE content includes:
- Violent, threatening, or harmful content
- Instructions for illegal activities
- Malware, exploits, or security vulnerabilities
- Content promoting harm to individuals or groups
- Explicitly prohibited content per enterprise policies

DOCUMENT CONTENT:
{document_content}

Respond in JSON format:
{{
    "is_unsafe": true/false,
    "confidence": 0.0-1.0,
    "reasoning": "Detailed explanation",
    "citation": "Exact quote and location if unsafe content found"
}}
""",
                    "temperature": 0.1,
                    "enabled": True
                },
                "confidential_check": {
                    "priority": 2,
                    "category": "CONFIDENTIAL",
                    "template": """
{policy_context}

VALIDATION PASS: {validation_pass}

TASK: Analyze the following document for CONFIDENTIAL content.

CONFIDENTIAL content includes:
- Trade secrets and proprietary algorithms
- Financial records and banking information
- Legal documents under attorney-client privilege
- Merger & acquisition plans
- Executive compensation details
- Source code and intellectual property
- Customer databases with high-risk PII (SSN, credit cards, medical records)

HIGH-RISK PII PATTERNS:
- SSN: XXX-XX-XXXX format
- Credit cards: 16 digits
- Bank accounts: 8-17 digits
- Medical record numbers
- Passport numbers

DOCUMENT CONTENT:
{document_content}

Respond in JSON format:
{{
    "is_confidential": true/false,
    "confidence": 0.0-1.0,
    "reasoning": "Detailed explanation citing specific evidence",
    "citation": "Exact quote and location of confidential content",
    "pii_found": ["list of PII types detected"]
}}
""",
                    "temperature": 0.1,
                    "enabled": True
                },
                "sensitive_check": {
                    "priority": 3,
                    "category": "SENSITIVE",
                    "template": """
{policy_context}

VALIDATION PASS: {validation_pass}

TASK: Analyze the following document for SENSITIVE content.

SENSITIVE content includes:
- Internal memos and communications
- Employee contact information
- Draft documents not for external distribution
- Internal project plans
- Budget information (non-executive)
- Customer feedback and survey data
- Performance reviews

MEDIUM-RISK PII PATTERNS:
- Email addresses
- Phone numbers
- Physical addresses
- Employee IDs
- Dates of birth

DOCUMENT CONTENT:
{document_content}

Respond in JSON format:
{{
    "is_sensitive": true/false,
    "confidence": 0.0-1.0,
    "reasoning": "Detailed explanation citing specific evidence",
    "citation": "Exact quote and location of sensitive content",
    "pii_found": ["list of PII types detected"]
}}
""",
                    "temperature": 0.1,
                    "enabled": True
                },
                "public_fallback": {
                    "priority": 4,
                    "category": "PUBLIC",
                    "template": """
Document contains no unsafe, confidential, or sensitive information.
Suitable for public distribution.
""",
                    "enabled": True
                }
            },
            "customization_guide": {
                "adding_new_category": "Add new prompt with unique priority and category name",
                "modifying_prompts": "Edit template field while maintaining {placeholders}",
                "temperature": "0.0-1.0, lower = more deterministic",
                "priority": "Lower number = checked first (1 = highest priority)"
            }
        }

    def _save_prompts(self, prompts: Dict):
        """Save prompts to file"""
        with open(self.library_path, 'w') as f:
            json.dump(prompts, f, indent=2)

    def get_prompt(self, prompt_name: str, **kwargs) -> str:
        """
        Get formatted prompt template

        Args:
            prompt_name: Name of prompt template
            **kwargs: Variables to insert into template

        Returns:
            Formatted prompt string
        """
        if prompt_name not in self.prompts['prompts']:
            raise ValueError(f"Prompt '{prompt_name}' not found in library")

        prompt_config = self.prompts['prompts'][prompt_name]

        if not prompt_config.get('enabled', True):
            raise ValueError(f"Prompt '{prompt_name}' is disabled")

        template = prompt_config['template']

        # Format template with provided variables
        try:
            return template.format(**kwargs)
        except KeyError as e:
            raise ValueError(f"Missing required variable for prompt: {e}")

    def get_prompt_temperature(self, prompt_name: str) -> float:
        """Get temperature setting for prompt"""
        return self.prompts['prompts'][prompt_name].get('temperature', 0.1)

    def get_classification_sequence(self) -> List[Dict]:
        """
        Get ordered sequence of classification prompts

        Returns:
            List of prompt configs sorted by priority
        """
        enabled_prompts = [
            {
                'name': name,
                'priority': config['priority'],
                'category': config['category'],
                'temperature': config.get('temperature', 0.1)
            }
            for name, config in self.prompts['prompts'].items()
            if config.get('enabled', True) and name != 'public_fallback'
        ]

        # Sort by priority (lower number = higher priority)
        return sorted(enabled_prompts, key=lambda x: x['priority'])

    def add_custom_prompt(self, name: str, category: str, template: str,
                         priority: int, temperature: float = 0.1):
        """
        Add custom prompt to library

        Args:
            name: Prompt identifier
            category: Classification category
            template: Prompt template with {placeholders}
            priority: Execution priority (lower = earlier)
            temperature: Model temperature setting
        """
        self.prompts['prompts'][name] = {
            'priority': priority,
            'category': category,
            'template': template,
            'temperature': temperature,
            'enabled': True
        }

        self._save_prompts(self.prompts)
        print(f"Added custom prompt: {name} (category: {category}, priority: {priority})")

    def update_prompt(self, name: str, **updates):
        """
        Update existing prompt configuration

        Args:
            name: Prompt to update
            **updates: Fields to update (template, temperature, enabled, etc.)
        """
        if name not in self.prompts['prompts']:
            raise ValueError(f"Prompt '{name}' not found")

        self.prompts['prompts'][name].update(updates)
        self._save_prompts(self.prompts)
        print(f"Updated prompt: {name}")

    def disable_prompt(self, name: str):
        """Disable a prompt without deleting it"""
        self.update_prompt(name, enabled=False)

    def enable_prompt(self, name: str):
        """Enable a previously disabled prompt"""
        self.update_prompt(name, enabled=True)

    def export_library(self, output_path: Path):
        """Export current prompt library"""
        with open(output_path, 'w') as f:
            json.dump(self.prompts, f, indent=2)
        print(f"Prompt library exported to: {output_path}")

    def import_library(self, input_path: Path):
        """Import prompt library from file"""
        with open(input_path, 'r') as f:
            imported = json.load(f)

        # Validate structure
        if 'prompts' not in imported:
            raise ValueError("Invalid prompt library format")

        self.prompts = imported
        self._save_prompts(self.prompts)
        print(f"Prompt library imported from: {input_path}")
