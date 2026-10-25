"""Versioned episodic records in SQLite; all caller values are bound parameters."""
from dataclasses import dataclass,asdict
import hashlib,json,sqlite3,time
@dataclass(frozen=True)
class Episode:
    id: str
    task: str
    outcome: dict
    evidence: tuple[str,...]
    owner: str
    sensitive: bool=False
    expires: float|None=None
    def __post_init__(self):
        if not self.id or not self.owner or not self.task:raise ValueError('Incomplete episode')
        if len(json.dumps(asdict(self),allow_nan=False).encode())>1024*1024:raise ValueError('Episode budget exceeded')
class EpisodeStore:
    def __init__(self,path):
        self.db=sqlite3.connect(path)
        self.db.execute('CREATE TABLE IF NOT EXISTS episodes(id TEXT,version INTEGER,sha TEXT,data TEXT,created REAL,PRIMARY KEY(id,version))');self.db.commit()
    def append(self,episode):
        data=json.dumps(asdict(episode),sort_keys=True,separators=(',',':'),allow_nan=False);sha=hashlib.sha256(data.encode()).hexdigest()
        with self.db:
            row=self.db.execute('SELECT version,sha FROM episodes WHERE id=? ORDER BY version DESC LIMIT 1',(episode.id,)).fetchone()
            if row and row[1]==sha:return row[0]
            version=row[0]+1 if row else 1
            self.db.execute('INSERT INTO episodes VALUES(?,?,?,?,?)',(episode.id,version,sha,data,time.time()))
        return version
    def get(self,id,version=None):
        query='SELECT data,sha FROM episodes WHERE id=?';args=[id]
        if version is not None:query+=' AND version=?';args.append(version)
        query+=' ORDER BY version DESC LIMIT 1';row=self.db.execute(query,args).fetchone()
        if row is None:raise KeyError(id)
        if hashlib.sha256(row[0].encode()).hexdigest()!=row[1]:raise ValueError('Episode integrity mismatch')
        value=json.loads(row[0])
        if value['expires'] is not None and time.time()>=value['expires']:raise PermissionError('Episode expired')
        return value
    def close(self):self.db.close()
