#ifndef OMEGA_KERNEL_SHA256_H
#define OMEGA_KERNEL_SHA256_H
#include <stdint.h>
#include <stddef.h>

typedef struct {
    uint32_t state[8];
    uint64_t bytes;
    unsigned char block[64];
    size_t used;
} ok_sha256;

static inline uint32_t ok_rotr32(uint32_t x, unsigned n)
{
    return (x >> n) | (x << (32 - n));
}

static void ok_sha256_transform(ok_sha256 *s, const unsigned char *data)
{
    static const uint32_t constants[64] = {
        0x428a2f98, 0x71374491, 0xb5c0fbcf, 0xe9b5dba5,
        0x3956c25b, 0x59f111f1, 0x923f82a4, 0xab1c5ed5,
        0xd807aa98, 0x12835b01, 0x243185be, 0x550c7dc3,
        0x72be5d74, 0x80deb1fe, 0x9bdc06a7, 0xc19bf174,
        0xe49b69c1, 0xefbe4786, 0x0fc19dc6, 0x240ca1cc,
        0x2de92c6f, 0x4a7484aa, 0x5cb0a9dc, 0x76f988da,
        0x983e5152, 0xa831c66d, 0xb00327c8, 0xbf597fc7,
        0xc6e00bf3, 0xd5a79147, 0x06ca6351, 0x14292967,
        0x27b70a85, 0x2e1b2138, 0x4d2c6dfc, 0x53380d13,
        0x650a7354, 0x766a0abb, 0x81c2c92e, 0x92722c85,
        0xa2bfe8a1, 0xa81a664b, 0xc24b8b70, 0xc76c51a3,
        0xd192e819, 0xd6990624, 0xf40e3585, 0x106aa070,
        0x19a4c116, 0x1e376c08, 0x2748774c, 0x34b0bcb5,
        0x391c0cb3, 0x4ed8aa4a, 0x5b9cca4f, 0x682e6ff3,
        0x748f82ee, 0x78a5636f, 0x84c87814, 0x8cc70208,
        0x90befffa, 0xa4506ceb, 0xbef9a3f7, 0xc67178f2
    };
    uint32_t w[64];
    for (unsigned i = 0; i < 16; ++i) {
        w[i] = (uint32_t)data[4*i] << 24 |
               (uint32_t)data[4*i+1] << 16 |
               (uint32_t)data[4*i+2] << 8 |
               data[4*i+3];
    }
    for (unsigned i = 16; i < 64; ++i) {
        uint32_t a = ok_rotr32(w[i-15], 7) ^ ok_rotr32(w[i-15], 18) ^ (w[i-15] >> 3);
        uint32_t b = ok_rotr32(w[i-2], 17) ^ ok_rotr32(w[i-2], 19) ^ (w[i-2] >> 10);
        w[i] = w[i-16] + a + w[i-7] + b;
    }
    uint32_t a = s->state[0];
    uint32_t b = s->state[1];
    uint32_t c = s->state[2];
    uint32_t d = s->state[3];
    uint32_t e = s->state[4];
    uint32_t f = s->state[5];
    uint32_t g = s->state[6];
    uint32_t h = s->state[7];
    for (unsigned i = 0; i < 64; ++i) {
        uint32_t sigma1 = ok_rotr32(e,6) ^ ok_rotr32(e,11) ^ ok_rotr32(e,25);
        uint32_t choose = (e & f) ^ (~e & g);
        uint32_t t1 = h + sigma1 + choose + constants[i] + w[i];
        uint32_t sigma0 = ok_rotr32(a,2) ^ ok_rotr32(a,13) ^ ok_rotr32(a,22);
        uint32_t majority = (a & b) ^ (a & c) ^ (b & c);
        uint32_t t2 = sigma0 + majority;
        h = g;
        g = f;
        f = e;
        e = d + t1;
        d = c;
        c = b;
        b = a;
        a = t1 + t2;
    }
    s->state[0] += a;
    s->state[1] += b;
    s->state[2] += c;
    s->state[3] += d;
    s->state[4] += e;
    s->state[5] += f;
    s->state[6] += g;
    s->state[7] += h;
}

static inline void ok_sha256_init(ok_sha256 *s)
{
    static const uint32_t initial[8] = {
        0x6a09e667, 0xbb67ae85, 0x3c6ef372, 0xa54ff53a,
        0x510e527f, 0x9b05688c, 0x1f83d9ab, 0x5be0cd19
    };
    for (unsigned i = 0; i < 8; ++i) {
        s->state[i] = initial[i];
    }
    s->bytes = 0;
    s->used = 0;
}

static inline int ok_sha256_update(ok_sha256 *s, const void *buffer, size_t length)
{
    const unsigned char *data = buffer;
    if (!s || (!data && length) || length > UINT64_MAX / 8 - s->bytes) {
        return 0;
    }
    s->bytes += length;
    while (length) {
        size_t n = 64 - s->used;
        if (n > length) {
            n = length;
        }
        for (size_t i = 0; i < n; ++i) {
            s->block[s->used+i] = data[i];
        }
        s->used += n;
        data += n;
        length -= n;
        if (s->used == 64) {
            ok_sha256_transform(s, s->block);
            s->used = 0;
        }
    }
    return 1;
}

static inline void ok_sha256_finish(ok_sha256 *s, unsigned char digest[32])
{
    uint64_t bits = s->bytes * 8;
    s->block[s->used++] = 0x80;
    if (s->used > 56) {
        while (s->used < 64) {
            s->block[s->used++] = 0;
        }
        ok_sha256_transform(s, s->block);
        s->used = 0;
    }
    while (s->used < 56) {
        s->block[s->used++] = 0;
    }
    for (unsigned i = 0; i < 8; ++i) {
        s->block[63-i] = (unsigned char)(bits >> (8*i));
    }
    ok_sha256_transform(s, s->block);
    for (unsigned i = 0; i < 8; ++i) {
        digest[4*i] = (unsigned char)(s->state[i] >> 24);
        digest[4*i+1] = (unsigned char)(s->state[i] >> 16);
        digest[4*i+2] = (unsigned char)(s->state[i] >> 8);
        digest[4*i+3] = (unsigned char)s->state[i];
    }
}

static inline void ok_sha256_hex(const void *data, size_t size, char output[65])
{
    static const char hex[] = "0123456789abcdef";
    ok_sha256 state;
    unsigned char digest[32];
    ok_sha256_init(&state);
    ok_sha256_update(&state, data, size);
    ok_sha256_finish(&state, digest);
    for (unsigned i = 0; i < 32; ++i) {
        output[2*i] = hex[digest[i] >> 4];
        output[2*i+1] = hex[digest[i] & 15];
    }
    output[64] = 0;
}

#endif
