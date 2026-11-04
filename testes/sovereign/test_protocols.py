import struct
from copy import deepcopy
import pytest
from omega_sovereign.models import call
from omega_sovereign.raft_store import Node


LOCAL=[10,0,0,1];REMOTE=[10,0,0,2]
def checksum(data):
    if len(data)%2:data+=b'\0'
    total=sum(struct.unpack('!'+str(len(data)//2)+'H',data))
    while total>65535:total=(total&65535)+(total>>16)
    return total^65535


def segment(seq,ack,flags,payload=b'',window=4096):
    tcp=struct.pack('!HHIIBBHHH',9000,8000,seq,ack,80,flags,window,0,0)+payload
    pseudo=bytes(REMOTE+LOCAL)+struct.pack('!BBH',0,6,len(tcp))
    tcp=tcp[:16]+struct.pack('!H',checksum(pseudo+tcp))+tcp[18:]
    ip=struct.pack('!BBHHHBBH',69,0,20+len(tcp),0,16384,64,6,0)+bytes(REMOTE+LOCAL)
    ip=ip[:10]+struct.pack('!H',checksum(ip))+ip[12:]
    return list(ip+tcp)


def tcp(events,**kwargs):
    return call('tcp',dict(local_ip=LOCAL,remote_ip=REMOTE,local_port=8000,remote_port=9000,isn=100,events=events,**kwargs))
def incoming(seq,ack,flags,payload=b''):return {'kind':'segment','packet':segment(seq,ack,flags,payload)}
def handshake():return [incoming(500,0,2),incoming(501,101,16)]


def test_tcp_passive_open_exact_wire_checksums_and_stream():
    result=tcp(handshake()+[incoming(501,101,24,b'hello'),{'kind':'send','payload':list(b'world')},incoming(506,106,16)])
    assert result['state']=='ESTABLISHED' and bytes(result['received'])==b'hello'
    assert result['snd_next']==106 and result['rcv_next']==506
    assert result['sent'][0][33]==18
    for raw in result['sent']:
        data=bytes(raw);assert checksum(data[:20])==0
        assert checksum(bytes(LOCAL+REMOTE)+struct.pack('!BBH',0,6,len(data)-20)+data[20:])==0


def test_tcp_bad_packet_checksum_and_sequence_dropped():
    bad=segment(501,101,24,b'bad');bad[-1]^=1
    result=tcp(handshake()+[{'kind':'segment','packet':bad},incoming(999,101,24,b'bad')])
    assert result['received']==[] and result['dropped']==2


def test_tcp_retry_close_timewait_and_sequence_wrap():
    result=tcp([incoming(4294967295,0,2),{'kind':'tick','now':1000}])
    assert result['retransmissions']==1 and result['rcv_next']==0
    result=tcp(handshake()+[{'kind':'close'},incoming(501,102,16),incoming(501,102,17),{'kind':'tick','now':60000}])
    assert result['state']=='CLOSED'
    result=tcp([incoming(500,0,2)]+[{'kind':'tick','now':t} for t in (1000,3000,7000,15000,31000,63000)])
    assert result['state']=='CLOSED' and result['retransmissions']==5


def test_tcp_obeys_peer_window_and_does_not_ack_rejected_fin_payload():
    with pytest.raises(RuntimeError):
        tcp([{'kind':'segment','packet':segment(500,0,2,window=0)},
             {'kind':'segment','packet':segment(501,101,16,window=0)}, {'kind':'send','payload':[1]}])
    result=tcp(handshake()+[incoming(501,101,24,b'x'*1460),incoming(1961,101,24,b'y'*1460),
                             incoming(3421,101,24,b'z'*1176),incoming(4597,101,25,b'!')])
    assert result['state']=='ESTABLISHED' and result['rcv_next']==4597
    assert len(result['received'])==4096 and result['dropped']==1


@pytest.mark.parametrize('events',[[{'kind':'send','payload':[1]}], [{'kind':'segment','packet':[256]}],
                                [{'kind':'tick','now':2},{'kind':'tick','now':1}], [{'kind':'close'}]])
def test_tcp_invalid_inputs_rejected(events):
    with pytest.raises(Exception):tcp(events)


def raft(events,hard=None,self=0):
    request={'members':[0,1,2],'self':self,'events':events}
    if hard is not None:request['hard_state']=hard
    return call('raft',request)


def leader():return [{'kind':'timeout'},{'kind':'vote_response','sender':1,'term':1,'granted':1}]


def test_raft_election_replication_and_recovery():
    result=raft(leader()+[{'kind':'propose','command':'set x 7'},{'kind':'append_response','sender':1,'term':1,'success':1,'match':1}])
    hard=result['hard_state'];assert result['role']=='leader' and hard['commit']==1
    assert result['requires_durable_barrier']==1
    follower=raft([{'kind':'append','sender':0,'term':1,'prev_index':0,'prev_term':0,'entries':hard['log'],'leader_commit':1}],self=1)
    assert follower['hard_state']['log']==hard['log'] and follower['hard_state']['commit']==1
    recovered=raft([],hard)
    assert recovered['hard_state']==hard and recovered['role']=='follower'


def test_raft_duplicate_votes_and_old_term_do_not_commit():
    result=call('raft',{'members':[0,1,2,3,4],'self':0,'events':[{'kind':'timeout'}]+[{'kind':'vote_response','sender':1,'term':1,'granted':1}]*3})
    assert result['role']=='candidate'
    hard={'term':2,'vote':-1,'log':[[1,'old']],'commit':0}
    result=raft([{'kind':'timeout'},{'kind':'vote_response','sender':1,'term':3,'granted':1},
                 {'kind':'append_response','sender':1,'term':3,'success':1,'match':1}],hard)
    assert result['hard_state']['commit']==0
    result=raft([{'kind':'vote_request','sender':1,'term':1,'last_index':0,'last_term':0},
                 {'kind':'vote_request','sender':2,'term':1,'last_index':0,'last_term':0}])
    assert [v['granted'] for v in result['responses_after_persist']]==[1,0]


def test_raft_cannot_overwrite_committed_prefix_or_commit_unmatched_suffix():
    hard={'term':1,'vote':-1,'log':[[1,'committed'],[1,'extra']],'commit':1}
    result=raft([{'kind':'append','sender':1,'term':2,'prev_index':0,'prev_term':0,'entries':[[2,'bad']],'leader_commit':1}],hard)
    assert result['hard_state']['log']==hard['log'] and result['responses_after_persist'][0]['success']==0
    result=raft([{'kind':'append','sender':1,'term':2,'prev_index':1,'prev_term':1,'entries':[],'leader_commit':2}],hard)
    assert result['hard_state']['commit']==1


def test_raft_term_stepdown_and_conflict_repair():
    hard={'term':1,'vote':0,'log':[[1,'kept'],[1,'discarded']],'commit':1}
    result=raft([{'kind':'append','sender':1,'term':2,'prev_index':1,'prev_term':1,'entries':[[2,'replacement']],'leader_commit':2}],hard)
    assert result['hard_state']['log']==[[1,'kept'],[2,'replacement']]
    assert result['hard_state']['commit']==2 and result['role']=='follower'


def test_raft_rejects_unknown_peer_and_impossible_matches():
    with pytest.raises(Exception):raft([{'kind':'vote_request','sender':99,'term':1,'last_index':0,'last_term':0}])
    with pytest.raises(Exception):raft(leader()+[{'kind':'append_response','sender':1,'term':1,'success':1,'match':256}])


def test_durable_raft_roles_across_requests_and_crash_restart(tmp_path):
    path=tmp_path/'node'
    with Node(path,[0,1,2],0) as node:
        assert node.step(leader())['role']=='leader'
        assert node.step([{'kind':'propose','command':'persist me'}])['hard_state']['commit']==0
        result=node.step([{'kind':'append_response','sender':1,'term':1,'success':1,'match':1}])
        assert result['hard_state']['commit']==1
        with pytest.raises(BlockingIOError):Node(path,[0,1,2],0)
    with Node(path,[0,1,2],0) as recovered:
        result=recovered.step([])
        assert result['role']=='follower' and result['hard_state']['commit']==1
    (path/'state.json').write_text('{}')
    with Node(path,[0,1,2],0) as corrupted:
        with pytest.raises(ValueError):corrupted.step([])


def test_no_raft_reply_if_durability_fails(tmp_path,monkeypatch):
    import omega_sovereign.raft_store as store
    node=Node(tmp_path/'node',[0,1,2],0)
    def fail(_):raise OSError('Simulated power-loss during fsync')
    monkeypatch.setattr(store.os,'fsync',fail)
    with pytest.raises(OSError):node.step([{'kind':'timeout'}])
    assert node.closed
    with pytest.raises(ValueError):node.step([])
