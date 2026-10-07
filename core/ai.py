import json
import re

def _parse_json(text):
    cleaned=text.strip()
    fenced=re.search(r"\\{.*\\}",cleaned,re.DOTALL)
    if fenced:
        cleaned=fenced.group(0)
    return json.loads(cleaned)

def _valid(data):
    keys=(
        "eligibility_score","profile_match_score","funding_score",
        "urgency_score","competitiveness_score","confidence_score",
        "overall_priority","decision"
    )
    if any(key not in data for key in keys):
        return False
    if data["decision"] not in {"PRIORITY","REVIEW","LOW"}:
        return False
    return not any(
        not isinstance(data[key],(int,float)) or not 0<=float(data[key])<=100
        for key in keys[:-1]
    )

def evaluate_with_ai(opportunity,profile,api_key):
    if not api_key:
        return None
    try:
        from google import genai
        client=genai.Client(api_key=api_key)
        prompt={
            "task":"Evaluate contextual fit. Never invent applicant facts. Return JSON only.",
            "opportunity":{
                "title":opportunity.title,"summary":opportunity.summary,
                "funding":opportunity.funding,"deadline":opportunity.deadline,
            },
            "profile":profile,
            "schema":{
                "eligibility_score":"0-100","profile_match_score":"0-100",
                "funding_score":"0-100","urgency_score":"0-100",
                "competitiveness_score":"0-100","confidence_score":"0-100",
                "overall_priority":"0-100","decision":"PRIORITY|REVIEW|LOW",
                "reasons":["string"]
            }
        }
        response=client.models.generate_content(
            model="gemini-2.5-flash",contents=json.dumps(prompt,ensure_ascii=False)
        )
        data=_parse_json(response.text)
        if not _valid(data):
            return None
        return data
    except Exception:  # noqa: BLE001
        return None
