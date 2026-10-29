/* C ABI adapter to the existing verified-admission CUDA search ABI.
   Library selection is trusted supervisor configuration, never candidate data. */
#include <stdint.h>
#include <stddef.h>
#include <stdio.h>
#include <dlfcn.h>
typedef struct __attribute__((aligned(16))) {int64_t num;uint64_t den;} OmegaCudaQ64;
typedef struct {OmegaCudaQ64 lower,upper;} OmegaCudaInterval;
typedef struct {uint32_t forests,capacity,rollouts,iterations,max_tokens,examples,variables,constants,elites;uint64_t seed;} OmegaCudaConfig;
typedef struct {uint64_t nonterminal[1],scope;uint32_t priors[64],prior_sum;} OmegaCudaGrammar;
typedef struct {uint16_t tokens[63],length,reserved;uint32_t reward,candidate_index;uint8_t admissible,error;uint16_t padding;} OmegaCudaElite;
typedef struct {uint64_t candidates,nodes_evaluated,tier1_survivors;float elapsed_ms;uint32_t elite_count;} OmegaCudaStats;
_Static_assert(sizeof(OmegaCudaQ64)==16,"Rational ABI");
_Static_assert(sizeof(OmegaCudaConfig)==48,"Search ABI");
typedef int (*Search)(OmegaCudaConfig,OmegaCudaGrammar,const OmegaCudaQ64*,const OmegaCudaQ64*,const OmegaCudaQ64*,const OmegaCudaInterval*,const OmegaCudaInterval*,OmegaCudaElite*,OmegaCudaStats*,char*,uint32_t);
int omega_bridge_search(const char *library,const OmegaCudaConfig *config,const OmegaCudaGrammar *grammar,const OmegaCudaQ64 *constants,const OmegaCudaQ64 *inputs,const OmegaCudaQ64 *targets,const OmegaCudaInterval *bounds,const OmegaCudaInterval *limits,OmegaCudaElite *elites,OmegaCudaStats *stats,char *error,uint32_t error_bytes){
 if(!library||!config||!grammar||!error||!error_bytes)return 1;
 void *handle=dlopen(library,RTLD_NOW|RTLD_LOCAL);
 if(!handle){snprintf(error,error_bytes,"CUDA library cannot be loaded");return 2;}
 Search search=(Search)dlsym(handle,"omega_cuda_search");int (*available)(void)=(int(*)(void))dlsym(handle,"omega_cuda_available");
 if(!search||!available){snprintf(error,error_bytes,"CUDA ABI symbols missing");dlclose(handle);return 3;}
 if(!available()){snprintf(error,error_bytes,"CUDA device unavailable; formal admission was not granted");dlclose(handle);return 77;}
 int status=search(*config,*grammar,constants,inputs,targets,bounds,limits,elites,stats,error,error_bytes);dlclose(handle);return status;
}
