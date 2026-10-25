"""Private trusted worker; only a bounded data-only request is interpreted."""
import json,sys
from pathlib import Path
def main():
    sys.path.insert(0,sys.argv[1])
    import wasmtime
    data=Path(sys.argv[2]).read_bytes()
    if len(data)>2*1024**2:raise ValueError('WASM request too large')
    request=json.loads(data)
    config=wasmtime.Config();config.consume_fuel=True;config.epoch_interruption=True
    engine=wasmtime.Engine(config);store=wasmtime.Store(engine)
    store.set_limits(memory_size=request['memory'],table_elements=1024,instances=1,tables=1,memories=1)
    store.set_fuel(request['fuel'])
    # Outer supervisor applies the wall deadline, including compilation time.
    store.set_epoch_deadline(1)
    module=wasmtime.Module(engine,wasmtime.wat2wasm(request['wat']))
    if module.imports:raise ValueError('WASM imports are forbidden')
    instance=wasmtime.Instance(store,module,[])
    function=instance.exports(store)['evaluate']
    value=function(store,*request['arguments'])
    print(json.dumps({'value':value,'fuel_remaining':store.get_fuel()}))
if __name__=='__main__':main()
