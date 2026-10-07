from core.eligibility import assess,infer_published_eligibility
from core.models import Opportunity

def test_infer_all_nationalities_and_master():
    meta=infer_published_eligibility(
        'Open to international students from all countries for a master degree',
        'Yemeni'
    )
    assert meta['eligible_nationalities']==['*']
    assert meta['required_degree_level']=='master'

def test_inferred_eligibility_can_be_eligible():
    profile={
        'identity':{'nationality':'Yemeni'},
        'education':{'degree_level':'Bachelor'},
    }
    opportunity=Opportunity(
        'International master scholarship',
        'https://example.org/master',
        'test',
        'Open to international students from all countries for a master degree',
    )
    result=assess(opportunity,profile)
    assert result.status=='ELIGIBLE'