"""
Policy RAG (Retrieval Augmented Generation) Setup
Manages Gemini File Search Store for policy knowledge base
"""
import json
import time
from pathlib import Path
from typing import Dict, List, Optional
import google.generativeai as genai
from google.ai.generativelanguage_v1beta.types import File

from ..config import Config


class PolicyRAG:
    """Manages the policy knowledge base using Gemini File Search"""

    def __init__(self):
        """Initialize Policy RAG system"""
        genai.configure(api_key=Config.GEMINI_API_KEY)
        self.policy_dir = Config.POLICY_DIR
        self.uploaded_files = []
        self.corpus_id = None

    def load_policies(self) -> Dict:
        """
        Load all policy files

        Returns:
            Dict containing all policy data
        """
        policies = {}

        # Load categories
        categories_path = self.policy_dir / "categories.json"
        if categories_path.exists():
            with open(categories_path, 'r') as f:
                policies['categories'] = json.load(f)

        # Load PII patterns
        pii_path = self.policy_dir / "pii_patterns.json"
        if pii_path.exists():
            with open(pii_path, 'r') as f:
                policies['pii_patterns'] = json.load(f)

        # Load few-shot examples
        examples_path = self.policy_dir / "few_shot_examples.json"
        if examples_path.exists():
            with open(examples_path, 'r') as f:
                policies['few_shot_examples'] = json.load(f)

        return policies

    def create_policy_document(self) -> str:
        """
        Create a comprehensive policy document for RAG

        Returns:
            Path to the generated policy document
        """
        policies = self.load_policies()

        # Create comprehensive policy text
        policy_text_parts = [
            "=" * 80,
            "ENTERPRISE DOCUMENT CLASSIFICATION POLICY",
            "=" * 80,
            "",
            "This document contains the complete policy definitions, PII patterns,",
            "and validated examples for the document classification system.",
            "",
        ]

        # Add category definitions
        if 'categories' in policies:
            policy_text_parts.append("\n" + "=" * 80)
            policy_text_parts.append("SECTION 1: CATEGORY DEFINITIONS")
            policy_text_parts.append("=" * 80 + "\n")

            for category in policies['categories']['categories']:
                policy_text_parts.append(f"\n### {category['name']} (Priority: {category['priority']})")
                policy_text_parts.append(f"\nDescription: {category['description']}")
                policy_text_parts.append(f"\nCriteria:")
                for criterion in category['criteria']:
                    policy_text_parts.append(f"  - {criterion}")

                if 'pii_indicators' in category:
                    policy_text_parts.append(f"\nPII Indicators:")
                    for pii in category['pii_indicators']:
                        policy_text_parts.append(f"  - {pii}")

                policy_text_parts.append(f"\nExamples:")
                for example in category['examples']:
                    policy_text_parts.append(f"  - {example}")

                if 'action' in category:
                    policy_text_parts.append(f"\nRequired Action: {category['action']}")

                policy_text_parts.append("")

            # Add decision tree
            if 'decision_tree' in policies['categories']:
                policy_text_parts.append("\n" + "=" * 80)
                policy_text_parts.append("CLASSIFICATION DECISION TREE")
                policy_text_parts.append("=" * 80 + "\n")
                policy_text_parts.append(policies['categories']['decision_tree']['description'])
                policy_text_parts.append("")

                for step in policies['categories']['decision_tree']['steps']:
                    policy_text_parts.append(f"\nStep {step['step']}: Check for {step['check']}")
                    policy_text_parts.append(f"Question: {step['question']}")
                    policy_text_parts.append(f"If YES: {step['if_yes']}")
                    policy_text_parts.append(f"If NO: {step['if_no']}")

        # Add PII patterns
        if 'pii_patterns' in policies:
            policy_text_parts.append("\n" + "=" * 80)
            policy_text_parts.append("SECTION 2: PII DETECTION PATTERNS")
            policy_text_parts.append("=" * 80 + "\n")

            pii_data = policies['pii_patterns']['pii_patterns']

            # High risk PII
            policy_text_parts.append("\n### HIGH RISK PII (CONFIDENTIAL)")
            policy_text_parts.append(f"Description: {pii_data['high_risk']['description']}\n")
            for pattern in pii_data['high_risk']['patterns']:
                policy_text_parts.append(f"- {pattern['name']}: {pattern['severity']}")
                policy_text_parts.append(f"  Examples: {', '.join(pattern['examples'])}")

            # Medium risk PII
            policy_text_parts.append("\n### MEDIUM RISK PII (SENSITIVE)")
            policy_text_parts.append(f"Description: {pii_data['medium_risk']['description']}\n")
            for pattern in pii_data['medium_risk']['patterns']:
                policy_text_parts.append(f"- {pattern['name']}: {pattern['severity']}")
                policy_text_parts.append(f"  Examples: {', '.join(pattern['examples'])}")

            # Financial indicators
            policy_text_parts.append("\n### FINANCIAL/CONFIDENTIAL INDICATORS")
            policy_text_parts.append("Keywords indicating financial or confidential content:")
            for keyword in pii_data['financial_indicators']['keywords']:
                policy_text_parts.append(f"  - {keyword}")

            # Technical indicators
            policy_text_parts.append("\n### TECHNICAL/CONFIDENTIAL INDICATORS")
            policy_text_parts.append("Keywords indicating technical or confidential content:")
            for keyword in pii_data['technical_indicators']['keywords']:
                policy_text_parts.append(f"  - {keyword}")

        # Add few-shot examples
        if 'few_shot_examples' in policies:
            policy_text_parts.append("\n" + "=" * 80)
            policy_text_parts.append("SECTION 3: VALIDATED CLASSIFICATION EXAMPLES")
            policy_text_parts.append("=" * 80 + "\n")
            policy_text_parts.append("These are SME-validated examples demonstrating correct classification:\n")

            for idx, example in enumerate(policies['few_shot_examples']['few_shot_examples'], 1):
                policy_text_parts.append(f"\n### Example {idx}: {example['document_type']}")
                policy_text_parts.append(f"Content: {example['content_snippet']}")
                policy_text_parts.append(f"Classification: {example['classification']}")
                policy_text_parts.append(f"Confidence: {example['confidence']}")
                policy_text_parts.append(f"Reasoning: {example['reasoning']}")
                policy_text_parts.append(f"Citations: {example['citations']}")
                policy_text_parts.append("")

        # Save to file
        policy_doc_path = self.policy_dir / "compiled_policy.txt"
        with open(policy_doc_path, 'w') as f:
            f.write("\n".join(policy_text_parts))

        return str(policy_doc_path)

    def upload_policy_to_gemini(self) -> str:
        """
        Upload policy document to Gemini File API

        Returns:
            File URI for use in RAG queries
        """
        # Create compiled policy document
        policy_path = self.create_policy_document()

        print(f"Uploading policy document to Gemini: {policy_path}")

        # Upload file
        uploaded_file = genai.upload_file(
            path=policy_path,
            display_name="Enterprise Classification Policy"
        )

        # Wait for processing
        print(f"Waiting for file processing...")
        while uploaded_file.state.name == "PROCESSING":
            time.sleep(2)
            uploaded_file = genai.get_file(uploaded_file.name)

        if uploaded_file.state.name == "FAILED":
            raise ValueError(f"File processing failed: {uploaded_file.state.name}")

        print(f"Policy uploaded successfully: {uploaded_file.uri}")
        self.uploaded_files.append(uploaded_file)

        return uploaded_file.uri

    def get_policy_context(self) -> str:
        """
        Get policy context for prompts

        Returns:
            Formatted policy context string
        """
        policies = self.load_policies()

        context_parts = [
            "You have access to the Enterprise Classification Policy document via RAG.",
            "Use this policy to ground your classification decisions.",
            "",
            "Key Categories (in priority order):",
        ]

        if 'categories' in policies:
            for cat in policies['categories']['categories']:
                context_parts.append(f"  {cat['priority']}. {cat['name']}: {cat['description']}")

        context_parts.append("")
        context_parts.append("IMPORTANT: Follow the decision tree in the policy document:")
        context_parts.append("  1. Check UNSAFE first (highest priority)")
        context_parts.append("  2. Then check CONFIDENTIAL")
        context_parts.append("  3. Then check SENSITIVE")
        context_parts.append("  4. Default to PUBLIC only if none of the above apply")

        return "\n".join(context_parts)

    def add_hitl_example(self, document_content: str, classification: str,
                        reasoning: str, citations: str, document_type: str = "HITL Validated"):
        """
        Add a new SME-validated example to the knowledge base

        Args:
            document_content: Content snippet
            classification: Validated classification
            reasoning: SME reasoning
            citations: Citation information
            document_type: Type of document
        """
        examples_path = self.policy_dir / "few_shot_examples.json"

        # Load existing examples
        with open(examples_path, 'r') as f:
            data = json.load(f)

        # Add new example
        new_example = {
            'document_type': document_type,
            'content_snippet': document_content[:500],  # Limit length
            'classification': classification,
            'confidence': 1.0,  # SME validation = 100% confidence
            'reasoning': reasoning,
            'citations': citations
        }

        data['few_shot_examples'].append(new_example)

        # Save updated examples
        with open(examples_path, 'w') as f:
            json.dump(data, f, indent=2)

        print(f"Added HITL example to knowledge base. Total examples: {len(data['few_shot_examples'])}")

        # Re-upload policy to update RAG
        self.upload_policy_to_gemini()

    def clear_ingested_documents(self):
        """
        Clear all HITL-validated examples from the knowledge base
        """
        examples_path = self.policy_dir / "few_shot_examples.json"

        # Load existing examples
        with open(examples_path, 'r') as f:
            data = json.load(f)

        # Clear examples
        data['few_shot_examples'] = []

        # Save updated examples
        with open(examples_path, 'w') as f:
            json.dump(data, f, indent=2)

        print("Cleared all HITL examples from the knowledge base.")

        # Re-upload policy to update RAG
        self.upload_policy_to_gemini()
