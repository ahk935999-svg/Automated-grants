def build_action_queue(opportunities):
    queue=[]
    for item in opportunities:
        evaluation=item.get('evaluation',{})
        state=item.get('application_state','')
        gates=item.get('application_plan',{}).get('gates',[])
        missing=item.get('application_plan',{}).get('missing_documents',[])
        priority=float(evaluation.get('overall_priority',0) or 0)
        decision=evaluation.get('decision','REVIEW')
        if state=='INTERVENTION':
            action_type='HUMAN_GATE'
            tier='P0' if priority>=85 else 'P1' if priority>=70 else 'P2'
        elif decision=='PRIORITY':
            action_type='REVIEW_PRIORITY'
            tier='P1'
        else:
            continue
        queue.append({
            'tier':tier,
            'action_type':action_type,
            'opportunity_id':item.get('id'),
            'title':item.get('title'),
            'url':item.get('url'),
            'priority':priority,
            'decision':decision,
            'state':state,
            'gates':gates,
            'missing_documents':missing,
            'next_action':item.get('application_plan',{}).get('next_action',''),
        })
    order={'P0':0,'P1':1,'P2':2}
    return sorted(queue,key=lambda item:(order.get(item['tier'],9),-item['priority']))