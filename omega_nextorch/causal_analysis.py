"""Explicit interventions; feature correlations alone are not causal evidence."""
def intervene(module,model,inputs,feature,score):
    import torch
    was_training=model.training;model.eval()
    with torch.no_grad():baseline=score(model(inputs))
    def ablate(layer,args,output):
        if not isinstance(output,torch.Tensor) or not 0<=feature<output.shape[-1]:raise ValueError('Unsupported intervention target')
        replacement=output.clone();replacement[...,feature]=0;return replacement
    handle=module.register_forward_hook(ablate)
    try:
        with torch.no_grad():modified=score(model(inputs))
    finally:handle.remove();model.train(was_training)
    return {'baseline':float(baseline),'intervention':float(modified),'delta':float(modified-baseline),'feature':feature}
def sae_intervention(sae,latent,feature,predict):
    import torch
    with torch.no_grad():
        reconstructed,features=sae(latent)
        if not 0<=feature<features.shape[-1]:raise ValueError('Invalid SAE feature')
        changed=features.clone();changed[...,feature]=0;ablated=sae.decoder(changed)+sae.b_dec
        return {'original':predict(latent),'reconstruction':predict(reconstructed),'intervened':predict(ablated),
                'reconstruction_mse':float(((latent-reconstructed)**2).mean())}
