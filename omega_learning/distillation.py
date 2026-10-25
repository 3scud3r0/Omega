"""Distill teacher logits on training data only; evaluate separately."""
def train(student,teacher,batches,*,steps=100,temperature=2.0,learning_rate=.001):
    import torch
    if not 1<=steps<=100000 or temperature<=0:raise ValueError('Invalid distillation budget')
    optimizer=torch.optim.Adam(student.parameters(),lr=learning_rate);teacher.eval();student.train();history=[]
    for inputs in batches:
        if len(history)>=steps:break
        with torch.no_grad():targets=torch.softmax(teacher(inputs)/temperature,dim=-1)
        logits=torch.log_softmax(student(inputs)/temperature,dim=-1)
        loss=torch.nn.functional.kl_div(logits,targets,reduction='batchmean')*temperature**2
        if not torch.isfinite(loss):raise FloatingPointError('Nonfinite distillation loss')
        optimizer.zero_grad(set_to_none=True);loss.backward();optimizer.step();history.append(float(loss.detach()))
    return tuple(history)
