import json
from .models import Evaluation

def evaluate_with_ai(opportunity, profile, api_key):
    if not api_key:
        return None
    try:
        from google import genai
        client = genai.Client(api_key=api_key)
        prompt = {
            "task": "Evaluate this opportunity against the applicant profile. Return JSON only.",
            "opportunity": {
                "title": opportunity.title,
                "summary": opportunity.summary,
                "funding": opportunity.funding,
                "deadline": opportunity.deadline
            },
            "profile": profile,
            "schema": {
                "eligibility_score": "0-100",
                "profile_match_score": "0-100",
                "funding_score": "0-100",
                "urgency_score": "0-100",
                "competitiveness_score": "0-100",
                "confidence_score": "0-100",
                "overall_priority": "0-100",
                "decision": "PRIORITY|REVIEW|LOW",
                "reasons": ["string"]
            }
        }
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=json.dumps(prompt)
        )
        return Evaluation(**json.loads(response.text))
    except Exception:
        return None
