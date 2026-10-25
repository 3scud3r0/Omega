"""OM-071: executable checks; source delivery, not a recorded pass."""
from omega_memory.episodes import Episode,EpisodeStore

def test_episodes_roundtrip_deduplicate_version_and_reopen(tmp_path):
    path=tmp_path/'episodes.db';store=EpisodeStore(path)
    original=Episode('e','task',{'status':'failed'},('sha',),'owner')
    assert store.append(original)==1 and store.append(original)==1
    assert store.append(Episode('e','task',{'status':'solved'},('sha2',),'owner'))==2
    store.close();store=EpisodeStore(path)
    assert store.get('e',version=1)['outcome']['status']=='failed'
    assert store.get('e')['outcome']['status']=='solved';store.close()
