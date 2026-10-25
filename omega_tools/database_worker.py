import base64,json,sqlite3,sys,time
from pathlib import Path
def main():
    request=json.loads(Path(sys.argv[2]).read_bytes());path=Path(request['path']);write=request['write'];query=request['query']
    connection=sqlite3.connect(path.as_uri()+('?mode=rw' if write else '?mode=ro'),uri=True,timeout=2)
    connection.enable_load_extension(False)
    read={sqlite3.SQLITE_SELECT,sqlite3.SQLITE_READ,sqlite3.SQLITE_TRANSACTION}
    mutation={sqlite3.SQLITE_UPDATE,sqlite3.SQLITE_INSERT,sqlite3.SQLITE_DELETE} if write else set()
    functions={'count','sum','avg','min','max','length','lower','upper','coalesce','abs','substr','round','trim','like'}
    def authorize(action,a,b,database,trigger):
        if action==sqlite3.SQLITE_FUNCTION:return sqlite3.SQLITE_OK if isinstance(b,str) and b.lower() in functions else sqlite3.SQLITE_DENY
        return sqlite3.SQLITE_OK if action in read|mutation else sqlite3.SQLITE_DENY
    connection.set_authorizer(authorize);deadline=time.monotonic()+10;steps=[0]
    def progress():steps[0]+=1;return int(steps[0]>10000 or time.monotonic()>deadline)
    connection.set_progress_handler(progress,100)
    try:
        with connection:
            cursor=connection.execute(query,request['parameters']);rows=cursor.fetchmany(10001)
            if len(rows)>10000:raise ValueError('Database row budget exceeded')
            def scalar(v):return {'base64':base64.b64encode(v).decode()} if isinstance(v,bytes) else v
            result={'columns':[c[0] for c in cursor.description] if cursor.description else [],'rows':[[scalar(v) for v in row] for row in rows],'changed':cursor.rowcount}
            if len(json.dumps(result).encode())>4*1024**2:raise ValueError('Database output budget exceeded')
        print(json.dumps(result))
    finally:connection.close()
if __name__=='__main__':main()
