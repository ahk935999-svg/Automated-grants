from core.action_queue import build_action_queue

def test_action_queue_prioritizes_human_gates():
    items=build_action_queue([
        {
            'id':1,'title':'Top opportunity','url':'https://example.org/a',
            'application_state':'INTERVENTION',
            'evaluation':{'overall_priority':92,'decision':'PRIORITY'},
            'application_plan':{'gates':['missing_document'],'missing_documents':['cv'],'next_action':'Upload CV'},
        },
        {
            'id':2,'title':'Lower opportunity','url':'https://example.org/b',
            'application_state':'READY',
            'evaluation':{'overall_priority':75,'decision':'PRIORITY'},
            'application_plan':{'gates':[],'missing_documents':[],'next_action':'Review'},
        },
    ])
    assert [item['tier'] for item in items]==['P0','P1']
    assert items[0]['action_type']=='HUMAN_GATE'
    assert items[0]['missing_documents']==['cv']