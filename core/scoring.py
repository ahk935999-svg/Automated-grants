from datetime import UTC,date,datetime
import re

MONTHS={
    "january":1,"jan":1,"february":2,"feb":2,"march":3,"mar":3,
    "april":4,"apr":4,"may":5,"june":6,"jun":6,"july":7,"jul":7,
    "august":8,"aug":8,"september":9,"sep":9,"sept":9,"october":10,
    "oct":10,"november":11,"nov":11,"december":12,"dec":12,
}

def clamp(value):
    return max(0.0,min(100.0,float(value)))

def infer_funding(text):
    lowered=text.lower()
    if any(x in lowered for x in (
        "fully funded","fully-funded","full scholarship",
        "tuition + stipend","tuition and stipend",
    )):
        return "fully funded"
    if any(x in lowered for x in (
        "scholarship","stipend","tuition waiver","tuition-free"
    )):
        return "scholarship/partial or full"
    return None

def _valid_date(year,month,day):
    try:
        date(year,month,day)
    except ValueError:
        return None
    return f"{year:04d}-{month:02d}-{day:02d}"

def infer_deadline(text):
    patterns=(
        r"\b(20\d{2})-(0?[1-9]|1[0-2])-([0-3]?\d)\b",
        r"\b([0-3]?\d)[ /.-](0?[1-9]|1[0-2])[ /.-](20\d{2})\b",
    )
    for pattern in patterns:
        match=re.search(pattern,text)
        if not match:
            continue
        groups=match.groups()
        if len(groups[0])==4:
            value=_valid_date(int(groups[0]),int(groups[1]),int(groups[2]))
        else:
            value=_valid_date(int(groups[2]),int(groups[1]),int(groups[0]))
        if value:
            return value

    month_names="|".join(MONTHS)
    named_patterns=(
        rf"\b(?:deadline|apply by|applications? (?:close|end)\w*|closing date)"
        rf"[^.\n]{{0,50}}?\b({month_names})\s+([0-3]?\d)(?:st|nd|rd|th)?(?:,?\s+(20\d{{2}}))?\b",
        rf"\b(?:deadline|apply by|applications? (?:close|end)\w*|closing date)"
        rf"[^.\n]{{0,50}}?\b([0-3]?\d)(?:st|nd|rd|th)?\s+({month_names})\s+(20\d{{2}})\b",
    )
    for pattern in named_patterns:
        match=re.search(pattern,text,re.IGNORECASE)
        if not match:
            continue
        first,second,year=match.groups()
        if first.lower() in MONTHS:
            month,day=int(MONTHS[first.lower()]),int(second)
        else:
            day,month=int(first),int(MONTHS[second.lower()])
        if year is None:
            year=datetime.now(UTC).year
        value=_valid_date(int(year),month,day)
        if value:
            return value
    return None

def urgency_score(deadline):
    if not deadline:
        return 25.0
    try:
        days=(datetime.fromisoformat(deadline).date()-datetime.now(UTC).date()).days
    except ValueError:
        return 10.0
    if days<0:
        return 0.0
    if days<=3:
        return 100.0
    if days<=7:
        return 90.0
    if days<=14:
        return 75.0
    if days<=30:
        return 55.0
    if days<=60:
        return 35.0
    return 20.0

def funding_score(funding):
    if not funding:
        return 20.0
    text=funding.lower()
    if "fully funded" in text or "full scholarship" in text:
        return 100.0
    if any(x in text for x in ("scholarship","stipend","tuition")):
        return 70.0
    return 30.0

def profile_match(opportunity,profile):
    field=profile.get("education",{}).get("field","").lower()
    haystack=f"{opportunity.title} {opportunity.summary}".lower()
    if field and field in haystack:
        return 100.0
    hits=sum(
        1 for k in profile.get("preferences",{}).get("keywords",[])
        if k.lower() in haystack
    )
    return clamp(35+hits*15)

def _decision(overall,threshold):
    if overall>=threshold:
        return "PRIORITY"
    if overall>=45:
        return "REVIEW"
    return "LOW"

def deterministic_evaluation(opportunity,profile,eligibility,priority_threshold=70):
    match=profile_match(opportunity,profile)
    funding=funding_score(opportunity.funding)
    urgency=urgency_score(opportunity.deadline)
    completeness=70.0
    if opportunity.deadline:
        completeness+=10.0
    if opportunity.funding:
        completeness+=10.0
    if eligibility.status!="UNKNOWN":
        completeness+=10.0
    overall=clamp(
        eligibility.score*0.30+match*0.25+funding*0.20+
        urgency*0.10+50.0*0.10+completeness*0.05
    )
    return {
        "eligibility_score":eligibility.score,
        "profile_match_score":match,
        "funding_score":funding,
        "urgency_score":urgency,
        "competitiveness_score":50.0,
        "confidence_score":clamp(completeness),
        "overall_priority":overall,
        "decision":"LOW" if eligibility.status=="INELIGIBLE" else _decision(overall,priority_threshold),
        "reasons":eligibility.reasons+eligibility.blockers,
    }

def merge_ai_scores(base,ai,eligibility_status,verification_status,priority_threshold=70):
    if not ai:
        return base
    merged=dict(base)
    for key in (
        "profile_match_score","funding_score","urgency_score",
        "competitiveness_score","confidence_score"
    ):
        if isinstance(ai.get(key),(int,float)):
            merged[key]=clamp(ai[key])
    merged["eligibility_score"]=base["eligibility_score"]
    merged["overall_priority"]=clamp(
        merged["eligibility_score"]*0.30+
        merged["profile_match_score"]*0.25+
        merged["funding_score"]*0.20+
        merged["urgency_score"]*0.10+
        merged["competitiveness_score"]*0.10+
        merged["confidence_score"]*0.05
    )
    if eligibility_status=="INELIGIBLE":
        merged["decision"]="LOW"
        merged["overall_priority"]=min(merged["overall_priority"],10.0)
    else:
        merged["decision"]=_decision(merged["overall_priority"],priority_threshold)
    verification_note=[] if verification_status=="VERIFIED" else ["Destination not independently verified"]
    merged["reasons"]=list(dict.fromkeys(base.get("reasons",[])+verification_note))
    return merged
