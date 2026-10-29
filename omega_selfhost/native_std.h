/* Narrow native system interface. Algorithms live in .omega; OS/crypto calls
   remain explicit host capabilities. GMP/OpenSSL may allocate internally. */
#ifndef OMEGA_NATIVE_STD_H
#define OMEGA_NATIVE_STD_H
#include <fcntl.h>
#include <sys/file.h>
#include <sys/stat.h>
#include <unistd.h>
#ifdef OMEGA_CRYPTO
#include <openssl/evp.h>
#include <openssl/rand.h>
#endif
static V o_qnum(V x){if(x->kind!=0)o_die("Rational required");V r=o_new(0);o_qinit(r);mpq_set_z(r->q,mpq_numref(x->q));return r;}
static V o_qden(V x){if(x->kind!=0)o_die("Rational required");V r=o_new(0);o_qinit(r);mpq_set_z(r->q,mpq_denref(x->q));return r;}
static V o_qfloor(V x){if(x->kind!=0)o_die("Rational required");V r=o_new(0);o_qinit(r);mpz_fdiv_q(mpq_numref(r->q),mpq_numref(x->q),mpq_denref(x->q));return r;}
static V o_qbits(V x){if(x->kind!=0)o_die("Rational required");size_t a=mpz_sizeinbase(mpq_numref(x->q),2),b=mpz_sizeinbase(mpq_denref(x->q),2);if(a>LONG_MAX||b>LONG_MAX)o_die("Bit count exceeds range");return o_int((long)(a>b?a:b));}
static V o_monotonic_ns(void){struct timespec t;if(clock_gettime(CLOCK_MONOTONIC,&t)||t.tv_sec<0)o_die("Clock unavailable");return o_add(o_mul(o_int((long)t.tv_sec),o_num("1000000000")),o_int(t.tv_nsec));}
static V o_readline(void){
 char *b=o_alloc(65538);size_t n=0;int c;
 while((c=fgetc(stdin))!=EOF&&c!='\n'){if(n>=65536)o_die("Line budget exceeded");if(!c)o_die("NUL input refused");b[n++]=(char)c;}
 V result=o_obj();o_put(result,o_str("eof"),o_int(c==EOF&&n==0));o_put(result,o_str("line"),o_str(b));return result;
}
static V o_flush(void){if(fflush(stdout))o_die("Flush failed");return o_int(0);}
static V o_unix_time(void){time_t t=time(NULL);if(t<0)o_die("Wall clock unavailable");return o_int((long)t);}
static int o_parent(V root,V path,char **leaf){
 if(root->kind!=1||path->kind!=1||!path->n||path->n>4096||path->s[0]=='/')o_die("Relative confined path required");
 int fd=open(root->s,O_RDONLY|O_DIRECTORY|O_NOFOLLOW|O_CLOEXEC);if(fd<0)o_die("Cannot open capability root");
 char *copy=o_copy(path->s,path->n),*p=copy,*component=copy;
 for(;;p++)if(!*p||*p=='/'){
  char end=*p;*p=0;if(!*component||!strcmp(component,".")||!strcmp(component,"..")){close(fd);o_die("Unsafe relative path");}
  if(!end){*leaf=component;return fd;}
  int next=openat(fd,component,O_RDONLY|O_DIRECTORY|O_NOFOLLOW|O_CLOEXEC);close(fd);if(next<0)o_die("Unsafe directory component");fd=next;component=p+1;
 }
}
static int o_open_root(V root,V path,int flags,mode_t mode){char *leaf;int parent=o_parent(root,path,&leaf);int fd=openat(parent,leaf,flags|O_NOFOLLOW|O_CLOEXEC|O_NONBLOCK,mode);close(parent);return fd;}
static char *o_fd_text(int fd,size_t *length){
 struct stat st;if(fstat(fd,&st)||!S_ISREG(st.st_mode)||st.st_size<0||st.st_size>64000000)o_die("Bounded regular file required");
 size_t n=(size_t)st.st_size;char *p=o_alloc(n+1);size_t at=0;
 while(at<n){ssize_t got=pread(fd,p+at,n-at,(off_t)at);if(got<0&&errno==EINTR)continue;if(got<=0)o_die("Short file read");at+=(size_t)got;}
 if(memchr(p,0,n))o_die("Text interface rejects NUL bytes");*length=n;return p;
}
static V o_root_read(V root,V path){int fd=o_open_root(root,path,O_RDONLY,0);if(fd<0)o_die("Cannot read confined file");size_t n;char *p=o_fd_text(fd,&n);close(fd);return o_str(p);}
static V o_root_exists(V root,V path){int fd=o_open_root(root,path,O_RDONLY,0);if(fd<0){if(errno==ENOENT)return o_int(0);o_die("Unsafe or unreadable path");}struct stat s;int ok=!fstat(fd,&s)&&S_ISREG(s.st_mode);close(fd);if(!ok)o_die("Regular file required");return o_int(1);}
static void o_write_all(int fd,const char *data,size_t n){size_t at=0;while(at<n){ssize_t wrote=write(fd,data+at,n-at);if(wrote<0&&errno==EINTR)continue;if(wrote<=0)o_die("File write failed");at+=(size_t)wrote;}}
static V o_root_write(V root,V path,V data){
 if(data->kind!=1||data->n>64000000)o_die("Bounded text required");char *leaf;int parent=o_parent(root,path,&leaf);
 struct stat st;if(!fstatat(parent,leaf,&st,AT_SYMLINK_NOFOLLOW)&&!S_ISREG(st.st_mode)){close(parent);o_die("Refusing nonregular destination");}
 char tmp[80];static unsigned long counter=0;snprintf(tmp,sizeof tmp,".omega-write-%ld-%lu",(long)getpid(),counter++);
 int fd=openat(parent,tmp,O_CREAT|O_EXCL|O_WRONLY|O_NOFOLLOW|O_CLOEXEC,0600);if(fd<0)o_die("Cannot create atomic output");
 o_write_all(fd,data->s,data->n);if(fsync(fd)||close(fd)||renameat(parent,tmp,parent,leaf)||fsync(parent))o_die("Atomic write failed");close(parent);return o_int(0);
}
static V o_sha256(V data){
 if(data->kind!=1)o_die("Hash requires text bytes");
#ifdef OMEGA_CRYPTO
 unsigned char digest[32];unsigned n=0;if(!EVP_Digest(data->s,data->n,digest,&n,EVP_sha256(),NULL)||n!=32)o_die("SHA256 failed");
 char hex[65];for(unsigned i=0;i<32;i++)snprintf(hex+2*i,3,"%02x",digest[i]);return o_str(hex);
#else
 o_die("Crypto support requires OMEGA_CRYPTO and OpenSSL");
#endif
}
static V o_file_sha256(V root,V path){
#ifdef OMEGA_CRYPTO
 int fd=o_open_root(root,path,O_RDONLY,0);if(fd<0)o_die("Cannot hash file");struct stat st;if(fstat(fd,&st)||!S_ISREG(st.st_mode)||st.st_size<0||st.st_size>64000000)o_die("Bounded regular file required");
 EVP_MD_CTX *ctx=EVP_MD_CTX_new();if(!ctx||!EVP_DigestInit_ex(ctx,EVP_sha256(),NULL))o_die("Hash initialization failed");
 unsigned char buffer[16384],digest[32];ssize_t got;while((got=read(fd,buffer,sizeof buffer))>0)if(!EVP_DigestUpdate(ctx,buffer,(size_t)got))o_die("Hash update failed");
 if(got<0)o_die("Hash read failed");unsigned n=0;if(!EVP_DigestFinal_ex(ctx,digest,&n)||n!=32)o_die("Hash finalize failed");EVP_MD_CTX_free(ctx);close(fd);
 char hex[65];for(unsigned i=0;i<32;i++)snprintf(hex+2*i,3,"%02x",digest[i]);return o_str(hex);
#else
 (void)root;(void)path;o_die("Crypto support unavailable");
#endif
}
static V o_append_cas(V root,V path,V expected,V text){
 if(expected->kind!=1||expected->n!=64||text->kind!=1||text->n>1048576)o_die("Invalid append request");
 char *leaf;int parent=o_parent(root,path,&leaf);int fd=openat(parent,leaf,O_RDWR|O_CREAT|O_APPEND|O_NOFOLLOW|O_CLOEXEC|O_NONBLOCK,0600);if(fd<0||flock(fd,LOCK_EX))o_die("Cannot lock append log");
 size_t n;char *prior=o_fd_text(fd,&n);V observed=o_sha256(o_str(prior));
 if(strcmp(observed->s,expected->s)){flock(fd,LOCK_UN);close(fd);close(parent);return o_int(0);}
 if(n>64000000-text->n)o_die("Append log capacity exceeded");o_write_all(fd,text->s,text->n);if(fsync(fd)||fsync(parent))o_die("Append durability failed");flock(fd,LOCK_UN);close(fd);close(parent);return o_int(1);
}
static int o_hex(V value,unsigned char *out,size_t count){if(value->kind!=1||value->n!=count*2)return 0;for(size_t i=0;i<count;i++){unsigned a=(unsigned char)value->s[2*i],b=(unsigned char)value->s[2*i+1];if(!isxdigit(a)||!isxdigit(b))return 0;a=isdigit(a)?a-'0':tolower(a)-'a'+10;b=isdigit(b)?b-'0':tolower(b)-'a'+10;out[i]=(unsigned char)((a<<4)|b);}return 1;}
static V o_ed25519_verify(V public_key,V payload,V signature){
#ifdef OMEGA_CRYPTO
 unsigned char pk[32],sig[64];if(payload->kind!=1||!o_hex(public_key,pk,32)||!o_hex(signature,sig,64))return o_int(0);
 EVP_PKEY *key=EVP_PKEY_new_raw_public_key(EVP_PKEY_ED25519,NULL,pk,32);EVP_MD_CTX *ctx=EVP_MD_CTX_new();
 int ok=key&&ctx&&EVP_DigestVerifyInit(ctx,NULL,NULL,NULL,key)>0&&EVP_DigestVerify(ctx,sig,64,(unsigned char*)payload->s,payload->n)==1;
 EVP_MD_CTX_free(ctx);EVP_PKEY_free(key);return o_int(ok);
#else
 (void)public_key;(void)payload;(void)signature;o_die("Crypto support unavailable");
#endif
}
static V o_ed25519_sign(V root,V path,V payload){
#ifdef OMEGA_CRYPTO
 if(payload->kind!=1)o_die("Signing bytes required");int fd=o_open_root(root,path,O_RDONLY,0);struct stat st;unsigned char seed[32];
 if(fd<0||fstat(fd,&st)||!S_ISREG(st.st_mode)||st.st_size!=32||(st.st_mode&077)||read(fd,seed,32)!=32)o_die("Private key requires regular mode 0600 and 32 bytes");close(fd);
 EVP_PKEY *key=EVP_PKEY_new_raw_private_key(EVP_PKEY_ED25519,NULL,seed,32);OPENSSL_cleanse(seed,sizeof seed);EVP_MD_CTX *ctx=EVP_MD_CTX_new();unsigned char sig[64];size_t n=64;
 if(!key||!ctx||EVP_DigestSignInit(ctx,NULL,NULL,NULL,key)<=0||EVP_DigestSign(ctx,sig,&n,(unsigned char*)payload->s,payload->n)<=0||n!=64)o_die("Signature failed");
 EVP_MD_CTX_free(ctx);EVP_PKEY_free(key);char hex[129];for(unsigned i=0;i<64;i++)snprintf(hex+2*i,3,"%02x",sig[i]);return o_str(hex);
#else
 (void)root;(void)path;(void)payload;o_die("Crypto support unavailable");
#endif
}
#endif
