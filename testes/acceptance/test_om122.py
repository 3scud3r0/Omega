"""OM-122: executable checks; source delivery, not a recorded pass."""
import sqlite3
import pytest
from omega_tools.database import query

def test_database_queries_use_parameters_and_write_requires_approval(tmp_path,signed_authority):
    path=tmp_path/'db.sqlite';connection=sqlite3.connect(path)
    with connection:connection.execute('CREATE TABLE items(id INTEGER,value TEXT)');connection.execute('INSERT INTO items VALUES(?,?)',(1,'original'))
    connection.close();verifier,mint=signed_authority
    result=query(path,'SELECT value FROM items WHERE id=?',[1],capability=mint(['database.read']),verifier=verifier,principal='agent')
    assert result['rows']==[['original']]
    with pytest.raises(PermissionError):query(path,'DELETE FROM items',write=True,capability=mint(['database.write']),verifier=verifier,principal='agent')
    connection=sqlite3.connect(path);assert connection.execute('SELECT count(*) FROM items').fetchone()[0]==1;connection.close()
