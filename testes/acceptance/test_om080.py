"""OM-080: executable checks; source delivery, not a recorded pass."""
import torch
from torch import nn
from omega_learning.distillation import train

def test_distillation_updates_smaller_student_without_teacher_gradients():
    with torch.random.fork_rng(devices=[]):
        torch.manual_seed(7)
        teacher=nn.Sequential(nn.Linear(2,8),nn.ReLU(),nn.Linear(8,2));student=nn.Linear(2,2)
        before=student.weight.detach().clone()
        history=train(student,teacher,[torch.eye(2)]*3,steps=3)
        assert len(history)==3 and all(torch.isfinite(torch.tensor(v)) for v in history)
        assert not torch.equal(before,student.weight) and all(p.grad is None for p in teacher.parameters())
        assert sum(p.numel() for p in student.parameters())<sum(p.numel() for p in teacher.parameters())
