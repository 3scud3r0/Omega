"""Cross-package host/model/tool/checker/memory boundaries; pending execution."""
import json
from omega_agent.integration import boolean_problem,boolean_agent
from omega_agent.problem import Goal
from omega_agent.runtime import ToolAuthorization
from omega_memory.episodes import Episode,EpisodeStore
from omega_memory.privacy import PrivateMemory,PrivacyPolicy
from omega_tools.capability_adapter import CapabilityAdapter
from omega_tools.memory import register_memory
from omega_security.encoding import digest,snapshot


def test_tool_observation_checker_and_episode_sink_keep_authority_in_host(tmp_path,signed_authority,events):
    verifier,mint=signed_authority
    store=EpisodeStore(tmp_path/'episodes.db')
    try:
        store.append(Episode('hint','p',{'hint':'use v0','private':'do-not-disclose'},('evidence',),'alice',sensitive=True))
        memory=PrivateMemory(store,PrivacyPolicy(lambda owner,principal,purpose,id,consent:consent=='owner-consent'),'agent')
        adapter=CapabilityAdapter(verifier,'agent',events)
        register_memory(adapter,memory,lambda id,principal:'owner-consent')
        contexts=[]
        class Model:
            def propose(self,problem,limit):
                contexts.append(snapshot(problem))
                if not problem['observations']:
                    return iter([{'kind':'tool_request','name':'memory.retrieve','arguments':{'id':'hint'}}])
                return iter([['v',0]])
        problem=boolean_problem({'id':'p','arity':1,'outputs':[0,1]})
        goal=Goal('p','match truth table','owner',3);subject=goal.subject(problem.fingerprint())
        def authorize(goal_subject,request):
            assert goal_subject==subject
            return ToolAuthorization(mint(['memory.retrieve'],subject=digest(request),id='memory-cap'))
        def observe(goal_subject,request,output):return {'hint':output['episode']['outcome']['hint']}
        agent=boolean_agent(Model(),verifier=verifier,principal='agent',audit=events,tools=adapter,
                            authorize_tool=authorize,observe_tool=observe,episode_store=store)
        result=agent.solve(problem,goal,mint(['agent.solve'],subject=subject,id='solve-cap'),limit=3)
        assert result['status']=='solved' and result['candidate']==['v',0] and result['remaining_actions']==1
        assert len(contexts)==2 and 'do-not-disclose' not in json.dumps(contexts) and 'signature' not in json.dumps(contexts)
        episode=store.get(result['run_id'])
        assert episode['sensitive'] is True and set(episode['outcome'])=={'status','problem_sha256','goal_sha256','attempts','candidate_sha256'}
        assert result['promoted'] is False
    finally:store.close()
