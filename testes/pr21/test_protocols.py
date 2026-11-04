from copy import deepcopy
from pathlib import Path
import struct
import hashlib
import pytest
from hypothesis import given,settings,strategies as st
from omega_sovereign.models import call
from omega_sovereign.bft import key,public,sign,experiment
from omega_sovereign.network import experiment as network


KEYS=[key(hashlib.sha256(f'unit-{i}'.encode()).digest()) for i in range(4)]
MEMBERS=[public(k) for k in KEYS]
def message(sender,phase,value='a'*64,round=0,pol=-1):
    b={'chain':'unit','height':0,'round':round,'phase':phase,'value':value,'parent':'0'*64,'pol_round':pol,'sender':MEMBERS[sender]}
    return sign(b,KEYS[sender])
def event(m):return {'kind':'message','message':m}
def bft(events,state=None):
    r={'members':MEMBERS,'self':MEMBERS[3],'chain':'unit','events':events}
    if state is not None:r['state']=state
    return call('bft',r)


def test_bft_replays_malformed_and_forged_votes_do_not_form_quorum():
    vote=message(0,'precommit');forged=deepcopy(message(1,'precommit'));forged['signature']=vote['signature']
    result=bft([event(vote)]*4+[event(forged),event({'body':{},'signature':'0'*128})])
    assert result['state']['height']==0 and len(result['state']['votes'])==1 and result['rejected']==2


def test_bft_commits_only_matching_height_parent_and_distinct_signatures():
    result=bft([event(message(i,'precommit')) for i in range(3)])
    assert result['state']['height']==1 and result['state']['parent']=='a'*64
    cert=result['commits'][0]
    assert bft([{'kind':'commit','entry':cert}])['state']['height']==1
    damaged=deepcopy(cert);damaged['parent']='b'*64
    assert bft([{'kind':'commit','entry':damaged}])['state']['height']==0


def test_bft_lock_persists_and_newer_valid_pol_can_unlock():
    locked=bft([event(message(i,'prevote')) for i in range(3)])['state']
    assert locked['locked_round']==0 and locked['locked_value']=='a'*64
    denied=bft([{'kind':'timeout'},event(message(1,'propose','b'*64,round=1))],locked)
    assert denied['state']['prevote']=='nil' and denied['state']['locked_value']=='a'*64
    proposal=message(2,'propose','b'*64,round=2,pol=1)
    proposal['certificate']=[message(i,'prevote','b'*64,round=1) for i in range(3)]
    allowed=bft([{'kind':'timeout'},{'kind':'timeout'},event(proposal)],locked)
    assert allowed['state']['prevote']=='b'*64
    bad=deepcopy(proposal);bad['certificate']=[bad['certificate'][0]]*3
    assert bft([{'kind':'timeout'},{'kind':'timeout'},event(bad)],locked)['state']['prevote']=='nil'


def test_four_real_processes_with_byzantine_equivocation_and_delays(tmp_path):
    report=experiment(tmp_path/'cluster')
    assert len(set(report['processes']))==4 and report['converged'] and report['equivocations']>=3
    assert report['rejected']>=3


def test_two_baremetal_nodes_authenticate_and_reject_wrong_key(tmp_path):
    report=network(tmp_path/'good')
    assert report['authenticated'],report['nodes']
    bad=network(tmp_path/'wrong-key',tamper_key=True)
    assert not bad['authenticated'] and any('FAIL' in node['stdout'] for node in bad['nodes'])


@given(st.binary(min_size=0,max_size=60),st.integers(0,15))
@settings(derandomize=True,database=None,max_examples=24,deadline=None)
def test_sliding_window_length_prefix_reordering_and_duplicates(payload,rotation):
    frame=struct.pack('!I',len(payload))+payload
    chunks=[list(frame[i:i+8]) for i in range(0,len(frame),8)]
    seq=list(range(len(chunks)));rotation%=len(seq);seq=seq[rotation:]+seq[:rotation]
    result=call('transport',{'window':16,'next':0,'segments':[{'sequence':i,'payload':chunks[i]} for i in seq]})
    assert result['messages']==[list(payload)] and result['ack_next']==len(chunks)
    repeated=call('transport',{'window':16,'next':0,'segments':[{'sequence':i,'payload':chunks[i]} for i in seq+seq]})
    assert repeated['messages']==[list(payload)] and repeated['dropped']==len(seq)


def checksum(raw):
    raw+=bytes(len(raw)%2);total=sum(struct.unpack('!'+str(len(raw)//2)+'H',raw))
    while total>65535:total=(total&65535)+(total>>16)
    return total^65535


@pytest.mark.parametrize('version',[4,6])
def test_ipv4_ipv6_udp_checksums_lengths_and_malformed_packets(version):
    payload=b'omega';udp=struct.pack('!HHHH',123,456,8+len(payload),0)+payload
    if version==4:
        addresses=bytes([10,0,0,1,10,0,0,2]);pseudo=addresses+struct.pack('!BBH',0,17,len(udp))
        ip=struct.pack('!BBHHHBBH',69,0,20+len(udp),0,16384,64,17,0)+addresses
        ip=ip[:10]+struct.pack('!H',checksum(ip))+ip[12:];eth=b'\x08\x00'
    else:
        addresses=bytes(15)+b'\x01'+bytes(15)+b'\x02';pseudo=addresses+struct.pack('!I3xB',len(udp),17)
        ip=struct.pack('!IHBB',6<<28,len(udp),17,64)+addresses;eth=b'\x86\xdd'
    udp=udp[:6]+struct.pack('!H',checksum(pseudo+udp))+udp[8:]
    packet=list(bytes(12)+eth+ip+udp)
    result=call('transport',{'mode':'decode-udp','packet':packet})
    assert result=={'ip_version':version,'source_port':123,'destination_port':456,'payload':list(payload)}
    packet[-1]^=1
    with pytest.raises(Exception):call('transport',{'mode':'decode-udp','packet':packet})


def test_frame_overflow_fails_closed():
    with pytest.raises(Exception):call('transport',{'window':8,'next':0,'segments':[{'sequence':0,'payload':list(struct.pack('!I',1025))}]})
