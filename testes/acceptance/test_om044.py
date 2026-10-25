"""OM-044: executable checks; source delivery, not a recorded pass."""
import pytest
from omega_agent.search import search,breadth_first

def test_uniform_cost_finds_cheaper_path_and_bfs_finds_fewer_edges():
    edges={'s':[('direct','g',5),('detour','a',1)],'a':[('finish','g',1)],'g':[]}
    result=search('s',lambda s:s=='g',lambda s:edges[s],lambda s:s)
    assert result.found and result.cost==2 and result.path==('detour','finish')
    bfs=breadth_first('s',lambda s:s=='g',lambda s:((a,t) for a,t,_ in edges[s]),lambda s:s)
    assert bfs.path==('direct',)

def test_search_rejects_negative_cost():
    with pytest.raises(ValueError):search(0,lambda _:False,lambda s:[('bad',1,-1)],lambda s:s)
