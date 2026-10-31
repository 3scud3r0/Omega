// Fixed trusted sieve. One invocation evaluates one candidate over all samples.
// Arithmetic domain: reduced n/d, abs(n) <= 32767, 1 <= d <= 32767.
// This bound makes every pre-reduction i32 product and addition exact.
@group(0) @binding(0) var<storage,read> metadata: array<u32>;
@group(0) @binding(1) var<storage,read> nodes: array<vec4<i32>>;
@group(0) @binding(2) var<storage,read> descriptions: array<vec2<u32>>;
@group(0) @binding(3) var<storage,read> samples: array<vec2<i32>>;
@group(0) @binding(4) var<storage,read_write> results: array<vec4<u32>>;

fn gcd(a0:i32,b0:i32)->i32 {
    var a=abs(a0);
    var b=abs(b0);
    for(var i=0u;i<64u;i=i+1u) {
        if(b==0) { return a; }
        let next=a%b;
        a=b;
        b=next;
    }
    return 0;
}

fn rational(n:i32,d:i32)->vec3<i32> {
    if(d<=0) { return vec3<i32>(0,1,0); }
    let divisor=gcd(n,d);
    if(divisor==0) { return vec3<i32>(0,1,0); }
    let reduced_n=n/divisor;
    let reduced_d=d/divisor;
    if(abs(reduced_n)>32767||reduced_d>32767) {
        return vec3<i32>(0,1,0);
    }
    return vec3<i32>(reduced_n,reduced_d,1);
}

fn combine(op:i32,a:vec2<i32>,b:vec2<i32>)->vec3<i32> {
    if(op==3||op==4) {
        let divisor=gcd(a.y,b.y);
        let ad=a.y/divisor;
        let bd=b.y/divisor;
        let left=a.x*bd;
        var right=b.x*ad;
        if(op==4) { right=-right; }
        return rational(left+right,ad*b.y);
    }
    let cancel_left=gcd(a.x,b.y);
    let cancel_right=gcd(b.x,a.y);
    return rational((a.x/cancel_left)*(b.x/cancel_right),
                    (a.y/cancel_right)*(b.y/cancel_left));
}

@compute @workgroup_size(64)
fn main(@builtin(global_invocation_id) invocation:vec3<u32>) {
    let candidate=invocation.x;
    if(candidate>=metadata[0]) { return; }
    let count=descriptions[candidate].x;
    let root=descriptions[candidate].y;
    if(count==0u||count>32u||root>=count) {
        results[candidate]=vec4<u32>(2u,0u,0u,0u);
        return;
    }
    var mismatches=0u;
    var first=0xffffffffu;
    var arithmetic_limit=0u;
    var visited=0u;
    for(var sample=0u;sample<metadata[1];sample=sample+1u) {
        var values:array<vec2<i32>,32>;
        var valid:array<bool,32>;
        for(var i=0u;i<count;i=i+1u) {
            let node=nodes[candidate*32u+i];
            var value=vec3<i32>(0,1,0);
            if(node.x==0) { value=rational(node.y,node.z); }
            if(node.x==1&&node.y>=0&&u32(node.y)<metadata[2]) {
                let lane=samples[sample*(metadata[2]+1u)+u32(node.y)];
                value=rational(lane.x,lane.y);
            }
            if(node.x==2&&node.y>=0&&u32(node.y)<i&&valid[u32(node.y)]) {
                let operand=values[u32(node.y)];
                value=vec3<i32>(-operand.x,operand.y,1);
            }
            if(node.x>=3&&node.x<=5&&node.y>=0&&node.z>=0&&u32(node.y)<i&&u32(node.z)<i) {
                if(valid[u32(node.y)]&&valid[u32(node.z)]) {
                    value=combine(node.x,values[u32(node.y)],values[u32(node.z)]);
                }
            }
            values[i]=value.xy;
            valid[i]=value.z==1;
            visited=visited+1u;
        }
        let expected=samples[sample*(metadata[2]+1u)+metadata[2]];
        if(!valid[root]) { arithmetic_limit=1u; }
        if(!valid[root]||any(values[root]!=expected)) {
            mismatches=mismatches+1u;
            if(first==0xffffffffu) { first=sample; }
        }
    }
    results[candidate]=vec4<u32>(arithmetic_limit,mismatches,first,visited);
}
