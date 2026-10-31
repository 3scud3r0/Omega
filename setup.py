"""Bundle native module sources from their canonical repository locations."""
from pathlib import Path
from shutil import copyfile
from setuptools import setup
from setuptools.command.build_py import build_py


class NativeBuild(build_py):
    def run(self):
        super().run()
        root=Path(__file__).parent
        output=Path(self.build_lib)/'omega_native'/'_sources'
        copyfile(root/'omega_kernel.omega',Path(self.build_lib)/'omega_kernel'/'omega_kernel.omega')
        files=[p for directory in ('kernel','omega_core','omega_ml','ciencia','agentes_cientificos','std','runtime','tools','omega_ingest','civilizacao_agentes','incubadora_continua','sociedade_hierarquica','metamorfose_cognitiva','fabrica_descobertas','imunologia_sistemica','infraestrutura_soberana') for p in (root/directory).rglob('*') if p.suffix in ('.omega','.h','.c')]
        files.append(root/'ciencia/catalogo.json')
        files.extend((root/'kernel/examples').glob('*.json'))
        files.extend((root/'omega_selfhost').glob('*.h'))
        files.append(root/'omega_core/catalogo.json')
        files.extend((root/'omega_core/formal').glob('*.lean'))
        files.extend((root/'formal/science_axioms').glob('*.lean'))
        files.extend(root/name for name in ('banco_de_dados.omega','synthesis.omega','fitness.omega','civilizacao_agentes.omega','incubadora_continua.omega','ginasio.omega'))
        for source in files:
            target=output/source.relative_to(root);target.parent.mkdir(parents=True,exist_ok=True);copyfile(source,target)


setup(cmdclass={'build_py':NativeBuild})
