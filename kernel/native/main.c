/* Linux JSON adapter. The proof checker itself is the allocation-free logic.h;
 * stdio, JSON storage and optional GMP tensors are outside that core's TCB. */
#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <inttypes.h>
#include <string.h>
#include "json.h"
#include "sha256.h"
#include "logic.h"
#include "tensor.h"
#ifdef OMEGA_KERNEL_GMP
#include "tensor_graph.h"
#endif

#define OK_INPUT_BYTES (4u*1024u*1024u)
#define OK_JSON_TOKENS 65536u
#define OK_TERM_CAPACITY 16384u
#define OK_BATCH_CAPACITY 4096u

static unsigned char input_buffer[OK_INPUT_BYTES+1];
static okj_token json_tokens[OK_JSON_TOKENS];
static ok_term term_arena[OK_TERM_CAPACITY];
static int64_t batch_an[OK_BATCH_CAPACITY];
static int64_t batch_bn[OK_BATCH_CAPACITY];
static int64_t batch_cn[OK_BATCH_CAPACITY];
static uint64_t batch_ad[OK_BATCH_CAPACITY];
static uint64_t batch_bd[OK_BATCH_CAPACITY];
static uint64_t batch_cd[OK_BATCH_CAPACITY];
static uint8_t batch_status[OK_BATCH_CAPACITY];

static const char *const term_names[OK_TAG_COUNT] = {
    "sort", "var", "pi", "lambda", "app", "let", "annotation", "sigma",
    "pair", "first", "second", "nat", "zero", "successor", "nat-literal",
    "nat-add", "nat-mul", "nat-rec", "equality", "refl", "transport", "unit",
    "unit-value", "empty", "absurd", "constant", "rat", "rat-literal",
    "rat-add", "rat-mul", "rat-neg"
};

static const char *const error_names[] = {
    "success", "bad-node", "scope", "type-mismatch", "not-a-type",
    "not-a-function", "not-a-pair", "constant-not-previously-checked",
    "arena-limit", "fuel-limit", "depth-limit", "context-limit",
    "universe-limit", "arithmetic-limit"
};

static void result_prefix(const char *operation, const char *digest)
{
    printf("{\"format\":\"omega-kernel-native-result-1\","
           "\"operation\":\"%s\",\"input_sha256\":\"%s\",",operation,digest);
}

static int malformed(const char *operation, const char *digest)
{
    result_prefix(operation,digest);
    puts("\"accepted\":false,\"verified\":false,\"status\":\"malformed-request\"}");
    return 3;
}

static int protocol_fields(const okj_parser *p, uint32_t object,
                           const char *const *keys, size_t count)
{
    return object<p->count && p->tokens[object].tag==OKJ_OBJECT &&
           okj_fields(p,object,keys,count);
}

static int integer_field(const okj_parser *p, uint32_t object, const char *name,
                          int64_t fallback, int64_t low, int64_t high, int64_t *out)
{
    uint32_t field=okj_field(p,object,name);
    if (field==UINT32_MAX) {
        *out=fallback;
        return fallback>=low && fallback<=high;
    }
    return okj_range(p,field,low,high,out);
}

static int proof_request(const okj_parser *p, uint32_t object, const char *digest)
{
    static const char *const keys[]={"format","nodes","definitions","proof","expected","limits"};
    if (!protocol_fields(p,object,keys,6) ||
        !okj_name(p,okj_field(p,object,"format"),"omega-kernel-proof-1")) {
        return malformed("verify",digest);
    }
    int64_t capacity=OK_TERM_CAPACITY;
    int64_t fuel=1000000;
    int64_t depth=128;
    uint32_t limits=okj_field(p,object,"limits");
    if (limits!=UINT32_MAX) {
        static const char *const limit_keys[]={"nodes","fuel","depth"};
        if (!protocol_fields(p,limits,limit_keys,3) ||
            !integer_field(p,limits,"nodes",OK_TERM_CAPACITY,16,OK_TERM_CAPACITY,&capacity) ||
            !integer_field(p,limits,"fuel",1000000,1,10000000,&fuel) ||
            !integer_field(p,limits,"depth",128,8,256,&depth)) {
            return malformed("verify",digest);
        }
    }
    uint32_t nodes=okj_field(p,object,"nodes");
    if (nodes>=p->count || p->tokens[nodes].tag!=OKJ_ARRAY ||
        !p->tokens[nodes].count || p->tokens[nodes].count>4096 ||
        p->tokens[nodes].count>(uint64_t)capacity) {
        return malformed("verify",digest);
    }
    ok_checker checker;
    if (!ok_init(&checker,term_arena,(size_t)capacity,(uint64_t)fuel,(uint32_t)depth)) {
        return malformed("verify",digest);
    }
    uint32_t cursor=nodes+1;
    size_t raw_count=p->tokens[nodes].count;
    for (size_t index=0;index<raw_count;++index) {
        static const char *const node_keys[]={"op","args","data"};
        if (!protocol_fields(p,cursor,node_keys,3) || p->tokens[cursor].count!=3) {
            return malformed("verify",digest);
        }
        uint32_t op=okj_field(p,cursor,"op");
        unsigned tag=OK_TAG_COUNT;
        for (unsigned i=0;i<OK_TAG_COUNT;++i) {
            if (okj_name(p,op,term_names[i])) {
                tag=i;
                break;
            }
        }
        uint32_t args=okj_field(p,cursor,"args");
        uint32_t data=okj_field(p,cursor,"data");
        if (tag==OK_TAG_COUNT || args>=p->count || data>=p->count ||
            p->tokens[args].tag!=OKJ_ARRAY || p->tokens[data].tag!=OKJ_ARRAY ||
            p->tokens[args].count!=ok_arity(tag) ||
            p->tokens[data].count!=ok_data_arity(tag)) {
            return malformed("verify",digest);
        }
        uint32_t children[4]={0,0,0,0};
        int64_t payload[2]={0,0};
        for (unsigned j=0;j<ok_arity(tag);++j) {
            int64_t child;
            if (!okj_range(p,okj_element(p,args,j),0,(int64_t)index-1,&child)) {
                return malformed("verify",digest);
            }
            children[j]=(uint32_t)child;
        }
        for (unsigned j=0;j<ok_data_arity(tag);++j) {
            if (!okj_i64(p,okj_element(p,data,j),&payload[j])) {
                return malformed("verify",digest);
            }
        }
        if ((tag==OK_SORT && (payload[0]<0 || payload[0]>OK_LEVEL_MAX+1)) ||
            ((tag==OK_VAR || tag==OK_CONSTANT) && (payload[0]<0 || payload[0]>=256)) ||
            (tag==OK_NAT_LITERAL && payload[0]<0) ||
            (tag==OK_RAT_LITERAL && (payload[0]==INT64_MIN || payload[1]<=0))) {
            return malformed("verify",digest);
        }
        if (ok_new(&checker,tag,children[0],children[1],children[2],children[3],payload[0],payload[1])==OK_NONE) {
            return malformed("verify",digest);
        }
        cursor=p->tokens[cursor].next;
    }
    int64_t proof;
    int64_t expected;
    if (!okj_range(p,okj_field(p,object,"proof"),0,(int64_t)raw_count-1,&proof) ||
        !okj_range(p,okj_field(p,object,"expected"),0,(int64_t)raw_count-1,&expected)) {
        return malformed("verify",digest);
    }
    uint32_t definitions=okj_field(p,object,"definitions");
    if (definitions>=p->count || p->tokens[definitions].tag!=OKJ_ARRAY ||
        p->tokens[definitions].count>OK_DEFINITIONS_MAX) {
        return malformed("verify",digest);
    }
    cursor=definitions+1;
    int accepted=1;
    for (size_t i=0;i<p->tokens[definitions].count;++i) {
        static const char *const definition_keys[]={"type","body"};
        int64_t type;
        int64_t body;
        if (!protocol_fields(p,cursor,definition_keys,2) || p->tokens[cursor].count!=2 ||
            !okj_range(p,okj_field(p,cursor,"type"),0,(int64_t)raw_count-1,&type) ||
            !okj_range(p,okj_field(p,cursor,"body"),0,(int64_t)raw_count-1,&body)) {
            return malformed("verify",digest);
        }
        if (!ok_define(&checker,(uint32_t)type,(uint32_t)body)) {
            accepted=0;
            break;
        }
        cursor=p->tokens[cursor].next;
    }
    if (accepted) {
        accepted=ok_verify(&checker,(uint32_t)proof,(uint32_t)expected);
    }
    int resource=ok_is_resource_error(checker.error);
    result_prefix("verify",digest);
    printf("\"accepted\":%s,\"verified\":%s,\"status\":\"%s\","
           "\"logic\":\"predicative-intensional-MLTT-1\",\"axioms\":[],"
           "\"expected_node\":%" PRId64 ",\"proof_node\":%" PRId64 ","
           "\"error\":\"%s\",\"error_node\":%u,\"arena_nodes\":%zu,"
           "\"fuel_used\":%" PRIu64 ",\"peak_depth\":%u}\n",
           accepted?"true":"false",accepted?"true":"false",
           accepted?"accepted":resource?"resource-limit":"rejected",
           expected,proof,error_names[checker.error],checker.error_node,checker.count,
           checker.initial_fuel-checker.fuel,checker.peak_depth);
    return accepted?0:resource?2:1;
}

static unsigned backend_field(const okj_parser *p, uint32_t request)
{
    uint32_t field=okj_field(p,request,"backend");
    if (field==UINT32_MAX || okj_name(p,field,"auto")) {
        return OKQ_AUTO;
    }
    if (okj_name(p,field,"scalar")) {
        return OKQ_SCALAR;
    }
    if (okj_name(p,field,"avx2")) {
        return OKQ_AVX2;
    }
    if (okj_name(p,field,"avx512")) {
        return OKQ_AVX512;
    }
    if (okj_name(p,field,"neon")) {
        return OKQ_NEON;
    }
    return UINT_MAX;
}

static int batch_request(const okj_parser *p, uint32_t request, const char *digest)
{
    static const char *const keys[]={"a","b","operation","backend"};
    if (!protocol_fields(p,request,keys,4)) {
        return malformed("batch",digest);
    }
    unsigned backend=backend_field(p,request);
    unsigned operation;
    if (okj_name(p,okj_field(p,request,"operation"),"add")) {
        operation=OKQ_ADD;
    } else if (okj_name(p,okj_field(p,request,"operation"),"mul")) {
        operation=OKQ_MULTIPLY;
    } else {
        return malformed("batch",digest);
    }
    uint32_t arrays[2]={okj_field(p,request,"a"),okj_field(p,request,"b")};
    if (backend==UINT_MAX || arrays[0]>=p->count || arrays[1]>=p->count ||
        p->tokens[arrays[0]].tag!=OKJ_ARRAY || p->tokens[arrays[1]].tag!=OKJ_ARRAY ||
        p->tokens[arrays[0]].count!=p->tokens[arrays[1]].count ||
        p->tokens[arrays[0]].count>OK_BATCH_CAPACITY) {
        return malformed("batch",digest);
    }
    size_t n=p->tokens[arrays[0]].count;
    int64_t *numerators[2]={batch_an,batch_bn};
    uint64_t *denominators[2]={batch_ad,batch_bd};
    for (unsigned side=0;side<2;++side) {
        uint32_t cursor=arrays[side]+1;
        for (size_t i=0;i<n;++i) {
            int64_t numerator;
            int64_t denominator;
            if (cursor>=p->count || p->tokens[cursor].tag!=OKJ_ARRAY ||
                p->tokens[cursor].count!=2 ||
                !okj_range(p,okj_element(p,cursor,0),-INT64_MAX,INT64_MAX,&numerator) ||
                !okj_range(p,okj_element(p,cursor,1),1,INT64_MAX,&denominator)) {
                return malformed("batch",digest);
            }
            numerators[side][i]=numerator;
            denominators[side][i]=(uint64_t)denominator;
            cursor=p->tokens[cursor].next;
        }
    }
    okq_view a={batch_an,batch_ad,n};
    okq_view b={batch_bn,batch_bd,n};
    okq_output out={batch_cn,batch_cd,batch_status,OK_BATCH_CAPACITY};
    okq_statistics statistics;
    int status=okq_batch(a,b,out,operation,backend,&statistics);
    result_prefix("batch",digest);
    if (status) {
        printf("\"accepted\":false,\"verified\":false,\"status\":\"batch-error\",\"error\":%d}\n",status);
        return 2;
    }
    printf("\"accepted\":%s,\"verified\":false,\"status\":\"%s\","
           "\"backend\":%u,\"simd_lanes\":%zu,\"scalar_lanes\":%zu,\"failed_lanes\":%zu,\"values\":[",
           statistics.failed_lanes?"false":"true",statistics.failed_lanes?"arithmetic-limit":"computed",
           statistics.backend,statistics.simd_lanes,statistics.scalar_lanes,statistics.failed_lanes);
    for (size_t i=0;i<n;++i) {
        printf("%s[%" PRId64 ",%" PRIu64 ",%u]",i?",":"",batch_cn[i],batch_cd[i],batch_status[i]);
    }
    puts("]}");
    return statistics.failed_lanes?2:0;
}

#ifdef OMEGA_KERNEL_GMP
typedef struct {
    const okj_parser *parser;
    uint32_t array;
    uint32_t cursor;
    size_t index;
} matrix_reader;

static int read_mpq(void *context, size_t index, mpq_t value)
{
    matrix_reader *reader=context;
    const okj_parser *p=reader->parser;
    if (index>=p->tokens[reader->array].count) {
        return 0;
    }
    if (index<reader->index) {
        reader->index=0;
        reader->cursor=reader->array+1;
    }
    while (reader->index<index) {
        reader->cursor=p->tokens[reader->cursor].next;
        reader->index++;
    }
    uint32_t token=reader->cursor;
    if (token>=p->count || (p->tokens[token].tag!=OKJ_STRING &&
                           p->tokens[token].tag!=OKJ_INTEGER)) {
        return 0;
    }
    size_t length=p->tokens[token].end-p->tokens[token].begin;
    if (!length || length>2048) {
        return 0;
    }
    char text[2049];
    unsigned slashes=0;
    size_t last_slash=0;
    for (size_t i=0;i<length;++i) {
        unsigned char c=p->text[p->tokens[token].begin+i];
        if (c=='/' && i>0 && i+1<length && slashes==0) {
            slashes++;
            last_slash=i;
        } else if (!(c>='0' && c<='9') && !(i==0 && c=='-' && length>1)) {
            return 0;
        }
        text[i]=(char)c;
    }
    if (slashes && (last_slash==1 && text[0]=='-')) {
        return 0;
    }
    text[length]=0;
    if (mpq_set_str(value,text,10)!=0 || mpz_sgn(mpq_denref(value))<=0) {
        return 0;
    }
    mpq_canonicalize(value);
    return 1;
}

static int read_matrix(const okj_parser *p, uint32_t object,
                        okg_matrix *out, okg_budget *budget)
{
    static const char *const keys[]={"rows","columns","values"};
    int64_t rows;
    int64_t columns;
    if (!protocol_fields(p,object,keys,3) || p->tokens[object].count!=3 ||
        !okj_range(p,okj_field(p,object,"rows"),1,1024,&rows) ||
        !okj_range(p,okj_field(p,object,"columns"),1,1024,&columns)) {
        return OKG_INPUT;
    }
    uint32_t values=okj_field(p,object,"values");
    if (values>=p->count || p->tokens[values].tag!=OKJ_ARRAY ||
        p->tokens[values].count!=(uint64_t)(rows*columns)) {
        return OKG_INPUT;
    }
    matrix_reader reader={p,values,values+1,0};
    return okg_from_reader(out,(size_t)rows,(size_t)columns,budget,read_mpq,&reader);
}

static void print_matrix(const okg_matrix *matrix)
{
    printf("{\"rows\":%zu,\"columns\":%zu,\"denominator\":\"",matrix->rows,matrix->columns);
    mpz_out_str(stdout,10,matrix->denominator);
    printf("\",\"numerators\":[");
    for (size_t i=0;i<matrix->count;++i) {
        printf("%s\"",i?",":"");
        mpz_out_str(stdout,10,matrix->numerators[i]);
        printf("\"");
    }
    printf("],\"backend\":%u,\"simd_products\":%zu}",matrix->backend,matrix->simd_products);
}

static int tensor_request(const okj_parser *p, uint32_t request, const char *digest)
{
    static const char *const keys[]={"a","b","operation","backend","bits","memory_bytes"};
    if (!protocol_fields(p,request,keys,6)) {
        return malformed("tensor",digest);
    }
    int64_t bits;
    int64_t memory;
    if (!integer_field(p,request,"bits",1024,64,8192,&bits) ||
        !integer_field(p,request,"memory_bytes",268435456,4096,1073741824,&memory)) {
        return malformed("tensor",digest);
    }
    okg_budget budget;
    okg_budget_init(&budget,(size_t)memory,(unsigned)bits);
    okg_matrix a={0};
    okg_matrix b={0};
    okg_matrix out={0};
    unsigned backend=backend_field(p,request);
    int status=backend==UINT_MAX ? OKG_ARGUMENT :
        read_matrix(p,okj_field(p,request,"a"),&a,&budget);
    uint32_t operation=okj_field(p,request,"operation");
    int binary=okj_name(p,operation,"gemm") || okj_name(p,operation,"add") ||
               okj_name(p,operation,"sub") || okj_name(p,operation,"hadamard");
    if (!status && binary) {
        status=read_matrix(p,okj_field(p,request,"b"),&b,&budget);
    }
    if (!status) {
        if (okj_name(p,operation,"gemm")) {
            status=okg_gemm(&out,&a,&b,backend);
        } else if (okj_name(p,operation,"add") || okj_name(p,operation,"sub")) {
            status=okg_add(&out,&a,&b,okj_name(p,operation,"sub"));
        } else if (okj_name(p,operation,"hadamard")) {
            status=okg_hadamard(&out,&a,&b);
        } else if (okj_name(p,operation,"transpose")) {
            status=okg_transpose(&out,&a);
        } else if (okj_name(p,operation,"relu")) {
            status=okg_relu(&out,&a);
        } else if (okj_name(p,operation,"sum") || okj_name(p,operation,"sum-squares")) {
            status=okg_reduce(&out,&a,okj_name(p,operation,"sum-squares"));
        } else {
            status=OKG_ARGUMENT;
        }
    }
    result_prefix("tensor",digest);
    printf("\"accepted\":%s,\"verified\":false,\"status\":\"%s\",\"error\":%d,"
           "\"logical_peak_bytes\":%zu",status?"false":"true",status?"tensor-error":"computed",status,budget.peak);
    if (!status) {
        printf(",\"matrix\":");
        print_matrix(&out);
    }
    puts("}");
    okg_clear(&out);
    okg_clear(&b);
    okg_clear(&a);
    return status ? (status==OKG_BUDGET ? 2 : 1) : 0;
}

static int graph_request(const okj_parser *p, uint32_t request, const char *digest)
{
    static const char *const keys[]={"nodes","output","backward","seed","backend","bits","memory_bytes"};
    if (!protocol_fields(p,request,keys,7)) {
        return malformed("graph",digest);
    }
    int64_t bits;
    int64_t memory;
    int64_t output;
    int64_t backward;
    uint32_t nodes=okj_field(p,request,"nodes");
    if (nodes>=p->count || p->tokens[nodes].tag!=OKJ_ARRAY ||
        !p->tokens[nodes].count || p->tokens[nodes].count>OKG_GRAPH_MAX ||
        !okj_range(p,okj_field(p,request,"output"),0,p->tokens[nodes].count-1,&output) ||
        !integer_field(p,request,"backward",1,0,1,&backward) ||
        !integer_field(p,request,"bits",1024,64,8192,&bits) ||
        !integer_field(p,request,"memory_bytes",268435456,4096,1073741824,&memory)) {
        return malformed("graph",digest);
    }
    okg_budget budget;
    okg_budget_init(&budget,(size_t)memory,(unsigned)bits);
    okg_graph graph={0};
    graph.budget=&budget;
    graph.count=p->tokens[nodes].count;
    graph.output=(size_t)output;
    graph.backend=backend_field(p,request);
    static const char *const operations[]={"input","add","sub","hadamard","matmul","transpose","relu","sum","sum-squares"};
    uint32_t cursor=nodes+1;
    int status=graph.backend==UINT_MAX ? OKG_ARGUMENT : OKG_SUCCESS;
    for (size_t i=0;!status && i<graph.count;++i) {
        static const char *const node_keys[]={"op","args","matrix"};
        if (!protocol_fields(p,cursor,node_keys,3)) {
            status=OKG_INPUT;
            break;
        }
        unsigned operation=OKG_GRAPH_TAGS;
        for (unsigned j=0;j<OKG_GRAPH_TAGS;++j) {
            if (okj_name(p,okj_field(p,cursor,"op"),operations[j])) {
                operation=j;
            }
        }
        if (operation==OKG_GRAPH_TAGS) {
            status=OKG_INPUT;
            break;
        }
        graph.nodes[i].operation=operation;
        uint32_t args=okj_field(p,cursor,"args");
        if (args>=p->count || p->tokens[args].tag!=OKJ_ARRAY ||
            p->tokens[args].count!=okg_graph_arity(operation)) {
            status=OKG_INPUT;
            break;
        }
        for (unsigned j=0;j<okg_graph_arity(operation);++j) {
            int64_t argument;
            if (!okj_range(p,okj_element(p,args,j),0,(int64_t)i-1,&argument)) {
                status=OKG_INPUT;
                break;
            }
            graph.nodes[i].arguments[j]=(size_t)argument;
        }
        if (!status && operation==OKG_INPUT_NODE) {
            status=read_matrix(p,okj_field(p,cursor,"matrix"),&graph.nodes[i].value,&budget);
        } else if (operation!=OKG_INPUT_NODE && okj_field(p,cursor,"matrix")!=UINT32_MAX) {
            status=OKG_INPUT;
        }
        cursor=p->tokens[cursor].next;
    }
    if (!status) {
        status=okg_graph_forward(&graph);
    }
    okg_matrix seed={0};
    uint32_t seed_object=okj_field(p,request,"seed");
    if (!status && backward) {
        if (seed_object!=UINT32_MAX) {
            status=read_matrix(p,seed_object,&seed,&budget);
        }
        if (!status) {
            status=okg_graph_backward(&graph,seed.initialized ? &seed : NULL);
        }
    }
    result_prefix("graph",digest);
    printf("\"accepted\":%s,\"verified\":false,\"status\":\"%s\",\"error\":%d,"
           "\"logical_peak_bytes\":%zu,\"relu_subgradient_at_zero\":0",
           status?"false":"true",status?"graph-error":"computed",status,budget.peak);
    if (!status) {
        printf(",\"values\":[");
        for (size_t i=0;i<graph.count;++i) {
            if (i) {
                putchar(',');
            }
            print_matrix(&graph.nodes[i].value);
        }
        printf("],\"gradients\":[");
        for (size_t i=0;i<graph.count;++i) {
            if (i) {
                putchar(',');
            }
            if (graph.nodes[i].gradient.initialized) {
                print_matrix(&graph.nodes[i].gradient);
            } else {
                printf("null");
            }
        }
        printf("],\"unreachable_gradients_are_zero\":true");
    }
    puts("}");
    okg_clear(&seed);
    okg_graph_clear(&graph);
    return status ? (status==OKG_BUDGET ? 2 : 1) : 0;
}
#endif

int main(int argc, char **argv)
{
    char digest[65];
    ok_sha256_hex("",0,digest);
    if (argc!=2) {
        return malformed("unknown",digest);
    }
    FILE *input=fopen(argv[1],"rb");
    if (!input) {
        return malformed("unknown",digest);
    }
    size_t length=fread(input_buffer,1,OK_INPUT_BYTES+1,input);
    int read_error=ferror(input);
    fclose(input);
    if (read_error || length>OK_INPUT_BYTES) {
        return malformed("unknown",digest);
    }
    ok_sha256_hex(input_buffer,length,digest);
    okj_parser parser;
    if (!okj_parse(&parser,input_buffer,length,json_tokens,OK_JSON_TOKENS)) {
        return malformed("unknown",digest);
    }
    static const char *const root_keys[]={"operation","request"};
    if (!protocol_fields(&parser,0,root_keys,2) || parser.tokens[0].count!=2) {
        return malformed("unknown",digest);
    }
    uint32_t operation=okj_field(&parser,0,"operation");
    uint32_t request=okj_field(&parser,0,"request");
    if (okj_name(&parser,operation,"verify")) {
        return proof_request(&parser,request,digest);
    }
    if (okj_name(&parser,operation,"batch")) {
        return batch_request(&parser,request,digest);
    }
#ifdef OMEGA_KERNEL_GMP
    if (okj_name(&parser,operation,"tensor")) {
        return tensor_request(&parser,request,digest);
    }
    if (okj_name(&parser,operation,"graph")) {
        return graph_request(&parser,request,digest);
    }
#endif
    if (okj_name(&parser,operation,"capabilities")) {
        result_prefix("capabilities",digest);
        printf("\"accepted\":true,\"verified\":false,\"status\":\"available\","
               "\"logic\":\"predicative-intensional-MLTT-1\",\"avx2\":%s,\"avx512\":%s,\"neon\":%s,",
               okq_available(OKQ_AVX2)?"true":"false",okq_available(OKQ_AVX512)?"true":"false",
               okq_available(OKQ_NEON)?"true":"false");
#ifdef OMEGA_KERNEL_GMP
        puts("\"gmp_tensor\":true}");
#else
        puts("\"gmp_tensor\":false}");
#endif
        return 0;
    }
    return malformed("unknown",digest);
}
