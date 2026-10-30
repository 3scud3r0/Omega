/* Adversarial C API, parser and SHA checks. Run only inside the OS sandbox. */
#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include "../../kernel/native/logic.h"
#include "../../kernel/native/json.h"
#include "../../kernel/native/sha256.h"
#include "../../kernel/native/tensor.h"

static uint64_t random_state=UINT64_C(0x9e3779b97f4a7c15);
static uint32_t random_word(void)
{
    random_state^=random_state<<13;
    random_state^=random_state>>7;
    random_state^=random_state<<17;
    return (uint32_t)random_state;
}

static void hashing(void)
{
    char actual[65];
    ok_sha256_hex("",0,actual);
    assert(!strcmp(actual,"e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"));
    ok_sha256_hex("abc",3,actual);
    assert(!strcmp(actual,"ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"));
    char input[1000];
    memset(input,'a',sizeof(input));
    ok_sha256 state;
    ok_sha256_init(&state);
    for (unsigned i=0;i<1000;++i) {
        ok_sha256_update(&state,input,sizeof(input));
    }
    unsigned char digest[32];
    ok_sha256_final(&state,digest);
    const unsigned char expected[32]={
        0xcd,0xc7,0x6e,0x5c,0x99,0x14,0xfb,0x92,0x81,0xa1,0xc7,0xe2,0x84,0xd7,0x3e,0x67,
        0xf1,0x80,0x9a,0x48,0xa4,0x97,0x20,0x0e,0x04,0x6d,0x39,0xcc,0xc7,0x11,0x2c,0xd0};
    assert(!memcmp(digest,expected,32));
}

static void json_boundary(void)
{
    okj_token tokens[128];
    okj_parser parser;
    const char *invalid[]={"", "{", "{\"a\":1,\"a\":2}", "[01]", "[+1]", "[1.2]",
        "[1e3]", "[1,]", "{\"x\":true,}", "[\"\\u0000\"]", "[\"\\n\"]", "{}{}"};
    for (unsigned i=0;i<sizeof(invalid)/sizeof(invalid[0]);++i) {
        assert(!okj_parse(&parser,(const unsigned char*)invalid[i],strlen(invalid[i]),tokens,128));
    }
    const char *valid="{\"a\":[-9223372036854775808,0,9223372036854775807],\"b\":false}";
    assert(okj_parse(&parser,(const unsigned char*)valid,strlen(valid),tokens,128));
    int64_t n;
    uint32_t array=okj_field(&parser,0,"a");
    assert(okj_i64(&parser,okj_element(&parser,array,0),&n)&&n==INT64_MIN);
    assert(okj_i64(&parser,okj_element(&parser,array,2),&n)&&n==INT64_MAX);
    unsigned char data[1024];
    for (unsigned iteration=0;iteration<20000;++iteration) {
        size_t length=random_word()%sizeof(data);
        for (size_t j=0;j<length;++j) {
            data[j]=(unsigned char)random_word();
        }
        (void)okj_parse(&parser,data,length,tokens,128);
    }
}

static void constructor_boundary(void)
{
    ok_term arena[512];
    ok_checker s;
    assert(ok_init(&s,arena,512,100000,64));
    assert(ok_new(&s,OK_VAR,0,0,0,0,INT64_MAX,0)==OK_NONE);
    assert(s.error==OK_BAD_NODE);
    assert(ok_init(&s,arena,512,100000,64));
    assert(ok_new(&s,OK_RAT_LITERAL,0,0,0,0,1,0)==OK_NONE);
    assert(ok_init(&s,arena,512,100000,64));
    assert(ok_binary(&s,OK_APP,99,99)==OK_NONE);
    for (unsigned iteration=0;iteration<2000;++iteration) {
        assert(ok_init(&s,arena,512,10000,32));
        for (unsigned j=0;j<16;++j) {
            uint32_t tag=random_word()%OK_TAG_COUNT;
            uint32_t a=j?random_word()%j:0;
            uint32_t b=j?random_word()%j:0;
            uint32_t c=j?random_word()%j:0;
            uint32_t d=j?random_word()%j:0;
            int64_t x=random_word()%4;
            int64_t y=1+random_word()%4;
            if(ok_new(&s,tag,a,b,c,d,x,y)==OK_NONE) {
                break;
            }
        }
        if(s.error==OK_SUCCESS&&s.count) {
            (void)ok_verify(&s,(uint32_t)s.count-1,0);
        }
    }
}

static void exact_batches(void)
{
    int64_t an[37],bn[37],cn[37];
    uint64_t ad[37],bd[37],cd[37];
    uint8_t errors[37];
    unsigned backends[]={OKQ_SCALAR,OKQ_AUTO,OKQ_AVX2,OKQ_AVX512,OKQ_NEON};
    for(unsigned round=0;round<200;++round) {
        for(unsigned i=0;i<37;++i) {
            an[i]=(int64_t)(random_word()%65535)-32767;
            bn[i]=(int64_t)(random_word()%65535)-32767;
            ad[i]=1+random_word()%4096;
            bd[i]=1+random_word()%4096;
        }
        for(unsigned b=0;b<5;++b) {
            if(!okq_available(backends[b])) { continue; }
            for(unsigned op=0;op<2;++op) {
                okq_view a={an,ad,37},v={bn,bd,37};
                okq_output out={cn,cd,errors,37};
                okq_statistics stats;
                assert(!okq_batch(a,v,out,op,backends[b],&stats));
                for(unsigned i=0;i<37;++i) {
                    assert(!errors[i]);
                    __int128 expected_n=op?(__int128)an[i]*bn[i]:
                        (__int128)an[i]*bd[i]+(__int128)bn[i]*ad[i];
                    __int128 expected_d=(__int128)ad[i]*bd[i];
                    assert((__int128)cn[i]*expected_d==expected_n*cd[i]);
                }
            }
        }
    }
}

int main(void)
{
    hashing();
    json_boundary();
    constructor_boundary();
    exact_batches();
    puts("native-kernel-api-checks: passed");
    return 0;
}
