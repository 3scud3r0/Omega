"""Distribution-scoped confidence, distinct from formal proof and Bayesian belief."""
from decimal import Decimal,localcontext,ROUND_CEILING
import math


def probability(value):
    if type(value) not in (str,int,Decimal):raise ValueError('Decimal probability required')
    p=Decimal(value)
    if not p.is_finite() or not 0<p<1:raise ValueError('Probability must be in (0,1)')
    return p


def confidence(tested,failures,*,alpha='0.05',epsilon='0.00001'):
    if type(tested) is not int or type(failures) is not int or not 0<=failures<=tested<=2_000_000:raise ValueError('Trial counts')
    a,e=probability(alpha),probability(epsilon)
    with localcontext() as c:
        c.prec=70
        if tested==0:upper=Decimal(1);posterior=None
        elif failures==0:
            # Exact zero-failure Clopper-Pearson upper endpoint, evaluated at
            # high precision and conservatively rounded up by 1e-60.
            upper=min(Decimal(1),1-(a.ln()/tested).exp()+Decimal('1e-60'))
            posterior=min(Decimal(1),1-(a.ln()/(tested+1)).exp()+Decimal('1e-60'))
        else:
            upper=min(Decimal(1),Decimal(failures)/tested+((-a.ln())/(2*tested)).sqrt()+Decimal('1e-60'))
            posterior=None
        return {'trials':tested,'failures':failures,'alpha':str(a),'confidence':str(1-a),
                'upper_failure_probability':str(upper),'epsilon':str(e),
                'accepted':tested>0 and failures==0 and upper<e,
                'method':'Clopper-Pearson zero failures; Hoeffding otherwise',
                'bayesian_uniform_prior_upper':str(posterior) if posterior is not None else None,
                'assumptions':['fixed hypothesis before draws','IID from declared grid distribution','host-owned oracle'],
                'formal_proof':False}


def required_trials(*,alpha='0.05',epsilon='0.00001'):
    a,e=probability(alpha),probability(epsilon)
    with localcontext() as c:
        c.prec=70
        n=int((a.ln()/(1-e).ln()).to_integral_value(rounding=ROUND_CEILING))
    while n<=2_000_000 and not confidence(n,0,alpha=str(a),epsilon=str(e))['accepted']:n+=1
    return n
