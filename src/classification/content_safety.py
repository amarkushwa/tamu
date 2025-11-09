"""
Enhanced Content Safety Module
Validates content for child safety, hate speech, violence, and unsafe material
"""
import re
from typing import Dict, List, Tuple
import google.generativeai as genai

from ..config import Config


class ContentSafetyValidator:
    """
    Multi-layer content safety validation with specific checks for:
    - Child safety (COPPA compliance)
    - Hate speech and discrimination
    - Violence and threats
    - Sexually explicit content
    - Dangerous activities
    """

    def __init__(self):
        """Initialize safety validator"""
        genai.configure(api_key=Config.GEMINI_API_KEY)
        self.model = genai.GenerativeModel(Config.GEMINI_MODEL)

        # Pattern-based safety checks (fast pre-screening)
        self.unsafe_patterns = self._build_unsafe_patterns()

    def _build_unsafe_patterns(self) -> Dict[str, List[str]]:
        """Build regex patterns for unsafe content detection"""
        return {
            'violence': [
                r'\b(kill|murder|assault|attack|weapon|gun|knife|bomb|explosive)\b',
                r'\b(violence|violent|harm|hurt|injure|wound)\b',
                r'\b(threat|threatening|terroris[mt]|radical)\b'
            ],
            'hate_speech': [
                r'\b(hate|hatred|racist|racism|sexist|sexism|discrimination)\b',
                r'\b(slur|derogatory|offensive|insult)\b',
                r'\b(supremac[yi]|extremis[mt]|bigot)\b'
            ],
            'explicit_content': [
                r'\b(porn|pornograph[yi]|xxx|explicit|sexual|nude|naked)\b',
                r'\b(adult content|nsfw|mature content)\b'
            ],
            'child_safety': [
                r'\b(child|children|minor|kid|teen|adolescent|youth)\b.*\b(abuse|exploitation|harm|danger)',
                r'\b(predator|grooming|inappropriate contact)\b',
                r'\b(age.*verification|parental.*consent)\b'
            ],
            'dangerous_activities': [
                r'\b(suicide|self-harm|self harm)\b',
                r'\b(drug|narcotic|illegal substance)\b',
                r'\b(instruct.*\w*.*harm|how to.*\w*.*damage)\b'
            ],
            'illegal_content': [
                r'\b(illegal|unlawful|criminal|contraband)\b',
                r'\b(fraud|scam|phishing|malware)\b',
                r'\b(piracy|counterfeit|stolen)\b'
            ]
        }

    def validate(self, content: str, document_id: str) -> Dict:
        """
        Comprehensive content safety validation

        Args:
            content: Document content to validate
            document_id: Document identifier

        Returns:
            Safety validation result
        """
        result = {
            'is_safe': True,
            'safety_score': 1.0,
            'violations': [],
            'categories_flagged': [],
            'recommendations': [],
            'child_safe': True,
            'detail': {}
        }

        # Layer 1: Fast pattern-based screening
        pattern_results = self._pattern_based_check(content)
        if pattern_results['flagged']:
            result['is_safe'] = False
            result['violations'].extend(pattern_results['violations'])
            result['categories_flagged'] = pattern_results['categories']

        # Layer 2: AI-powered deep safety analysis
        ai_results = self._ai_safety_check(content)
        if not ai_results['is_safe']:
            result['is_safe'] = False
            result['violations'].extend(ai_results['violations'])
            result['categories_flagged'].extend(ai_results['categories'])
            result['safety_score'] = min(result['safety_score'], ai_results['safety_score'])

        # Layer 3: Child safety specific validation
        child_safety = self._child_safety_check(content)
        result['child_safe'] = child_safety['is_child_safe']
        if not child_safety['is_child_safe']:
            result['is_safe'] = False
            result['violations'].append(child_safety['reason'])

        # Generate recommendations
        if not result['is_safe']:
            result['recommendations'] = self._generate_recommendations(result['categories_flagged'])

        # Remove duplicates
        result['categories_flagged'] = list(set(result['categories_flagged']))
        result['violations'] = list(set(result['violations']))

        result['detail'] = {
            'pattern_check': pattern_results,
            'ai_check': ai_results,
            'child_safety_check': child_safety
        }

        return result

    def _pattern_based_check(self, content: str) -> Dict:
        """Fast regex-based safety check"""
        content_lower = content.lower()
        flagged_categories = []
        violations = []

        for category, patterns in self.unsafe_patterns.items():
            for pattern in patterns:
                matches = re.findall(pattern, content_lower, re.IGNORECASE)
                if matches:
                    flagged_categories.append(category)
                    violations.append(f"{category}: Pattern match found - {matches[:3]}")
                    break  # Only report once per category

        return {
            'flagged': len(flagged_categories) > 0,
            'categories': flagged_categories,
            'violations': violations
        }

    def _ai_safety_check(self, content: str) -> Dict:
        """
        AI-powered deep safety analysis using Gemini

        Returns:
            Safety assessment from AI
        """
        # Limit content length for safety check
        content_sample = content[:5000] if len(content) > 5000 else content

        prompt = f"""
You are a content safety validator. Analyze the following content for safety violations.

SAFETY CATEGORIES TO CHECK:
1. Violence/Threats: Content promoting or describing violence, threats, weapons
2. Hate Speech: Discriminatory, racist, sexist, or hateful content
3. Explicit Content: Sexually explicit or pornographic material
4. Child Safety: Content inappropriate for children or child exploitation
5. Dangerous Activities: Instructions for self-harm, illegal drugs, dangerous acts
6. Illegal Content: Fraud, malware, piracy, criminal activities

CONTENT TO ANALYZE:
{content_sample}

Respond in JSON format:
{{
    "is_safe": true/false,
    "safety_score": 0.0-1.0,
    "violations": ["list of specific violations found"],
    "categories": ["list of safety categories violated"],
    "severity": "low/medium/high/critical",
    "reasoning": "detailed explanation"
}}
"""

        try:
            response = self.model.generate_content(
                prompt,
                generation_config=genai.GenerationConfig(
                    temperature=0.0,  # Consistent safety checks
                    response_mime_type="application/json"
                )
            )

            import json
            result = json.loads(response.text)
            return result

        except Exception as e:
            print(f"AI safety check error: {e}")
            # Conservative: flag as potentially unsafe if check fails
            return {
                'is_safe': False,
                'safety_score': 0.5,
                'violations': [f'Safety check failed: {str(e)}'],
                'categories': ['check_error'],
                'severity': 'medium',
                'reasoning': 'Unable to complete safety validation'
            }

    def _child_safety_check(self, content: str) -> Dict:
        """
        Specific child safety validation (COPPA compliance)

        Returns:
            Child safety assessment
        """
        content_sample = content[:3000] if len(content) > 3000 else content

        prompt = f"""
You are a child safety expert. Determine if the following content is safe for children under 13 (COPPA compliance).

CHILD SAFETY CRITERIA:
- No inappropriate or mature content
- No collection of personal information from minors
- No content that could endanger children
- No violence, explicit material, or scary content
- Educational or age-appropriate material only

CONTENT:
{content_sample}

Respond in JSON format:
{{
    "is_child_safe": true/false,
    "age_appropriate": "all_ages/13+/17+/18+",
    "concerns": ["list of child safety concerns"],
    "reason": "brief explanation"
}}
"""

        try:
            response = self.model.generate_content(
                prompt,
                generation_config=genai.GenerationConfig(
                    temperature=0.0,
                    response_mime_type="application/json"
                )
            )

            import json
            result = json.loads(response.text)
            return result

        except Exception as e:
            print(f"Child safety check error: {e}")
            # Conservative: mark as not child-safe if check fails
            return {
                'is_child_safe': False,
                'age_appropriate': '18+',
                'concerns': ['Unable to verify child safety'],
                'reason': f'Safety check error: {str(e)}'
            }

    def _generate_recommendations(self, flagged_categories: List[str]) -> List[str]:
        """Generate safety recommendations based on violations"""
        recommendations = []

        if 'violence' in flagged_categories:
            recommendations.append("Content contains violent or threatening material. Mark as UNSAFE and require escalation.")

        if 'hate_speech' in flagged_categories:
            recommendations.append("Content contains hate speech or discriminatory language. Immediate rejection required.")

        if 'explicit_content' in flagged_categories:
            recommendations.append("Explicit or adult content detected. Mark as UNSAFE and restrict access.")

        if 'child_safety' in flagged_categories:
            recommendations.append("Child safety concerns identified. URGENT: Escalate to compliance team immediately.")

        if 'dangerous_activities' in flagged_categories:
            recommendations.append("Content promotes dangerous activities. Mark as UNSAFE and consider reporting.")

        if 'illegal_content' in flagged_categories:
            recommendations.append("Potentially illegal content detected. Legal review required.")

        if not recommendations:
            recommendations.append("General safety violation detected. Review required before classification.")

        return recommendations

    def get_safety_report(self, validation_result: Dict) -> str:
        """
        Generate human-readable safety report

        Args:
            validation_result: Result from validate()

        Returns:
            Formatted safety report
        """
        report_lines = [
            "=" * 80,
            "CONTENT SAFETY VALIDATION REPORT",
            "=" * 80,
            f"Overall Safety Status: {'✓ SAFE' if validation_result['is_safe'] else '✗ UNSAFE'}",
            f"Safety Score: {validation_result['safety_score']:.2%}",
            f"Child Safe: {'✓ Yes' if validation_result['child_safe'] else '✗ No'}",
            ""
        ]

        if validation_result['violations']:
            report_lines.append("VIOLATIONS DETECTED:")
            for violation in validation_result['violations']:
                report_lines.append(f"  • {violation}")
            report_lines.append("")

        if validation_result['categories_flagged']:
            report_lines.append("FLAGGED CATEGORIES:")
            for category in validation_result['categories_flagged']:
                report_lines.append(f"  • {category.replace('_', ' ').title()}")
            report_lines.append("")

        if validation_result['recommendations']:
            report_lines.append("RECOMMENDATIONS:")
            for rec in validation_result['recommendations']:
                report_lines.append(f"  → {rec}")
            report_lines.append("")

        report_lines.append("=" * 80)

        return "\n".join(report_lines)
