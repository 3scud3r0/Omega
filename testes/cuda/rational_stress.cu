#include <cuda_runtime.h>
#include <algorithm>
#include <cstdio>
#include <cstdlib>
#include <numeric>
#include <vector>
#include "../../hardware/cuda/rational_alu.cuh"
using namespace omega_gpu;
__global__ void rational_stress(Checked *out,uint64_t base,uint32_t count){
 uint32_t i=blockIdx.x*blockDim.x+threadIdx.x;if(i>=count)return;
 uint64_t id=base+i;Rational64 a={int64_t(id%997)+1,17},b={int64_t(id%991)+1,19};
 switch(id%4){case 0:out[i]=rat_add(a,b);break;case 1:out[i]=rat_sub(a,b);break;
 case 2:out[i]=rat_mul(a,b);break;default:out[i]=rat_div(a,b);}
}
int main(int argc,char **argv){
 int devices=0;if(cudaGetDeviceCount(&devices)!=cudaSuccess||devices<1){std::fputs("CUDA device unavailable\n",stderr);return 77;}
 uint64_t count=argc==2?std::strtoull(argv[1],nullptr,10):10000000;
 if(!count||count>100000000)return 2;
 const uint32_t chunk=65536;Checked *device=nullptr;std::vector<Checked> host(chunk);
 if(cudaMalloc(&device,sizeof(Checked)*chunk)!=cudaSuccess)return 3;
 for(uint64_t base=0;base<count;base+=chunk){
  uint32_t n=uint32_t(std::min<uint64_t>(chunk,count-base));rational_stress<<<(n+255)/256,256>>>(device,base,n);
  if(cudaGetLastError()!=cudaSuccess||cudaMemcpy(host.data(),device,n*sizeof(Checked),cudaMemcpyDeviceToHost)!=cudaSuccess)return 4;
  for(uint32_t i=0;i<n;i++){
   int64_t a=int64_t((base+i)%997)+1,b=int64_t((base+i)%991)+1,num=0,den=1;
   switch((base+i)%4){case 0:num=a*19+b*17;den=323;break;case 1:num=a*19-b*17;den=323;break;
   case 2:num=a*b;den=323;break;default:num=a*19;den=17*b;}
   int64_t g=std::gcd(num,den);num/=g;den/=g;
   if(host[i].error||host[i].value.num!=num||host[i].value.den!=uint64_t(den))return 5;
  }
 }
 cudaFree(device);std::printf("{\"cuda_operations\":%llu,\"exact_matches\":true}\n",(unsigned long long)count);return 0;
}
