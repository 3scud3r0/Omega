"""Complete Boolean Orange tables become explicit Omega specifications."""
from .gate import validate_domain


def task_from_table(table, task_id="orange"):
    import numpy as np

    attrs = table.domain.attributes
    classes = table.domain.class_vars
    if not 0 <= len(attrs) <= 12 or len(classes) != 1 or len(table) != 2 ** len(attrs):
        raise ValueError("Forneça uma tabela-verdade completa, até 12 entradas e um alvo")

    def bit(value, variable):
        number = float(value)
        if not np.isfinite(number):
            raise ValueError("Valores ausentes não definem uma especificação exata")
        if variable.is_discrete:
            if number != int(number) or not 0 <= int(number) < len(variable.values):
                raise ValueError("Código categórico inválido")
            label = variable.values[int(number)]
            if label not in ("0", "1"):
                raise ValueError("Categorias devem ser os rótulos 0 e 1")
            return int(label)
        if number not in (0.0, 1.0):
            raise ValueError("A ponte exata exige valores booleanos 0/1")
        return int(number)

    outputs = [None] * len(table)
    for row in table:
        index = sum(bit(row[var], var) << i for i, var in enumerate(attrs))
        if outputs[index] is not None:
            raise ValueError("Linha de entrada duplicada; domínio incompleto")
        outputs[index] = bit(row[classes[0]], classes[0])
    task = {"id": task_id, "arity": len(attrs), "outputs": outputs}
    validate_domain(task)
    return task
