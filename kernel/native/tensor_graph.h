#ifndef OMEGA_KERNEL_TENSOR_GRAPH_H
#define OMEGA_KERNEL_TENSOR_GRAPH_H
#include "tensor_gmp.h"

#define OKG_GRAPH_MAX 64
#define OKG_GRAPH_CELLS 16384

enum {
    OKG_INPUT_NODE,
    OKG_ADD_NODE,
    OKG_SUB_NODE,
    OKG_HADAMARD_NODE,
    OKG_MATMUL_NODE,
    OKG_TRANSPOSE_NODE,
    OKG_RELU_NODE,
    OKG_SUM_NODE,
    OKG_SQUARE_SUM_NODE,
    OKG_GRAPH_TAGS
};

typedef struct {
    unsigned operation;
    size_t arguments[2];
    okg_matrix value;
    okg_matrix gradient;
} okg_graph_node;

typedef struct {
    okg_graph_node nodes[OKG_GRAPH_MAX];
    size_t count;
    size_t output;
    size_t cells;
    okg_budget *budget;
    unsigned backend;
} okg_graph;

static inline unsigned okg_graph_arity(unsigned operation)
{
    if (operation==OKG_INPUT_NODE) {
        return 0;
    }
    if (operation==OKG_ADD_NODE || operation==OKG_SUB_NODE ||
        operation==OKG_HADAMARD_NODE || operation==OKG_MATMUL_NODE) {
        return 2;
    }
    return 1;
}

static inline void okg_graph_clear(okg_graph *graph)
{
    if (!graph) {
        return;
    }
    for (size_t i=0;i<graph->count && i<OKG_GRAPH_MAX;++i) {
        okg_clear(&graph->nodes[i].value);
        okg_clear(&graph->nodes[i].gradient);
    }
    graph->count=0;
    graph->cells=0;
}

static inline int okg_fill(okg_matrix *out, size_t rows, size_t columns,
                            const mpq_t value, okg_budget *budget)
{
    int status=okg_allocate(out,rows,columns,budget);
    if (status) {
        return status;
    }
    mpz_set(out->denominator,mpq_denref(value));
    for (size_t i=0;i<out->count;++i) {
        mpz_set(out->numerators[i],mpq_numref(value));
    }
    status=okg_normalize(out);
    if (status) {
        okg_clear(out);
    }
    return status;
}

static int okg_graph_forward(okg_graph *graph)
{
    if (!graph || !graph->budget || graph->count==0 || graph->count>OKG_GRAPH_MAX ||
        graph->output>=graph->count || okq_choose(graph->backend)==UINT_MAX) {
        return OKG_ARGUMENT;
    }
    graph->cells=0;
    for (size_t i=0;i<graph->count;++i) {
        okg_graph_node *node=&graph->nodes[i];
        if (node->operation>=OKG_GRAPH_TAGS) {
            return OKG_ARGUMENT;
        }
        unsigned arity=okg_graph_arity(node->operation);
        for (unsigned j=0;j<arity;++j) {
            if (node->arguments[j]>=i) {
                return OKG_ARGUMENT;
            }
        }
        const okg_matrix *a=arity ? &graph->nodes[node->arguments[0]].value : NULL;
        const okg_matrix *b=arity>1 ? &graph->nodes[node->arguments[1]].value : NULL;
        int status=OKG_SUCCESS;
        switch (node->operation) {
        case OKG_INPUT_NODE:
            if (!node->value.initialized || node->value.budget!=graph->budget) {
                return OKG_INPUT;
            }
            break;
        case OKG_ADD_NODE:
        case OKG_SUB_NODE:
            status=okg_add(&node->value,a,b,node->operation==OKG_SUB_NODE);
            break;
        case OKG_HADAMARD_NODE:
            status=okg_hadamard(&node->value,a,b);
            break;
        case OKG_MATMUL_NODE:
            status=okg_gemm(&node->value,a,b,graph->backend);
            break;
        case OKG_TRANSPOSE_NODE:
            status=okg_transpose(&node->value,a);
            break;
        case OKG_RELU_NODE:
            status=okg_relu(&node->value,a);
            break;
        case OKG_SUM_NODE:
        case OKG_SQUARE_SUM_NODE:
            status=okg_reduce(&node->value,a,node->operation==OKG_SQUARE_SUM_NODE);
            break;
        default:
            return OKG_ARGUMENT;
        }
        if (status) {
            return status;
        }
        if (node->value.count>OKG_GRAPH_CELLS-graph->cells) {
            return OKG_BUDGET;
        }
        graph->cells+=node->value.count;
    }
    return OKG_SUCCESS;
}

static int okg_graph_backward(okg_graph *graph, const okg_matrix *seed)
{
    if (!graph || graph->count==0 || graph->count>OKG_GRAPH_MAX || graph->output>=graph->count) {
        return OKG_ARGUMENT;
    }
    for (size_t i=0;i<graph->count;++i) {
        if (graph->nodes[i].gradient.initialized) {
            return OKG_ARGUMENT;
        }
    }
    okg_graph_node *output=&graph->nodes[graph->output];
    int status;
    if (seed) {
        if (!seed->initialized || seed->rows!=output->value.rows ||
            seed->columns!=output->value.columns || seed->budget!=graph->budget) {
            return OKG_SHAPE;
        }
        status=okg_clone(&output->gradient,seed);
    } else {
        if (output->value.count!=1) {
            return OKG_SHAPE;
        }
        mpq_t one;
        mpq_init(one);
        mpq_set_ui(one,1,1);
        status=okg_fill(&output->gradient,1,1,one,graph->budget);
        mpq_clear(one);
    }
    if (status) {
        return status;
    }
    for (size_t cursor=graph->output+1;cursor>0;--cursor) {
        size_t index=cursor-1;
        okg_graph_node *node=&graph->nodes[index];
        if (!node->gradient.initialized || node->operation==OKG_INPUT_NODE) {
            continue;
        }
        okg_matrix *a=&graph->nodes[node->arguments[0]].value;
        okg_matrix *b=okg_graph_arity(node->operation)>1 ?
                       &graph->nodes[node->arguments[1]].value : NULL;
        okg_matrix first={0};
        okg_matrix second={0};
        okg_matrix temporary={0};
        mpq_t scalar;
        mpq_init(scalar);
        switch (node->operation) {
        case OKG_ADD_NODE:
            status=okg_clone(&first,&node->gradient);
            if (!status) {
                status=okg_clone(&second,&node->gradient);
            }
            break;
        case OKG_SUB_NODE:
            status=okg_clone(&first,&node->gradient);
            mpq_set_si(scalar,-1,1);
            if (!status) {
                status=okg_scale(&second,&node->gradient,scalar);
            }
            break;
        case OKG_HADAMARD_NODE:
            status=okg_hadamard(&first,&node->gradient,b);
            if (!status) {
                status=okg_hadamard(&second,&node->gradient,a);
            }
            break;
        case OKG_MATMUL_NODE:
            status=okg_transpose(&temporary,b);
            if (!status) {
                status=okg_gemm(&first,&node->gradient,&temporary,graph->backend);
            }
            okg_clear(&temporary);
            if (!status) {
                status=okg_transpose(&temporary,a);
            }
            if (!status) {
                status=okg_gemm(&second,&temporary,&node->gradient,graph->backend);
            }
            break;
        case OKG_TRANSPOSE_NODE:
            status=okg_transpose(&first,&node->gradient);
            break;
        case OKG_RELU_NODE:
            status=okg_relu_pullback(&first,a,&node->gradient);
            break;
        case OKG_SUM_NODE:
            mpz_set(mpq_numref(scalar),node->gradient.numerators[0]);
            mpz_set(mpq_denref(scalar),node->gradient.denominator);
            mpq_canonicalize(scalar);
            status=okg_fill(&first,a->rows,a->columns,scalar,graph->budget);
            break;
        case OKG_SQUARE_SUM_NODE:
            mpz_mul_ui(mpq_numref(scalar),node->gradient.numerators[0],2);
            mpz_set(mpq_denref(scalar),node->gradient.denominator);
            mpq_canonicalize(scalar);
            status=okg_scale(&first,a,scalar);
            break;
        default:
            status=OKG_ARGUMENT;
            break;
        }
        if (!status) {
            status=okg_accumulate(&graph->nodes[node->arguments[0]].gradient,&first);
        }
        if (!status && okg_graph_arity(node->operation)==2) {
            status=okg_accumulate(&graph->nodes[node->arguments[1]].gradient,&second);
        }
        mpq_clear(scalar);
        okg_clear(&first);
        okg_clear(&second);
        okg_clear(&temporary);
        if (status) {
            return status;
        }
    }
    return OKG_SUCCESS;
}

#endif
