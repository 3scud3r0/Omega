"""Budgeted supervised optimization; held-out measurement remains a separate caller."""
def train(model,batches,*,steps=100,learning_rate=.001,device='cpu',grad_clip=1.0):
    import torch
    if not 1<=steps<=100000 or not 0<learning_rate<=1 or grad_clip<=0:raise ValueError('Invalid training configuration')
    model=model.to(device);model.train();optimizer=torch.optim.AdamW(model.parameters(),lr=learning_rate);history=[]
    for inputs,targets in batches:
        if len(history)>=steps:break
        inputs=inputs.to(device);targets=targets.to(device)
        if inputs.numel()>10000000 or targets.numel()>10000000:raise ValueError('Batch element budget exceeded')
        logits=model(inputs)
        loss=torch.nn.functional.cross_entropy(logits.reshape(-1,logits.shape[-1]),targets.reshape(-1),ignore_index=-100)
        if not torch.isfinite(loss):raise FloatingPointError('Nonfinite supervised loss')
        optimizer.zero_grad(set_to_none=True);loss.backward();torch.nn.utils.clip_grad_norm_(model.parameters(),grad_clip);optimizer.step()
        history.append(float(loss.detach()))
    return {'steps':len(history),'training_loss':tuple(history),'optimizer_state':optimizer.state_dict(),'heldout_evaluated':False}
